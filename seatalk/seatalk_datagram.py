from abc import abstractmethod, ABCMeta
import enum
import datetime

from common.helper import byte_to_str, bytes_to_str, UnitConverter, TwoWayDict, Orientation, PartPosition, Position
from nmea import nmea_datagram
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

class TotalMileage(SeatalkDatagram):
    """
    22  02  XX  XX  00  Total Mileage: XXXX/10 nautical miles
    """
    seatalk_id = 0x22
    data_length = 2

    def __init__(self, mileage_miles=None):
        SeatalkDatagram.__init__(self)
        self.mileage_miles = mileage_miles

    def process_datagram(self, first_half_byte, data):
        self.mileage_miles = self.get_value(data[:2]) / 10

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length]) + self.set_value(self.mileage_miles * 10) + bytearray([0x00])


class WaterTemperatureDatagram(SeatalkDatagram, nmea_datagram.WaterTemperature):  # NMEA: mtw
    """
    23  Z1  XX  YY  Water temperature (ST50): XX deg Celsius, YY deg Fahrenheit
                 Flag Z&4: Sensor defective or not connected (Z=4)
                 Corresponding NMEA sentence: MTW
    """
    seatalk_id = 0x23
    data_length = 1
    
    def __init__(self, sensor_defective=None, *args, **kwargs):
        SeatalkDatagram.__init__(self)
        nmea_datagram.WaterTemperature.__init__(self, *args, **kwargs)
        self.sensor_defective = sensor_defective

    def process_datagram(self, first_half_byte, data):
        self.sensor_defective = first_half_byte & 4 == 4
        self.temperature_c = data[0]

    def get_seatalk_datagram(self):
        fahrenheit = UnitConverter.celsius_to_fahrenheit(self.temperature_c)
        first_half_byte = (self.sensor_defective << 6) | self.data_length
        return bytearray([self.seatalk_id, first_half_byte, int(self.temperature_c), int(fahrenheit)])


class DisplayUnitsMileageSpeed(_TwoWayDictDatagram):
    """
    24  02  00  00  XX  Display units for Mileage & Speed
                    XX: 00=nm/knots, 06=sm/mph, 86=km/kmh
    """
    seatalk_id = 0x24
    data_length = 2
    
    class Unit(enum.IntEnum):
        Knots = enum.auto()
        Mph = enum.auto()
        Kph = enum.auto()

    def __init__(self, unit: Unit=None):
        unit_map = TwoWayDict({
            bytes([0x00, 0x00, 0x00]): self.Unit.Knots,
            bytes([0x00, 0x00, 0x06]): self.Unit.Mph,
            bytes([0x00, 0x00, 0x86]): self.Unit.Kph,
        })
        _TwoWayDictDatagram.__init__(self, map=unit_map, set_key=unit)


class TotalTripLog(SeatalkDatagram):
    """
    25  Z4  XX  YY  UU  VV AW  Total & Trip Log
                     total= (XX+YY*256+Z* 4096)/ 10 [max=104857.5] nautical miles
                     trip = (UU+VV*256+W*65536)/100 [max=10485.75] nautical miles


    https://github.com/mariokonrad/marnav/blob/master/src/marnav/seatalk/message_25.cpp

    total= (XX+YY*256+Z*65536)/ 10 [max=104857.5] nautical miles
    (the factor for Z in the description from Thomas Knauf is wrong)

    (Shifting and other logical operations are faster than division and additions. Maybe some compilers would see that, but this looks way more straight forward and prettier ;-) )
    """
    seatalk_id = 0x25
    data_length = 4
    
    def __init__(self, total_miles=None, trip_miles=None):
        SeatalkDatagram.__init__(self)
        self.total_miles = total_miles
        self.trip_miles = trip_miles

    def process_datagram(self, first_half_byte, data):
        # * 256   <=> <<  8
        # * 4096  <=> << 12
        # * 65536 <=> << 16
        total_nibble = first_half_byte
        trip_nibble = data[4] & 0x0F  # What is the "A" for?

        #                       Z                   YY             XX
        self.total_miles = (total_nibble << 16 | data[1] << 8 | data[0]) / 10

        #                       W               VV              UU
        self.trip_miles = (trip_nibble << 16 | data[3] << 8 | data[2]) / 100

    def get_seatalk_datagram(self):
        raw_total = int(self.total_miles * 10)
        z = raw_total >> 16
        xx = raw_total & 0x0000FF
        yy = (raw_total >> 8) & 0x0000FF

        raw_trip = int(self.trip_miles * 100)
        aw = raw_trip >> 16
        uu = raw_trip & 0x0000FF
        vv = (raw_trip >> 8) & 0x0000FF

        first_byte = (z << 4) | self.data_length
        return bytearray([self.seatalk_id, first_byte, xx, yy, uu, vv, aw])


class SpeedDatagram2(SeatalkDatagram, nmea_datagram.SpeedThroughWater):  # NMEA: vhw
    """
    26  04  XX  XX  YY  YY DE  Speed through water:
                     XXXX/100 Knots, sensor 1, current speed, valid if D&4=4
                     YYYY/100 Knots, average speed (trip/time) if D&8=0
                              or data from sensor 2 if D&8=8
                     E&1=1: Average speed calculation stopped
                     E&2=2: Display value in MPH
                     Corresponding NMEA sentence: VHW
    """
    seatalk_id = 0x26
    data_length = 4
    
    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self)
        nmea_datagram.SpeedThroughWater.__init__(self, *args, **kwargs)

    def process_datagram(self, first_half_byte, data):
        # TODO Y and E flag
        self.speed_knots = self.get_value(data) / 100.0

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length]) + self.set_value(self.speed_knots * 100) + bytearray([0x00, 0x00, 0x00])


class WaterTemperatureDatagram2(SeatalkDatagram, nmea_datagram.WaterTemperature):  # NMEA: mtw
    """
    27  01  XX  XX  Water temperature: (XXXX-100)/10 deg Celsius
                 Corresponding NMEA sentence: MTW
    """
    seatalk_id = 0x27
    data_length = 1
    
    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self)
        nmea_datagram.WaterTemperature.__init__(self, *args, **kwargs)

    def process_datagram(self, first_half_byte, data):
        self.temperature_c = (self.get_value(data) - 100) / 10

    def get_seatalk_datagram(self):
        celsius_val = self.set_value((self.temperature_c * 10) + 100)
        return bytearray([self.seatalk_id, self.data_length]) + celsius_val


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


class SetLampIntensity1(_SetLampIntensityDatagram):
    """
    30  00  0X      Set lamp Intensity; X=0: L0, X=4: L1, X=8: L2, X=C: L3
                    (only sent once when setting the lamp intensity)
    """
    seatalk_id = 0x30
    data_length = 0
    
    def __init__(self, intensity=0):
        _SetLampIntensityDatagram.__init__(self, intensity=intensity)


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


class LatitudePosition(_SeatalkPartPosition):
    """
    50  Z2  XX  YY  YY  LAT position: XX degrees, (YYYY & 0x7FFF)/100 minutes
                     MSB of Y = YYYY & 0x8000 = South if set, North if cleared
                     Z= 0xA or 0x0 (reported for Raystar 120 GPS), meaning unknown
                     Stable filtered position, for raw data use command 58
                     Corresponding NMEA sentences: RMC, GAA, GLL
    """
    seatalk_id = 0x50
    data_length = 2
    
    def __init__(self, position: PartPosition=None):
        super().__init__(position=position)

    def _get_orientation(self, value_set: bool) -> Orientation:
        return Orientation.South if value_set else Orientation.North

    def _get_value_orientation(self, orientation: Orientation) -> bool:
        return True if orientation == Orientation.South else False


class LongitudePosition(_SeatalkPartPosition):
    """
    51  Z2  XX  YY  YY  LON position: XX degrees, (YYYY & 0x7FFF)/100 minutes
                                           MSB of Y = YYYY & 0x8000 = East if set, West if cleared
                                           Z= 0xA or 0x0 (reported for Raystar 120 GPS), meaning unknown
                     Stable filtered position, for raw data use command 58
                     Corresponding NMEA sentences: RMC, GAA, GLL
    """
    seatalk_id = 0x51
    data_length = 2
    
    def __init__(self, position: PartPosition=None):
        super().__init__(position=position, )

    def _get_orientation(self, value_set: bool) -> Orientation:
        return Orientation.East if value_set else Orientation.West

    def _get_value_orientation(self, orientation: Orientation) -> bool:
        return True if orientation == Orientation.East else False


class SpeedOverGround(SeatalkDatagram):  # TODO RMC, VTG?
    """
    52  01  XX  XX  Speed over Ground: XXXX/10 Knots
                 Corresponding NMEA sentences: RMC, VT
    """
    seatalk_id = 0x52
    data_length = 1
    
    def __init__(self, speed_knots=None):
        SeatalkDatagram.__init__(self)
        self.speed_knots = speed_knots

    def process_datagram(self, first_half_byte, data):
        self.speed_knots = self.get_value(data) / 10

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length]) + self.set_value(int(self.speed_knots * 10))


class CourseOverGround(SeatalkDatagram):
    """
    53  U0  VW      Course over Ground (COG) in degrees:
                 The two lower  bits of  U * 90 +
                    the six lower  bits of VW *  2 +
                    the two higher bits of  U /  2 =
                    (U & 0x3) * 90 + (VW & 0x3F) * 2 + (U & 0xC) / 8
                 The Magnetic Course may be offset by the Compass Variation (see datagram 99) to get the Course Over Ground (COG).
                 Corresponding NMEA sentences: RMC, VTG
    """
    seatalk_id = 0x53
    data_length = 0
    
    def __init__(self, course_degrees=None):
        SeatalkDatagram.__init__(self)
        self.course_degrees = course_degrees

    def process_datagram(self, first_half_byte, data):
        val_1 = (first_half_byte & 0b0011) * 90
        val_2 = (data[0] & 0b00111111) / 8
        val_3 = (first_half_byte & 0b1100)
        self.course_degrees = val_1 + val_2 + val_3

    def get_seatalk_datagram(self):
        u_0 = int(self.course_degrees / 90) & 0b0011
        u_1 = int((self.course_degrees % 2) * 8) & 0b1100
        data_0 = int((self.course_degrees % 90) / 2) & 0b00111111

        return bytearray([self.seatalk_id, ((u_0 | u_1) << 4) | self.data_length, data_0])


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


class GMTTime(SeatalkDatagram):
    """
     54  T1  RS  HH  GMT-time: HH hours,
                           6 MSBits of RST = minutes = (RS & 0xFC) / 4
                           6 LSBits of RST = seconds =  ST & 0x3F
                 Corresponding NMEA sentences: RMC, GAA, BWR, BWC
    """
    seatalk_id = 0x54
    data_length = 1
    
    def __init__(self, hours=None, minutes=None, seconds=None):
        SeatalkDatagram.__init__(self)
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds

    def process_datagram(self, first_half_byte, data):
        self.hours = data[1]
        self.minutes = (data[0] & 0xFC) // 4
        st = ((data[0] & 0x0F) << 4) | first_half_byte
        self.seconds = st & 0x3F

    def get_seatalk_datagram(self):
        hh_byte = self.hours
        t_nibble = self.seconds & 0x0F
        rs_byte = ((self.minutes * 4) & 0xFC) + ((self.seconds >> 4) & 0x03)

        first_byte = t_nibble << 4 | self.data_length
        return bytearray([self.seatalk_id, first_byte, rs_byte, hh_byte])


class KeyStroke1(_KeyStroke):
    """
    55  X1  YY  yy  TRACK keystroke on GPS unit
    """
    seatalk_id = 0x55
    data_length = 1
    
    def __init__(self, increment_decrement=0, key=None):
        _KeyStroke.__init__(self, increment_decrement=increment_decrement, key=key)


class Date(SeatalkDatagram):  # TODO RMC?
    """
    56  M1  DD  YY  Date: YY year, M month, DD day in month
                    Corresponding NMEA sentence: RMC
    """
    seatalk_id = 0x56
    data_length = 1
    
    def __init__(self, date=None):
        SeatalkDatagram.__init__(self)
        self.date = date
        self._year_offset = 2000  # TODO correct?

    def process_datagram(self, first_half_byte, data):
        month = first_half_byte
        day = data[0]
        year = self._year_offset + data[1]
        self.date = datetime.date(year=year, month=month, day=day)

    def get_seatalk_datagram(self):
        if self.date is None:
            pass  # TODO Exception
        first_byte = (self.date.month << 4) | self.data_length
        return bytearray([self.seatalk_id, first_byte, self.date.day, self.date.year - self._year_offset])


class SatInfo(SeatalkDatagram):
    """
    57  S0  DD      Sat Info: S number of sats, DD horiz. dilution of position, if S=1 -> DD=0x94
                    Corresponding NMEA sentences: GGA, GSA
    """
    seatalk_id = 0x57
    data_length = 0
    
    def __init__(self, amount_satellites=None, horizontal_dilution=None):
        SeatalkDatagram.__init__(self)
        self.amount_satellites = amount_satellites
        self.horizontal_dilution = horizontal_dilution

    def process_datagram(self, first_half_byte, data):
        self.amount_satellites = first_half_byte
        self.horizontal_dilution = data[0]

    def get_seatalk_datagram(self):
        first_byte = (self.amount_satellites << 4) | self.data_length
        return bytearray([self.seatalk_id, first_byte, self.horizontal_dilution])


class PositionDatagram(SeatalkDatagram):
    """
    58  Z5  LA XX YY LO QQ RR   LAT/LON
                 LA Degrees LAT, LO Degrees LON
                 minutes LAT = (XX*256+YY) / 1000
                 minutes LON = (QQ*256+RR) / 1000
                 Z&1: South (Z&1 = 0: North)
                 Z&2: East  (Z&2 = 0: West)
                 Raw unfiltered position, for filtered data use commands 50&51
                 Corresponding NMEA sentences: RMC, GAA, GLL
    """
    seatalk_id = 0x58
    data_length = 5
    
    def __init__(self, position:Position=None):
        SeatalkDatagram.__init__(self)
        self.position = position

    def process_datagram(self, first_half_byte, data):
        lat_orientation = Orientation.South if first_half_byte & 1 else Orientation.North
        lat_degree = data[0]
        lat_min = (data[1] << 8 | data[2]) / 1000
        latitude = PartPosition(degrees=lat_degree, minutes=lat_min, direction=lat_orientation)

        lon_orientation = Orientation.East if first_half_byte & 2 else Orientation.West
        lon_degree = data[3]
        lon_min = (data[4] << 8 | data[5]) / 1000
        longitude = PartPosition(degrees=lon_degree, minutes=lon_min, direction=lon_orientation)
        self.position = Position(latitude=latitude, longitude=longitude)

    def get_seatalk_datagram(self):
        first_half_byte = 0x00
        if self.position.latitude.direction == Orientation.South:
            first_half_byte |= 1

        if self.position.longitude.direction == Orientation.East:
            first_half_byte |= 2

        la = self.position.latitude.degrees
        la_raw_min = int(self.position.latitude.minutes * 1000)
        xx = (la_raw_min & 0xFF00) >> 8
        yy = la_raw_min & 0x00FF

        lo = self.position.longitude.degrees
        lo_raw_min = int(self.position.longitude.minutes * 1000)
        qq = (lo_raw_min & 0xFF00) >> 8
        rr = lo_raw_min & 0x00FF

        return bytearray([self.seatalk_id, first_half_byte << 4 | self.data_length, la, xx, yy, lo, qq, rr])


class CountDownTimer(SeatalkDatagram):
    """
    59  22  SS MM XH  Set Count Down Timer
                   MM=Minutes ( 00..3B ) ( 00 .. 63 Min ), MSB:0 Count up start flag
                   SS=Seconds ( 00..3B ) ( 00 .. 59 Sec )
                   H=Hours    ( 0..9 )   ( 00 .. 09 Hours )
                   X= Counter Mode: 0 Count up and start if MSB of MM set
                                    4 Count down
                                    8 Count down and start
                   ( Example 59 22 3B 3B 49 -> Set Countdown Timer to 9.59:59 )
    59  22  0A 00 80  Sent by ST60 in countdown mode when counted down to 10 Seconds.
    """
    seatalk_id = 0x59
    data_length = 2
    
    class CounterMode(enum.IntEnum):
        CountUpStart = 0
        CountDown = 4
        CountDownStart = 8

    def __init__(self, hours=None, minutes=None, seconds=None, mode:CounterMode=None):
        SeatalkDatagram.__init__(self)
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds
        self.mode = mode

    def process_datagram(self, first_half_byte, data):
        if first_half_byte != 0x02:
            raise DataValidationException(f"{type(self).__name__}: First half byte is not 0x02 but {byte_to_str(first_half_byte)}")
        self.seconds = data[0]
        self.minutes = data[1]
        self.hours = data[2] & 0x0F
        try:  # At startup ST60+ sends 0x59 0x22 0x00 0x59 0x59
            self.mode = self.CounterMode(data[2] >> 4)
        except ValueError:
            raise DataValidationException(f"{type(self).__name__}: CounterMode invalid: {data[2] >> 4}")

    def get_seatalk_datagram(self):
        first_byte = (0x02 << 4) | self.data_length
        last_byte = (self.mode.value << 4) | self.hours
        return bytearray([self.seatalk_id, first_byte, self.minutes, self.seconds, last_byte])


class E80Initialization(SeatalkDatagram):
    """
    61  03  03 00 00 00  Issued by E-80 multifunction display at initialization
    """
    seatalk_id = 0x61
    data_length = 3
    
    def __init__(self):
        SeatalkDatagram.__init__(self)

    def process_datagram(self, first_half_byte, data):
        if not (first_half_byte == 0 and data[0] == 0x03 and data[1] == data[2] == data[3] == 0x00):
            raise DataValidationException(f"{type(self).__name__}: Cannot recognize given data: {byte_to_str(self.seatalk_id)}{byte_to_str(first_half_byte << 4 | self.data_length)}{bytes_to_str(data)}")

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length, 0x03, 0x00, 0x00, 0x00])


class SelectFathom(SeatalkDatagram):
    """
    65  00  02      Select Fathom (feet/3.33) display units for depth display (see command 00)
    """
    seatalk_id = 0x65
    data_length = 0
    
    def __init__(self):
        SeatalkDatagram.__init__(self)
        self.byte_value = 0x02

    def process_datagram(self, first_half_byte, data):
        if data[0] != self.byte_value:
            raise DataValidationException(f"{type(self).__name__}: Expected byte {self.byte_value}, got {byte_to_str(data[0])} instead")

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length, self.byte_value])


class WindAlarm(SeatalkDatagram):
    """
    66  00  XY     Wind alarm as indicated by flags in XY:
                   X&8 = 8: Apparent Wind angle low
                   X&4 = 4: Apparent Wind angle high
                   X&2 = 2: Apparent Wind speed low
                   X&1 = 1: Apparent Wind speed high
                   Y&8 = 8: True Wind angle low
                   Y&4 = 4: True Wind angle high
                   Y&2 = 2: True Wind speed low
                   Y&1 = 1: True Wind speed high (causes Wind-High-Alarm on ST40 Wind Instrument)
                   XY  =00: End of wind alarm (only sent once)
    """
    seatalk_id = 0x66
    data_length = 0
    
    class Alarm(enum.IntEnum):
        AngleLow = 0x08
        AngleHigh = 0x04
        SpeedLow = 0x02
        SpeedHigh = 0x01
        NoAlarm = 0x00

    def __init__(self, apparent_alarm: Alarm=None, true_alarm: Alarm=None):
        SeatalkDatagram.__init__(self)
        self.apparent_alarm = apparent_alarm
        self.true_alarm = true_alarm

    def process_datagram(self, first_half_byte, data):
        x_nibble = (data[0] & 0xF0) >> 4
        y_nibble = (data[0] & 0x0F)
        self.apparent_alarm = self.Alarm(x_nibble)  # TODO enum exception
        self.true_alarm = self.Alarm(y_nibble)

    def get_seatalk_datagram(self):
        x_nibble = self.apparent_alarm.value << 4   # TODO enum exception
        y_nibble = self.true_alarm.value
        return bytearray([self.seatalk_id, self.data_length, (x_nibble | y_nibble)])


class AlarmAcknowledgement(SeatalkDatagram):
    """
    68  X1 01 00   Alarm acknowledgment keystroke (from ST80 Masterview)
    68  X1 03 00   Alarm acknowledgment keystroke (from ST80 Masterview)   TODO 2 ST80 Masterview?
    68  41 15 00   Alarm acknowledgment keystroke (from ST40 Wind Instrument)   TODO X=4 -> ST40? maybe data[0] = 0x15 -> ST40
                  X: 1=Shallow Shallow Water Alarm, 2=Deep Water Alarm, 3=Anchor Alarm
                     4=True Wind High Alarm, 5=True Wind Low Alarm, 6=True Wind Angle high
                     7=True Wind Angle low, 8=Apparent Wind high Alarm, 9=Apparent Wind low Alarm
                     A=Apparent Wind Angle high, B=Apparent Wind Angle low
    """
    seatalk_id = 0x68
    data_length = 1

    class AcknowledgementAlarms(enum.IntEnum):
        ShallowWaterAlarm = 0x01
        DeepWaterAlarm = 0x02
        AnchorAlarm = 0x03
        TrueWindHighAlarm = 0x04
        TrueWindLowAlarm = 0x05
        TrueWindAngleHigh = 0x06
        TrueWindAngleLow = 0x07
        ApparentWindHighAlarm = 0x08
        ApparentWindLowAlarm = 0x09
        ApparentWindAngleHigh = 0x0A
        ApparentWindAngleLow = 0x0B

    def __init__(self, acknowledged_alarm: AcknowledgementAlarms=None):
        SeatalkDatagram.__init__(self)
        self.acknowledged_alarm = acknowledged_alarm

    def process_datagram(self, first_half_byte, data):
        self.acknowledged_alarm = self.AcknowledgementAlarms(first_half_byte)  # TODO enum exception

    def get_seatalk_datagram(self):
        first_half_byte = self.acknowledged_alarm.value << 4   # TODO enum exception
        acknowledging_device = bytearray([0x01, 0x00])  # TODO see description of class
        return bytearray([self.seatalk_id, first_half_byte | self.data_length]) + acknowledging_device


class EquipmentIDDatagram2(_TwoWayDictDatagram):
    """
     6C  05  XX XX XX XX XX XX Second equipment-ID datagram (follows 01...), reported examples:
             04 BA 20 28 2D 2D ST60 Tridata
             05 70 99 10 28 2D ST60 Log
             F3 18 00 26 2D 2D ST80 Masterview
    """
    seatalk_id = 0x6C
    data_length = 5

    class Equipments(enum.IntEnum):
        ST60_Tridata = enum.auto()
        ST60_Tridata_Plus = enum.auto()
        ST60_Log = enum.auto()
        ST80_Masterview = enum.auto()

    def __init__(self, equipment_id: Equipments=None):
        equipment_map = TwoWayDict({
            bytes([0x04, 0xBA, 0x20, 0x28, 0x2D, 0x2D]): self.Equipments.ST60_Tridata,
            bytes([0x87, 0x72, 0x25, 0x28, 0x2D, 0x2D]): self.Equipments.ST60_Tridata_Plus,
            bytes([0x05, 0x70, 0x99, 0x10, 0x28, 0x2D]): self.Equipments.ST60_Log,
            bytes([0xF3, 0x18, 0x00, 0x26, 0x2D, 0x2D]): self.Equipments.ST80_Masterview,
        })
        _TwoWayDictDatagram.__init__(self, map=equipment_map, set_key=equipment_id)


class ManOverBoard(SeatalkDatagram):
    """
    According to Thomas Knauf:
    6E  07  00  00 00 00 00 00 00 00 MOB (Man Over Board), (ST80), preceded
                 by a Waypoint 999 command: 82 A5 40 BF 92 6D 24 DB
    I noticed on Raymarine RN300 (not sure about the byte meaning though):
    6E  47  0F  E7 59 00 00 0F A7 70
    """
    seatalk_id = 0x6E
    data_length = 7

    def process_datagram(self, first_half_byte, data):
        pass  # Nothing to do here

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length, 0, 0, 0, 0, 0, 0, 0, 0])


class SetLampIntensity2(_SetLampIntensityDatagram):
    """
    80  00  0X      Set Lamp Intensity: X=0 off, X=4:  1, X=8:  2, X=C: 3
    """
    seatalk_id = 0x80
    data_length = 0

    def __init__(self, intensity=0):
        _SetLampIntensityDatagram.__init__(self, intensity=intensity)


class CourseComputerSetup(SeatalkDatagram):
    """
    81  01  00  00  Sent by course computer during setup when going past USER CAL.
    81  00  00      Sent by course computer immediately after above.
    """
    seatalk_id = 0x81
    data_length = -1

    class MessageTypes(enum.IntEnum):
        SetupFinished = 0
        Setup = 1

    def __init__(self, message_type:MessageTypes=None):
        super().__init__()
        self.message_type = message_type

    def verify_data_length(self, data_len):
        try:
            self.message_type = self.MessageTypes(data_len)
        except ValueError as e:
            raise TooMuchData(data_gram=self, expected=[e.value for e in self.MessageTypes], actual=data_len) from e

    def process_datagram(self, first_half_byte, data):
        all_bytes = bytearray([first_half_byte]) + data
        for value in all_bytes:
            if value != 0:
                raise DataValidationException(f"{type(self).__name__}: Not all bytes are 0x00: {bytes_to_str(all_bytes)}")

    def get_seatalk_datagram(self):
        ret_val = bytearray([self.seatalk_id, self.message_type.value, 0x00])
        if self.message_type == self.MessageTypes.Setup:
            ret_val.append(0x00)
        return ret_val


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
