from abc import abstractmethod, ABCMeta
import enum

from common.helper import bytes_to_str, TwoWayDict, Orientation, PartPosition
from seatalk.seatalk_exceptions import NotEnoughData, TooMuchData, DataValidationException


class SeatalkDatagram(object, metaclass=ABCMeta):
    seatalk_id = None
    data_length = None  # # "Attribute" = length + 3 in datagram

    def __init__(self):
        self.__class_init__()

    @classmethod
    def __class_init__(cls):
        """
        Checks if class attributes are set
        """
        if cls.seatalk_id is None or cls.data_length is None:
            raise NotImplementedError(f"{cls.__name__}: SeatalkID ({cls.seatalk_id}) and/or DataLength ({cls.data_length}) is not set")

    def verify_data_length(self, data_len):
        """
        Verifies if received data-length is correct. Raises exception if not

        :param data_len: length of data
        """
        if data_len < self.data_length:
            raise NotEnoughData(data_gram=self, expected=self.data_length, actual=data_len)
        elif data_len > self.data_length:
            raise TooMuchData(data_gram=self, expected=self.data_length, actual=data_len)

    @abstractmethod
    def process_datagram(self, first_half_byte, data):
        """
        Most important seatalk-method which finally processes given bytes
        """
        raise NotImplementedError()

    @staticmethod
    def get_value(data):
        """
        Returns the two-byte value as an integer
        """
        return data[1] << 8 | data[0]

    @staticmethod
    def set_value(data):
        """
        Returns the integer as two-byte value
        """
        return bytes([int(data) & 0xFF, (int(data) >> 8)])

    @abstractmethod
    def get_seatalk_datagram(self):
        """
        Creates byte-array to send back on seatalk-bus
        """
        raise NotImplementedError()


class _ZeroContentClass(SeatalkDatagram, metaclass=ABCMeta):
    """
    Class which only checks/fills every first_half_byte and data-bytes with 0x00
    """
    def process_datagram(self, first_half_byte, data):
        all_bytes = bytearray([first_half_byte]) + data
        for value in all_bytes:
            if value != 0:
                raise DataValidationException(f"{type(self).__name__}: Not all bytes are 0x00: {bytes_to_str(all_bytes)}")

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length] + [0x00 for _ in range(self.data_length + 1)])  # + 1 for very first byte


class _TwoWayDictDatagram(SeatalkDatagram, metaclass=ABCMeta):
    """
    BaseClass for TwoWayDictionaries
    """
    def __init__(self, map: TwoWayDict, set_key=None):
        SeatalkDatagram.__init__(self)
        self._map = map
        self.set_key = set_key

    def process_datagram(self, first_half_byte, data):
        try:
            self.set_key = self._map[bytes(data)]
        except KeyError as e:
            raise DataValidationException(f"{type(self).__name__}: No corresponding value to given bytes: {bytes_to_str(data)}") from e

    def get_seatalk_datagram(self, first_half_byte=0):
        try:
            map_bytes = self._map.get_reversed(self.set_key)
        except ValueError as e:
            raise DataValidationException(f"{type(self).__name__}: No corresponding bytes to given value: {self.set_key}") from e
        first_byte = first_half_byte << 4 | self.data_length
        return bytearray([self.seatalk_id, first_byte]) + map_bytes


class _SetLampIntensityDatagram(_TwoWayDictDatagram, metaclass=ABCMeta):
    """
    BaseClass for Set Lamp Intensity: X=0 off, X=4: 1, X=8: 2, X=C: 3
    """
    def __init__(self, intensity=0):
        # Left: byte-value, Right: intensity
        intensity_map = TwoWayDict({
            bytes([0]):  0,
            bytes([4]):  1,
            bytes([8]):  2,
            bytes([12]): 3   # That's weird. All the time it's a shifted bit but this is 0x1100
        })
        _TwoWayDictDatagram.__init__(self, map=intensity_map, set_key=intensity)


class _SeatalkPartPosition(SeatalkDatagram, metaclass=ABCMeta):
    """
    BaseClass for PartPositions (Latitude and Longitude)
    ID  Z2  XX  YY  YY  position: XX degrees, (YYYY & 0x7FFF)/100 minutes
                     MSB of Y = YYYY & 0x8000 = x if set, y if cleared
                     Z= 0xA or 0x0 (reported for Raystar 120 GPS), meaning unknown
                     Stable filtered position, for raw data use command 58
                     Corresponding NMEA sentences: RMC, GAA, GLL
    """
    def __init__(self, position: PartPosition):
        SeatalkDatagram.__init__(self)
        self.position = position

    @abstractmethod
    def _get_orientation(self, value_set: bool) -> Orientation:
        raise NotImplementedError()

    @abstractmethod
    def _get_value_orientation(self, orientation: Orientation) -> bool:
        raise NotImplementedError()

    def process_datagram(self, first_half_byte, data):
        degrees = data[0]
        yyyy = self.get_value(data[1:])
        minutes = (yyyy & 0x7FFF) / 100
        orientation = self._get_orientation(yyyy & 0x8000 > 0)
        self.position = PartPosition(degrees=degrees, minutes=minutes, direction=orientation)

    def get_seatalk_datagram(self):
        degrees = self.position.degrees
        yyyy = int(self.position.minutes * 100)
        orientation = self._get_value_orientation(self.position.direction)
        yyyy |= (orientation << 15)
        return bytearray([self.seatalk_id, self.data_length, degrees]) + self.set_value(yyyy)


class _KeyStroke(_TwoWayDictDatagram):
    """
    Base-Class for KeyStrokes
    ID   X1  YY  yy  Keystroke
                 X=1: Sent by Z101 remote control to increment/decrement
                      course of autopilot
         11  05  FA     -1
         11  06  F9    -10
         11  07  F8     +1
         11  08  F7    +10
         11  20  DF     +1 &  -1
         11  21  DE     -1 & -10
         11  22  DD     +1 & +10
         11  28  D7    +10 & -10
         11  45  BA     -1        pressed longer than 1 second
         11  46  B9    -10        pressed longer than 1 second
         11  47  B8     +1        pressed longer than 1 second
         11  48  B7    +10        pressed longer than 1 second
         11  60  DF     +1 &  -1  pressed longer than 1 second
         11  61  9E     -1 & -10  pressed longer than 1 second
         11  62  9D     +1 & +10  pressed longer than 1 second
         11  64  9B    +10 & -10  pressed longer than 1 second (why not 11 68 97 ?)

                     Sent by autopilot (X=0: ST 1000+,  X=2: ST4000+ or ST600R)
         X1  01  FE    Auto
         X1  02  FD    Standby
         X1  03  FC    Track
         X1  04  FB    disp (in display mode or page in auto chapter = advance)
         X1  05  FA     -1 (in auto mode)
         X1  06  F9    -10 (in auto mode)
         X1  07  F8     +1 (in auto mode)
         X1  08  F7    +10 (in auto mode)
         X1  09  F6     -1 (in resp or rudder gain mode)
         X1  0A  F5     +1 (in resp or rudder gain mode)
         X1  21  DE     -1 & -10 (port tack, doesn´t work on ST600R?)
         X1  22  DD     +1 & +10 (stb tack)
         X1  23  DC    Standby & Auto (wind mode)
         X1  28  D7    +10 & -10 (in auto mode)
         X1  2E  D1     +1 & -1 (Response Display)
         X1  41  BE    Auto pressed longer
         X1  42  BD    Standby pressed longer
         X1  43  BC    Track pressed longer
         X1  44  BB    Disp pressed longer
         X1  45  BA     -1 pressed longer (in auto mode)
         X1  46  B9    -10 pressed longer (in auto mode)
         X1  47  B8     +1 pressed longer (in auto mode)
         X1  48  B7    +10 pressed longer (in auto mode)
         X1  63  9C    Standby & Auto pressed longer (previous wind angle)
         X1  68  97    +10 & -10 pressed longer (in auto mode)
         X1  6E  91     +1 & -1 pressed longer (Rudder Gain Display)
         X1  80  7F     -1 pressed (repeated 1x per second)
         X1  81  7E     +1 pressed (repeated 1x per second)
         X1  82  7D    -10 pressed (repeated 1x per second)
         X1  83  7C    +10 pressed (repeated 1x per second)
         X1  84  7B     +1, -1, +10 or -10 released
    """
    class Key(enum.Enum):
        M1 = enum.auto()
        M10 = enum.auto()
        P1 = enum.auto()
        P10 = enum.auto()
        P1M1 = enum.auto()
        M1M10 = enum.auto()
        P1P10 = enum.auto()
        P10M10 = enum.auto()

        # Longer than 1 sec
        M1GT1S = enum.auto()
        M10GT1S = enum.auto()
        P1GT1S = enum.auto()
        P10GT1S = enum.auto()
        P1M1GT1S = enum.auto()
        M1M10GT1S = enum.auto()
        P1P10GT1S = enum.auto()
        P10M10GT1S = enum.auto()

        # AutoPilot
        Auto = enum.auto()
        Standby = enum.auto()
        Track = enum.auto()
        Display = enum.auto()
        StandbyAuto = enum.auto()

        AutoGT1S = enum.auto()
        StandbyGT1S = enum.auto()
        TrackGT1S = enum.auto()
        DisplayGT1S = enum.auto()
        StandbyAutoGT1S = enum.auto()

        M1Auto = enum.auto()
        M10Auto = enum.auto()
        P1Auto = enum.auto()
        P10Auto = enum.auto()
        P10M10Auto = enum.auto()

        M1AutoGT1S = enum.auto()
        M10AutoGT1S = enum.auto()
        P1AutoGT1S = enum.auto()
        P10AutoGT1S = enum.auto()
        P10M10AutoGT1S = enum.auto()

        M1Resp = enum.auto()
        P1Resp = enum.auto()
        P1M1Resp = enum.auto()

        P1M1RudderGain = enum.auto()

        M1Repeat = enum.auto()
        P1Repeat = enum.auto()
        M10Repeat = enum.auto()
        P10Repeat = enum.auto()

        M1M10PortTack = enum.auto()
        P1P10StbTack = enum.auto()

        P1M1_P10M10Released = enum.auto()

    def __init__(self, increment_decrement=0, key: Key = None):
        key_map = TwoWayDict({
            bytes([0x05, 0xFA]): self.Key.M1,
            bytes([0x06, 0xF9]): self.Key.M10,
            bytes([0x07, 0xF8]): self.Key.P1,
            bytes([0x08, 0xF7]): self.Key.P10,
            bytes([0x20, 0xDF]): self.Key.P1M1,
            bytes([0x21, 0xDE]): self.Key.M1M10,
            bytes([0x22, 0xDD]): self.Key.P1P10,
            bytes([0x28, 0xD7]): self.Key.P10M10,
            bytes([0x45, 0xBA]): self.Key.M1GT1S,
            bytes([0x46, 0xB9]): self.Key.M10GT1S,
            bytes([0x47, 0xB8]): self.Key.P1GT1S,
            bytes([0x48, 0xB7]): self.Key.P10GT1S,
            bytes([0x60, 0xDF]): self.Key.P1M1GT1S,
            bytes([0x61, 0x9E]): self.Key.M1M10GT1S,
            bytes([0x62, 0x9D]): self.Key.P1P10GT1S,
            bytes([0x64, 0x9B]): self.Key.P10M10GT1S,

            bytes([0x01, 0xFE]): self.Key.Auto,
            bytes([0x02, 0xFD]): self.Key.Standby,
            bytes([0x03, 0xFC]): self.Key.Track,
            bytes([0x04, 0xFB]): self.Key.Display,

            bytes([0x05, 0xFA]): self.Key.M1Auto,
            bytes([0x06, 0xF9]): self.Key.M10Auto,
            bytes([0x07, 0xF8]): self.Key.P1Auto,
            bytes([0x08, 0xF7]): self.Key.P10Auto,

            bytes([0x09, 0xF6]): self.Key.M1Resp,
            bytes([0x0A, 0xF5]): self.Key.P1Resp,
            bytes([0x21, 0xDE]): self.Key.M1M10PortTack,
            bytes([0x22, 0xDD]): self.Key.P1P10StbTack,

            bytes([0x23, 0xDC]): self.Key.StandbyAuto,
            bytes([0x28, 0xD7]): self.Key.P10M10Auto,
            bytes([0x2E, 0xD1]): self.Key.P1M1Resp,
            bytes([0x41, 0xBE]): self.Key.AutoGT1S,
            bytes([0x42, 0xBD]): self.Key.StandbyGT1S,
            bytes([0x43, 0xBC]): self.Key.TrackGT1S,
            bytes([0x44, 0xBB]): self.Key.DisplayGT1S,

            bytes([0x45, 0xBA]): self.Key.M1AutoGT1S,
            bytes([0x46, 0xB9]): self.Key.M10AutoGT1S,
            bytes([0x47, 0xB8]): self.Key.P1AutoGT1S,
            bytes([0x48, 0xB7]): self.Key.P10AutoGT1S,
            bytes([0x63, 0x9C]): self.Key.StandbyAutoGT1S,
            bytes([0x68, 0x97]): self.Key.P10M10AutoGT1S,
            bytes([0x6E, 0x91]): self.Key.P1M1RudderGain,
            bytes([0x80, 0x7F]): self.Key.M1Repeat,
            bytes([0x81, 0x7E]): self.Key.P1Repeat,
            bytes([0x82, 0x7D]): self.Key.M10Repeat,
            bytes([0x83, 0x7C]): self.Key.P10Repeat,
            bytes([0x84, 0x7B]): self.Key.P1M1_P10M10Released,
        })
        _TwoWayDictDatagram.__init__(self, map=key_map, set_key=key)
        self.increment_decrement = increment_decrement

    def process_datagram(self, first_half_byte, data):
        super().process_datagram(first_half_byte, data)
        self.increment_decrement = first_half_byte

    def get_seatalk_datagram(self):
        return super().get_seatalk_datagram(first_half_byte=self.increment_decrement)

# Description of Thomas Knauf for 0x83 is weird: "83 07 XX 00 00 00 00 00 80 00 00": That's one byte too much. But which one? 0x80?
