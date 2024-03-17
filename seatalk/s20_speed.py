from nmea import nmea_datagram
from seatalk.seatalk_datagram import SeatalkDatagram


class Speed(SeatalkDatagram, nmea_datagram.SpeedThroughWater):  # NMEA: vhw
    """
    20  01  XX  XX  Speed through water: XXXX/10 Knots
                     Corresponding NMEA sentence: VHW
    """
    seatalk_id = 0x20
    data_length = 1

    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self)
        nmea_datagram.SpeedThroughWater.__init__(self, *args, **kwargs)

    def process_datagram(self, first_half_byte, data):
        self.speed_knots = self.get_value(data) / 10

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length]) + self.set_value(self.speed_knots * 10)
