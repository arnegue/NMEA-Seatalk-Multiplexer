from seatalk.seatalk_datagram import SeatalkDatagram
from seatalk.seatalk_exceptions import DataValidationException


class TargetWaypointName(SeatalkDatagram):
    """
    82  05  XX  xx YY yy ZZ zz   Target waypoint name
                 XX+xx = YY+yy = ZZ+zz = FF (allows error detection)
                 Takes the last 4 chars of name, assumes upper case only
                 Char= ASCII-Char - 0x30
                 XX&0x3F: char1
                 (YY&0xF)*4+(XX&0xC0)/64: char2
                 (ZZ&0x3)*16+(YY&0xF0)/16: char3
                 (ZZ&0xFC)/4: char4
                 Corresponding NMEA sentences: RMB, APB, BWR, BWC
    """
    seatalk_id = 0x82
    data_length = 5

    def __init__(self, name: str=None):
        SeatalkDatagram.__init__(self)
        self.name = name

    def process_datagram(self, first_half_byte, data):
        X_byte_index = 0
        x_byte_index = 1
        Y_byte_index = 2
        y_byte_index = 3
        Z_byte_index = 4
        z_byte_index = 5

        if data[X_byte_index] + data[x_byte_index] == data[Y_byte_index] + data[y_byte_index] == data[Z_byte_index] + data[z_byte_index] != 0xFF:
            raise DataValidationException("Received datagrams checksum doesn't match")
        char1 = 0x30 + (data[X_byte_index] & 0x3F)
        char2 = 0x30 + (((data[Y_byte_index] & 0xF) << 2) | ((data[X_byte_index] & 0xC0) >> 6))
        char3 = 0x30 + (((data[Z_byte_index] & 0x3) << 4) | ((data[Y_byte_index] & 0xF0) >> 4))
        char4 = 0x30 + ((data[Z_byte_index] & 0xFC) >> 2)
        name = ""
        for char in (char1, char2, char3, char4):
            name += chr(char)
        self.name = name
        # if name == "0999":
        #     pass  # MOB

    def get_seatalk_datagram(self):
        char_1 = ord(self.name[0]) - 0x30
        char_2 = ord(self.name[1]) - 0x30
        char_3 = ord(self.name[2]) - 0x30
        char_4 = ord(self.name[3]) - 0x30

        X_byte = (char_1 & 0x3f) | ((char_2 & 0x3) << 6)
        x_byte = 0xFF - X_byte
        Y_byte = (char_2 >> 2) | ((char_3 & 0xf) << 4)
        y_byte = 0xFF - Y_byte
        Z_Byte = ((char_3 & 0x3c) >> 4) | (char_4 << 2)
        z_byte = 0xFF - Z_Byte
        return bytearray([self.seatalk_id, self.data_length, X_byte, x_byte, Y_byte, y_byte, Z_Byte, z_byte])
