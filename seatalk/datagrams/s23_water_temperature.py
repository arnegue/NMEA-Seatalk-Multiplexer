from common.helper import UnitConverter
from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class WaterTemperature1(SeatalkDatagram):
    """
    23  Z1  XX  YY  Water temperature (ST50): XX deg Celsius, YY deg Fahrenheit
                 Flag Z&4: Sensor defective or not connected (Z=4)
    """
    seatalk_id = 0x23
    data_length = 1

    def __init__(self, temperature_c=None, sensor_defective=None):
        super().__init__()
        self.temperature_c = temperature_c
        self.sensor_defective = sensor_defective

    def process_datagram(self, first_half_byte, data):
        self.sensor_defective = first_half_byte & 4 == 4
        self.temperature_c = data[0]

    def get_seatalk_datagram(self):
        fahrenheit = UnitConverter.celsius_to_fahrenheit(self.temperature_c)
        first_half_byte = (self.sensor_defective << 6) | self.data_length
        return bytearray([self.seatalk_id, first_half_byte, int(self.temperature_c), int(fahrenheit)])
