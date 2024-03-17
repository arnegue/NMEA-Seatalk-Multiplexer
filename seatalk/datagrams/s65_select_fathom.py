from common.helper import byte_to_str
from seatalk.datagrams.seatalk_datagram import SeatalkDatagram
from seatalk.seatalk_exceptions import DataValidationException


class SelectFathom(SeatalkDatagram):
    """
    65  00  02      Select Fathom (feet/3.33) display units for depth display (see command 00)
    """
    seatalk_id = 0x65
    data_length = 0

    def __init__(self):
        SeatalkDatagram.__init__(self)
        self.byte_value = 0x02

    def process_datagram(self, first_half_byte, data):
        if data[0] != self.byte_value:
            raise DataValidationException(
                f"{type(self).__name__}: Expected byte {self.byte_value}, got {byte_to_str(data[0])} instead")

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length, self.byte_value])
