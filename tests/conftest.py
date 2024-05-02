import datetime

import pytest
import inspect
import curio
import os
import shipdatabase

import logger
from common.helper import Position, PartPosition, Orientation

test_kernel = None


def default_ship_database():
    database = shipdatabase.ShipDataBase(0)  # For testing, do net let it run out of time
    # Satellite / GPS
    database.utc_time = datetime.time(hour=8, minute=57, second=32)
    database.date = datetime.date(year=2024, month=4, day=18)
    test_position = Position(PartPosition(degrees=23, minutes=33, direction=Orientation.North),
                             PartPosition(degrees=8, minutes=2, direction=Orientation.East))
    database.latitude_position = test_position.latitude
    database.longitude_position = test_position.longitude
    database.target_waypoints = [("abc", test_position), ("def", test_position)]

    # Heading and course
    database.course_over_ground_degree_true = 320
    database.course_over_ground_degree_magnetic = 325
    database.heading_degrees_true = 170
    database.heading_degrees_magnetic = 175

    # Speed
    database.speed_over_ground_knots = 13.2
    database.speed_through_water_knots = 12.4

    database.true_wind_speed_knots = 2.3
    database.true_wind_speed_angle = 23
    database.apparent_wind_speed_knots = 1.9
    database.apparent_wind_angle = 19

    # Mileage
    database.trip_mileage_miles = 37
    database.total_mileage_miles = 120

    # Water
    database.depth_m = 13
    database.water_temperature_c = 5

    # Seatalk-specific
    database.set_light_intensity = 3


def _get_kernel():
    global test_kernel
    if test_kernel is None:
        test_kernel = curio.Kernel()
    return test_kernel


def kernel_fixture():
    return _get_kernel()


@pytest.fixture(scope="session", autouse=True)
def session_start_fixture():
    logger.GeneralLogger()


@pytest.fixture(scope="function", autouse=True)
def log_function(session_start_fixture):
    """
    Logs currently running name of test-function
    """
    logger.info("Current test: " + os.environ.get('PYTEST_CURRENT_TEST'))


@pytest.mark.tryfirst
def pytest_pycollect_makeitem(collector, name, obj):
    """
    From https://docs.pytest.org/en/latest/reference.html
    return custom item/collector for a python object in a module, or None
    Stops at first non-None result, see firstresult: stop at first non-None result
    """
    if collector.funcnamefilter(name) and inspect.iscoroutinefunction(obj):
        item = pytest.Function.from_parent(name=name, parent=collector)
        if 'curio' in item.keywords:
            return list(collector._genfunctions(name, obj))


@pytest.mark.tryfirst
def pytest_pyfunc_call(pyfuncitem):
    """
    From https://docs.pytest.org/en/latest/reference.html
    call underlying test function.
    Stops at first non-None result, see firstresult: stop at first non-None result
    """
    _test_kernel = _get_kernel()
    if 'curio' in pyfuncitem.keywords:
        funcargs = pyfuncitem.funcargs
        testargs = {arg: funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames}
        fut = pyfuncitem.obj(**testargs)
        try:
            _test_kernel.run(fut)
        except curio.TaskError as e:
            raise e.__cause__ from e
        return True


def pytest_configure(config):
    # register an additional marker
    config.addinivalue_line(
        "markers", "curio: Asynchronous test functions"
    )


def pytest_sessionfinish(session, exitstatus):
    """ whole test run finishes. """
    if test_kernel is not None:
        test_kernel.run(shutdown=True)
