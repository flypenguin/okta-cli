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
    # now, check if the "active" config exists. we might have deleted it ...
    if config["default"] not in config["profiles"]:
        raise ExitException("Default profile '{}' not configured. "
                            "Use use-profile command to change it.")
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


def get_manager(profile="default"):
    config = load_config()
    return Okta(**config["profiles"][config[profile]])


def filter_users(user_list, *, filters={}, partial=False):
    if not filters:
        return user_list

    if not partial:
        filters = {k: re.compile(v).fullmatch for k, v in filters.items()}
    else:
        filters = {k: re.compile(v).search for k, v in filters.items()}

    def _match(user):
        for k, check_func in filters.items():
            user_value = user["profile"].get(k, None)
            # user does not have the key? go away.
            if user_value is None:
                return False
            # user has the key? let's do an exact string match
            if not check_func(user_value):
                return False
        return True

    return filter(_match, user_list)
