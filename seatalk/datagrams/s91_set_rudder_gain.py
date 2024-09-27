from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class SetRudderGain(SeatalkDatagram):
    """
    91  00  0X        Set Rudder gain to X
    """
    seatalk_id = 0x91
    data_length = 0

    def __init__(self, rudder_gain=None):
        super().__init__()
        self.rudder_gain = rudder_gain

    def process_datagram(self, first_half_byte, data):
        self.rudder_gain = data[0]

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length, self.rudder_gain])
