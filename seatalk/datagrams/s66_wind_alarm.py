import enum

from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class WindAlarm(SeatalkDatagram):
    """
    66  00  XY     Wind alarm as indicated by flags in XY:
                   X&8 = 8: Apparent Wind angle low
                   X&4 = 4: Apparent Wind angle high
                   X&2 = 2: Apparent Wind speed low
                   X&1 = 1: Apparent Wind speed high
                   Y&8 = 8: True Wind angle low
                   Y&4 = 4: True Wind angle high
                   Y&2 = 2: True Wind speed low
                   Y&1 = 1: True Wind speed high (causes Wind-High-Alarm on ST40 Wind Instrument)
                   XY  =00: End of wind alarm (only sent once)
    """
    seatalk_id = 0x66
    data_length = 0

    class Alarm(enum.IntEnum):
        AngleLow = 0x08
        AngleHigh = 0x04
        SpeedLow = 0x02
        SpeedHigh = 0x01
        NoAlarm = 0x00

    def __init__(self, apparent_alarm: Alarm=None, true_alarm: Alarm=None):
        SeatalkDatagram.__init__(self)
        self.apparent_alarm = apparent_alarm
        self.true_alarm = true_alarm

    def process_datagram(self, first_half_byte, data):
        x_nibble = (data[0] & 0xF0) >> 4
        y_nibble = (data[0] & 0x0F)
        self.apparent_alarm = self.Alarm(x_nibble)  # TODO enum exception
        self.true_alarm = self.Alarm(y_nibble)

    def get_seatalk_datagram(self):
        x_nibble = self.apparent_alarm.value << 4   # TODO enum exception
        y_nibble = self.true_alarm.value
        return bytearray([self.seatalk_id, self.data_length, (x_nibble | y_nibble)])
