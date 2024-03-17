from seatalk.seatalk_datagram import SeatalkDatagram


class CodeLockData(SeatalkDatagram):
    """
    38  X1  YY  yy  CodeLock data
    """
    seatalk_id = 0x38
    data_length = 1

    def __init__(self, x=None, y=None, z=None):
        SeatalkDatagram.__init__(self)
        self.x = x  # X
        self.y = y  # YY
        self.z = z  # yy

    def process_datagram(self, first_half_byte, data):
        self.x = first_half_byte
        self.y = data[0]
        self.z = data[1]

    def get_seatalk_datagram(self):
        first_byte = (self.x << 4) | self.data_length
        return bytearray([self.seatalk_id, first_byte, self.y, self.z])
