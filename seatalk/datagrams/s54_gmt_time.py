from datetime import time as dt_time
from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class GMT_Time(SeatalkDatagram):
    """
     54  T1  RS  HH  GMT-time: HH hours,
                           6 MSBits of RST = minutes = (RS & 0xFC) / 4
                           6 LSBits of RST = seconds =  ST & 0x3F
                 Corresponding NMEA sentences: RMC, GAA, BWR, BWC
    """
    seatalk_id = 0x54
    data_length = 1

    def __init__(self, time=None):
        super().__init__()
        self.time = time

    def process_datagram(self, first_half_byte, data):
        hours = data[1]
        minutes = (data[0] & 0xFC) // 4
        st = ((data[0] & 0x0F) << 4) | first_half_byte
        seconds = st & 0x3F
        self.time = dt_time(hour=hours, minute=minutes, second=seconds)

    def get_seatalk_datagram(self):
        hh_byte = self.time.hour
        t_nibble = self.time.second & 0x0F
        rs_byte = ((self.time.minute * 4) & 0xFC) + ((self.time.second >> 4) & 0x03)

        first_byte = t_nibble << 4 | self.data_length
        return bytearray([self.seatalk_id, first_byte, rs_byte, hh_byte])
