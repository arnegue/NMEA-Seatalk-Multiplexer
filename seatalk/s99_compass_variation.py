from seatalk.seatalk_datagram import SeatalkDatagram


class CompassVariation(SeatalkDatagram):
    """
    99  00  XX       Compass variation sent by ST40 compass instrument
                     or ST1000, ST2000, ST4000+, E-80 every 10 seconds
                     but only if the variation is set on the instrument
                     Positive XX values: Variation West, Negative XX values: Variation East
                     Examples (XX => variation): 00 => 0, 01 => -1 west, 02 => -2 west ...
                                                 FF => +1 east, FE => +2 east ...
                     Corresponding NMEA sentences: RMC, HDG
    """
    seatalk_id = 0x99
    data_length = 0

    def __init__(self, variation=None):
        SeatalkDatagram.__init__(self)
        self.variation = variation

    def process_datagram(self, first_half_byte, data):
        self.variation = int.from_bytes(bytes([data[0]]), byteorder="big", signed=True)  # TODO unsure if variation *-1

    def get_seatalk_datagram(self):
        my_bytes = int.to_bytes(self.variation, byteorder="big", signed=True, length=1)
        return bytearray([self.seatalk_id, self.data_length]) + bytearray(my_bytes)
