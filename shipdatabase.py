from datetime import datetime, timedelta
from typing import List, Tuple

from common.helper import Position, PartPosition, Orientation


class ShipDataBase(object):
    """
    DataBase of ship-data. Its data gets deleted if its too old
    """
    def __init__(self, max_data_point_age_s=60):
        self._data = {}
        self._property_timestamps = {}
        self._max_data_point_age_timedelta = timedelta(seconds=max_data_point_age_s)

        self.utc_time: datetime = datetime.now()
        self.current_position: Position = Position(latitude=PartPosition(0, 0, Orientation.North), longitude=PartPosition(0, 0, Orientation.East))
        self.target_waypoints: List[Tuple[str, Position]] = []
        self.depth_m: float = 0
        # True HEADING
        # True Course
        self.heading_true_deg: float = 0.0
        self.heading_magnetic_deg: float = 0.0
        self.speed_over_ground_knots: float = 0.0
        self.speed_over_water_knots: float = 0.0
        self.apparent_wind_speed_knots: float = 0.0
        self.apparent_wind_angle: float = 0.0
        self.trip_mileage: float = 0.0
        self.total_mileage: float = 0.0
        self.water_temperature_c: float = 0.0

        # Seatalk-specific
        self.set_light_intensity = 0

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