from abc import abstractmethod, ABCMeta
import inspect
import sys

from helper import get_numeric_byte_value, byte_to_str, bytes_to_str
import logger
from device import TaskDevice
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


class SeatalkDevice(TaskDevice, metaclass=ABCMeta):
    class RawSeatalkLogger(TaskDevice.RawDataLogger):
        def __init__(self, device_name):
            super().__init__(device_name=device_name, terminator="\n")

        def write_raw_seatalk(self, rec, attribute, data):
            data_gram_bytes = bytearray() + rec + attribute + data
            self.write_raw(bytes_to_str(data_gram_bytes))

    def __init__(self, name, io_device):
        super().__init__(name=name, io_device=io_device)
        self._seatalk_datagram_map = dict()
        for name, obj in inspect.getmembers(sys.modules[__name__]):
            if inspect.isclass(obj) and issubclass(obj, SeatalkDatagram) and not inspect.isabstract(obj):
                instantiated_datagram = obj()
                self._seatalk_datagram_map[instantiated_datagram.id] = instantiated_datagram

    def _get_data_logger(self):
        return self.RawSeatalkLogger(self._name)

    async def _read_task(self):
        """
        For more info: http://www.thomasknauf.de/seatalk.htm
        """
        while True:
            cmd_byte = attribute = bytes()
            data_bytes = bytearray()
            try:
                # Get Command-Byte
                cmd_byte = await self._io_device.read(1)
                if cmd_byte in self._seatalk_datagram_map:
                    # Extract datagram
                    data_gram = self._seatalk_datagram_map[cmd_byte]

                    # Receive attribute byte which tells how long the message will be and maybe some additional info important to the SeatalkDatagram
                    attribute = await self._io_device.read(1)
                    attribute_nr = get_numeric_byte_value(attribute)
                    data_length = attribute_nr & 0b00001111  # DataLength according to seatalk-datagram. length of 0 means 1 byte of data
                    attr_data = (attribute_nr & 0b11110000) >> 4
                    # Verifies length (will raise exception before actually receiving data which won't be needed
                    data_gram.verify_data_length(data_length)

                    # At this point data_length is okay, finally receive it and progress whole datagram
                    data_bytes += await self._io_device.read(data_length + 1)
                    data_gram.process_datagram(first_half_byte=attr_data, data=data_bytes)
                    # No need to verify checksum since it is generated the same way as it is checked

                    # Now check if there is a corresponding NMEA-Datagram (e.g. SetLampIntensityDatagram does not have one)
                    if isinstance(data_gram, nmea_datagram.NMEADatagram):
                        val = data_gram.get_nmea_sentence()
                        await self._read_queue.put(val)
                    else:
                        raise NoCorrespondingNMEASentence(data_gram)
                else:
                    raise DataNotRecognizedException(self.get_name(), cmd_byte)
            except SeatalkException as e:
                logger.error(repr(e) + " " + byte_to_str(cmd_byte) + byte_to_str(attribute) + bytes_to_str(data_bytes))
                # TODO maybe flush afterwards?
            finally:
                self._logger.write_raw_seatalk(cmd_byte, attribute, data_bytes)


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


class DepthDatagram(SeatalkDatagram, nmea_datagram.DepthBelowKeel):   # NMEA: dbt
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x00, data_length=2)
        nmea_datagram.DepthBelowKeel.__init__(self)

    def process_datagram(self, first_half_byte, data):
        data = data[1:]  # TODO first_byte & 8 = anchor-alarm, first_byte & 4 = meter or fathom
        feet = self.get_value(data) / 10.0
        self.depth_m = feet / 3.2808  # TODO double-conversion


class SpeedDatagram(SeatalkDatagram, nmea_datagram.SpeedThroughWater):  # NMEA: vhw
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x20, data_length=1)
        nmea_datagram.SpeedThroughWater.__init__(self)

    def process_datagram(self, first_half_byte, data):
        self.speed_knots = self.get_value(data) / 10.0


class SpeedDatagram2(SeatalkDatagram, nmea_datagram.SpeedThroughWater):  # NMEA: vhw
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x26, data_length=4)
        nmea_datagram.SpeedThroughWater.__init__(self)

    def process_datagram(self, first_half_byte, data):
        self.speed_knots = self.get_value(data) / 100.0


class WaterTemperatureDatagram(SeatalkDatagram, nmea_datagram.WaterTemperature):  # NMEA: mtw
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x23, data_length=1)
        nmea_datagram.WaterTemperature.__init__(self)

    def process_datagram(self, first_half_byte, data):
        # TODO first_half_byte: Flag Z&4: Sensor defective or not connected (Z=4)
        self.temperature_c = data[0]


class WaterTemperatureDatagram2(SeatalkDatagram, nmea_datagram.WaterTemperature):  # NMEA: mtw
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x27, data_length=1)
        nmea_datagram.WaterTemperature.__init__(self)

    def process_datagram(self, first_half_byte, data):
        self.temperature_c = (self.get_value(data) - 100) / 10


class SetLampIntensityDatagram(SeatalkDatagram):
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x30, data_length=0)
        self._intensity = 0

    def get_set_intensity(self, intensity):
        if intensity == 0:
            self._intensity = 0
        elif intensity == 1:
            self._intensity = 4
        elif intensity == 2:
            self._intensity = 8
        elif intensity == 3:
            self._intensity = 12  # That's weird. All the time it's a shifted bit but this is 0x1100
        return [self.id, self.data_length, self._intensity]

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

