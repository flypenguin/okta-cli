import json
import re
from os import path as osp
from pathlib import Path

import appdirs

from .exceptions import ExitException
from .okta import Okta


def _check_config(config):
    # first - check how many configurations we have. if we have only one,
    # set this as the active one
    if len(config["profiles"]) == 1:
        config["default"] = list(config["profiles"].keys())[0]
    return config


def get_config_file():
    config_dir = appdirs.user_config_dir("okta-cli")
    config_file = osp.join(config_dir, "config.json")
    return config_file


def load_config():
    config_file = get_config_file()
    if not osp.isfile(config_file):
        raise ExitException("okta-cli was not configured. Please run with "
                            "'config new' command.")
    with open(config_file, "r") as fh:
        return _check_config(json.loads(fh.read()))


def save_config(config_to_save):
    config_file = get_config_file()
    Path(osp.dirname(config_file)).mkdir(parents=True, exist_ok=True)
    with open(config_file, "w") as fh:
        fh.write(json.dumps(config_to_save))


def get_manager():
    config = load_config()
    if "default" not in config or config["default"] not in config["profiles"]:
        raise ExitException("Default profile '{}' not configured. "
                            "Use use-profile command to change it.")
    return Okta(**config["profiles"][config["default"]])


def filter_dicts(dicts, *, filters={}, partial=False):
    if not filters:
        return dicts

    # filters dict contents:
    # key:   okta field name. CASE SENSITIVE!
    # value: regex filter / matching function compiled with
    #        with lowercase (!) input
    if not partial:
        filters = {k: re.compile(v.lower()).fullmatch
                   for k, v in filters.items()}
    else:
        filters = {k: re.compile(v.lower()).search
                   for k, v in filters.items()}

    def _match(testee):
        for k, check_func in filters.items():
            # recursive "dot lookup" from key
            desc = k.split(".")
            test_value = testee
            for k in desc:
                test_value = test_value.get(k, None)
                if test_value is None:
                    # no key? go away.
                    return False
            # user has the key? let's do an exact string match, but
            # lower case, cause we "normalize" everything to lower
            # case to get case insensitive matches.
            if not check_func(test_value.lower()):
                return False
        return True

    return filter(_match, dicts)
