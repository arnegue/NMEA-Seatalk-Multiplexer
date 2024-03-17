from nmea import nmea_datagram
from seatalk.seatalk_datagram import SeatalkDatagram


class WaterTemperature2(SeatalkDatagram, nmea_datagram.WaterTemperature):  # NMEA: mtw
    """
    27  01  XX  XX  Water temperature: (XXXX-100)/10 deg Celsius
                 Corresponding NMEA sentence: MTW
    """
    seatalk_id = 0x27
    data_length = 1

    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self)
        nmea_datagram.WaterTemperature.__init__(self, *args, **kwargs)

    def process_datagram(self, first_half_byte, data):
        self.temperature_c = (self.get_value(data) - 100) / 10

    def get_seatalk_datagram(self):
        celsius_val = self.set_value((self.temperature_c * 10) + 100)
        return bytearray([self.seatalk_id, self.data_length]) + celsius_val
