from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class SatInfo(SeatalkDatagram):
    """
    57  S0  DD      Sat Info: S number of sats, DD horiz. dilution of position, if S=1 -> DD=0x94
                    Corresponding NMEA sentences: GGA, GSA
    """
    seatalk_id = 0x57
    data_length = 0

    def __init__(self, amount_satellites=None, horizontal_dilution=None):
        super().__init__()
        self.amount_satellites = amount_satellites
        self.horizontal_dilution = horizontal_dilution

    def process_datagram(self, first_half_byte, data):
        self.amount_satellites = first_half_byte
        self.horizontal_dilution = data[0]

    def get_seatalk_datagram(self):
        first_byte = (self.amount_satellites << 4) | self.data_length
        return bytearray([self.seatalk_id, first_byte, self.horizontal_dilution])
