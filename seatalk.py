from abc import abstractmethod
import serial
from device_indicator.device import SerialDevice
from device_indicator import nmea_datagram


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


class SeatalkDevice(SerialDevice):

    async def write_to_device(self, sentence: nmea_datagram.NMEADatagram):
        pass  # Not supported yet, i think

    def __init__(self, name, port):
        super().__init__(name=name, port=port, parity=serial.PARITY_MARK)
        self._seatalk_datagram_map = dict()
        for datagram in DepthDatagram, SpeedDatagram, WaterTemperatureDatagram:
            instantiated_datagram = datagram()
            self._seatalk_datagram_map[instantiated_datagram.id] = instantiated_datagram

    def _read_thread(self):
        """
        For more info: http://www.thomasknauf.de/seatalk.htm
        """
        while self._continue:
            rec = list(self._serial.read(1))[0]
            if rec in self._seatalk_datagram_map:
                attribute = list(self._serial.read(1))[0]
                data_length = (attribute & 0b00001111) + 1
                attr_data = (attribute & 0b11110000) >> 4
                data = list(self._serial.read(data_length))

                data_gram = self._seatalk_datagram_map[rec]
                try:
                    data_gram.process_datagram(first_half_byte=attr_data, data=data)
                    val = data_gram.get_nmea_sentence()
                    self._read_queue.put(val)
                except SeatalkException as e:
                    print(repr(e))
            else:
                print(f"Unknown data-byte: {hex(rec)}")

    def _doesnt_work(self):
        while self._continue:
            rec = list(self._serial.read(1))[0]  # ODO 0?
            if rec in self._seatalk_datagram_map:
                data_gram = self._seatalk_datagram_map[rec]

                attribute = list(self._serial.read(1))[0]
                data_length = (attribute & 0b00001111) + 1
                attr_data = (attribute & 0b11110000) >> 4
                data = list(self._serial.read(data_length))

                try:
                    val = data_gram.process_datagram(first_half_byte=attr_data, data=data)
                    self._read_queue.put(val)
                except SeatalkException as e:
                    print(repr(e))
            else:
                print(f"Unknown data-byte: {hex(rec)}")


class NotEnoughData(DataLengthException):
    def __init__(self, device, expected, actual):
        super().__init__(f"{device}: Not enough data arrived. Expected: {expected}, actual {actual}")


class TooMuchData(DataLengthException):
    def __init__(self, device, actual):
        super().__init__(f"{device}: Length > 18 not allowed. Given length: {actual}")


class SeatalkDatagram(object):
    def __init__(self, id, data_length):
        self.id = id
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
