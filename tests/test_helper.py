from common.helper import *
import pytest


class TestTwoWayDict(object):
    @staticmethod
    def test_two_way_dict():
        my_dict = TwoWayDict({
            1: 3,
            4: 5,
        })

        assert my_dict.get(1) == 3
        assert my_dict.get(4) == 5

        assert my_dict.get_reversed(3) == 1
        assert my_dict.get_reversed(5) == 4


    @staticmethod
    def test_none_unique_keys():
        my_dict = TwoWayDict({  # Dictionary will filter out the first key-value anyway
            1: 3,
            1: 5,
        })
        assert my_dict.get(1) == 5
        assert my_dict.get_reversed(5) == 1
        with pytest.raises(ValueError):
            my_dict.get_reversed(3)


    @staticmethod
    def test_none_unique_values():
        with pytest.raises(ValueError):
            TwoWayDict({
                1: 5,
                4: 5,
            })


    @staticmethod
    def test_unknown_key():
        my_dict = TwoWayDict({
            1: 3,
            4: 5,
        })
        with pytest.raises(KeyError):
            my_dict.get(9)


    @staticmethod
    def test_unknown_value():
        my_dict = TwoWayDict({
            1: 3,
            4: 5,
        })
        with pytest.raises(ValueError):
            my_dict.get_reversed(4)


    @staticmethod
    def test_update_dict():
        my_dict = TwoWayDict({
            1: 3,
            4: 5,
        })
        my_dict.update({3: 9})
        assert my_dict[3] == 9
        assert my_dict.get_reversed(9) == 3


    @staticmethod
    def test_put_new_item():
        my_dict = TwoWayDict({
            1: 3,
            4: 5,
        })
        my_dict[3] = 9
        assert my_dict[3] == 9
        assert my_dict.get_reversed(9) == 3


    @staticmethod
    def test_override_item():
        my_dict = TwoWayDict({
            1: 3
        })
        assert my_dict[1] == 3
        my_dict[1] = 6
        assert my_dict[1] == 6


    @staticmethod
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


class TestTimedCircleQueue(object):
    @staticmethod
    @pytest.mark.curio
    async def test_max_time():
        max_size = 1
        max_age = timedelta(seconds=0)  # Zero-time
        queue = TimedCircleQueue(maxsize=max_size, maxage=max_age)
        await queue.put(object())
        await curio.sleep(1)
        with pytest.raises(curio.TaskTimeout):
            async with curio.timeout_after(1):
                await queue.get()  # Should get stuck, since queue must be empty at this point
                assert False, f"Shouldn't dequeue an item, because of max_time {max_age}"

    @staticmethod
    @pytest.mark.curio
    async def test_max_size():
        max_size = 10
        max_age = timedelta(days=10)
        queue = TimedCircleQueue(maxsize=max_size, maxage=max_age)
        for i in range(max_size + 1):  # Enqueue one too much
            await queue.put(i)

        for i in range(max_size):
            dequeued_item = await queue.get()
            assert dequeued_item == i + 1  # First item was removed
