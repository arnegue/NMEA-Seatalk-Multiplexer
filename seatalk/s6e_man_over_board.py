from seatalk.seatalk_datagram import SeatalkDatagram


class ManOverBoard(SeatalkDatagram):
    """
    6E  07  00  00 00 00 00 00 00 00 MOB (Man Over Board), (ST80), preceded
                 by a Waypoint 999 command: 82 A5 40 BF 92 6D 24 DB
    I noticed on Raymarine RN300 (not sure about the byte meaning though):
    6E  47  0F  E7 59 00 00 0F A7 70
    """
    seatalk_id = 0x6E
    data_length = 7

    def process_datagram(self, first_half_byte, data):
        pass  # Nothing to do here

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length, 0, 0, 0, 0, 0, 0, 0, 0])
