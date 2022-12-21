import responses
from .testdata import okta_user_schema
from .testdata import okta_groups_list


def prepare_standard_calls(func):
    def wrapped(*args, **kwargs):
        responses.add(
            responses.GET,
            "http://okta/api/v1/meta/schemas/user/default/",
            json=okta_user_schema,
            status=200,
        )
        responses.add(
            responses.GET,
            "http://okta/api/v1/groups/",
            json=okta_groups_list,
            status=200,
        )
        return func(*args, **kwargs)

    return wrapped
