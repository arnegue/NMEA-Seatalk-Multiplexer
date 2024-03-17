import enum

from common.helper import TwoWayDict
from seatalk.seatalk_datagram import _TwoWayDictDatagram


class DeviceIdentification1(_TwoWayDictDatagram):
    """
    90  00  XX    Device Identification
                  XX=02  sent by ST600R ~every 2 secs
                  XX=05  sent by type 150, 150G and 400G course computer
                  XX=A3  sent by NMEA <-> SeaTalk bridge ~every 10 secs
    """
    seatalk_id = 0x90
    data_length = 0

    class DeviceID(enum.IntEnum):
        ST600R = enum.auto()
        Type_150_150G_400G = enum.auto()
        NMEASeatalkBridge = enum.auto()

    def __init__(self, device_id: DeviceID=None):
        device_id_map = TwoWayDict({
            bytes([0x02]): self.DeviceID.ST600R,
            bytes([0x05]): self.DeviceID.Type_150_150G_400G,
            bytes([0xA3]): self.DeviceID.NMEASeatalkBridge
        })
        _TwoWayDictDatagram.__init__(self, map=device_id_map, set_key=device_id)
