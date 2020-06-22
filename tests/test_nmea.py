import pytest
import datetime
import nmea_datagram
import helper


@pytest.mark.parametrize(("nmea_str", "expected_type", "value_name", "expected_value"), (
        ("$INMTW,17.9,C*1B\r\n",                                                            nmea_datagram.WaterTemperature,           "temperature_c", 17.9),
        ("$SDDBT,7.8,f,2.4,M,1.3,F*0D\r\n",                                                 nmea_datagram.DepthBelowKeel,             "depth_m", 2.4),
        ("$GPRMC,225446,A,4916.45,N,12311.12,W,000.5,054.7,191194,020.3,E*68\r\n",          nmea_datagram.RecommendedMinimumSentence, "magnetic_variation", 20.3),
        ("$GPRMC,144858.193500,A,5235.3151,N,00207.6577,W,0.0,144.8,160610,3.6,W,A*32\r\n", nmea_datagram.RecommendedMinimumSentence, "magnetic_variation", 3.6),
        ("$WIMWV,281,R,7.2,N,A*33\r\n",                                                     nmea_datagram.WindSpeedAndAngle,          "speed_knots", 7.2),
        ("$IIVHW,245.1,T,245.1,M,23.01,N,000.01,K*64\r\n",                                  nmea_datagram.SpeedThroughWater,          "speed_knots", 23.01)
))
def test_parse_rmc(nmea_str, expected_type, value_name, expected_value):
    nmea_instance = nmea_datagram.NMEADatagram.parse_nmea_sentence(nmea_str)

    assert type(nmea_instance) == expected_type
    assert getattr(nmea_instance, value_name) == expected_value


@pytest.mark.parametrize(("nmea_instance", "expected_string"), (
                         (nmea_datagram.WaterTemperature(temperature_c=17.9, talker_id="IN"),                                   "$INMTW,17.90,C*2B\r\n"),

                         (nmea_datagram.DepthBelowKeel(depth_m=18.223, talker_id="SD"),                                         "$SDDBT,59.79,f,18.22,M,9.96,F*3B\r\n"),

                         (nmea_datagram.RecommendedMinimumSentence(date=datetime.datetime(year=2020, month=12, day=8,
                                                                                          hour=16, minute=7, second=55, microsecond=590),
                                                                   valid_status=nmea_datagram.NMEAValidity.Valid,
                                                                   position=helper.Position(
                                                                       latitude=helper.PartPosition(degrees=123, minutes=23.1, direction=helper.Orientation.North),
                                                                       longitude=helper.PartPosition(degrees=60, minutes=2.90, direction=helper.Orientation.West)),
                                                                   speed_over_ground_knots=19.3,
                                                                   track_made_good=12.9,
                                                                   magnetic_variation=1.2,
                                                                   variation_sense=helper.Orientation.East,
                                                                   mode="D", talker_id="GP"),                                   "$GPRMC,160755.000590,A,12323.1,N,602.9,W,19.30,12.90,081220,1.20,E,D*28\r\n"),

                         (nmea_datagram.WindSpeedAndAngle(angle=39.2, reference_true=True, speed_knots=29.93,
                                                          validity=nmea_datagram.NMEAValidity.Invalid, talker_id="WI"),         "$WIMWV,39.20,T,29.93,N,V*3B\r\n"),

                         (nmea_datagram.SpeedThroughWater(speed_knots=10.1, heading_degrees_true=29.01,
                                                          heading_degrees_magnetic=31.09, talker_id="II"),                      "$IIVHW,29.01,T,31.09,M,10.10,N,18.71,K*5B\r\n")
                         ))
def test_nmea_sentence_creation(nmea_instance, expected_string):
    nmea_sentence = nmea_instance.get_nmea_sentence()
    assert expected_string == nmea_sentence


def test_message_without_data():
    depth = nmea_datagram.DepthBelowKeel()
    nmea_sentence = depth.get_nmea_sentence()
    a = nmea_datagram.NMEADatagram.parse_nmea_sentence(nmea_sentence)
