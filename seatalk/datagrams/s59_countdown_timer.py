import enum

from common.helper import byte_to_str
from seatalk.datagrams.seatalk_datagram import SeatalkDatagram
from seatalk.seatalk_exceptions import DataValidationException


class CountdownTimer(SeatalkDatagram):
    """
    59  22  SS MM XH  Set Count Down Timer
                   MM=Minutes ( 00..3B ) ( 00 .. 63 Min ), MSB:0 Count up start flag
                   SS=Seconds ( 00..3B ) ( 00 .. 59 Sec )
                   H=Hours    ( 0..9 )   ( 00 .. 09 Hours )
                   X= Counter Mode: 0 Count up and start if MSB of MM set
                                    4 Count down
                                    8 Count down and start
                   ( Example 59 22 3B 3B 49 -> Set Countdown Timer to 9.59:59 )
    59  22  0A 00 80  Sent by ST60 in countdown mode when counted down to 10 Seconds.
    """
    seatalk_id = 0x59
    data_length = 2

    class CounterMode(enum.IntEnum):
        CountUpStart = 0
        CountDown = 4
        CountDownStart = 8

    def __init__(self, hours=None, minutes=None, seconds=None, mode: CounterMode = None):
        SeatalkDatagram.__init__(self)
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds
        self.mode = mode

    def process_datagram(self, first_half_byte, data):
        if first_half_byte != 0x02:
            raise DataValidationException(
                f"{type(self).__name__}: First half byte is not 0x02 but {byte_to_str(first_half_byte)}")
        self.seconds = data[0]
        self.minutes = data[1]
        self.hours = data[2] & 0x0F
        try:  # At startup ST60+ sends 0x59 0x22 0x00 0x59 0x59
            self.mode = self.CounterMode(data[2] >> 4)
        except ValueError:
            raise DataValidationException(f"{type(self).__name__}: CounterMode invalid: {data[2] >> 4}")

    def get_seatalk_datagram(self):
        first_byte = (0x02 << 4) | self.data_length
        last_byte = (self.mode.value << 4) | self.hours
        return bytearray([self.seatalk_id, first_byte, self.minutes, self.seconds, last_byte])
