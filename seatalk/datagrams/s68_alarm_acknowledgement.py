import enum

from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class AlarmAcknowledgement(SeatalkDatagram):
    """
    68  X1 01 00   Alarm acknowledgment keystroke (from ST80 Masterview)
    68  X1 03 00   Alarm acknowledgment keystroke (from ST80 Masterview)   TODO 2 ST80 Masterview?
    68  41 15 00   Alarm acknowledgment keystroke (from ST40 Wind Instrument)   TODO X=4 -> ST40? maybe data[0] = 0x15 -> ST40
                  X: 1=Shallow Shallow Water Alarm, 2=Deep Water Alarm, 3=Anchor Alarm
                     4=True Wind High Alarm, 5=True Wind Low Alarm, 6=True Wind Angle high
                     7=True Wind Angle low, 8=Apparent Wind high Alarm, 9=Apparent Wind low Alarm
                     A=Apparent Wind Angle high, B=Apparent Wind Angle low
    """
    seatalk_id = 0x68
    data_length = 1

    class AcknowledgementAlarms(enum.IntEnum):
        ShallowWaterAlarm = 0x01
        DeepWaterAlarm = 0x02
        AnchorAlarm = 0x03
        TrueWindHighAlarm = 0x04
        TrueWindLowAlarm = 0x05
        TrueWindAngleHigh = 0x06
        TrueWindAngleLow = 0x07
        ApparentWindHighAlarm = 0x08
        ApparentWindLowAlarm = 0x09
        ApparentWindAngleHigh = 0x0A
        ApparentWindAngleLow = 0x0B

    def __init__(self, acknowledged_alarm: AcknowledgementAlarms=None):
        SeatalkDatagram.__init__(self)
        self.acknowledged_alarm = acknowledged_alarm

    def process_datagram(self, first_half_byte, data):
        self.acknowledged_alarm = self.AcknowledgementAlarms(first_half_byte)  # TODO enum exception

    def get_seatalk_datagram(self):
        first_half_byte = self.acknowledged_alarm.value << 4   # TODO enum exception
        acknowledging_device = bytearray([0x01, 0x00])  # TODO see description of class
        return bytearray([self.seatalk_id, first_half_byte | self.data_length]) + acknowledging_device
