import datetime
import nmea_datagram


def test_parse_rmc():
    # Recommended Minimum Sentence
    nmea_str = "$GPRMC,144858.193500,A,5235.3151,N,00207.6577,W,0.0,144.8,160610,3.6,W,A*32\r\n"
    nmea_dg = nmea_datagram.RecommendedMinimumSentence()
    nmea_dg.parse_nmea_sentence(nmea_str)

    actual = nmea_dg.get_nmea_sentence()
    assert nmea_str == actual

