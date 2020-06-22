def byte_to_str(byte):
    """
    Returns string representation of given byte 0x2A -> "Ox2A "

    :param byte:
    :return:
    """
    if isinstance(byte, int):
        value = byte
    else:
        value = get_numeric_byte_value(byte)
    return '0x%02X ' % value


def bytes_to_str(bytes):
    """
    Returns string representation of given bytes [0x21, 0x2E] -> "0x21 0x2E"

    :param bytes: 
    :return:
    """
    byte_str = ""
    for byte in bytes:
        byte_str += byte_to_str(byte)
    return byte_str


def get_numeric_byte_value(byte):
    return int.from_bytes(byte, "big")


class UnitConverter(object):
    # Distances
    @staticmethod
    def meter_to_feet(meter):
        return meter * 3.28084

    @staticmethod
    def feet_to_meter(feet):
        return feet / 3.28084

    @staticmethod
    def meter_to_fathom(meter):
        return meter * 0.54680665

    @staticmethod
    def fathom_to_meter(fathom):
        return fathom / 0.54680665

    @staticmethod
    def meter_to_nm(meter):
        return meter * 0.0005399568

    @staticmethod
    def nm_to_meter(nm):
        return nm / 0.0005399568

    # Temperatures
    @staticmethod
    def celsius_to_fahrenheit(celsius):
        return celsius * 1.8 + 32

    @staticmethod
    def fahrenheit_to_celsius(fahrenheit):
        return (fahrenheit - 32) / 1.8000


class TwoWayDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        own_values = self.values()
        if len(own_values) != len(set(own_values)):
            raise ValueError("Values are not unique")

    def get_reversed(self, value):
        for key in self.keys():
            if value == self[key]:
                return key
        else:
            raise ValueError(f"Value not found {value}")

    def get(self, key):
        """
        Overrides the default get of dictionary (would return None if not available)
        Now raises KeyError if not available
        """
        return self[key]


class PartPosition(object):
    def __init__(self, degrees, minutes, direction):
        self.degrees = degrees
        self.minutes = minutes
        self.direction = direction


class Position(object):
    def __init__(self, latitude: PartPosition, longitude: PartPosition):
        self.latitude = latitude
        self.longitude = longitude
