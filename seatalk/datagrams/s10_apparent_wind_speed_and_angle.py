from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


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
        value = data[0] << 8 | data[1]  # For whatever reason these bytes are handled as the usual get_value
        self.angle_degree = value / 2

    def get_seatalk_datagram(self):
        value = self.angle_degree * 2
        data = bytes([int(value) >> 8, (int(value) & 0xFF)])
        return bytearray([self.seatalk_id, self.data_length]) + data
