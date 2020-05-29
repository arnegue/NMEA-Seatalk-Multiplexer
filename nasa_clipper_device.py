import device
import logger
from abc import ABCMeta, abstractmethod
from nmea_datagram import NMEADatagram, DepthBelowKeel, SpeedThroughWater


class SevenSegmentDisplay(object):
    display_map = [
        # a     b      c      d      e      f      g
        [True,  True,  True,  True,  True,  True,  False],  # 0
        [False, True,  True,  False, False, False, False],  # 1
        [True,  True,  False, True,  True,  False, True],   # 2
        [True,  True,  True,  True,  False, False, True],   # 3
        [False, True,  True,  False, False, True,  True],   # 4
        [True,  False, True,  True,  False, True,  True],   # 5
        [True,  False, True,  True,  True,  True,  False],  # 6
        [True,  True,  True,  False, False, False, False],  # 7
        [True,  True,  True,  True,  True,  True,  True],   # 8
        [True,  True,  True,  True,  False, True,  True],   # 9
    ]

    @classmethod
    def get_value(cls, a, b, c, d, e, f, g):
        search = [a, b, c, d, e, f, g]
        for i in range(len(cls.display_map)):
            value_array = cls.display_map[i]
            if value_array == search:
                return i
        raise NotParsableDisplayException("Value", search)


class ClipperException(Exception):
    pass


class WrongCmdBytesException(ClipperException):
    def __init__(self, expected, actual):
        super().__init__(f"Received unexpected command bytes. Expected: {expected}, Actual {actual}")


class NotParsableDisplayException(ClipperException):
    def __init__(self, type, search):
        super().__init__(f"Could not find {type} in {search}")


def get_bit_at(value, position):
    bit_map = 1 << position
    return (value & bit_map) >> position


class NasaClipperDevice(device.TaskDevice, metaclass=ABCMeta):
    def __init__(self, name, io_device, command_bytes, nmea_datagram: NMEADatagram):
        super().__init__(name=name, io_device=io_device)
        self.cmd_bytes = command_bytes
        self.nmea_datagram = nmea_datagram

    @staticmethod
    def main_display_is_set(data):
        return get_bit_at(data[0], 0) == 1

    def get_nmea_datagram(self, data):
        display_is_set = not self.main_display_is_set(data)
        if display_is_set:
            raise NotParsableDisplayException("DisplayMode", display_is_set)

        value = self.extract_display_value(data)
        primary_unit = self.primary_unit_is_set(data)
        if not primary_unit:
            value = self.convert_value(value)

        return self.nmea_datagram(value)

    @abstractmethod
    def convert_value(self, value):
        raise NotImplementedError()

    async def _read_task(self):
        """
        https://wiki.openseamap.org/wiki/De:NASA_Clipper_Range
        Byte     0              1     2     3     4     5     6     7     8     9     10    11
        Meaning  ADDR+WRITE     CMD   CMD   CMD   CMD   CMD   DATA  DATA  DATA  DATA  DATA  DATA
        Content  0x3E+W = 0x7C  0xCE  0x80  0xE0  0xF8  0x70  DATA  DATA  DATA  DATA  DATA  DATA
        """
        while True:
            received = await self._io_device.read(12)
            split_index = 5
            cmd = received[:split_index]
            data = received[split_index:]

            try:
                if cmd != self.cmd_bytes:
                    raise WrongCmdBytesException(self.cmd_bytes, cmd)

                datagram = self.get_nmea_datagram(data)
                self._read_queue.put(datagram)

            except ClipperException as e:
                logger.error(repr(e))

                NMEADatagram.verify_checksum(data)
                self._logger.info(data)
                await self._read_queue.put(data)

    @staticmethod
    def extract_display_value(data):
        first_digit =  SevenSegmentDisplay.get_value(a=get_bit_at(data[4], 5),
                                                     b=get_bit_at(data[4], 2),
                                                     c=get_bit_at(data[5], 6),
                                                     d=get_bit_at(data[5], 7),
                                                     e=get_bit_at(data[4], 1),
                                                     f=get_bit_at(data[4], 3),
                                                     g=get_bit_at(data[4], 0))

        second_digit = SevenSegmentDisplay.get_value(a=get_bit_at(data[0], 1),
                                                     b=get_bit_at(data[0], 2),
                                                     c=get_bit_at(data[0], 6),
                                                     d=get_bit_at(data[0], 7),
                                                     e=get_bit_at(data[0], 5),
                                                     f=get_bit_at(data[0], 3),
                                                     g=get_bit_at(data[0], 4))

        third_digit =  SevenSegmentDisplay.get_value(a=get_bit_at(data[1], 7),
                                                     b=get_bit_at(data[1], 4),
                                                     c=get_bit_at(data[1], 0),
                                                     d=get_bit_at(data[1], 1),
                                                     e=get_bit_at(data[1], 3),
                                                     f=get_bit_at(data[1], 5),
                                                     g=get_bit_at(data[1], 2))
        decimal_dot = get_bit_at(data[3], 7)

        if decimal_dot:
            value = first_digit * 10 + second_digit + third_digit / 10
        else:
            value = first_digit * 100 + second_digit * 10 + third_digit
        return value

    @staticmethod
    def primary_unit_is_set(data):
        primary_unit = get_bit_at(data[3], 6)
        secondary_unit = get_bit_at(data[2], 0)

        if primary_unit == secondary_unit:
            raise NotParsableDisplayException(type="UOM|Same Value", search=[primary_unit, secondary_unit])

        if primary_unit:
            return True
        else:
            return False


class ClipperEcho(NasaClipperDevice):
    def __init__(self, name, io_device):
        super().__init__(name, io_device, command_bytes=[0xCE, 0x80, 0xE0, 0xF8, 0x70], nmea_datagram=DepthBelowKeel)

    def convert_value(self, value):
        return value / 3.28084  # feet to meters


class ClipperLog(NasaClipperDevice):
    def __init__(self, name, io_device):
        super().__init__(name, io_device, command_bytes=[], nmea_datagram=SpeedThroughWater)  # TODO how is that different to log?

    def convert_value(self, value):
        return value / 1.150  # statute miles miles  to knots


a = ClipperEcho(name="fakeEcho", io_device=None)

answer_addr = 0x7c
cmd = [answer_addr, 0xCE, 0x80, 0xE0, 0xF8, 0x70]
data = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
a.get_nmea_datagram(data= data)
