import enum
import os
import curio
from datetime import datetime, timedelta
from math import cos, asin, sqrt, pi


class Singleton(type):
    """
    Allows only one instance of given class (use as metaclass)
    Copied from: https://stackoverflow.com/questions/6760685/
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class TimedCircleQueue(curio.Queue):
    """
    Queue which ensures that new items get added anyway (old ones get removed).
    When popping item, look if that item is older than given max_time

    On super()-level a queue-item contains a tuple of the real item and it's timestamp when enqueuing
    """
    def __init__(self, maxsize, maxage: timedelta):
        super().__init__(maxsize=maxsize)
        self.maxage = maxage  # Keep naming to curio's maxsize

    async def put(self, item):
        if self.maxsize != 0 and self.full():
            await super().get()  # discard first item
        item_timestamp = datetime.now()
        await super().put((item, item_timestamp))

    async def get(self):
        item, item_timestamp = await super().get()
        diff = datetime.now() - item_timestamp
        if diff > self.maxage:
            item = await self.get()
        return item


def set_system_time(date: datetime):
    """
    Sets system time (Win and Linux). Taken and adapted from https://stackoverflow.com/a/52971307

    :param date: datetime-instanceW
    :return: -
    """
    def _win_set_time(date):
        import win32api
        win32api.SetSystemTime(date.year, date.month, date.isoweekday(), date.day, date.hour, date.minute, date.second, date.microsecond // 1000)

    def _linux_set_time(date):
        import subprocess
        import shlex

        time_string = date.isoformat()

        subprocess.call(shlex.split("timedatectl set-ntp false"))  # May be necessary
        subprocess.call(shlex.split("sudo date -s '%s'" % time_string))
        subprocess.call(shlex.split("sudo hwclock -w"))

    if os.name == 'nt':
        _win_set_time(date)
    else:
        _linux_set_time(date)


def byte_to_str(byte_to_convert):
    """
    Returns string representation of given byte 0x2A -> "Ox2A "

    :param byte_to_convert: given byte to convert
    :return: string representation with hex prefix
    """
    if isinstance(byte_to_convert, int):
        value = byte_to_convert
    else:
        value = get_numeric_byte_value(byte_to_convert)
    return '0x%02X ' % value


def bytes_to_str(bytes_to_convert) -> str:
    """
    Returns string representation of given bytes [0x21, 0x2E] -> "0x21 0x2E"

    :param bytes_to_convert: given byte to convert
    :return: string representation with hex prefix
    """
    byte_str = ""
    for byte in bytes_to_convert:
        byte_str += byte_to_str(byte)
    return byte_str[:-1]  # Remove last space


def get_numeric_byte_value(byte) -> int:
    """
    Returns numeric value of given byte

    :param byte: byte to convert
    :return: numeric integer value
    """
    return int.from_bytes(byte, "big")


class UnitConverter(object):
    # Distances
    @staticmethod
    def meter_to_feet(meter) -> float:
        return meter * 3.28084

    @staticmethod
    def feet_to_meter(feet) -> float:
        return feet / 3.28084

    @staticmethod
    def meter_to_fathom(meter) -> float:
        return meter * 0.54680665

    @staticmethod
    def fathom_to_meter(fathom) -> float:
        return fathom / 0.54680665

    @staticmethod
    def meter_to_nm(meter) -> float:
        return meter / 1852

    @staticmethod
    def nm_to_meter(nm) -> float:
        return nm * 1852

    @staticmethod
    def sm_to_nm(sm) -> float:
        return sm * 0.868976

    @staticmethod
    def nm_to_sm(sm) -> float:
        return sm / 0.868976

    # Temperatures
    @staticmethod
    def celsius_to_fahrenheit(celsius) -> float:
        return celsius * 1.8 + 32

    @staticmethod
    def fahrenheit_to_celsius(fahrenheit) -> float:
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

    def to_degrees(self):
        return self.degrees + (self.minutes / 60)
        # Takes degrees only (as float) and converts it into a split part_position


class Position(object):
    def __init__(self, latitude: PartPosition, longitude: PartPosition):
        self.latitude = latitude
        self.longitude = longitude

    @staticmethod
    def distance(position_1, position_2):
        """
        Returns the distance between two Positions
        :param position_1: first Positions
        :param position_2: second Positions
        :return: distance in km
        """
        lat1 = position_1.latitude.to_degrees()
        lat2 = position_2.latitude.to_degrees()
        lon1 = position_1.longitude.to_degrees()
        lon2 = position_2.longitude.to_degrees()

        # Taken and adapted from https://stackoverflow.com/a/21623206
        p = pi / 180
        a = 0.5 - cos((lat2 - lat1) * p) / 2 + cos(lat1 * p) * cos(lat2 * p) * (1 - cos((lon2 - lon1) * p)) / 2
        return 12742 * asin(sqrt(a))  # 2*R*asin...


def cast_if_at_position(values, index, cast):
    try:
        return cast(values[index])
    except (TypeError, ValueError, IndexError):
        return None
