from abc import abstractmethod
from functools import reduce
import operator


class NMEAError(Exception):
    pass


class NMEAParseError(Exception):
    pass


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
            temp_nmea_str = nmea_str[1:]  # Remove dollar
            temp_nmea_str = temp_nmea_str[:-5]  # Remove \r\n and checksum
            own_checksum = cls.checksum(temp_nmea_str)
        except ValueError as e:
            raise NMEAParseError(f"Could not parse {nmea_str}") from e

        if own_checksum != nmea_str_checksum:
            raise ChecksumError(nmea_str, own_checksum)

    @staticmethod
    def _get_value(value, unit):
        """
        Only create value if it is set
        """
        empty_data = ",,"
        return f",{value:.1f},{unit}" if value is not None else empty_data

    @classmethod
    def _nmea_conversion(cls, *value_tuple):
        sentence = ""
        for value, unit in value_tuple:
            sentence += cls._get_value(value, unit)
        return sentence


class DepthBelowKeel(NMEADatagram):
    def __init__(self, depth_m=None):
        super().__init__(nmea_tag="DBT")
        self.depth_m = depth_m

    def _convert_to_nmea(self):
        """
        $--DBT,x.x,f,x.x,M,x.x,F*hh<CR><LF>
        $SDDBT,7.8,f,2.4,M,1.3,F*0D\r\n
        """
        feet = self.depth_m * 3.28084
        fathoms = self.depth_m * 0.54680665
        return self._nmea_conversion((feet, 'f'),
                                     (self.depth_m, 'M'),
                                     (fathoms, 'F'),)


class SpeedOverWater(NMEADatagram):
    def __init__(self, speed_knots=None, heading_degrees_true=None, heading_degrees_magnetic=None):
        super().__init__(nmea_tag="VHW")
        self.speed_knots = speed_knots
        self.heading_degrees_true = heading_degrees_true
        self.heading_degrees_magnetic = heading_degrees_magnetic

    def _convert_to_nmea(self):
        """
        $--VHW,x.x,T,x.x,M,x.x,N,x.x,K*hh<CR><LF>
        """
        kmh = self.speed_knots * 1.852
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

