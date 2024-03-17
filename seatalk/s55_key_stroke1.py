from seatalk.seatalk_datagram import _KeyStroke


class KeyStroke1(_KeyStroke):
    """
    55  X1  YY  yy  TRACK keystroke on GPS unit
    """
    seatalk_id = 0x55
    data_length = 1
