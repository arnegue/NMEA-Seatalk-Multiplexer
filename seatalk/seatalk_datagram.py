from abc import abstractmethod, ABCMeta

from helper import byte_to_str, UnitConverter
import logger
import nmea_datagram


class SeatalkException(Exception):
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
        # TODO X and Z flag
        data = data[1:]
        feet = self.get_value(data) / 10.0
        self.depth_m = feet / 3.2808

    def get_seatalk_datagram(self):
        feet_value = UnitConverter.meter_to_feet(self.depth_m) * 10
        default_byte_array = bytearray([self.data_length,
                                        0x00])  # No sensor defectives
        return self.id + default_byte_array + self.set_value(feet_value)


class SpeedDatagram(SeatalkDatagram, nmea_datagram.SpeedThroughWater):  # NMEA: vhw
    """
    20  01  XX  XX  Speed through water: XXXX/10 Knots
                     Corresponding NMEA sentence: VHW
    """
    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self, id=0x20, data_length=1)
        nmea_datagram.SpeedThroughWater.__init__(self, *args, **kwargs)

    def process_datagram(self, first_half_byte, data):
        self.speed_knots = self.get_value(data) / 10.0

    def get_seatalk_datagram(self):
        return self.id + bytes([self.data_length]) + self.set_value(self.speed_knots * 10)


class SpeedDatagram2(SeatalkDatagram, nmea_datagram.SpeedThroughWater):  # NMEA: vhw
    """
    26  04  XX  XX  YY  YY DE  Speed through water:
                     XXXX/100 Knots, sensor 1, current speed, valid if D&4=4
                     YYYY/100 Knots, average speed (trip/time) if D&8=0
                              or data from sensor 2 if D&8=8
                     E&1=1: Average speed calulation stopped
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


class SetLampIntensityDatagram(SeatalkDatagram):
    """
    80  00  0X      Set Lamp Intensity: X=0 off, X=4: 1, X=8: 2, X=C: 3
    """
    def __init__(self, intensity=0):
        SeatalkDatagram.__init__(self, id=0x30, data_length=0)
        self._intensity = intensity

    def get_seatalk_datagram(self):
        intensity = 0  # if self._intensity == 0:
        if self._intensity == 1:
            intensity = 4
        elif self._intensity == 2:
            intensity = 8
        elif self._intensity == 3:
            intensity = 12  # That's weird. All the time it's a shifted bit but this is 0x1100
        return self.id + bytearray([self.data_length, intensity])

    def process_datagram(self, first_half_byte, data):
        intensity = data[0]
        if intensity == 0:
            self._intensity = 0
        elif intensity == 4:
            self._intensity = 1
        elif intensity == 8:
            self._intensity = 2
        elif intensity == 12:
            self._intensity = 3  # That's weird. All the time it's a shifted bit but this is 0x1100
        # else:
        #   TODO what now? parse-exception?

