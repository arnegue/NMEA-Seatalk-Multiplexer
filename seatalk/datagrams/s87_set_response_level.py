import enum

from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class SetResponseLevel(SeatalkDatagram):
    """
    87  00  0X        Set Response level
                  X=1  Response level 1: Automatic Deadband
                  X=2  Response level 2: Minimum Deadband
    """
    seatalk_id = 0x87
    data_length = 0

    class Deadband(enum.IntEnum):
        Automatic = 1,
        Minimum = 2

    def __init__(self, response_level: Deadband=None):
        super().__init__()
        self.response_level = response_level

    def process_datagram(self, first_half_byte, data):
        self.response_level = self.Deadband(data[0])

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length, self.response_level.value])
