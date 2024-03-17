from common.helper import byte_to_str
from seatalk.datagrams.seatalk_datagram import SeatalkDatagram
from seatalk.seatalk_exceptions import DataValidationException


class E80Initialization(SeatalkDatagram):
    """
    61  03  03 00 00 00  Issued by E-80 multifunction display at initialization
    """
    seatalk_id = 0x61
    data_length = 3

    def __init__(self):
        SeatalkDatagram.__init__(self)

    def process_datagram(self, first_half_byte, data):
        if not (first_half_byte == 0 and data[0] == 0x03 and data[1] == data[2] == data[3] == 0x00):
            raise DataValidationException(
                f"{type(self).__name__}: Cannot recognize given data: {byte_to_str(self.seatalk_id)}{byte_to_str(first_half_byte << 4 | self.data_length)}{bytes_to_str(data)}")

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length, 0x03, 0x00, 0x00, 0x00])
