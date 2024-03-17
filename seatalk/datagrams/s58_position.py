from common import helper
from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class Position(SeatalkDatagram):
    """
    58  Z5  LA XX YY LO QQ RR   LAT/LON
                 LA Degrees LAT, LO Degrees LON
                 minutes LAT = (XX*256+YY) / 1000
                 minutes LON = (QQ*256+RR) / 1000
                 Z&1: South (Z&1 = 0: North)
                 Z&2: East  (Z&2 = 0: West)
                 Raw unfiltered position, for filtered data use commands 50&51
                 Corresponding NMEA sentences: RMC, GAA, GLL
    """
    seatalk_id = 0x58
    data_length = 5

    def __init__(self, position: helper.Position = None):
        SeatalkDatagram.__init__(self)
        self.position = position

    def process_datagram(self, first_half_byte, data):
        lat_orientation = helper.Orientation.South if first_half_byte & 1 else helper.Orientation.North
        lat_degree = data[0]
        lat_min = (data[1] << 8 | data[2]) / 1000
        latitude = helper.PartPosition(degrees=lat_degree, minutes=lat_min, direction=lat_orientation)

        lon_orientation = helper.Orientation.East if first_half_byte & 2 else helper.Orientation.West
        lon_degree = data[3]
        lon_min = (data[4] << 8 | data[5]) / 1000
        longitude = helper.PartPosition(degrees=lon_degree, minutes=lon_min, direction=lon_orientation)
        self.position = helper.Position(latitude=latitude, longitude=longitude)

    def get_seatalk_datagram(self):
        first_half_byte = 0x00
        if self.position.latitude.direction == helper.Orientation.South:
            first_half_byte |= 1

        if self.position.longitude.direction == helper.Orientation.East:
            first_half_byte |= 2

        la = self.position.latitude.degrees
        la_raw_min = int(self.position.latitude.minutes * 1000)
        xx = (la_raw_min & 0xFF00) >> 8
        yy = la_raw_min & 0x00FF

        lo = self.position.longitude.degrees
        lo_raw_min = int(self.position.longitude.minutes * 1000)
        qq = (lo_raw_min & 0xFF00) >> 8
        rr = lo_raw_min & 0x00FF

        return bytearray([self.seatalk_id, first_half_byte << 4 | self.data_length, la, xx, yy, lo, qq, rr])
