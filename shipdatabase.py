from datetime import datetime, timedelta, date, time
from typing import List, Tuple

from common.helper import Position, PartPosition, Orientation, TimedCircleQueue


class ShipDataBase(object):
    """
    DataBase of ship-data. Its data gets deleted if its too old
    """
    def __init__(self, max_data_point_age_s=60):
        self._data = {}
        self._property_timestamps = {}
        self._max_data_point_age_timedelta = timedelta(seconds=max_data_point_age_s)

        # Satellite / GPS
        self.utc_time: time = None
        self.date: date = None
        self.latitude_position: PartPosition = None
        self.longitude_position: PartPosition = None
        self.target_waypoints: List[Tuple[str, Position]] = None
        # TODO list of satellites

        # Heading and course
        self.course_over_ground_degree_true: float = None
        self.course_over_ground_degree_magnetic: float = None
        self.heading_degrees_true: float = None
        self.heading_degrees_magnetic: float = None
        self.heading_true_deg: float = None
        self.heading_magnetic_deg: float = None

        # Speed
        self.speed_over_ground_knots: float = None
        self.speed_through_water_knots: float = None

        # Wind
        self.true_wind_speed_knots: float = None
        self.true_wind_speed_angle: float = None
        self.apparent_wind_speed_knots: float = None
        self.apparent_wind_angle: float = None

        # Mileage
        self.trip_mileage_miles: float = None
        self.total_mileage_miles: float = None

        # Water
        self.depth_m: float = None
        self.water_temperature_c: float = None

        # Seatalk-specific
        self.set_light_intensity: int = None

        # List of valid datagrams which still can be tried to be forwarded to other listeners
        # (avoid loss of data just because we can't parse it yet)
        # TODO queue is not really needed but a list
        self._list_unknown_nmea_datagrams = TimedCircleQueue(maxsize=100, maxage=self._max_data_point_age_timedelta)
        self._list_unknown_seatalk_datagrams = TimedCircleQueue(maxsize=100, maxage=self._max_data_point_age_timedelta)

    def _is_property_too_old(self, property_name):
        """
        Checks if property is too old.
        :param property_name: name of property to get
        :return: True if too old, False if not
        """
        property_time_stamp = self._get_timestamp(property_name)
        if property_time_stamp is None:
            return False
        current_time = datetime.now()
        return current_time - property_time_stamp > self._max_data_point_age_timedelta

    def _get_timestamp(self, property_name):
        """
        Returns the timestamp when item was added
        :param property_name: name of property
        :return: timestamp
        """
        return self._property_timestamps.get(property_name, None)

    def _set_timestamp(self, property_name, timestamp):
        """
        Sets timestamp of property
        :param property_name: name of property
        :param timestamp: timestamp to add
        """
        self._property_timestamps[property_name] = timestamp

    def _get_property(self, property_name):
        """
        Returns property if it's not too old
        :param property_name: name of property
        :return: value of property or None
        """
        data = self._data.get(property_name, None)
        if data is not None and self._is_property_too_old(property_name):
            del data
            return None
        else:
            return data

    def __getattr__(self, name):
        if name in self._data:
            return self._get_property(name)
        else:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            self._set_timestamp(name, datetime.now())
            self._data[name] = value

    def __delattr__(self, name):
        if name in self._data:
            self._delete_property(name)
        else:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")