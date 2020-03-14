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
        prefix = f"{self._talker_id}{self.nmea_tag},"
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


class DepthBelowKeel(NMEADatagram):
    def __init__(self, depth_m=0.0):
        super().__init__(nmea_tag="DBT")
        self.depth_m = depth_m

    def _convert_to_nmea(self):
        """
        $--DBT,x.x,f,x.x,M,x.x,F*hh<CR><LF>
        $SDDBT,7.8,f,2.4,M,1.3,F*0D\r\n
        """
        feet = self.depth_m * 3.28084
        fantoms = self.depth_m * 0.54680665
        return f"{feet:.1f},f," \
               f"{self.depth_m:.1f},M," \
               f"{fantoms:.1f},F"


class SpeedOverWater(NMEADatagram):
    def __init__(self, speed_knots=0.0, heading_degrees_true=0.0, heading_degrees_magnetic=0.0):
        super().__init__(nmea_tag="VHW")
        self.speed_knots = speed_knots
        self.heading_degrees_true = heading_degrees_true
        self.heading_degrees_magnetic = heading_degrees_magnetic

    def _convert_to_nmea(self):
        """
        $--VHW,x.x,T,x.x,M,x.x,N,x.x,K*hh<CR><LF>
        """
        kmh = self.speed_knots * 1.852
        # TODO mabye test what happens if heading is left out
        return f"{self.heading_degrees_true:.1f},T," \
               f"{self.heading_degrees_magnetic:.1f},M," \
               f"{self.speed_knots:.1f},N," \
               f"{kmh:.1f},K"


class WaterTemperature(NMEADatagram):
    def __init__(self, temperature_c=0.0):
        super().__init__(nmea_tag="MTW")
        self.temperature_c = temperature_c

    def _convert_to_nmea(self):
        """
        $--MTW,x.x,C*hh<CR><LF>
        """
        return f"{self.temperature_c:.1f}"

