import enum

from common.helper import bytes_to_str
from seatalk.datagrams.seatalk_datagram import SeatalkDatagram
from seatalk.seatalk_exceptions import TooMuchData, DataValidationException


class CourseComputerSetup(SeatalkDatagram):
    """
    81  01  00  00  Sent by course computer during setup when going past USER CAL.
    81  00  00      Sent by course computer immediately after above.
    """
    seatalk_id = 0x81
    data_length = -1

    class MessageTypes(enum.IntEnum):
        SetupFinished = 0
        Setup = 1

    def __init__(self, message_type:MessageTypes=None):
        super().__init__()
        self.message_type = message_type

    def verify_data_length(self, data_len):
        try:
            self.message_type = self.MessageTypes(data_len)
        except ValueError as e:
            raise TooMuchData(data_gram=self, expected=[e.value for e in self.MessageTypes], actual=data_len) from e

    def process_datagram(self, first_half_byte, data):
        all_bytes = bytearray([first_half_byte]) + data
        for value in all_bytes:
            if value != 0:
                raise DataValidationException(f"{type(self).__name__}: Not all bytes are 0x00: {bytes_to_str(all_bytes)}")

    def get_seatalk_datagram(self):
        ret_val = bytearray([self.seatalk_id, self.message_type.value, 0x00])
        if self.message_type == self.MessageTypes.Setup:
            ret_val.append(0x00)
        return ret_val
