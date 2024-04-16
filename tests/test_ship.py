import time

import pytest

from shipdatabase import ShipDataBase


class TestShip:
    def test_unset_data(self):
        ship = ShipDataBase()
        data = ship.speed_over_ground_knots
        assert data is None

    def test_not_existing_data(self):
        ship = ShipDataBase()
        with pytest.raises(AttributeError):
            _ = ship.abc

    def test_too_old_data(self):
        test_wait_time = 5
        ship = ShipDataBase(max_data_point_age_s=test_wait_time)
        ship.speed_over_ground_knots = 1  # Set Data

        time.sleep(test_wait_time - 2)  # This should work (1 < 5)
        data = ship.speed_over_ground_knots
        assert data == 1

        time.sleep(test_wait_time)  # This shouldn't work anymore, so None is returned
        data = ship.speed_over_ground_knots
        assert data is None

