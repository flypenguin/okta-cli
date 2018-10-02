from oktacli.cli import _dict_flat_to_nested


def test_dict_conversion():
    d0 = {"one": "two", "three.four": "five", "six.seven": "eight"}
    t0 = {"one": "two", "three.four": "six"}
    r0 = {"one": "two", "three": {"four": "six"}, "six": {"seven": "eight"}}
    assert r0 == _dict_flat_to_nested(t0, defaults=d0)
