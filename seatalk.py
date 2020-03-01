from abc import abstractmethod


class SeatalkException(Exception):
    pass


class DataValidationException(SeatalkException):
    pass


class DataLengthException(SeatalkException):
    def __init__(self, device, expected, actual):
        super().__init__(f"{device}: Not enough data arrived. Excpeted: {expected}, actual {actual}")


class SeatalkDatagram(object):
    def __init__(self, name, id, data_length):
        self.name = name
        self.id = id
        self.data_length = data_length  # "Attribute" = length + 3 in datagram
        if data_length > 18 + 3:
            raise Exception("Length > 18 not allowed. Given length:", data_length)

    def process_datagram(self, first_half_byte, data):
        if len(data) != self.data_length:
            raise DataLengthException(device=self.name, expected=self.data_length, actual=len(data))
        return self.name + f": {self._process_datagram(first_half_byte, data):.2f}"

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


class DepthDatagram(SeatalkDatagram):
    def __init__(self):
        super().__init__(name="Depth", id=0x00, data_length=3)

    def _process_datagram(self, first_half_byte, data):
        if len(data) == 3:  # TODO ? 3
            data = data[1:]
        feet = self.get_value(data)
        meters = feet / 3.2808
        return meters


class SpeedDatagram(SeatalkDatagram):  # NMEA: vhw
    def __init__(self):
        super().__init__(name="Speed", id=0x20, data_length=2)

    def _process_datagram(self, first_half_byte, data):
        knots = self.get_value(data)
        return knots


class WaterTemperatureDatagram(SeatalkDatagram):
    def __init__(self, celsius_notFahrenheit=True):
        super().__init__(name="WaterTemperature", id=0x23, data_length=2)
        self.celsius_notFahrenheit = celsius_notFahrenheit

    def _process_datagram(self, first_half_byte, data):
        if self.celsius_notFahrenheit:
            value = data[0]  # Celsius
        else:
            value = data[1]  # Fahrenheit (TODO might be buggy?)

        return self.twos_complement(value, 1)


class EquipmentID(SeatalkDatagram):
    pass #def __init__(self, id=1, length=


def create_seatalk_map():
    depth = DepthDatagram()
    speed = SpeedDatagram()
    temper = WaterTemperatureDatagram()
    list_datagrams = [depth, speed, temper]
    st_map = dict()
    for datagram in list_datagrams:
        st_map[datagram.id] = datagram
    return st_map