from abc import abstractmethod, ABCMeta
import enum

from common.helper import byte_to_str, bytes_to_str, TwoWayDict, Orientation, PartPosition
from seatalk.seatalk_exceptions import NotEnoughData, TooMuchData, DataValidationException, DataLengthException


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
        return int(data).to_bytes(2, "little")

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

    def __init__(self, increment_decrement, key: Key):
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




class TargetWayPointName(SeatalkDatagram):
    """
    82  05  XX  xx YY yy ZZ zz   Target waypoint name
                 XX+xx = YY+yy = ZZ+zz = FF (allows error detection)
                 Takes the last 4 chars of name, assumes upper case only
                 Char= ASCII-Char - 0x30
                 XX&0x3F: char1
                 (YY&0xF)*4+(XX&0xC0)/64: char2
                 (ZZ&0x3)*16+(YY&0xF0)/16: char3
                 (ZZ&0xFC)/4: char4
                 Corresponding NMEA sentences: RMB, APB, BWR, BWC
    """
    seatalk_id = 0x82
    data_length = 5

    def __init__(self, name: str=None):
        SeatalkDatagram.__init__(self)
        self.name = name

    def process_datagram(self, first_half_byte, data):
        X_byte_index = 0
        x_byte_index = 1
        Y_byte_index = 2
        y_byte_index = 3
        Z_byte_index = 4
        z_byte_index = 5

        if data[X_byte_index] + data[x_byte_index] == data[Y_byte_index] + data[y_byte_index] == data[Z_byte_index] + data[z_byte_index] != 0xFF:
            raise DataValidationException("Received datagrams checksum doesn't match")
        char1 = 0x30 + (data[X_byte_index] & 0x3F)
        char2 = 0x30 + (((data[Y_byte_index] & 0xF) << 2) | ((data[X_byte_index] & 0xC0) >> 6))
        char3 = 0x30 + (((data[Z_byte_index] & 0x3) << 4) | ((data[Y_byte_index] & 0xF0) >> 4))
        char4 = 0x30 + ((data[Z_byte_index] & 0xFC) >> 2)
        name = ""
        for char in (char1, char2, char3, char4):
            name += chr(char)
        self.name = name
        # if name == "0999":
        #     pass  # MOB

    def get_seatalk_datagram(self):
        char_1 = ord(self.name[0]) - 0x30
        char_2 = ord(self.name[1]) - 0x30
        char_3 = ord(self.name[2]) - 0x30
        char_4 = ord(self.name[3]) - 0x30

        X_byte = (char_1 & 0x3f) | ((char_2 & 0x3) << 6)
        x_byte = 0xFF - X_byte
        Y_byte = (char_2 >> 2) | ((char_3 & 0xf) << 4)
        y_byte = 0xFF - Y_byte
        Z_Byte = ((char_3 & 0x3c) >> 4) | (char_4 << 2)
        z_byte = 0xFF - Z_Byte
        return bytearray([self.seatalk_id, self.data_length, X_byte, x_byte, Y_byte, y_byte, Z_Byte, z_byte])


# Description of Thomas Knauf for 0x83 is weird: "83 07 XX 00 00 00 00 00 80 00 00": That's one byte too much. But which one? 0x80?


class KeyStroke2(_KeyStroke):
    """
    86  X1  YY  yy  Keystroke
    """
    seatalk_id = 0x86
    data_length = 1

    def __init__(self, increment_decrement=0, key=None):
        _KeyStroke.__init__(self, increment_decrement=increment_decrement, key=key)


class SetResponseLevel(SeatalkDatagram):
    """
    87  00  0X        Set Response level
                  X=1  Response level 1: Automatic Deadband
                  X=2  Response level 2: Minimum Deadband
    """
    seatalk_id = 0x87
    data_length = 0

    class Deadband(enum.IntEnum):
        Automatic = 1,
        Minimum = 2

    def __init__(self, response_level: Deadband=None):
        SeatalkDatagram.__init__(self)
        self.response_level = response_level

    def process_datagram(self, first_half_byte, data):
        self.response_level = self.Deadband(data[0])

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length, self.response_level.value])


class DeviceIdentification1(_TwoWayDictDatagram):
    """
    90  00  XX    Device Identification
                  XX=02  sent by ST600R ~every 2 secs
                  XX=05  sent by type 150, 150G and 400G course computer
                  XX=A3  sent by NMEA <-> SeaTalk bridge ~every 10 secs
    """
    seatalk_id = 0x90
    data_length = 0

    class DeviceID(enum.IntEnum):
        ST600R = enum.auto()
        Type_150_150G_400G = enum.auto()
        NMEASeatalkBridge = enum.auto()

    def __init__(self, device_id: DeviceID=None):
        device_id_map = TwoWayDict({
            bytes([0x02]): self.DeviceID.ST600R,
            bytes([0x05]): self.DeviceID.Type_150_150G_400G,
            bytes([0xA3]): self.DeviceID.NMEASeatalkBridge
        })
        _TwoWayDictDatagram.__init__(self, map=device_id_map, set_key=device_id)


class SetRudderGain(SeatalkDatagram):
    """
    91  00  0X        Set Rudder gain to X
    """
    seatalk_id = 0x91
    data_length = 0

    def __init__(self, rudder_gain=None):
        SeatalkDatagram.__init__(self)
        self.rudder_gain = rudder_gain

    def process_datagram(self, first_half_byte, data):
        self.rudder_gain = data[0]

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length, self.rudder_gain])


class EnterAPSetup(_ZeroContentClass):
    """
    93  00  00      Enter AP-Setup: Sent by course computer before
                    finally entering the dealer setup. It is repeated
                    once per second, and times out after ten seconds.
                    While this is being sent, command 86 X1 68 97 is
                    needed for final entry into Setup. (600R generates
                    this when –1 & +1 are pressed simultaneously in this
                    mode).
    """
    seatalk_id = 0x93
    data_length = 0


class CompassVariation(SeatalkDatagram):
    """
    99  00  XX       Compass variation sent by ST40 compass instrument
                     or ST1000, ST2000, ST4000+, E-80 every 10 seconds
                     but only if the variation is set on the instrument
                     Positive XX values: Variation West, Negative XX values: Variation East
                     Examples (XX => variation): 00 => 0, 01 => -1 west, 02 => -2 west ...
                                                 FF => +1 east, FE => +2 east ...
                     Corresponding NMEA sentences: RMC, HDG
    """
    seatalk_id = 0x99
    data_length = 0

    def __init__(self, variation=None):
        SeatalkDatagram.__init__(self)
        self.variation = variation

    def process_datagram(self, first_half_byte, data):
        self.variation = int.from_bytes(bytes([data[0]]), byteorder="big", signed=True)  # TODO unsure if variation *-1

    def get_seatalk_datagram(self):
        my_bytes = int.to_bytes(self.variation, byteorder="big", signed=True, length=1)
        return bytearray([self.seatalk_id, self.data_length]) + bytearray(my_bytes)


class DeviceIdentification2(SeatalkDatagram):
    """
    Special class, which basically holds 3 other classes (depending on length and first half byte)
    """
    seatalk_id = 0xA4
    data_length = -1

    def __init__(self, real_datagram=None):
        SeatalkDatagram.__init__(self)
        self._real_datagram = real_datagram

    def verify_data_length(self, data_len):
        valid_values = [data_gram.data_length for data_gram in (self.BroadCast, self.Answer, self.Termination)]
        if data_len not in valid_values:
            raise DataLengthException(f"{type(self).__name__}: Length not valid. Expected values: {valid_values}, Actual: {data_len}")
        self.data_length = data_len

    def process_datagram(self, first_half_byte, data):
        if self.data_length == 2:
            if first_half_byte == 1:
                data_gram = self.Answer
            else:
                data_gram = self.BroadCast
        else:
            data_gram = self.Termination
        self._real_datagram = data_gram()
        self._real_datagram.process_datagram(first_half_byte, data)

    def get_seatalk_datagram(self):
        return self._real_datagram.get_seatalk_datagram

    class BroadCast(_ZeroContentClass):
        """
        A4  02  00  00 00 Broadcast query to identify all devices on the bus, issued e.g. by C70 plotter
        """
        seatalk_id = 0xA4
        data_length = 2

    class Termination(_ZeroContentClass):
        """
        A4  06  00  00 00 00 00 Termination of request for device identification, sent e.g. by C70 plotter
        """
        seatalk_id = 0xA4
        data_length = 6

    class Answer(SeatalkDatagram):
        """
        A4  12  II  VV WW Device answers identification request
                              II: Unit ID (01=Depth, 02=Speed, 03=Multi, 04=Tridata, 05=Tridata repeater,
                                           06=Wind, 07=WMG, 08=Navdata GPS, 09=Maxview, 0A=Steering compas,
                                           0B=Wind Trim, 0C=Speed trim, 0D=Seatalk GPS, 0E=Seatalk radar ST50,
                                           0F=Rudder angle indicator, 10=ST30 wind, 11=ST30 bidata, 12=ST30 speed,
                                           13=ST30 depth, 14=LCD navcenter, 15=Apelco LCD chartplotter,
                                           16=Analog speedtrim, 17=Analog depth, 18=ST30 compas,
                                           19=ST50 NMEA bridge, A8=ST80 Masterview)
                              VV: Main Software Version
                              WW: Minor Software Version
        """
        seatalk_id = 0xA4
        data_length = 2

        class DeviceID(enum.IntEnum):
            Depth = 0x01
            Speed = 0x02
            Multi = 0x03
            TriData = 0x04
            TriDataRepeater = 0x05
            Wind = 0x06
            WMG = 0x07
            NavdataGPS = 0x08
            Maxview = 0x09
            SteeringCompass = 0x0A
            WindTrim = 0x0B
            SpeedTrim = 0x0C
            SeatalkGPS = 0x0D
            SeatalkRadarST50 = 0x0E
            RudderAngleIndicator = 0x0F
            ST30Wind = 0x10
            ST30BiData = 0x11
            ST30Speed = 0x12
            ST30Depth = 0x13
            LCDNavCenter = 0x14
            ApelcoLCDChartPlotter = 0x15
            AnalogSpeedTrim = 0x16
            AnalogDepth = 0x17
            ST30Compass = 0x18
            ST50NMEABridge = 0x19
            ST80MasterView = 0xA8

        def __init__(self, device_id: DeviceID = None, main_sw_version=None, minor_sw_version=None):
            SeatalkDatagram.__init__(self)
            self.device_id = device_id
            self.main_sw_version = main_sw_version
            self.minor_sw_version = minor_sw_version

        def process_datagram(self, first_half_byte, data):
            if first_half_byte != 0x01:
                raise DataValidationException(f"{type(self).__name__}: First half byte is not 0x01, but {byte_to_str(first_half_byte)}")

            try:
                self.device_id = self.DeviceID(data[0])
            except KeyError as e:
                raise DataValidationException(f"{type(self).__name__}: No corresponding Device to given device-id: {byte_to_str(data[0])}") from e

            self.main_sw_version = data[1]
            self.minor_sw_version = data[2]

        def get_seatalk_datagram(self):
            first_byte = (0x01 << 4) | self.data_length
            # TODO None-values
            return bytearray([self.seatalk_id, first_byte, self.device_id.value, self.main_sw_version, self.minor_sw_version])
