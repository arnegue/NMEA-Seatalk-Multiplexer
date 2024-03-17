from seatalk.seatalk_datagram import _SetLampIntensityDatagram


class SetLampIntensity1(_SetLampIntensityDatagram):
    """
    30  00  0X      Set lamp Intensity; X=0: L0, X=4: L1, X=8: L2, X=C: L3
                    (only sent once when setting the lamp intensity)
    """
    seatalk_id = 0x30
    data_length = 0
