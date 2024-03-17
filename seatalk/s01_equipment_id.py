import enum

from common.helper import TwoWayDict
from seatalk.seatalk_datagram import _TwoWayDictDatagram


class EquipmentID1(_TwoWayDictDatagram):
    """
    01  05  XX XX XX XX XX XX  Equipment ID, sent at power on, reported examples:
    01  05  00 00 00 60 01 00  Course Computer 400G
    01  05  04 BA 20 28 01 00  ST60 Tridata
    01  05  70 99 10 28 01 00  ST60 Log
    01  05  F3 18 00 26 0F 06  ST80 Masterview
    01  05  FA 03 00 30 07 03  ST80 Maxi Display
    01  05  FF FF FF D0 00 00  Smart Controller Remote Control Handset
    """
    seatalk_id = 0x01
    data_length = 5

    class Equipments(enum.IntEnum):
        Course_Computer_400G = enum.auto()
        ST60_Tridata = enum.auto()
        ST60_Tridata_Plus = enum.auto()
        ST60_Log = enum.auto()
        ST80_Masterview = enum.auto()
        ST80_Maxi_Display = enum.auto()
        Smart_Controller_Remote_Control_Handset = enum.auto()

    def __init__(self, set_key: Equipments = None):
        equipment_map = TwoWayDict({
            bytes([0x00, 0x00, 0x00, 0x60, 0x01, 0x00]): self.Equipments.Course_Computer_400G,
            bytes([0x04, 0xBA, 0x20, 0x28, 0x01, 0x00]): self.Equipments.ST60_Tridata,
            bytes([0x87, 0x72, 0x25, 0x28, 0x01, 0x00]): self.Equipments.ST60_Tridata_Plus,
            bytes([0x70, 0x99, 0x10, 0x28, 0x01, 0x00]): self.Equipments.ST60_Log,
            bytes([0xF3, 0x18, 0x00, 0x26, 0x0F, 0x06]): self.Equipments.ST80_Masterview,
            bytes([0xFA, 0x03, 0x00, 0x30, 0x07, 0x03]): self.Equipments.ST80_Maxi_Display,
            bytes([0xFF, 0xFF, 0xFF, 0xD0, 0x00, 0x00]): self.Equipments.Smart_Controller_Remote_Control_Handset,
        })
        _TwoWayDictDatagram.__init__(self, map=equipment_map, set_key=set_key)
