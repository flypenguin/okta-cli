import re
from unittest.mock import patch

from click.testing import CliRunner
import responses

from oktacli import cli
from oktacli.okta import Okta
from .testdata import okta_user_schema


def _prep_schema_response(func):
    def wrapped(*args, **kwargs):
        responses.add(
            responses.GET,
            "http://okta/api/v1/meta/schemas/user/default/",
            json=okta_user_schema,
            status=200,
        )
        return func(*args, **kwargs)

    return wrapped


@patch("oktacli.cli.get_manager")
@responses.activate
@_prep_schema_response
def test_user_update(get_manager):
    # test data
    params0 = ["update", "myuser", "-s", "profile.abool=true"]
    # set up test
    get_manager.return_value = Okta("http://okta", "12ab")
    runner = CliRunner()
    responses.add(
        responses.POST,
        re.compile(".+/users/[0-9a-z]+$"),
        json={"test": "ok"},
        status=200,
    )
    # run command
    result = runner.invoke(cli.cli_users, params0)
    # validate
    assert result.exit_code == 0
    assert result.exception is None
