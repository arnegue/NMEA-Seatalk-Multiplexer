import datetime

from seatalk.seatalk_datagram import SeatalkDatagram


class Date(SeatalkDatagram):  # TODO RMC?
    """
    56  M1  DD  YY  Date: YY year, M month, DD day in month
                    Corresponding NMEA sentence: RMC
    """
    seatalk_id = 0x56
    data_length = 1

    def __init__(self, date=None):
        SeatalkDatagram.__init__(self)
        self.date = date
        self._year_offset = 2000  # TODO correct?

    def process_datagram(self, first_half_byte, data):
        month = first_half_byte
        day = data[0]
        year = self._year_offset + data[1]
        self.date = datetime.date(year=year, month=month, day=day)

    def get_seatalk_datagram(self):
        if self.date is None:
            pass  # TODO Exception
        first_byte = (self.date.month << 4) | self.data_length
        return bytearray([self.seatalk_id, first_byte, self.date.day, self.date.year - self._year_offset])
