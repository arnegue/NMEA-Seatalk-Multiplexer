from seatalk.seatalk_datagram import SeatalkDatagram


class GMT_Time(SeatalkDatagram):
    """
     54  T1  RS  HH  GMT-time: HH hours,
                           6 MSBits of RST = minutes = (RS & 0xFC) / 4
                           6 LSBits of RST = seconds =  ST & 0x3F
                 Corresponding NMEA sentences: RMC, GAA, BWR, BWC
    """
    seatalk_id = 0x54
    data_length = 1

    def __init__(self, hours=None, minutes=None, seconds=None):
        SeatalkDatagram.__init__(self)
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds

    def process_datagram(self, first_half_byte, data):
        self.hours = data[1]
        self.minutes = (data[0] & 0xFC) // 4
        st = ((data[0] & 0x0F) << 4) | first_half_byte
        self.seconds = st & 0x3F

    def get_seatalk_datagram(self):
        hh_byte = self.hours
        t_nibble = self.seconds & 0x0F
        rs_byte = ((self.minutes * 4) & 0xFC) + ((self.seconds >> 4) & 0x03)

        first_byte = t_nibble << 4 | self.data_length
        return bytearray([self.seatalk_id, first_byte, rs_byte, hh_byte])
