from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class TotalMileage(SeatalkDatagram):
    """
    22  02  XX  XX  00  Total Mileage: XXXX/10 nautical miles
    """
    seatalk_id = 0x22
    data_length = 2

    def __init__(self, mileage_miles=None):
        super().__init__()
        self.mileage_miles = mileage_miles

    def process_datagram(self, first_half_byte, data):
        self.mileage_miles = self.get_value(data[:2]) / 10

    def get_seatalk_datagram(self):
        return bytearray([self.seatalk_id, self.data_length]) + self.set_value(self.mileage_miles * 10) + bytearray([0x00])
