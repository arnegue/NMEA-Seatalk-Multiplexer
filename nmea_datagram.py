from abc import abstractmethod, ABCMeta
from functools import reduce
import operator
import datetime
import inspect
import sys

from helper import UnitConverter, Position, PartPosition, byte_to_str


class NMEAError(Exception):
    pass


class NMEAParseError(Exception):
    pass


class WrongFormatError(NMEAParseError):
    def __init__(self, sentence: str):
        super().__init__(f"Could not parse sentence. First (\"$\") or last characters (\"\\r\\n\") are wrong/missing: \"" + sentence + "\"")


class ChecksumError(NMEAParseError):
    def __init__(self, sentence, actual_checksum, expected_checksum):
        super().__init__(f"ChecksumError: {sentence} checksum {byte_to_str(actual_checksum)} does not match own calculated checksum: {byte_to_str(expected_checksum)}")


class NMEADatagram(object, metaclass=ABCMeta):
    nmea_tag_datagram_map = None

    def __init__(self, nmea_tag):
        self.nmea_tag = nmea_tag
        self._talker_id = "--"  # may be overridden

    @classmethod
    def create_map(cls):
        cls.nmea_tag_datagram_map = dict()
        for name, obj in inspect.getmembers(sys.modules[__name__]):
            if inspect.isclass(obj) and issubclass(obj, NMEADatagram) and not inspect.isabstract(obj):
                nmea_datagram = obj()
                cls.nmea_tag_datagram_map[nmea_datagram.nmea_tag] = obj

    @abstractmethod
    def _convert_to_nmea(self):
        pass

    @classmethod
    def parse_nmea_sentence(cls, nmea_string: str):
        if nmea_string[0] != '$' and nmea_string[-2:] != '\r\n':
            raise WrongFormatError(nmea_string)
        if not cls.nmea_tag_datagram_map:
            cls.create_map()

        cls.verify_checksum(nmea_string)

        nmea_tag = nmea_string[3:6]  # Get Tag
        nmea_class = cls.nmea_tag_datagram_map[nmea_tag]  # Extract class from tag
        nmea_datagram_instance = nmea_class()  # Create instance
        nmea_datagram_instance._talker_id = nmea_string[1:3]  # Set Talker ID

        nmea_datagram_instance._parse_nmea_sentence(nmea_string[7:-5].split(","))  # Now parse it, start after nmea-tag, stop at checksum
        return nmea_datagram_instance

    @abstractmethod
    def _parse_nmea_sentence(self, nmea_value_list: list):
        raise NotImplementedError()

    def get_nmea_sentence(self):
        prefix = f"{self._talker_id}{self.nmea_tag}"
        data = prefix + self._convert_to_nmea()
        checksum = self.checksum(data)
        return f"${data}*{checksum:02X}\r\n"

    @staticmethod
    def checksum(nmea_str):
        return reduce(operator.xor, map(ord, nmea_str), 0)

    @classmethod
    def verify_checksum(cls, nmea_str):
        try:
            nmea_str_checksum = int(nmea_str[-4:-2], 16)
            expected = cls.checksum(nmea_str[1:-5])  # Remove dollar, \r\n and checksum
        except ValueError as e:
            raise NMEAParseError(f"Could not parse {nmea_str}") from e

        if expected != nmea_str_checksum:
            raise ChecksumError(nmea_str, nmea_str_checksum, expected)

    @staticmethod
    def _get_value(value, unit):
        """
        Only fill in value if it is set
        """
        return f",{value:.1f},{unit}" if value is not None else f",,{unit}"

    @classmethod
    def _nmea_conversion(cls, *value_tuple):
        sentence = ""
        for value, unit in value_tuple:
            sentence += cls._get_value(value, unit)
        return sentence

    @classmethod
    def check_validity(cls, validity):
        return validity.upper() == "A"  # A = valid, V = invalid. Very intuitive...


class RecommendedMinimumSentence(NMEADatagram):
    def __init__(self, date=None, valid_status=None, position=None, speed_over_ground=None, track_made_good=None, magnetic_variation=None, variation_sense=None, mode=None):
        super().__init__("RMC")
        self.date = date
        self.valid_status = valid_status
        self.position = position
        self.speed_over_ground = speed_over_ground
        self.track_made_good = track_made_good
        self.magnetic_variation = magnetic_variation
        self.variation_sense = variation_sense
        self.mode = mode

        self._date_format_date = "%d%m%y"
        self._date_format_time = "%H%M%S.%f"  # TODO f = microseconds, not milliseconds?

    def _convert_to_nmea(self):
        """
        $GPRMC,hhmmss.ss,a,ddmm.mmmm,n,dddmm.mmmm,w,z.z,y.y,ddmmyy,d.d,v*CC<CR><LF>
        $GPRMC,144858,A,5235.3151,N,00207.6577,W,0.0,144.8,160610,3.6,W,A*12\r\n
        """
        return_string = ","
        string_date, string_time = self.date.strftime(self._date_format_date + "|" + self._date_format_time).split("|")  # Use | only to make it splittable
        return_string += string_time + ","
        return_string += ("A" if self.valid_status else "V") + ","
        return_string += f"{self.position.latitude.degrees:02}"  + str(self.position.latitude.minutes)  + "," + self.position.latitude.direction + ","
        return_string += f"{self.position.longitude.degrees:02}" + str(self.position.longitude.minutes) + "," + self.position.longitude.direction + ","
        return_string += str(self.speed_over_ground) + ","
        return_string += str(self.track_made_good) + ","
        return_string += string_date + ","
        return_string += str(self.magnetic_variation) + ","
        return_string += str(self.variation_sense) + ","
        return_string += self.mode
        return return_string

    def _parse_nmea_sentence(self, nmea_value_list: list):
        gps_time = nmea_value_list[0]
        if "." not in gps_time:  # Some dont send millseconds
            gps_time += ".0"
        gps_date = nmea_value_list[8]

        self.date = datetime.datetime.strptime(gps_date + gps_time, self._date_format_date + self._date_format_time)
        self.valid_status = self.check_validity(nmea_value_list[1])

        latitude_degrees = int(nmea_value_list[2][0:2])  # TODO one line?
        latitude_minutes = float(nmea_value_list[2][2:])  # Remove degrees
        latitude_direction = nmea_value_list[3]
        latitude = PartPosition(degrees=latitude_degrees, minutes=latitude_minutes, direction=latitude_direction)

        longitude_degrees = int(nmea_value_list[4][0:2])
        longitude_minutes = float(nmea_value_list[4][2:])  # Remove degrees
        longitude_direction = nmea_value_list[5]
        longitude = PartPosition(degrees=longitude_degrees, minutes=longitude_minutes, direction=longitude_direction)

        self.position = Position(latitude, longitude)

        self.speed_over_ground = float(nmea_value_list[6])
        self.track_made_good = float(nmea_value_list[7])
        self.magnetic_variation = float(nmea_value_list[9])
        self.variation_sense = nmea_value_list[10]
        self.mode = nmea_value_list[11]


class DepthBelowKeel(NMEADatagram):
    def __init__(self, depth_m=None):
        super().__init__(nmea_tag="DBT")
        self.depth_m = depth_m

    def _convert_to_nmea(self):
        """
        $--DBT,x.x,f,x.x,M,x.x,F*hh<CR><LF>
        $SDDBT,7.8,f,2.4,M,1.3,F*0D\r\n
        """
        feet = UnitConverter.meter_to_feet(self.depth_m)
        fathoms = UnitConverter.meter_to_fathom(self.depth_m)
        return self._nmea_conversion((feet, 'f'),
                                     (self.depth_m, 'M'),
                                     (fathoms, 'F'),)

    def _parse_nmea_sentence(self, nmea_value_list: list):
        if nmea_value_list[2]:
            self.depth_m = float(nmea_value_list[2])
        elif nmea_value_list[0]:
            self.depth_m = UnitConverter.feet_to_meter(float(nmea_value_list[0]))
        elif nmea_value_list[4]:
            self.depth_m = UnitConverter.fathom_to_meter(float(nmea_value_list[4]))
        else:
            pass  # TODO what now ? no value in values seems weird


class SpeedThroughWater(NMEADatagram):
    def __init__(self, speed_knots=None, heading_degrees_true=None, heading_degrees_magnetic=None):
        super().__init__(nmea_tag="VHW")
        self.speed_knots = speed_knots
        self.heading_degrees_true = heading_degrees_true
        self.heading_degrees_magnetic = heading_degrees_magnetic

    def _convert_to_nmea(self):
        """
        $--VHW,x.x,T,x.x,M,x.x,N,x.x,K*hh<CR><LF>
        $IIVHW,245.1,T,245.1,M,000.01,N,000.01,K
        """
        return self._nmea_conversion((self.heading_degrees_true, 'T'),
                                     (self.heading_degrees_magnetic, 'M'),
                                     (self.speed_knots, 'N'),
                                     (UnitConverter.nm_to_meter(self.speed_knots) * 1000, 'K'))

    def _parse_nmea_sentence(self, nmea_value_list: list):
        self.heading_degrees_true = nmea_value_list[0]
        self.heading_degrees_magnetic = nmea_value_list[2]
        self.speed_knots = float(nmea_value_list[4])


class WaterTemperature(NMEADatagram):
    def __init__(self, temperature_c=None):
        super().__init__(nmea_tag="MTW")
        self.temperature_c = temperature_c

    def _convert_to_nmea(self):
        """
        $--MTW,x.x,C*hh<CR><LF>
        """
        return self._nmea_conversion((self.temperature_c, "C"))

    def _parse_nmea_sentence(self, nmea_value_list: list):
        self.temperature_c = float(nmea_value_list[0])


class WindSpeedAndAngle(NMEADatagram):
    def __init__(self, angle=None, reference_true=None, speed_knots=None, validity=None):
        super().__init__("MWV")
        self.angle = angle
        self.reference_true = reference_true
        self.speed_knots = speed_knots
        self.valid_status = validity

    def _convert_to_nmea(self):
        """
        $--MWV,x.x,a,x.x,a*hh<CR><LF>
        $WIMWV,214.8,R,0.1,K,A*28
        """
        return self._nmea_conversion((self.angle, "T" if self.reference_true else "R"),
                                     (self.speed_knots, "N")) + "," + ("A" if self.valid_status else "V")

    def _parse_nmea_sentence(self, nmea_value_list: list):
        self.angle = float(nmea_value_list[0])
        self.reference_true = True if nmea_value_list[1] == "T" else False

        if nmea_value_list[3] == "N":
            self.speed_knots = float(nmea_value_list[2])
        elif nmea_value_list[3] == "K":
            self.speed_knots = UnitConverter.meter_to_nm(float(nmea_value_list[2]) * 1000)
        elif nmea_value_list[3] == "M":
            self.speed_knots = UnitConverter.meter_to_nm(float(nmea_value_list[2]) * 60 * 60)

        self.valid_status = self.check_validity(nmea_value_list[4])
