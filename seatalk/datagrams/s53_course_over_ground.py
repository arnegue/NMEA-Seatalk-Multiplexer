from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class CourseOverGround(SeatalkDatagram):
    """
    53  U0  VW      Course over Ground (COG) in degrees:
                 The two lower  bits of  U * 90 +
                    the six lower  bits of VW *  2 +
                    the two higher bits of  U /  2 =
                    (U & 0x3) * 90 + (VW & 0x3F) * 2 + (U & 0xC) / 8
                 The Magnetic Course may be offset by the Compass Variation (see datagram 99) to get the Course Over Ground (COG).
    """
    seatalk_id = 0x53
    data_length = 0

    def __init__(self, course_degrees=None):
        super().__init__()
        self.course_degrees = course_degrees

    def process_datagram(self, first_half_byte, data):
        val_1 = (first_half_byte & 0b0011) * 90
        val_2 = (data[0] & 0b00111111) / 8
        val_3 = (first_half_byte & 0b1100)
        self.course_degrees = val_1 + val_2 + val_3

    def get_seatalk_datagram(self):
        u_0 = int(self.course_degrees / 90) & 0b0011
        u_1 = int((self.course_degrees % 2) * 8) & 0b1100
        data_0 = int((self.course_degrees % 90) / 2) & 0b00111111

        return bytearray([self.seatalk_id, ((u_0 | u_1) << 4) | self.data_length, data_0])
