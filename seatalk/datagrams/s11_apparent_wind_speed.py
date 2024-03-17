from common.helper import UnitConverter, byte_to_str
from seatalk.datagrams.seatalk_datagram import SeatalkDatagram
from seatalk.seatalk_exceptions import DataValidationException


class ApparentWindSpeed(SeatalkDatagram):  # TODO nmea mwv with ApparentWindAngle
    """
    11  01  XX  0Y  Apparent Wind Speed: (XX & 0x7F) + Y/10 Knots
                Units flag: XX&0x80=0    => Display value in Knots
                            XX&0x80=0x80 => Display value in Meter/Second
                Corresponding NMEA sentence: MWV
    """
    seatalk_id = 0x11
    data_length = 1

    def __init__(self, speed_knots=None):
        SeatalkDatagram.__init__(self)
        self.speed_knots = speed_knots

    def process_datagram(self, first_half_byte, data):
        if data[1] & 0xF0:  # 0Y <- the 0 is important
            raise DataValidationException(f"{type(self).__name__}: Byte 1 is bigger than 0x0F {byte_to_str(data[1])}")

        speed = (data[0] & 0x7F) + data[1] / 10

        if data[0] & 0x80:  # Meter/Second
            self.speed_knots = UnitConverter.meter_to_nm(speed * 60 * 60)
        else:  # Knots
            self.speed_knots = speed

    def get_seatalk_datagram(self):
        x_byte = int(self.speed_knots)
        y_byte = int((round(self.speed_knots, 1) - x_byte) * 10)
        return bytearray([self.seatalk_id, self.data_length, x_byte, y_byte])
