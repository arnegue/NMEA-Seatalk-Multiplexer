from seatalk.datagrams.seatalk_datagram import SeatalkDatagram


class Depth(SeatalkDatagram):   # NMEA: dbt
    """
    00  02  YZ  XX XX  Depth below transducer: XXXX/10 feet
                   Flags in Y: Y&8 = 8: Anchor Alarm is active
                               Y&4 = 4: Metric display units or
                                          Fathom display units if followed by command 65
                               Y&2 = 2: Used, unknown meaning
                   Flags in Z: Z&4 = 4: Transducer defective
                               Z&2 = 2: Deep Alarm is active
                               Z&1 = 1: Shallow Depth Alarm is active
                   Corresponding NMEA sentences: DPT, DBT
    """
    seatalk_id = 0x00
    data_length = 2

    def __init__(self, depth_feet=None, anchor_alarm_active=None, metric_display_units=None, transducer_defective=None, depth_alarm_active=None, shallow_alarm_active=None):
        super().__init__()
        self.depth_feet = depth_feet
        self.anchor_alarm_active = anchor_alarm_active
        self.metric_display_units = metric_display_units
        self.transducer_defective = transducer_defective
        self.depth_alarm_active = depth_alarm_active
        self.shallow_alarm_active = shallow_alarm_active

    def process_datagram(self, first_half_byte, data):
        self.anchor_alarm_active =  (data[0] & 0x80) != 0
        self.metric_display_units = (data[0] & 0x40) != 0
        self.transducer_defective = (data[0] & 0x04) != 0
        self.depth_alarm_active =   (data[0] & 0x02) != 0
        self.shallow_alarm_active = (data[0] & 0x01) != 0

        self.depth_feet = self.get_value(data[1:]) / 10.0

    def get_seatalk_datagram(self):
        feet_value = self.depth_feet * 10
        flags = 0
        flags |= 0x80 if self.anchor_alarm_active  else 0x00
        flags |= 0x40 if self.metric_display_units else 0x00
        flags |= 0x04 if self.transducer_defective else 0x00
        flags |= 0x02 if self.depth_alarm_active   else 0x00
        flags |= 0x01 if self.shallow_alarm_active else 0x00

        return bytearray([self.seatalk_id, self.data_length, flags]) + self.set_value(feet_value)
