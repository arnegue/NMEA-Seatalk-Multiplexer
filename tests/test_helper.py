import helper
import pytest

def ltest_two_way_dict():
    my_dict = helper.TwoWayDict({
        1: 3,
        4: 5,
    })

    assert my_dict.get(1) == 3
    assert my_dict.get(4) == 5

    assert my_dict.get_reversed(3) == 1
    assert my_dict.get_reversed(5) == 4


def test_none_unique_keys():
    my_dict = helper.TwoWayDict({  # Dictionary will filter out the first key-value anyway
        1: 3,
        1: 5,
    })
    assert my_dict.get(1) == 5
    assert my_dict.get_reversed(5) == 1
    with pytest.raises(ValueError):
        my_dict.get_reversed(3)


def test_none_unique_values():
    with pytest.raises(ValueError):
        helper.TwoWayDict({
            1: 5,
            4: 5,
        })


def test_unknown_key():
    my_dict = helper.TwoWayDict({
        1: 3,
        4: 5,
    })
    with pytest.raises(KeyError):
        my_dict.get(9)


def test_unknown_value():
    my_dict = helper.TwoWayDict({
        1: 3,
        4: 5,
    })
    with pytest.raises(ValueError):
        my_dict.get_reversed(4)
