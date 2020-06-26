from abc import abstractmethod, ABCMeta

from helper import byte_to_str, UnitConverter, TwoWayDict
import logger
import nmea_datagram
import enum


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
        if data_length > 18 + 3:
            raise TypeError(f"{type(self).__name__}: Length > 18 not allowed. Given length: {data_length + 3}")

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


class EquipmentIDDatagram(SeatalkDatagram):
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
        SeatalkDatagram.__init__(self, id=0x01, data_length=5)
        self.equipment_id = equipment_id
        self._equipment_map = TwoWayDict({
            bytes([0x00, 0x00, 0x00, 0x60, 0x01, 0x00]): self.Equipments.Course_Computer_400G,
            bytes([0x04, 0xBA, 0x20, 0x28, 0x01, 0x00]): self.Equipments.ST60_Tridata,
            bytes([0x70, 0x99, 0x10, 0x28, 0x01, 0x00]): self.Equipments.ST60_Log,
            bytes([0xF3, 0x18, 0x00, 0x26, 0x0F, 0x06]): self.Equipments.ST80_Masterview,
            bytes([0xFA, 0x03, 0x00, 0x30, 0x07, 0x03]): self.Equipments.ST80_Maxi_Display,
            bytes([0xFF, 0xFF, 0xFF, 0xD0, 0x00, 0x00]): self.Equipments.ST60_Log,
        })

    def process_datagram(self, first_half_byte, data):
        try:
            self.equipment_id = self._equipment_map[bytes(data)]
        except KeyError as e:
            raise DataValidationException(f"{type(self).__name__}: No corresponding Equipment to given equipment-bytes: {byte_to_str(data)}") from e
        print(self.equipment_id.name)

    def get_seatalk_datagram(self):
        try:
            equipment_bytes = self._equipment_map.get_reversed(self.equipment_id)
        except ValueError as e:
            raise DataValidationException(f"{type(self).__name__}: No corresponding Equipment-bytes to given equipment-ID: {self.equipment_id}") from e
        return self.id + bytearray([self.data_length]) + equipment_bytes


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


class SetLampIntensityDatagram(SeatalkDatagram):
    """
    80  00  0X      Set Lamp Intensity: X=0 off, X=4: 1, X=8: 2, X=C: 3
    """
    def __init__(self, intensity=0):
        SeatalkDatagram.__init__(self, id=0x30, data_length=0)
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
