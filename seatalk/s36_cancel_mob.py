from seatalk.seatalk_datagram import SeatalkDatagram
from seatalk.seatalk_exceptions import DataValidationException


class CancelMOB(SeatalkDatagram):
    """
    36  00  01      Cancel MOB (Man Over Board) condition
    """
    seatalk_id = 0x36
    data_length = 0

    def __init__(self, *args, **kwargs):
        SeatalkDatagram.__init__(self)
        self._expected_byte = bytearray([0x01])

    def process_datagram(self, first_half_byte, data):
        if data != self._expected_byte:
            raise DataValidationException(f"{type(self).__name__}: Expected {self._expected_byte}, got {data} instead.")

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length]) + self._expected_byte
