import enum

from common.helper import TwoWayDict
from seatalk.datagrams.seatalk_datagram import _TwoWayDictDatagram


class EquipmentID2(_TwoWayDictDatagram):
    """
     6C  05  XX XX XX XX XX XX Second equipment-ID datagram (follows 01...), reported examples:
             04 BA 20 28 2D 2D ST60 Tridata
             05 70 99 10 28 2D ST60 Log
             F3 18 00 26 2D 2D ST80 Masterview
    """
    seatalk_id = 0x6C
    data_length = 5

    class Equipments(enum.IntEnum):
        ST60_Tridata = enum.auto()
        ST60_Tridata_Plus = enum.auto()
        ST60_Log = enum.auto()
        ST80_Masterview = enum.auto()

    def __init__(self, equipment_id: Equipments=None):
        equipment_map = TwoWayDict({
            bytes([0x04, 0xBA, 0x20, 0x28, 0x2D, 0x2D]): self.Equipments.ST60_Tridata,
            bytes([0x87, 0x72, 0x25, 0x28, 0x2D, 0x2D]): self.Equipments.ST60_Tridata_Plus,
            bytes([0x05, 0x70, 0x99, 0x10, 0x28, 0x2D]): self.Equipments.ST60_Log,
            bytes([0xF3, 0x18, 0x00, 0x26, 0x2D, 0x2D]): self.Equipments.ST80_Masterview,
        })
        super().__init__(map=equipment_map, set_key=equipment_id)
