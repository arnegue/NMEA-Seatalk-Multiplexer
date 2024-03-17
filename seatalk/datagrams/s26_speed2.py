from nmea import nmea_datagram
from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class Speed2(SeatalkDatagram, nmea_datagram.SpeedThroughWater):  # NMEA: vhw
    """
    26  04  XX  XX  YY  YY DE  Speed through water:
                     XXXX/100 Knots, sensor 1, current speed, valid if D&4=4
                     YYYY/100 Knots, average speed (trip/time) if D&8=0
                              or data from sensor 2 if D&8=8
                     E&1=1: Average speed calculation stopped
                     E&2=2: Display value in MPH
                     Corresponding NMEA sentence: VHW
    """
    seatalk_id = 0x26
    data_length = 4

    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self)
        nmea_datagram.SpeedThroughWater.__init__(self, *args, **kwargs)

    def process_datagram(self, first_half_byte, data):
        # TODO Y and E flag
        self.speed_knots = self.get_value(data) / 100.0

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length]) + self.set_value(self.speed_knots * 100) + bytearray([0x00, 0x00, 0x00])
