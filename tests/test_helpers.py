from oktacli.cli import _dict_flat_to_nested
from oktacli.cli import _prepare_okta_filter_string


def test_dict_conversion():
    d0 = {"one": "two", "three.four": "five", "six.seven": "eight"}
    t0 = {"one": "two", "three.four": "six"}
    r0 = {"one": "two", "three": {"four": "six"}, "six": {"seven": "eight"}}
    assert r0 == _dict_flat_to_nested(t0, defaults=d0)


def test_filter_prep():
    base = "profile.firstname eq heinz and id gt asdf"
    good = "profile.firstname eq \"heinz\" and id gt \"asdf\""
    assert good == _prepare_okta_filter_string(base)
    assert good == _prepare_okta_filter_string(good)
    base = "(a eq b or c eq d) and e eq f"
    good = '(a eq "b" or c eq "d") and e eq "f"'
    assert good == _prepare_okta_filter_string(base)
    assert good == _prepare_okta_filter_string(good)
