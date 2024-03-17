from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class TotalTripLog(SeatalkDatagram):
    """
    25  Z4  XX  YY  UU  VV AW  Total & Trip Log
                     total= (XX+YY*256+Z* 4096)/ 10 [max=104857.5] nautical miles
                     trip = (UU+VV*256+W*65536)/100 [max=10485.75] nautical miles


    https://github.com/mariokonrad/marnav/blob/master/src/marnav/seatalk/message_25.cpp

    total= (XX+YY*256+Z*65536)/ 10 [max=104857.5] nautical miles
    (the factor for Z in the description from Thomas Knauf is wrong)

    (Shifting and other logical operations are faster than division and additions. Maybe some compilers would see that, but this looks way more straight forward and prettier ;-) )
    """
    seatalk_id = 0x25
    data_length = 4

    def __init__(self, total_miles=None, trip_miles=None):
        SeatalkDatagram.__init__(self)
        self.total_miles = total_miles
        self.trip_miles = trip_miles

    def process_datagram(self, first_half_byte, data):
        # * 256   <=> <<  8
        # * 4096  <=> << 12
        # * 65536 <=> << 16
        total_nibble = first_half_byte
        trip_nibble = data[4] & 0x0F  # What is the "A" for?

        #                       Z                   YY             XX
        self.total_miles = (total_nibble << 16 | data[1] << 8 | data[0]) / 10

        #                       W               VV              UU
        self.trip_miles = (trip_nibble << 16 | data[3] << 8 | data[2]) / 100

    def get_seatalk_datagram(self):
        raw_total = int(self.total_miles * 10)
        z = raw_total >> 16
        xx = raw_total & 0x0000FF
        yy = (raw_total >> 8) & 0x0000FF

        raw_trip = int(self.trip_miles * 100)
        aw = raw_trip >> 16
        uu = raw_trip & 0x0000FF
        vv = (raw_trip >> 8) & 0x0000FF

        first_byte = (z << 4) | self.data_length
        return bytearray([self.seatalk_id, first_byte, xx, yy, uu, vv, aw])
