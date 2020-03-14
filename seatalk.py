from abc import abstractmethod
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


class SeatalkDevice(TaskDevice):
    class RawSeatalkLogger(TaskDevice.RawDataLogger):
        def write_raw_seatalk(self, rec, attribute, data):
            raw_string = ""
            data_gram_bytes = bytearray() + rec + attribute + data
            for val in data_gram_bytes:
                raw_string += '0x%02X ' % val
            self.write_raw(raw_string)

    def __init__(self, name, io_device):
        super().__init__(name=name, io_device=io_device)
        self._seatalk_datagram_map = dict()
        for datagram in DepthDatagram, SpeedDatagram, WaterTemperatureDatagram, SetLampIntensityDatagram:
            instantiated_datagram = datagram()
            self._seatalk_datagram_map[instantiated_datagram.id] = instantiated_datagram

    @classmethod
    def byte_to_str(cls, byte):
        return '0x%02X ' % cls.get_numeric_byte_value(byte)

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
                        logger.error(repr(e))
                else:
                    logger.error(f"Unknown data-byte: {self.byte_to_str(rec)}")
                    self._logger.write_raw(self.byte_to_str(rec))
            finally:
                self._logger.write_raw_seatalk(rec, attribute, data_bytes)


class NotEnoughData(DataLengthException):
    def __init__(self, device, expected, actual):
        super().__init__(f"{device}: Not enough data arrived. Expected: {expected}, actual {actual}")


class TooMuchData(DataLengthException):
    def __init__(self, device, actual):
        super().__init__(f"{device}: Length > 18 not allowed. Given length: {actual}")


class SeatalkDatagram(object):
    def __init__(self, id, data_length):
        self.id = bytes([id])
        self.data_length = data_length  # "Attribute" = length + 3 in datagram
        if data_length > 18 + 3:
            raise TooMuchData(self, data_length)

    def process_datagram(self, first_half_byte, data):
        if len(data) != self.data_length:
            raise NotEnoughData(device=self, expected=self.data_length, actual=len(data))
        self._process_datagram(first_half_byte, data)

    @staticmethod
    def get_value(data):
        return (data[1] << 8 | data[0]) / 10.0

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
        feet = self.get_value(data)
        self.depth_m = feet / 3.2808  # TODO double-conversion


class SpeedDatagram(SeatalkDatagram, nmea_datagram.SpeedOverWater):  # NMEA: vhw
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x20, data_length=2)
        nmea_datagram.SpeedOverWater.__init__(self)

    def _process_datagram(self, first_half_byte, data):
        self.speed_knots = self.get_value(data)


class WaterTemperatureDatagram(SeatalkDatagram, nmea_datagram.WaterTemperature):
    def __init__(self):
        SeatalkDatagram.__init__(self, id=0x23, data_length=2)
        nmea_datagram.WaterTemperature.__init__(self)

    def _process_datagram(self, first_half_byte, data):
        # value = data[0]  # Celsius
        # value = data[1]  # Fahrenheit
        self.speed_knots = self.twos_complement(data[0], 1)


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

