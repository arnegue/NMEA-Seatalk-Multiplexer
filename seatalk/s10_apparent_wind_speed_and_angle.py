from seatalk.seatalk_datagram import SeatalkDatagram


class ApparentWindAngle(SeatalkDatagram):  # TODO nmea mwv with ApparentWindSpeed
    """
    10  01  XX  YY  Apparent Wind Angle: XXYY/2 degrees right of bow
                Used for autopilots Vane Mode (WindTrim)
                Corresponding NMEA sentence: MWV
    """
    seatalk_id = 0x10
    data_length = 1

    def __init__(self, angle_degree=None):
        SeatalkDatagram.__init__(self)
        self.angle_degree = angle_degree

    def process_datagram(self, first_half_byte, data):
        self.angle_degree = self.get_value(data) / 2  # TODO maybe some validation for <0° or >360° ?

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length]) + self.set_value(int(self.angle_degree * 2))
