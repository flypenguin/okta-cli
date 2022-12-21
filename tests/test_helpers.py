from oktacli.cli import _dict_flat_to_nested
from oktacli.cli import _dict_nested_to_flat
from oktacli.cli import _dict_get_dotted_keys


def test_dict_flat_to_nested():
    d0 = {"one": "two", "three.four": "five", "six.seven": "eight"}
    t0 = {"one": "two", "three.four": "six"}
    r0 = {"one": "two", "three": {"four": "six"}, "six": {"seven": "eight"}}
    assert r0 == _dict_flat_to_nested(t0, defaults=d0)


def test_dict_nested_to_flat():
    input = {"a": 1, "c": {"a": 2, "b": {"x": 5, "y": 10}}, "d": [1, 2, 3]}
    wanted = {"a": 1, "c.a": 2, "c.b.x": 5, "d": [1, 2, 3], "c.b.y": 10}
    assert wanted == _dict_nested_to_flat(input)


test_dict = {
    "hi": {
        "ho": {
            "silver": "horse",
            "letsgo": "now",
        },
        "howareyou": "thanksfine",
    },
    "schmee": "meeh",
}


def test_get_dotted():
    dotted_keys = _dict_get_dotted_keys(test_dict)
    assert 4 == len(dotted_keys)
    for item in ["hi.ho.silver", "hi.ho.letsgo", "hi.howareyou", "schmee"]:
        assert item in dotted_keys
