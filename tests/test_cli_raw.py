import re
from unittest.mock import patch

from click.testing import CliRunner
import responses

from oktacli import cli
from oktacli.okta import Okta
from .testprep import prepare_standard_calls


@patch("oktacli.cli.get_manager")
@responses.activate
def test_raw_accept_header(get_manager):
    # test data
    params0 = ["raw", "-H", "Accept: application/xml", "-H", "Some: header", "some/endpoint"]
    wanted_result = {"test_add_user_to_group": "ok"}
    # set up test
    get_manager.return_value = Okta("http://okta", "12ab")
    runner = CliRunner()
    responses.add(
        responses.GET,
        re.compile(".+/some/endpoint/?"),
        body="",
        status=204,
        match=[responses.matchers.header_matcher({"Accept": "application/xml", "Some": "header"})],
    )
    # run command
    result = runner.invoke(cli.cli_main, params0)
    # validate
    assert result.exit_code == 0, result.stdout
    assert result.exception is None
