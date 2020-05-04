from abc import abstractmethod, ABCMeta
import inspect
import sys
import logger
from device import TaskDevice
import nmea_datagram


class SeatalkException(Exception):
    """
    Any Exception concerning Seatalk
    """


class DataValidationException(SeatalkException):
    """
    Errors happening when converting raw Seatalk-Data
    """


class DataLengthException(DataValidationException):
    """
    Exceptions happening in validation if length is incorrect
    """


class SeatalkDevice(TaskDevice, metaclass=ABCMeta):
    class RawSeatalkLogger(TaskDevice.RawDataLogger):
        def __init__(self, device_name):
            super().__init__(device_name=device_name, terminator="\n")

        def write_raw_seatalk(self, rec, attribute, data):
            data_gram_bytes = bytearray() + rec + attribute + data
            self.write_raw(SeatalkDevice.bytes_to_str(data_gram_bytes))

    def __init__(self, name, io_device):
        super().__init__(name=name, io_device=io_device)
        self._seatalk_datagram_map = dict()
        for name, obj in inspect.getmembers(sys.modules[__name__]):
            if inspect.isclass(obj) and issubclass(obj, SeatalkDatagram) and not inspect.isabstract(obj):
                instantiated_datagram = obj()
                self._seatalk_datagram_map[instantiated_datagram.id] = instantiated_datagram

    @classmethod
    def byte_to_str(cls, byte):
        return '0x%02X ' % cls.get_numeric_byte_value(byte)

    @classmethod
    def bytes_to_str(cls, bytes):
        return [cls.byte_to_str(byte) for byte in bytes]

    def _get_data_logger(self):
        return self.RawSeatalkLogger(self._name)

    @staticmethod
    def get_numeric_byte_value(byte):
        return int.from_bytes(byte, "big")

    async def _read_task(self):
        """
        For more info: http://www.thomasknauf.de/seatalk.htm
        """
        while True:
            rec = attribute = bytes()
            data_bytes = bytearray()
            try:
                rec = await self._io_device.read(1)
                if rec in self._seatalk_datagram_map:
                    attribute = await self._io_device.read(1)
                    attribute_nr = self.get_numeric_byte_value(attribute)
                    data_length = (attribute_nr & 0b00001111) + 1
                    attr_data = (attribute_nr & 0b11110000) >> 4

                    data_bytes += await self._io_device.read(data_length)
                    data_gram = self._seatalk_datagram_map[rec]
                    try:
                        data_gram.process_datagram(first_half_byte=attr_data, data=data_bytes)
                        # No need to verify checksum since it is generated the same way as it is checked
                        if isinstance(data_gram, nmea_datagram.NMEADatagram):
                            val = data_gram.get_nmea_sentence()
                            await self._read_queue.put(val)
                        else:
                            logger.info(f"{self.get_name()} doesn't have a corresponding NMEADatagram. Not enqueueing")
                    except SeatalkException as e:
                        logger.error(repr(e) + " " + self.byte_to_str(rec) + self.byte_to_str(attribute) + self.bytes_to_str(data_bytes))
                else:
                    logger.error(f"Unknown data-byte: {self.byte_to_str(rec)}")
                    self._logger.write_raw(self.byte_to_str(rec))
            finally:
                self._logger.write_raw_seatalk(rec, attribute, data_bytes)


class NotEnoughData(DataLengthException):
    def __init__(self, device, expected, actual):
        super().__init__(f"{type(device).__name__}: Not enough data arrived. Expected: {expected}, actual {actual}")


class TooMuchData(DataLengthException):
    def __init__(self, device, expected, actual):
        super().__init__(f"{type(device).__name__}: Too much data arrived. Expected: {expected}, actual {actual}")


class SeatalkDatagram(object, metaclass=ABCMeta):
    def __init__(self, id, data_length):
        self.id = bytes([id])
        self.data_length = data_length  # "Attribute" = length + 3 in datagram
        if data_length > 18 + 3:
            raise TypeError(f"{type(self).__name__}: Length > 18 not allowed. Given length: {data_length + 3}")

    def process_datagram(self, first_half_byte, data):
        if len(data) < self.data_length:
            raise NotEnoughData(device=self, expected=self.data_length, actual=len(data))
        elif len(data) > self.data_length:
            raise TooMuchData(device=self, expected=self.data_length, actual=len(data))
        self._process_datagram(first_half_byte, data)

    @staticmethod
    def get_value(data):
        return data[1] << 8 | data[0]

    @staticmethod
    def twos_complement(value, byte):  # https://stackoverflow.com/questions/6727975
        bits = byte * 8
        if value & (1 << (bits - 1)):
            value -= 1 << bits
        return value

    @abstractmethod
    def _process_datagram(self, first_half_byte, data):
        pass


class DepthDatagram(SeatalkDatagram, nmea_datagram.DepthBelowKeel):
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x00, data_length=3)
        nmea_datagram.DepthBelowKeel.__init__(self)

    def _process_datagram(self, first_half_byte, data):
        if len(data) == 3:  # TODO ? 3
            data = data[1:]
        feet = self.get_value(data) / 10.0
        self.depth_m = feet / 3.2808  # TODO double-conversion


class SpeedDatagram(SeatalkDatagram, nmea_datagram.SpeedOverWater):  # NMEA: vhw
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x20, data_length=2)
        nmea_datagram.SpeedOverWater.__init__(self)

    def _process_datagram(self, first_half_byte, data):
        self.speed_knots = self.get_value(data) / 10.0


class SpeedDatagram2(SeatalkDatagram, nmea_datagram.SpeedOverWater):  # NMEA: vhw
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x26, data_length=5)
        nmea_datagram.SpeedOverWater.__init__(self)

    def _process_datagram(self, first_half_byte, data):
        self.speed_knots = self.get_value(data) / 100.0


class WaterTemperatureDatagram(SeatalkDatagram, nmea_datagram.WaterTemperature):  # NMEA: mtw
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x23, data_length=2)
        nmea_datagram.WaterTemperature.__init__(self)

    def _process_datagram(self, first_half_byte, data):
        # TODO first_half_byte: Flag Z&4: Sensor defective or not connected (Z=4)
        self.temperature_c = data[0]


class WaterTemperatureDatagram2(SeatalkDatagram, nmea_datagram.WaterTemperature):  # NMEA: mtw
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x27, data_length=2)
        nmea_datagram.WaterTemperature.__init__(self)

    def _process_datagram(self, first_half_byte, data):
        self.temperature_c = (self.get_value(data) - 100) / 10


class SetLampIntensityDatagram(SeatalkDatagram):
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x30, data_length=1)
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
        return [self.id, 0x40, self._intensity]

    def _process_datagram(self, first_half_byte, data):
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

