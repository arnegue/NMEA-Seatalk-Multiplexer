from helper import *
import pytest


def test_two_way_dict():
    my_dict = TwoWayDict({
        1: 3,
        4: 5,
    })

    assert my_dict.get(1) == 3
    assert my_dict.get(4) == 5

    assert my_dict.get_reversed(3) == 1
    assert my_dict.get_reversed(5) == 4


def test_none_unique_keys():
    my_dict = TwoWayDict({  # Dictionary will filter out the first key-value anyway
        1: 3,
        1: 5,
    })
    assert my_dict.get(1) == 5
    assert my_dict.get_reversed(5) == 1
    with pytest.raises(ValueError):
        my_dict.get_reversed(3)


def test_none_unique_values():
    with pytest.raises(ValueError):
        TwoWayDict({
            1: 5,
            4: 5,
        })


def test_unknown_key():
    my_dict = TwoWayDict({
        1: 3,
        4: 5,
    })
    with pytest.raises(KeyError):
        my_dict.get(9)


def test_unknown_value():
    my_dict = TwoWayDict({
        1: 3,
        4: 5,
    })
    with pytest.raises(ValueError):
        my_dict.get_reversed(4)


def test_update_dict():
    my_dict = TwoWayDict({
        1: 3,
        4: 5,
    })
    my_dict.update({3: 9})
    assert my_dict[3] == 9
    assert my_dict.get_reversed(9) == 3


def test_put_new_item():
    my_dict = TwoWayDict({
        1: 3,
        4: 5,
    })
    my_dict[3] = 9
    assert my_dict[3] == 9
    assert my_dict.get_reversed(9) == 3


def test_override_item():
    my_dict = TwoWayDict({
        1: 3
    })
    assert my_dict[1] == 3
    my_dict[1] = 6
    assert my_dict[1] == 6


def test_update_invalid_item():
    my_dict = TwoWayDict({
        1: 3,
        4: 5
    })
    with pytest.raises(ValueError):
        my_dict[4] = 3


@pytest.mark.parametrize(("converting_function", "expected_value"), (
                         (UnitConverter.meter_to_feet,          405.0196),
                         (UnitConverter.feet_to_meter,           37.6275),
                         (UnitConverter.meter_to_fathom,         67.5032),
                         (UnitConverter.fathom_to_meter,        225.7653),
                         (UnitConverter.meter_to_nm,              0.06665),
                         (UnitConverter.nm_to_meter,         228629.4),
                         (UnitConverter.nm_to_sm,              142.063723),
                         (UnitConverter.sm_to_nm,              107.275117),
                         (UnitConverter.celsius_to_fahrenheit, 254.21),
                         (UnitConverter.fahrenheit_to_celsius,  50.805555),
))
def test_unit_converter(converting_function, expected_value):
    eps = 0.01
    to_be_converted_value = 123.45
    actual_value = converting_function(to_be_converted_value)
    assert abs(actual_value - expected_value) < eps


@pytest.mark.curio
async def test_type_safe_queue():
    class TestBase(object):
        pass

    class DerivedClass(TestBase):
        pass

    test_queue = TypeSafeQueue(TestBase)

    # Test base-instance
    test_item = TestBase()
    await test_queue.put(test_item)
    assert await test_queue.get() is test_item

    # Test derived-instance
    test_item = DerivedClass()
    await test_queue.put(test_item)
    assert await test_queue.get() is test_item

    # Test wrong types
    for test_item in (TestBase, DerivedClass, float, 1, "abc"):
        with pytest.raises(TypeError):
            await test_queue.put(test_item)
