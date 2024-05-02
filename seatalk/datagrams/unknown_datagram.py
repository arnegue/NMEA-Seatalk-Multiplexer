from seatalk.datagrams import SeatalkDatagram


class UnknownDatagram(SeatalkDatagram):
    def __init__(self, datagram: bytearray = None):
        self.__class__.seatalk_id = datagram[0]
        self.__class__.data_length = datagram[1] & 0x0F
        super().__init__()
        self.data = datagram[1:]

    def verify_data_length(self, data_len):
        pass  # Nothing to verify

    def process_datagram(self, first_half_byte, data):
        """
        Most important seatalk-method which finally processes given bytes
        """
        raise NotImplementedError()

    def get_seatalk_datagram(self):
        """
        Creates byte-array to send back on seatalk-bus
        """
        return bytearray([self.seatalk_id, self.data_length]) + self.data
