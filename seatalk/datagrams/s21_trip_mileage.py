from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class TripMileage(SeatalkDatagram):
    """
    21  02  XX  XX  0X  Trip Mileage: XXXXX/100 nautical miles
    """
    seatalk_id = 0x21
    data_length = 2

    def __init__(self, mileage_miles=None):
        super().__init__()
        self.mileage_miles = mileage_miles

    def process_datagram(self, first_half_byte, data):
        value = (data[2] & 0x0F) << 16 | data[1] << 8 | data[0]
        self.mileage_miles = value / 100

    def get_seatalk_datagram(self):
        data = int(self.mileage_miles * 100).to_bytes(3, "little")
        return bytearray([self.seatalk_id, self.data_length]) + data
