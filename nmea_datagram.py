from abc import abstractmethod, ABCMeta
from functools import reduce
import operator
import datetime
import inspect
import sys
import enum

from helper import UnitConverter, Position, PartPosition, byte_to_str, Orientation, cast_if_at_position


class NMEAValidity(enum.Enum):
    """
    Some NMEA-Datagrams have validity-characters
    """
    # A = valid, V = invalid. Very intuitive...
    Valid = "A"
    Invalid = "V"


class NMEAError(Exception):
    """
    General Exceptions concerning NMEA
    """


class NMEAParseError(NMEAError):
    """
    Exceptions occurring when parsing NMEA-Datagrams
    """


class UnknownUnitError(NMEAParseError):
    """
    Error if given unit in datagram is unknown
    """


class WrongFormatError(NMEAParseError):
    """
    Error if given datagram does not apply to nmea-standard
    """
    def __init__(self, sentence: str):
        super().__init__(f"Could not parse sentence. First (\"$\") or last characters (\"\\r\\n\") are wrong/missing: \"" + sentence + "\"")


class ChecksumError(NMEAParseError):
    """
    Error if given datagram's checksum does not match the calculated one
    """
    def __init__(self, sentence, actual_checksum, expected_checksum):
        super().__init__(f"ChecksumError: {sentence} checksum {byte_to_str(actual_checksum)} does not match own calculated checksum: {byte_to_str(expected_checksum)}")


class UnknownNMEATag(NMEAParseError):
    def __init__(self, nmea_tag: str):
        super().__init__(f"Could not parse sentence. Unknown NMEA-Tag: {nmea_tag}")


class NMEADatagram(object, metaclass=ABCMeta):
    """
    General NMEA-Datagram-Class
    """
    nmea_tag_datagram_map = None

    def __init__(self, nmea_tag, talker_id="--"):
        self.nmea_tag = nmea_tag
        self._talker_id = talker_id

    @classmethod
    def create_map(cls):
        """
        Creates a map of all known NMEA-Tags to it's representing Classes
        """
        cls.nmea_tag_datagram_map = dict()
        for name, obj in inspect.getmembers(sys.modules[__name__]):
            if inspect.isclass(obj) and issubclass(obj, NMEADatagram) and not inspect.isabstract(obj):
                nmea_datagram = obj()  # TODO that's a little kinda bad to instantiate it just for the tag and then leave it unused
                cls.nmea_tag_datagram_map[nmea_datagram.nmea_tag] = obj

    @classmethod
    def parse_nmea_sentence(cls, nmea_string: str):
        """
        Parses given NMEA-Sentence and returns an instance of NMEADatagram
        """
        if nmea_string[0] != '$' and nmea_string[-2:] != '\r\n':
            raise WrongFormatError(nmea_string)
        if not cls.nmea_tag_datagram_map:
            cls.create_map()

        cls.verify_checksum(nmea_string)  # TODO not necessary, gets checked before anyway

        nmea_tag = nmea_string[3:6]  # Get Tag
        try:
            nmea_class = cls.nmea_tag_datagram_map[nmea_tag]  # Extract class from tag
        except KeyError as e:
            raise UnknownNMEATag(nmea_tag) from e
        nmea_datagram_instance = nmea_class()  # Create instance
        nmea_datagram_instance._talker_id = nmea_string[1:3]  # Set Talker ID

        nmea_datagram_instance._parse_nmea_sentence(nmea_string[7:-5].split(","))  # Now parse it, start after nmea-tag, stop at checksum
        return nmea_datagram_instance

    @abstractmethod
    def _parse_nmea_sentence(self, nmea_value_list: list):
        """
        Abstract method to be implemented by each Datagram. Parses content of NMEA-string and fills sets own members
        """
        raise NotImplementedError()

    def get_nmea_sentence(self) -> str:
        """
        Returns NMEA-String from instance
        """
        prefix = f"{self._talker_id}{self.nmea_tag}"
        data = prefix + self._get_nmea_sentence()
        checksum = self.create_checksum(data)
        return f"${data}*{checksum:02X}\r\n"

    @abstractmethod
    def _get_nmea_sentence(self) -> str:
        """
        Abstract method to be implemented by each Datagram. Creates content for NMEA-String (return string)
        """
        raise NotImplementedError()

    @staticmethod
    def create_checksum(nmea_str: str):
        """
        Creates string checksum to given NMEA-String
        """
        return reduce(operator.xor, map(ord, nmea_str), 0)

    @classmethod
    def verify_checksum(cls, nmea_str: str):
        """
        Verifies checksum in given NMEA-String.
        Raises NMEAParseError if string could not be parsed as expected
        Raise ChecksumError if given checksum differs to calculated checksum
        """
        try:
            nmea_str_checksum = int(nmea_str[-4:-2], 16)
            expected = cls.create_checksum(nmea_str[1:-5])  # Remove dollar, \r\n and checksum
        except ValueError as e:
            raise NMEAParseError(f"Could not parse {nmea_str}") from e

        if expected != nmea_str_checksum:
            raise ChecksumError(nmea_str, nmea_str_checksum, expected)

    @classmethod
    def _append_tuple(cls, value, unit):
        """
        Returns formatted string for given value and unit (used for NMEA-String generation)
        """
        return cls._append_value(value) + "," + unit

    @classmethod
    def _append_value(cls, value):
        """
        Returns formatted string for given value (used for NMEA-String generation)
        """
        if isinstance(value, float):
            value = f"{value:.2f}"
        elif isinstance(value, enum.Enum):
            value = value.value
        return f",{value}" if value is not None else ","


class RecommendedMinimumSentence(NMEADatagram):
    def __init__(self, date=None, valid_status=None, position=None, speed_over_ground_knots=None, track_made_good=None, magnetic_variation=None, variation_sense=None, mode=None, *args, **kwargs):
        super().__init__("RMC", *args, **kwargs)
        self.date = date
        self.valid_status = valid_status
        self.position = position
        self.speed_over_ground_knots = speed_over_ground_knots
        self.track_made_good = track_made_good
        self.magnetic_variation = magnetic_variation
        self.variation_sense = variation_sense
        self.mode = mode

        self._date_format_date = "%d%m%y"
        self._date_format_time = "%H%M%S.%f"  # TODO f = microseconds, not milliseconds?


    def _get_nmea_sentence(self):
        """
        $GPRMC,hhmmss.ss,a,ddmm.mmmm,n,dddmm.mmmm,w,z.z,y.y,ddmmyy,d.d,v*CC<CR><LF>
        $GPRMC,144858,A,5235.3151,N,00207.6577,W,0.0,144.8,160610,3.6,W,A*12\r\n
        """
        return_string = ""
        string_date, string_time = self.date.strftime(self._date_format_date + "|" + self._date_format_time).split("|")  # Use | only to make it splittable
        return_string += self._append_value(string_time)
        return_string += self._append_value(self.valid_status)
        return_string += f",{self.position.latitude.degrees:02}"  + str(self.position.latitude.minutes)  + self._append_value(self.position.latitude.direction)
        return_string += f",{self.position.longitude.degrees:02}" + str(self.position.longitude.minutes) + self._append_value(self.position.longitude.direction)

        return_string += self._append_value(self.speed_over_ground_knots) + \
                         self._append_value(self.track_made_good) + \
                         self._append_value(string_date) + \
                         self._append_value(self.magnetic_variation) + \
                         self._append_value(self.variation_sense) + \
                         self._append_value(self.mode)
        return return_string

    def _parse_nmea_sentence(self, nmea_value_list: list):
        gps_time = nmea_value_list[0]
        if "." not in gps_time:  # Some dont send milliseconds
            gps_time += ".0"  # TODO float-string-parse? {:.2}?
        gps_date = nmea_value_list[8]

        self.date = datetime.datetime.strptime(gps_date + gps_time, self._date_format_date + self._date_format_time)
        self.valid_status = NMEAValidity(nmea_value_list[1])

        latitude_degrees = int(nmea_value_list[2][0:2])
        latitude_minutes = float(nmea_value_list[2][2:])  # Remove degrees
        latitude = PartPosition(degrees=latitude_degrees, minutes=latitude_minutes, direction=Orientation(nmea_value_list[3]))

        longitude_degrees = int(nmea_value_list[4][0:3])
        longitude_minutes = float(nmea_value_list[4][2:])  # Remove degrees
        longitude = PartPosition(degrees=longitude_degrees, minutes=longitude_minutes, direction=Orientation(nmea_value_list[5]))

        self.position = Position(latitude, longitude)

        self.speed_over_ground_knots = cast_if_at_position(nmea_value_list, 6, float)
        self.track_made_good = cast_if_at_position(nmea_value_list, 7, float)
        self.magnetic_variation = cast_if_at_position(nmea_value_list, 9, float)
        self.variation_sense = cast_if_at_position(nmea_value_list, 10, float)
        if len(nmea_value_list) == 12:  # Mode is not given every time
            self.mode = nmea_value_list[11]


class DepthBelowKeel(NMEADatagram):
    def __init__(self, depth_m=None, *args, **kwargs):
        super().__init__(nmea_tag="DBT", *args, **kwargs)
        self.depth_m = depth_m

    def _get_nmea_sentence(self):
        """
        $--DBT,x.x,f,x.x,M,x.x,F*hh<CR><LF>
        $SDDBT,7.8,f,2.4,M,1.3,F*0D\r\n
        """
        feet = fathoms = None
        if self.depth_m:
            feet = UnitConverter.meter_to_feet(self.depth_m)
            fathoms = UnitConverter.meter_to_fathom(self.depth_m)
        return self._append_tuple(feet, 'f') + self._append_tuple(self.depth_m, 'M') + self._append_tuple(fathoms, 'F')

    def _parse_nmea_sentence(self, nmea_value_list: list):
        if nmea_value_list[2]:  # If meter is given
            self.depth_m = float(nmea_value_list[2])
        elif nmea_value_list[0]:  # If feet is given
            self.depth_m = UnitConverter.feet_to_meter(float(nmea_value_list[0]))
        elif nmea_value_list[4]:  # If fathom is given
            self.depth_m = UnitConverter.fathom_to_meter(float(nmea_value_list[4]))
        else:
            pass  # Nothing is given?


class SpeedThroughWater(NMEADatagram):
    def __init__(self, speed_knots=None, heading_degrees_true=None, heading_degrees_magnetic=None, *args, **kwargs):
        super().__init__(nmea_tag="VHW", *args, **kwargs)
        self.speed_knots = speed_knots
        self.heading_degrees_true = heading_degrees_true
        self.heading_degrees_magnetic = heading_degrees_magnetic

    def _get_nmea_sentence(self):
        """
        $--VHW,x.x,T,x.x,M,x.x,N,x.x,K*hh<CR><LF>
        $IIVHW,245.1,T,245.1,M,000.01,N,000.01,K
        """
        return self._append_tuple(self.heading_degrees_true, 'T') +\
               self._append_tuple(self.heading_degrees_magnetic, 'M') +\
               self._append_tuple(self.speed_knots, 'N') +\
               self._append_tuple(UnitConverter.nm_to_meter(self.speed_knots) * 1000, 'K')

    def _parse_nmea_sentence(self, nmea_value_list: list):
        self.heading_degrees_true = nmea_value_list[0]
        self.heading_degrees_magnetic = nmea_value_list[2]
        self.speed_knots = float(nmea_value_list[4])


class WaterTemperature(NMEADatagram):
    def __init__(self, temperature_c=None, *args, **kwargs):
        super().__init__(nmea_tag="MTW", *args, **kwargs)
        self.temperature_c = temperature_c

    def _get_nmea_sentence(self):
        """
        $--MTW,x.x,C*hh<CR><LF>
        """
        return self._append_tuple(self.temperature_c, "C")

    def _parse_nmea_sentence(self, nmea_value_list: list):
        self.temperature_c = float(nmea_value_list[0])


class WindSpeedAndAngle(NMEADatagram):
    def __init__(self, angle_degree=None, reference_true=None, speed_knots=None, validity: NMEAValidity=None, *args, **kwargs):
        super().__init__("MWV", *args, **kwargs)
        self.angle_degree = angle_degree
        self.reference_true = reference_true
        self.speed_knots = speed_knots
        self.valid_status = validity

    def _get_nmea_sentence(self):
        """
        $--MWV,x.x,a,x.x,a*hh<CR><LF>
        $WIMWV,214.8,R,0.1,K,A*28
        """
        nmea_str = self._append_tuple(self.angle_degree, "T" if self.reference_true else "R") + \
                   self._append_tuple(self.speed_knots, "N") + \
                   self._append_value(self.valid_status)

        return nmea_str

    def _parse_nmea_sentence(self, nmea_value_list: list):
        self.angle_degree = float(nmea_value_list[0])
        self.reference_true = True if nmea_value_list[1] == "T" else False

        value = float(nmea_value_list[2])
        unit = nmea_value_list[3]
        if unit == "N":
            self.speed_knots = value
        elif unit == "K":
            self.speed_knots = UnitConverter.meter_to_nm(value * 1000)
        elif unit == "M":
            self.speed_knots = UnitConverter.meter_to_nm(value * 60 * 60)
        else:
            raise UnknownUnitError(f"Unknown unit: {unit}")

        self.valid_status = NMEAValidity(nmea_value_list[4])
