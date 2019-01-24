from oktacli.cli import _dict_flat_to_nested
from oktacli.cli import _prepare_okta_filter_string
from oktacli.cli import _dict_get_dotted_keys


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
