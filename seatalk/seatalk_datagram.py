from abc import abstractmethod, ABCMeta
import enum
import datetime

from helper import byte_to_str, bytes_to_str, UnitConverter, TwoWayDict
import logger
import nmea_datagram


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
        return self.id + bytearray([self.data_length] + [0x00 for _ in range(self.data_length + 1)]) # + 1 for very first byte


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


class _EquipmentIDDatagram(SeatalkDatagram, metaclass=ABCMeta):
    """
    BaseClass for EquipmentID Datagrams
    """
    def __init__(self, equipment_map: TwoWayDict, id, data_length, equipment_id=None):
        SeatalkDatagram.__init__(self, id=id, data_length=data_length)
        self._equipment_map = equipment_map
        self.equipment_id = equipment_id

    def process_datagram(self, first_half_byte, data):
        try:
            self.equipment_id = self._equipment_map[bytes(data)]
        except KeyError as e:
            raise DataValidationException(f"{type(self).__name__}: No corresponding Equipment-ID to given Equipment-bytes: {bytes_to_str(data)}") from e

    def get_seatalk_datagram(self):
        try:
            equipment_bytes = self._equipment_map.get_reversed(self.equipment_id)
        except ValueError as e:
            raise DataValidationException(f"{type(self).__name__}: No corresponding Equipment-bytes to given Equipment-ID: {self.equipment_id}") from e
        return self.id + bytearray([self.data_length]) + equipment_bytes


class EquipmentIDDatagram1(_EquipmentIDDatagram):
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

    def __init__(self, equipment_id: Equipments=None):
        equipment_map = TwoWayDict({
            bytes([0x00, 0x00, 0x00, 0x60, 0x01, 0x00]): self.Equipments.Course_Computer_400G,
            bytes([0x04, 0xBA, 0x20, 0x28, 0x01, 0x00]): self.Equipments.ST60_Tridata,
            bytes([0x70, 0x99, 0x10, 0x28, 0x01, 0x00]): self.Equipments.ST60_Log,
            bytes([0xF3, 0x18, 0x00, 0x26, 0x0F, 0x06]): self.Equipments.ST80_Masterview,
            bytes([0xFA, 0x03, 0x00, 0x30, 0x07, 0x03]): self.Equipments.ST80_Maxi_Display,
            bytes([0xFF, 0xFF, 0xFF, 0xD0, 0x00, 0x00]): self.Equipments.Smart_Controller_Remote_Control_Handset,
        })
        _EquipmentIDDatagram.__init__(self, equipment_map=equipment_map, id=0x01, data_length=5, equipment_id=equipment_id)


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
    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self, id=0x23, data_length=1)
        nmea_datagram.WaterTemperature.__init__(self, *args, **kwargs)

    def process_datagram(self, first_half_byte, data):
        # TODO Y and Z Flag
        #  Z = first_half_byte
        #  Y = data[1]
        self.temperature_c = data[0]

    def get_seatalk_datagram(self):
        fahrenheit = UnitConverter.celsius_to_fahrenheit(self.temperature_c)
        return self.id + bytes([self.data_length, int(self.temperature_c), int(fahrenheit)])


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
        celsius_val = self.set_value((self.temperature_c + 100) * 10)
        return self.id + bytes([self.data_length]) + celsius_val


class _SetLampIntensityDatagram(SeatalkDatagram, metaclass=ABCMeta):
    """
    BaseClass for Set Lamp Intensity: X=0 off, X=4: 1, X=8: 2, X=C: 3
    """
    def __init__(self, id, intensity=0):
        SeatalkDatagram.__init__(self, id=id, data_length=0)
        self.intensity = intensity

        # Left: byte-value, Right: intensity
        self._intensity_map = TwoWayDict({
            0:  0,
            4:  1,
            8:  2,
            12: 3   # That's weird. All the time it's a shifted bit but this is 0x1100
        })

    def process_datagram(self, first_half_byte, data):
        try:
            self.intensity = self._intensity_map[data[0]]
        except KeyError as e:
            raise DataValidationException(f"{type(self).__name__}: Unexpected Intensity: {data[0]}") from e

    def get_seatalk_datagram(self):
        try:
            intensity = self._intensity_map.get_reversed(self.intensity)
        except ValueError as e:
            raise DataValidationException(f"{type(self).__name__}: No corresponding Intensity-byte to intensity: {self.intensity}") from e
        return self.id + bytearray([self.data_length, intensity])


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


class EquipmentIDDatagram2(_EquipmentIDDatagram):
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
        _EquipmentIDDatagram.__init__(self, equipment_map=equipment_map, id=0x6C, data_length=5, equipment_id=equipment_id)


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


class DeviceIdentification(SeatalkDatagram):
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
        SeatalkDatagram.__init__(self, id=0x90, data_length=0)
        self.device_id = device_id
        self._device_id_map = TwoWayDict({
            0x02: self.DeviceID.ST600R,
            0x05: self.DeviceID.Type_150_150G_400G,
            0xA3: self.DeviceID.NMEASeatalkBridge
        })

    def process_datagram(self, first_half_byte, data):
        try:
            self.device_id = self._device_id_map[data[0]]
        except KeyError as e:
            raise DataValidationException(f"{type(self).__name__}: Unexpected DeviceID: {data[0]}") from e

    def get_seatalk_datagram(self):
        try:
            intensity = self._device_id_map.get_reversed(self.device_id)
        except ValueError as e:
            raise DataValidationException(f"{type(self).__name__}: No corresponding DeviceID-byte to intensity: {self.device_id}") from e
        return self.id + bytearray([self.data_length, intensity])


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
