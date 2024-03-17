import enum

from common.helper import TwoWayDict
from seatalk.datagrams.seatalk_datagram import _TwoWayDictDatagram


class DisplayUnitsMileageSpeed(_TwoWayDictDatagram):
    """
    24  02  00  00  XX  Display units for Mileage & Speed
                    XX: 00=nm/knots, 06=sm/mph, 86=km/kmh
    """
    seatalk_id = 0x24
    data_length = 2

    class Unit(enum.IntEnum):
        Knots = enum.auto()
        Mph = enum.auto()
        Kph = enum.auto()

    def __init__(self, unit: Unit = None):
        unit_map = TwoWayDict({
            bytes([0x00, 0x00, 0x00]): self.Unit.Knots,
            bytes([0x00, 0x00, 0x06]): self.Unit.Mph,
            bytes([0x00, 0x00, 0x86]): self.Unit.Kph,
        })
        _TwoWayDictDatagram.__init__(self, map=unit_map, set_key=unit)
