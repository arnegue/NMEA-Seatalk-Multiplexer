from common.helper import Orientation, PartPosition
from seatalk.seatalk_datagram import _SeatalkPartPosition


class LatitudePosition(_SeatalkPartPosition):
    """
    50  Z2  XX  YY  YY  LAT position: XX degrees, (YYYY & 0x7FFF)/100 minutes
                     MSB of Y = YYYY & 0x8000 = South if set, North if cleared
                     Z= 0xA or 0x0 (reported for Raystar 120 GPS), meaning unknown
                     Stable filtered position, for raw data use command 58
                     Corresponding NMEA sentences: RMC, GAA, GLL
    """
    seatalk_id = 0x50
    data_length = 2

    def __init__(self, position: PartPosition = None):
        super().__init__(position=position)

    def _get_orientation(self, value_set: bool) -> Orientation:
        return Orientation.South if value_set else Orientation.North

    def _get_value_orientation(self, orientation: Orientation) -> bool:
        return True if orientation == Orientation.South else False
