from seatalk.datagrams.seatalk_datagram import _SetLampIntensityDatagram


class SetLampIntensity2(_SetLampIntensityDatagram):
    """
    80  00  0X      Set Lamp Intensity: X=0 off, X=4:  1, X=8:  2, X=C: 3
    """
    seatalk_id = 0x80
    data_length = 0
