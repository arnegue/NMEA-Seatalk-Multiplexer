from abc import abstractmethod, ABCMeta
import enum
import datetime

from helper import byte_to_str, bytes_to_str, UnitConverter, TwoWayDict
import logger
from nmea import nmea_datagram


class SeatalkException(nmea_datagram.NMEAError):
    """
    Any Exception concerning Seatalk
    """


class NoCorrespondingNMEASentence(SeatalkException):
    """
    Exception if Seatalk-Datagram doesn't have a belonging NMEA-Sentence (e.g. some commands for Display-Light)
    """
    def __init__(self, data_gram):
        logger.info(f"{type(data_gram).__name__}: There is no corresponding NMEADatagram")


class DataValidationException(SeatalkException):
    """
    Errors happening when converting raw Seatalk-Data
    """


class DataLengthException(DataValidationException):
    """
    Exceptions happening in validation if length is incorrect
    """


class NotEnoughData(DataLengthException):
    def __init__(self, data_gram, expected, actual):
        super().__init__(f"{type(data_gram).__name__}: Not enough data arrived. Expected: {expected}, actual {actual}")


class TooMuchData(DataLengthException):
    def __init__(self, data_gram, expected, actual):
        super().__init__(f"{type(data_gram).__name__}: Too much data arrived. Expected: {expected}, actual {actual}")


class DataNotRecognizedException(DataValidationException):
    """
    This exception is getting raised if the Command-Byte is not recognized
    """
    def __init__(self, device_name, command_byte):
        super().__init__(f"{device_name}: Unknown command-byte: {byte_to_str(command_byte)}")


class SeatalkDatagram(object, metaclass=ABCMeta):
    def __init__(self, id, data_length):
        self.id = bytes([id])
        self.data_length = data_length  # "Attribute" = length + 3 in datagram

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
        all_bytes = bytes([first_half_byte]) + data
        for value in all_bytes:
            if value != 0:
                raise DataValidationException(f"{type(self).__name__}: Not all bytes are 0x00: {bytes_to_str(all_bytes)}")

    def get_seatalk_datagram(self):
        return self.id + bytearray([self.data_length] + [0x00 for _ in range(self.data_length + 1)])  # + 1 for very first byte


class DepthDatagram(SeatalkDatagram, nmea_datagram.DepthBelowKeel):   # NMEA: dbt
    """
    00  02  YZ  XX XX  Depth below transducer: XXXX/10 feet
                   Flags in Y: Y&8 = 8: Anchor Alarm is active
                               Y&4 = 4: Metric display units or
                                          Fathom display units if followed by command 65
                               Y&2 = 2: Used, unknown meaning
                   Flags in Z: Z&4 = 4: Transducer defective
                               Z&2 = 2: Deep Alarm is active
                               Z&1 = 1: Shallow Depth Alarm is active
                   Corresponding NMEA sentences: DPT, DBT
    """
    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self, id=0x00, data_length=2)
        nmea_datagram.DepthBelowKeel.__init__(self, *args, **kwargs)

    def process_datagram(self, first_half_byte, data):
        # TODO Y and Z flag
        data = data[1:]
        feet = self.get_value(data) / 10.0
        self.depth_m = feet / 3.2808

    def get_seatalk_datagram(self):
        feet_value = UnitConverter.meter_to_feet(self.depth_m) * 10
        default_byte_array = bytearray([self.data_length,
                                        0x00])  # No sensor defectives
        return self.id + default_byte_array + self.set_value(feet_value)


class _TwoWayDictDatagram(SeatalkDatagram, metaclass=ABCMeta):
    """
    BaseClass for TwoWayDictionaries
    """
    def __init__(self, map: TwoWayDict, id, data_length, set_key=None):
        SeatalkDatagram.__init__(self, id=id, data_length=data_length)
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
        return self.id + bytearray([first_byte]) + map_bytes


class EquipmentIDDatagram1(_TwoWayDictDatagram):
    """
    01  05  XX XX XX XX XX XX  Equipment ID, sent at power on, reported examples:
    01  05  00 00 00 60 01 00  Course Computer 400G
    01  05  04 BA 20 28 01 00  ST60 Tridata
    01  05  70 99 10 28 01 00  ST60 Log
    01  05  F3 18 00 26 0F 06  ST80 Masterview
    01  05  FA 03 00 30 07 03  ST80 Maxi Display
    01  05  FF FF FF D0 00 00  Smart Controller Remote Control Handset
    """
    class Equipments(enum.IntEnum):
        Course_Computer_400G = enum.auto()
        ST60_Tridata = enum.auto()
        ST60_Log = enum.auto()
        ST80_Masterview = enum.auto()
        ST80_Maxi_Display = enum.auto()
        Smart_Controller_Remote_Control_Handset = enum.auto()

    def __init__(self, set_key: Equipments=None):
        equipment_map = TwoWayDict({
            bytes([0x00, 0x00, 0x00, 0x60, 0x01, 0x00]): self.Equipments.Course_Computer_400G,
            bytes([0x04, 0xBA, 0x20, 0x28, 0x01, 0x00]): self.Equipments.ST60_Tridata,
            bytes([0x70, 0x99, 0x10, 0x28, 0x01, 0x00]): self.Equipments.ST60_Log,
            bytes([0xF3, 0x18, 0x00, 0x26, 0x0F, 0x06]): self.Equipments.ST80_Masterview,
            bytes([0xFA, 0x03, 0x00, 0x30, 0x07, 0x03]): self.Equipments.ST80_Maxi_Display,
            bytes([0xFF, 0xFF, 0xFF, 0xD0, 0x00, 0x00]): self.Equipments.Smart_Controller_Remote_Control_Handset,
        })
        _TwoWayDictDatagram.__init__(self, map=equipment_map, id=0x01, data_length=5, set_key=set_key)


class ApparentWindAngleDatagram(SeatalkDatagram):  # TODO nmea mwv with ApparentWindSpeed
    """
    10  01  XX  YY  Apparent Wind Angle: XXYY/2 degrees right of bow
                Used for autopilots Vane Mode (WindTrim)
                Corresponding NMEA sentence: MWV
    """
    def __init__(self, angle_degree=None):
        SeatalkDatagram.__init__(self, id=0x10, data_length=1)
        self.angle_degree = angle_degree

    def process_datagram(self, first_half_byte, data):
        self.angle_degree = self.get_value(data) / 2  # TODO maybe some validation for <0° or >360° ?

    def get_seatalk_datagram(self):
        return self.id + bytes([self.data_length]) + self.set_value(int(self.angle_degree * 2))


class ApparentWindSpeedDatagram(SeatalkDatagram):  # TODO nmea mwv with ApparentWindAngle
    """
    11  01  XX  0Y  Apparent Wind Speed: (XX & 0x7F) + Y/10 Knots
                Units flag: XX&0x80=0    => Display value in Knots
                            XX&0x80=0x80 => Display value in Meter/Second
                Corresponding NMEA sentence: MWV
    """
    def __init__(self, speed_knots=None):
        SeatalkDatagram.__init__(self, id=0x11, data_length=1)
        self.speed_knots = speed_knots

    def process_datagram(self, first_half_byte, data):
        if data[1] & 0xF0:  # 0Y <- the 0 is important
            raise DataValidationException(f"{type(self).__name__}: Byte 1 is bigger than 0x0F {byte_to_str(data[1])}")

        speed = (data[0] & 0x7F) + data[1] / 10

        if data[0] & 0x80:  # Meter/Second
            self.speed_knots = UnitConverter.meter_to_nm(speed * 60 * 60)
        else:  # Knots
            self.speed_knots = speed

    def get_seatalk_datagram(self):
        x_byte = int(self.speed_knots)
        y_byte = int((round(self.speed_knots, 1) - x_byte) * 10)
        return self.id + bytes([self.data_length, x_byte, y_byte])


class SpeedDatagram(SeatalkDatagram, nmea_datagram.SpeedThroughWater):  # NMEA: vhw
    """
    20  01  XX  XX  Speed through water: XXXX/10 Knots
                     Corresponding NMEA sentence: VHW
    """
    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self, id=0x20, data_length=1)
        nmea_datagram.SpeedThroughWater.__init__(self, *args, **kwargs)

    def process_datagram(self, first_half_byte, data):
        self.speed_knots = self.get_value(data) / 10

    def get_seatalk_datagram(self):
        return self.id + bytes([self.data_length]) + self.set_value(self.speed_knots * 10)


class TripMileage(SeatalkDatagram):
    """
    21  02  XX  XX  0X  Trip Mileage: XXXXX/100 nautical miles
    """
    def __init__(self, mileage_miles=None):
        SeatalkDatagram.__init__(self, id=0x21, data_length=2)
        self.mileage_miles = mileage_miles

    def process_datagram(self, first_half_byte, data):
        value = (data[2] & 0x0F) << 16 | data[1] << 8 | data[0]
        self.mileage_miles = value / 100

    def get_seatalk_datagram(self):
        data = int(self.mileage_miles * 100).to_bytes(3, "little")
        return self.id + bytes([self.data_length]) + data


class TotalMileage(SeatalkDatagram):
    """
    22  02  XX  XX  00  Total Mileage: XXXX/10 nautical miles
    """

    def __init__(self, mileage_miles=None):
        SeatalkDatagram.__init__(self, id=0x22, data_length=2)
        self.mileage_miles = mileage_miles

    def process_datagram(self, first_half_byte, data):
        self.mileage_miles = self.get_value(data[:2]) / 10

    def get_seatalk_datagram(self):
        return self.id + bytes([self.data_length]) + self.set_value(self.mileage_miles * 10) + bytes([0x00])


class WaterTemperatureDatagram(SeatalkDatagram, nmea_datagram.WaterTemperature):  # NMEA: mtw
    """
    23  Z1  XX  YY  Water temperature (ST50): XX deg Celsius, YY deg Fahrenheit
                 Flag Z&4: Sensor defective or not connected (Z=4)
                 Corresponding NMEA sentence: MTW
    """
    def __init__(self, sensor_defective=None, *args, **kwargs):
        SeatalkDatagram.__init__(self, id=0x23, data_length=1)
        nmea_datagram.WaterTemperature.__init__(self, *args, **kwargs)
        self.sensor_defective = sensor_defective

    def process_datagram(self, first_half_byte, data):
        self.sensor_defective = first_half_byte & 4 == 4
        self.temperature_c = data[0]

    def get_seatalk_datagram(self):
        fahrenheit = UnitConverter.celsius_to_fahrenheit(self.temperature_c)
        first_half_byte = (self.sensor_defective << 6) | self.data_length
        return self.id + bytes([first_half_byte, int(self.temperature_c), int(fahrenheit)])


class DisplayUnitsMileageSpeed(_TwoWayDictDatagram):
    """
    24  02  00  00  XX  Display units for Mileage & Speed
                    XX: 00=nm/knots, 06=sm/mph, 86=km/kmh
    """
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
        _TwoWayDictDatagram.__init__(self, map=unit_map, id=0x24, data_length=2, set_key=unit)


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
    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self, id=0x26, data_length=4)
        nmea_datagram.SpeedThroughWater.__init__(self, *args, **kwargs)

    def process_datagram(self, first_half_byte, data):
        # TODO Y and E flag
        self.speed_knots = self.get_value(data) / 100.0

    def get_seatalk_datagram(self):
        return self.id + bytes([self.data_length]) + self.set_value(self.speed_knots * 100) + bytes([0x00, 0x00, 0x00])


class WaterTemperatureDatagram2(SeatalkDatagram, nmea_datagram.WaterTemperature):  # NMEA: mtw
    """
    27  01  XX  XX  Water temperature: (XXXX-100)/10 deg Celsius
                 Corresponding NMEA sentence: MTW
    """
    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self, id=0x27, data_length=1)
        nmea_datagram.WaterTemperature.__init__(self, *args, **kwargs)

    def process_datagram(self, first_half_byte, data):
        self.temperature_c = (self.get_value(data) - 100) / 10

    def get_seatalk_datagram(self):
        celsius_val = self.set_value((self.temperature_c * 10) + 100)
        return self.id + bytes([self.data_length]) + celsius_val


class _SetLampIntensityDatagram(_TwoWayDictDatagram, metaclass=ABCMeta):
    """
    BaseClass for Set Lamp Intensity: X=0 off, X=4: 1, X=8: 2, X=C: 3
    """
    def __init__(self, id, intensity=0):
        # Left: byte-value, Right: intensity
        intensity_map = TwoWayDict({
            bytes([0]):  0,
            bytes([4]):  1,
            bytes([8]):  2,
            bytes([12]): 3   # That's weird. All the time it's a shifted bit but this is 0x1100
        })
        _TwoWayDictDatagram.__init__(self, map=intensity_map, id=id, data_length=0, set_key=intensity)


class SetLampIntensity1(_SetLampIntensityDatagram):
    """
    30  00  0X      Set lamp Intensity; X=0: L0, X=4: L1, X=8: L2, X=C: L3
                    (only sent once when setting the lamp intensity)
    """
    def __init__(self, intensity=0):
        _SetLampIntensityDatagram.__init__(self, id=0x30, intensity=intensity)


class CancelMOB(SeatalkDatagram):
    """
    36  00  01      Cancel MOB (Man Over Board) condition
    """
    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self, id=0x36, data_length=0)
        self._expected_byte = bytes([0x01])

    def process_datagram(self, first_half_byte, data):
        if data != self._expected_byte:
            raise DataValidationException(f"{type(self).__name__}:Expected {self._expected_byte}, got {data} instead.")

    def get_seatalk_datagram(self):
        return self.id + bytes([self.data_length]) + self._expected_byte


class CodeLockData(SeatalkDatagram):
    """
    38  X1  YY  yy  CodeLock data
    """
    def __init__(self, x=None, y=None, z=None):
        SeatalkDatagram.__init__(self, id=0x38, data_length=1)
        self.x = x  # X
        self.y = y  # YY
        self.z = z  # yy

    def process_datagram(self, first_half_byte, data):
        self.x = first_half_byte
        self.y = data[0]
        self.z = data[1]

    def get_seatalk_datagram(self):
        first_byte = (self.x << 4) | self.data_length
        return self.id + bytes([first_byte, self.y, self.z])


class SpeedOverGround(SeatalkDatagram):  # TODO RMC, VTG?
    """
    52  01  XX  XX  Speed over Ground: XXXX/10 Knots
                 Corresponding NMEA sentences: RMC, VT
    """
    def __init__(self, speed_knots=None):
        SeatalkDatagram.__init__(self, id=0x52, data_length=1)
        self.speed_knots = speed_knots

    def process_datagram(self, first_half_byte, data):
        self.speed_knots = self.get_value(data) / 10

    def get_seatalk_datagram(self):
        return self.id + bytes([self.data_length]) + self.set_value(int(self.speed_knots * 10))


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

    def __init__(self, id, increment_decrement, key: Key):
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
        _TwoWayDictDatagram.__init__(self, map=key_map, id=id, data_length=1, set_key=key)
        self.increment_decrement = increment_decrement

    def process_datagram(self, first_half_byte, data):
        super().process_datagram(first_half_byte, data)
        self.increment_decrement = first_half_byte

    def get_seatalk_datagram(self):
        return super().get_seatalk_datagram(first_half_byte=self.increment_decrement)


class KeyStroke1(_KeyStroke):
    """
    55  X1  YY  yy  TRACK keystroke on GPS unit
    """
    def __init__(self, increment_decrement=0, key=None):
        _KeyStroke.__init__(self, id=0x55, increment_decrement=increment_decrement, key=key)


class GMTTime(SeatalkDatagram):
    """
     54  T1  RS  HH  GMT-time: HH hours,
                           6 MSBits of RST = minutes = (RS & 0xFC) / 4
                           6 LSBits of RST = seconds =  ST & 0x3F
                 Corresponding NMEA sentences: RMC, GAA, BWR, BWC
    """
    def __init__(self, hours=None, minutes=None, seconds=None):
        SeatalkDatagram.__init__(self, id=0x54, data_length=1)
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
        return self.id + bytes([first_byte, rs_byte, hh_byte])


class Date(SeatalkDatagram):  # TODO RMC?
    """
    56  M1  DD  YY  Date: YY year, M month, DD day in month
                    Corresponding NMEA sentence: RMC
    """
    def __init__(self, date=None):
        SeatalkDatagram.__init__(self, id=0x56, data_length=1)
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
        return self.id + bytes([first_byte, self.date.day, self.date.year - self._year_offset])


class SatInfo(SeatalkDatagram):
    """
    57  S0  DD      Sat Info: S number of sats, DD horiz. dilution of position, if S=1 -> DD=0x94
                    Corresponding NMEA sentences: GGA, GSA
    """
    def __init__(self, amount_satellites=None, horizontal_dilution=None):
        SeatalkDatagram.__init__(self, id=0x57, data_length=0)
        self.amount_satellites = amount_satellites
        self.horizontal_dilution = horizontal_dilution

    def process_datagram(self, first_half_byte, data):
        self.amount_satellites = first_half_byte
        self.horizontal_dilution = data[0]

    def get_seatalk_datagram(self):
        first_byte = (self.amount_satellites << 4) | self.data_length
        return self.id + bytes([first_byte, self.horizontal_dilution])


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
    class CounterMode(enum.IntEnum):
        CountUpStart = 0
        CountDown = 4
        CountDownStart = 8

    def __init__(self, hours=None, minutes=None, seconds=None, mode:CounterMode=None):
        SeatalkDatagram.__init__(self, id=0x59, data_length=2)
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds
        self.mode = mode

    def process_datagram(self, first_half_byte, data):
        if first_half_byte != 0x02:
            raise DataValidationException(f"First half byte is not 0x02 but {byte_to_str(first_half_byte)}")
        self.seconds = data[0]
        self.minutes = data[1]
        self.hours = data[2] & 0x0F
        self.mode = self.CounterMode(data[2] >> 4)

    def get_seatalk_datagram(self):
        first_byte = (0x02 << 4) | self.data_length
        last_byte = (self.mode.value << 4) | self.hours
        return self.id + bytes([first_byte, self.minutes, self.seconds, last_byte])


class E80Initialization(SeatalkDatagram):
    """
    61  03  03 00 00 00  Issued by E-80 multifunction display at initialization
    """
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x61, data_length=3)

    def process_datagram(self, first_half_byte, data):
        if not (first_half_byte == 0 and data[0] == 0x03 and data[1] == data[2] == data[3] == 0x00):
            raise DataValidationException(f"Cannot recognize given data: {byte_to_str(self.id)}{byte_to_str(first_half_byte << 4 | self.data_length)}{bytes_to_str(data)}")

    def get_seatalk_datagram(self):
        return self.id + bytes([self.data_length, 0x03, 0x00, 0x00, 0x00])


class SelectFathom(SeatalkDatagram):
    """
    65  00  02      Select Fathom (feet/3.33) display units for depth display (see command 00)
    """
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x65, data_length=0)
        self.byte_value = 0x02

    def process_datagram(self, first_half_byte, data):
        if data[0] != self.byte_value:
            raise DataValidationException(f"Expected byte {self.byte_value}, got {byte_to_str(data[0])}instead")

    def get_seatalk_datagram(self):
        return self.id + bytes([self.data_length, self.byte_value])


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
    class Alarm(enum.IntEnum):
        AngleLow = 0x08
        AngleHigh = 0x04
        SpeedLow = 0x02
        SpeedHigh = 0x01
        NoAlarm = 0x00

    def __init__(self, apparent_alarm: Alarm=None, true_alarm: Alarm=None):
        SeatalkDatagram.__init__(self, id=0x66, data_length=0)
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
        return self.id + bytearray([self.data_length, (x_nibble | y_nibble)])


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
        SeatalkDatagram.__init__(self, id=0x68, data_length=1)
        self.acknowledged_alarm = acknowledged_alarm

    def process_datagram(self, first_half_byte, data):
        self.acknowledged_alarm = self.AcknowledgementAlarms(first_half_byte)  # TODO enum exception

    def get_seatalk_datagram(self):
        first_half_byte = self.acknowledged_alarm.value << 4   # TODO enum exception
        acknowledging_device = bytes([0x01, 0x00])  # TODO see description of class
        return self.id + bytearray([first_half_byte | self.data_length]) + acknowledging_device


class EquipmentIDDatagram2(_TwoWayDictDatagram):
    """
     6C  05  XX XX XX XX XX XX Second equipment-ID datagram (follows 01...), reported examples:
             04 BA 20 28 2D 2D ST60 Tridata
             05 70 99 10 28 2D ST60 Log
             F3 18 00 26 2D 2D ST80 Masterview
    """
    class Equipments(enum.IntEnum):
        ST60_Tridata = enum.auto()
        ST60_Log = enum.auto()
        ST80_Masterview = enum.auto()

    def __init__(self, equipment_id: Equipments=None):
        equipment_map = TwoWayDict({
            bytes([0x04, 0xBA, 0x20, 0x28, 0x2D, 0x2D]): self.Equipments.ST60_Tridata,
            bytes([0x05, 0x70, 0x99, 0x10, 0x28, 0x2D]): self.Equipments.ST60_Log,
            bytes([0xF3, 0x18, 0x00, 0x26, 0x2D, 0x2D]): self.Equipments.ST80_Masterview,
        })
        _TwoWayDictDatagram.__init__(self, map=equipment_map, id=0x6C, data_length=5, set_key=equipment_id)


class ManOverBoard(_ZeroContentClass):
    """
    6E  07  00  00 00 00 00 00 00 00 MOB (Man Over Board), (ST80), preceded
                 by a Waypoint 999 command: 82 A5 40 BF 92 6D 24 DB
    """
    def __init__(self):
        _ZeroContentClass.__init__(self, id=0x6E, data_length=7)


class SetLampIntensity2(_SetLampIntensityDatagram):
    """
    80  00  0X      Set Lamp Intensity: X=0 off, X=4:  1, X=8:  2, X=C: 3
    """
    def __init__(self, intensity=0):
        _SetLampIntensityDatagram.__init__(self, id=0x80, intensity=intensity)


class KeyStroke2(_KeyStroke):
    """
    86  X1  YY  yy  Keystroke
    """
    def __init__(self, increment_decrement=0, key=None):
        _KeyStroke.__init__(self, id=0x86, increment_decrement=increment_decrement, key=key)


class SetResponseLevel(SeatalkDatagram):
    """
    87  00  0X        Set Response level
                  X=1  Response level 1: Automatic Deadband
                  X=2  Response level 2: Minimum Deadband
    """
    class Deadband(enum.IntEnum):
        Automatic = 1,
        Minimum = 2

    def __init__(self, response_level: Deadband=None):
        SeatalkDatagram.__init__(self, id=0x87, data_length=0)
        self.response_level = response_level

    def process_datagram(self, first_half_byte, data):
        self.response_level = self.Deadband(data[0])

    def get_seatalk_datagram(self):
        return self.id + bytearray([self.data_length, self.response_level.value])


class DeviceIdentification1(_TwoWayDictDatagram):
    """
    90  00  XX    Device Identification
                  XX=02  sent by ST600R ~every 2 secs
                  XX=05  sent by type 150, 150G and 400G course computer
                  XX=A3  sent by NMEA <-> SeaTalk bridge ~every 10 secs
    """
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
        _TwoWayDictDatagram.__init__(self, id=0x90, data_length=0, map=device_id_map, set_key=device_id)


class SetRudderGain(SeatalkDatagram):
    """
    91  00  0X        Set Rudder gain to X
    """
    def __init__(self, rudder_gain=None):
        SeatalkDatagram.__init__(self, id=0x91, data_length=0)
        self.rudder_gain = rudder_gain

    def process_datagram(self, first_half_byte, data):
        self.rudder_gain = data[0]

    def get_seatalk_datagram(self):
        return self.id + bytearray([self.data_length, self.rudder_gain])


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
    def __init__(self):
        _ZeroContentClass.__init__(self, id=0x93, data_length=0)


class DeviceIdentification2(SeatalkDatagram):
    """
    Special class, which basically holds 3 other classes (depending on length and first half byte)
    """
    id = 0xA4

    def __init__(self, real_datagram=None):
        SeatalkDatagram.__init__(self, id=self.id, data_length=-1)  # TODO -1?
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
        data_length = 2

        def __init__(self):
            _ZeroContentClass.__init__(self, id=DeviceIdentification2.id, data_length=self.data_length)

    class Termination(_ZeroContentClass):
        """
        A4  06  00  00 00 00 00 Termination of request for device identification, sent e.g. by C70 plotter
        """
        data_length = 6

        def __init__(self):
            _ZeroContentClass.__init__(self, id=DeviceIdentification2.id, data_length=self.data_length)  # TODO 6? Example shows only 4?

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
            SeatalkDatagram.__init__(self, id=DeviceIdentification2.id, data_length=self.data_length)
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
            return self.id + bytearray([first_byte, self.device_id.value, self.main_sw_version, self.minor_sw_version])
