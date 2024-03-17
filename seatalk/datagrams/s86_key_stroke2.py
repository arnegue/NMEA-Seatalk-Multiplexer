from seatalk.datagrams.seatalk_datagram import _KeyStroke


class KeyStroke2(_KeyStroke):
    """
    86  X1  YY  yy  Keystroke
    """
    seatalk_id = 0x86
    data_length = 1
