import enum
import curio


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
    return byte_str[:-1]  # Remove last space


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
        return meter / 1852

    @staticmethod
    def nm_to_meter(nm):
        return nm * 1852

    @staticmethod
    def sm_to_nm(sm):
        return sm * 0.868976

    @staticmethod
    def nm_to_sm(sm):
        return sm / 0.868976

    # Temperatures
    @staticmethod
    def celsius_to_fahrenheit(celsius):
        return celsius * 1.8 + 32

    @staticmethod
    def fahrenheit_to_celsius(fahrenheit):
        return (fahrenheit - 32) / 1.8000


class TwoWayDict(dict):
    """
    Similar to a normal dict, but both sides need to be unique
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reversed_dict = dict()
        self._update_reversed_dict()

    def get_reversed(self, value):
        try:
            return self.reversed_dict[value]
        except KeyError as e:
            raise ValueError from e  # Reversed

    def get(self, key):
        """
        Overrides the default get of dictionary (would return None if not available)
        Now raises KeyError if not available
        """
        return self[key]

    def _update_reversed_dict(self):
        own_values = self.values()
        if len(own_values) != len(set(own_values)):
            raise ValueError("Values are not unique")

        for key in self.keys():
            self.reversed_dict[self[key]] = key

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._update_reversed_dict()

    def __setitem__(self, key, value):
        """
        overrides []
        """
        super().__setitem__(key, value)
        self._update_reversed_dict()


class Orientation(enum.Enum):
    North = "N"
    South = "S"
    West = "W"
    East = "E"


class PartPosition(object):
    def __init__(self, degrees, minutes, direction: Orientation):
        self.degrees = degrees
        self.minutes = minutes
        self.direction = direction


class Position(object):
    def __init__(self, latitude: PartPosition, longitude: PartPosition):
        self.latitude = latitude
        self.longitude = longitude


def cast_if_at_position(values, index, cast):
    try:
        return cast(values[index])
    except (TypeError, ValueError):
        return None


class TypeSafeQueue(curio.Queue):
    def __init__(self, queue_type, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queue_type = queue_type

    async def put(self, item):
        """
        Check instance before enqueuing
        """
        if not isinstance(item, self._queue_type):
            raise TypeError(f"Wrong type of item. Expected: {self._queue_type.__name__}, actual: {type(item).__name__}")
        await super().put(item)
