from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class SpeedOverGround(SeatalkDatagram):
    """
    52  01  XX  XX  Speed over Ground: XXXX/10 Knots
    """
    seatalk_id = 0x52
    data_length = 1

    def __init__(self, speed_knots=None):
        super().__init__()
        self.speed_knots = speed_knots

    def process_datagram(self, first_half_byte, data):
        self.speed_knots = self.get_value(data) / 10

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length]) + self.set_value(int(self.speed_knots * 10))
