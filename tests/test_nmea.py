import pytest
from nmea.nmea_datagram import *
from common.helper import Orientation


@pytest.mark.parametrize(("nmea_str", "expected_type", "value_name", "expected_value"), (
        ("$INMTW,17.9,C*1B\r\n",                                                            WaterTemperature,           "temperature_c", 17.9),
        ("$SDDBT,7.8,f,2.4,M,1.3,F*0D\r\n",                                                 DepthBelowKeel,             "depth_m", 2.4),
        ("$GPRMC,225446,A,4916.45,N,12311.12,W,000.5,054.7,191194,020.3,E*68\r\n",          RecommendedMinimumSentence, "magnetic_variation", 20.3),
        ("$GPVTG,,T,,M,0.431,N,0.798,K,A*23\r\n",                                           TrackMadeGoodGroundSpeed,   "speed_over_ground_knots", 0.431),
        ("$GPGSA,A,3,10,26,27,16,20,18,08,21,,,,,2.15,1.36,1.67*07\r\n",                    GPSDOPActiveSatellites,     "mode_1", GPSModes.Automatic),
        ("$GPGSA,A,3,10,26,27,16,20,18,08,21,,,,,2.15,1.36,1.67*07\r\n",                    GPSDOPActiveSatellites,     "list_satellite_ids", ["10", "26", "27", "16", "20", "18", "08", "21", "", "", "", ""]),
        ("$WIMWV,281,R,7.2,N,A*33\r\n",                                                     WindSpeedAndAngle,          "speed_knots", 7.2),
        ("$IIVHW,245.1,T,245.1,M,23.01,N,000.01,K*64\r\n",                                  SpeedThroughWater,          "speed_knots", 23.01)
))
def test_parse_rmc(nmea_str, expected_type, value_name, expected_value):
    nmea_datagram_instance = NMEADatagram.parse_nmea_sentence(nmea_str)
    nmea_datagram_instance.get_nmea_sentence()

    assert type(nmea_datagram_instance) == expected_type
    assert getattr(nmea_datagram_instance, value_name) == expected_value


@pytest.mark.parametrize(("nmea_instance", "expected_string"), (
                         (WaterTemperature(temperature_c=17.9, talker_id="IN"),                         "$INMTW,17.90,C*2B\r\n"),

                         (DepthBelowKeel(depth_m=18.223, talker_id="SD"),                               "$SDDBT,59.79,f,18.22,M,9.96,F*3B\r\n"),

                         (RecommendedMinimumSentence(date=datetime.datetime(year=2020, month=12, day=8,
                                                                            hour=16, minute=7, second=55, microsecond=590),
                                                     valid_status=NMEAValidity.Valid,
                                                     position=Position(
                                                         latitude=PartPosition(degrees=123, minutes=23.1, direction=Orientation.North),
                                                         longitude=PartPosition(degrees=60, minutes=2.90, direction=Orientation.West)),
                                                     speed_over_ground_knots=19.3,
                                                     track_made_good=12.9,
                                                     magnetic_variation=1.2,
                                                     variation_sense=Orientation.East,
                                                     mode=FAAModeIndicator.Differential,
                                                     talker_id="GP"),                                   "$GPRMC,160755.000590,A,12323.1,N,602.9,W,19.30,12.90,081220,1.20,E,D*28\r\n"),

                         (GPSDOPActiveSatellites(mode_1=GPSModes.Automatic, mode_2=GPSFixType.ThreeD,
                                                 list_satellite_ids=["10", "26", "27", "16", "20", "07", "08", "21", "11", "", "", "", ""],
                                                 pdop=1.87, hdop=1.14, vdop=1.48, talker_id="GP"),      "$GPGSA,A,3,10,26,27,16,20,07,08,21,11,,,,,1.87,1.14,1.48*20\r\n"),

                         (WindSpeedAndAngle(angle_degree=39.2, reference_true=True, speed_knots=29.93,
                                            validity=NMEAValidity.Invalid, talker_id="WI"),             "$WIMWV,39.20,T,29.93,N,V*3B\r\n"),

                         (TrackMadeGoodGroundSpeed(course_over_ground_degree_true=None,
                                                   course_over_ground_degree_magnetic=None,
                                                   speed_over_ground_knots=0.15, mode=GPSModes.Automatic,
                                                   talker_id="GP"),                                     "$GPVTG,,T,,M,0.15,N,0.28,K,A*2D\r\n"),

                         (SpeedThroughWater(speed_knots=10.1, heading_degrees_true=29.01,
                                            heading_degrees_magnetic=31.09, talker_id="II"),            "$IIVHW,29.01,T,31.09,M,10.10,N,18.71,K*5B\r\n")
                         ))
def test_nmea_sentence_creation(nmea_instance, expected_string):
    nmea_sentence = nmea_instance.get_nmea_sentence()
    assert nmea_sentence == expected_string


def test_message_without_data():
    depth = DepthBelowKeel()
    nmea_sentence = depth.get_nmea_sentence()
    NMEADatagram.parse_nmea_sentence(nmea_sentence)
