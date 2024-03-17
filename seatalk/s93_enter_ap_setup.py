from seatalk.seatalk_datagram import _ZeroContentClass


class EnterAPSetup(_ZeroContentClass):
    """
    93  00  00      Enter AP-Setup: Sent by course computer before
                    finally entering the dealer setup. It is repeated
                    once per second, and times out after ten seconds.
                    While this is being sent, command 86 X1 68 97 is
                    needed for final entry into Setup. (600R generates
                    this when –1 & +1 are pressed simultaneously in this
                    mode).
    """
    seatalk_id = 0x93
    data_length = 0
