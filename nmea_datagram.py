from abc import abstractmethod
from functools import reduce
import operator
import datetime

from helper import UnitConverter, Position, PartPosition


class NMEAError(Exception):
    pass


class NMEAParseError(Exception):
    pass


class WrongFormatError(NMEAParseError):
    def __init__(self, sentence: str):
        super().__init__(f"Could not parse sentence. First (\"$\") or last characters (\"\\r\\n\") are wrong/missing: \"" + sentence + "\"")


class ChecksumError(NMEAParseError):
    def __init__(self, sentence, own_checksum):
        super().__init__(f"ChecksumError: {sentence} checksum does not match own calculated checksum: {own_checksum}")


class NMEADatagram(object):
    def __init__(self, nmea_tag):
        self.nmea_tag = nmea_tag
        self._talker_id = "--"  # may be overridden

    @abstractmethod
    def _convert_to_nmea(self):
        pass

    def parse_nmea_sentence(self, nmea_string: str):
        if nmea_string[0] != '$' and nmea_string[-2:] != '\r\n':
            raise WrongFormatError(nmea_string)
        self._talker_id = nmea_string[1:3]
        tag = nmea_string[3:6]
        if tag != self.nmea_tag:
            pass  # TODO raise exception

        self._parse_nmea_sentence(nmea_string[7:-5])  # Start after nmea-tag, stop at checksum

    #@abstractmethod
    def _parse_nmea_sentence(self, nmea_string: str):
        pass

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
            own_checksum = cls.checksum(nmea_str[1:-5])  # Remove dollar, \r\n and checksum
        except ValueError as e:
            raise NMEAParseError(f"Could not parse {nmea_str}") from e

        if own_checksum != nmea_str_checksum:
            raise ChecksumError(nmea_str, own_checksum)

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

    def _parse_nmea_sentence(self, nmea_string: str):
        split = nmea_string.split(",")
        gps_time = split[0]
        if "." not in gps_time:  # Some dont send millseconds
            gps_time += ".0"
        gps_date = split[8]

        self.date = datetime.datetime.strptime(gps_date + gps_time, self._date_format_date + self._date_format_time)
        self.valid_status = split[1].upper() == "A"  # A = valid, V = invalid. Very intuitive...

        latitude_degrees = int(split[2][0:2])  # TODO one line?
        latitude_minutes = float(split[2][2:])  # Remove degrees
        latitude_direction = split[3]
        latitude = PartPosition(degrees=latitude_degrees, minutes=latitude_minutes, direction=latitude_direction)

        longitude_degrees = int(split[4][0:2])
        longitude_minutes = float(split[4][2:])  # Remove degrees
        longitude_direction = split[5]
        longitude = PartPosition(degrees=longitude_degrees, minutes=longitude_minutes, direction=longitude_direction)

        self.position = Position(latitude, longitude)

        self.speed_over_ground = float(split[6])
        self.track_made_good = float(split[7])
        self.magnetic_variation = float(split[9])
        self.variation_sense = split[10]
        self.mode = split[11]


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


class SpeedThroughWater(NMEADatagram):
    def __init__(self, speed_knots=None, heading_degrees_true=None, heading_degrees_magnetic=None):
        super().__init__(nmea_tag="VHW")
        self.speed_knots = speed_knots
        self.heading_degrees_true = heading_degrees_true
        self.heading_degrees_magnetic = heading_degrees_magnetic

    def _convert_to_nmea(self):
        """
        $--VHW,x.x,T,x.x,M,x.x,N,x.x,K*hh<CR><LF>
        """
        kmh = UnitConverter.nm_to_meter(self.speed_knots) * 1000
        return self._nmea_conversion((self.heading_degrees_true, 'T'),
                                     (self.heading_degrees_magnetic, 'M'),
                                     (self.speed_knots, 'N'),
                                     (kmh, 'K'))


class WaterTemperature(NMEADatagram):
    def __init__(self, temperature_c=None):
        super().__init__(nmea_tag="MTW")
        self.temperature_c = temperature_c

    def _convert_to_nmea(self):
        """
        $--MTW,x.x,C*hh<CR><LF>
        """
        return self._nmea_conversion((self.temperature_c, "C"))

