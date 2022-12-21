import re
from unittest.mock import patch

from click.testing import CliRunner
import responses

from oktacli import cli
from oktacli.okta import Okta
from .testprep import prepare_standard_calls


@patch("oktacli.cli.get_manager")
@responses.activate
@prepare_standard_calls
def test_group_adduser(get_manager):
    # test data
    params0 = ["adduser", "-u", "user00", "-g", "group1"]
    wanted_result = {"test_add_user_to_group": "ok"}
    # set up test
    get_manager.return_value = Okta("http://okta", "12ab")
    runner = CliRunner()
    responses.add(
        responses.PUT,
        re.compile(".+/groups/group1/users/user00/?"),
        body="",
        status=204,
    )
    # run command
    result = runner.invoke(cli.cli_groups, params0)
    # validate
    assert result.exit_code == 0
    assert result.exception is None
