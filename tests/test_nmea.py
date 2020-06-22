import pytest
import datetime
import nmea_datagram


@pytest.mark.parametrize(("nmea_str", "expected_type", "value_name", "expected_value"), (
        ("$INMTW,17.9,C*1B\r\n",                                                            nmea_datagram.WaterTemperature,           "temperature_c", 17.9),
        ("$SDDBT,7.8,f,2.4,M,1.3,F*0D\r\n",                                                 nmea_datagram.DepthBelowKeel,             "depth_m", 2.4),
        ("$GPRMC,144858.193500,A,5235.3151,N,00207.6577,W,0.0,144.8,160610,3.6,W,A*32\r\n", nmea_datagram.RecommendedMinimumSentence, "magnetic_variation", 3.6),
        ("$WIMWV,281,R,7.2,N,A*33\r\n",                                                     nmea_datagram.WindSpeedAndAngle,          "speed_knots", 7.2),
        ("$IIVHW,245.1,T,245.1,M,23.01,N,000.01,K*64\r\n",                                  nmea_datagram.SpeedThroughWater,          "speed_knots", 23.01)
))
def test_parse_rmc(nmea_str, expected_type, value_name, expected_value):
    nmea_instance = nmea_datagram.NMEADatagram.parse_nmea_sentence(nmea_str)

    assert type(nmea_instance) == expected_type
    assert getattr(nmea_instance, value_name) == expected_value


