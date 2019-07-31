import json
import sys
import collections
import csv
import re
from datetime import datetime as dt
from functools import wraps
from os.path import splitext, join, isdir
from os import mkdir
from concurrent.futures import ThreadPoolExecutor, as_completed

import click
from dotted.collection import DottedDict, DottedCollection
from requests.exceptions import HTTPError as RequestsHTTPError
from openpyxl import load_workbook

from .api import load_config, save_config, get_manager, filter_users
from .okta import REST
from .exceptions import ExitException

VERSION = "7.2.0"

okta_manager = None
config = None

# https://is.gd/T1enMM
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


def _print_table_from(print_obj, fields):
    if isinstance(print_obj, dict):
        print_obj = [print_obj]
    arr = DottedCollection.factory(print_obj)
    col_lengths = []
    for col in fields:
        try:
            col_lengths.append(max([len(str(DottedDict(item)[col]))
                                    for item in arr if col in item]))
        except ValueError:
            # we don't have a "col" field or it's not used.
            # and we can't use 0 as width cause this will cause a weird
            # exception
            col_lengths.append(1)
            print(f"WARNING: field {col} either never filled or non-existant.",
                  file=sys.stderr)
    for row in arr:
        for col_idx, col in enumerate(fields):
            val = str(row[col]) if col in row else ""
            print(f"{val:{col_lengths[col_idx]}}  ", end="")
        print("")


def _dump_csv(print_obj, *, dialect=None, out=sys.stdout, fields=None):
    if isinstance(print_obj, dict):
        print_obj = [print_obj]
    # extract all the column fields from the result set
    tmp_dict = {}
    for obj in print_obj:
        tmp_dict.update(dict.fromkeys(_dict_get_dotted_keys(obj)))
    fieldlist = list(sorted(tmp_dict.keys()))
    # iterate through the list and print it
    writer = csv.DictWriter(out,
                            fieldnames=fieldlist,
                            extrasaction='ignore',
                            dialect=dialect)
    writer.writeheader()
    for obj in print_obj:
        writer.writerow(_dict_nested_to_flat(obj))


def _command_wrapper(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global okta_manager
        global config
        try:
            okta_manager = get_manager()
            rv = func(*args, **kwargs)
            if not isinstance(rv, str):
                if kwargs.get("print_json", False) is True:
                    print(json.dumps(rv, indent=2, sort_keys=True))
                elif kwargs.get("print_yaml", False) is True:
                    raise ExitException("YAML printing not (yet) implemented.")
                elif kwargs.get("print_csv", False) is True:
                    _dump_csv(rv, dialect=kwargs['csv_dialect'])
                elif "output_fields" in kwargs and len(rv) > 0:
                    _print_table_from(rv, kwargs["output_fields"].split(","))
                else:
                    # default fallback setting - print json.
                    print(json.dumps(rv, indent=2, sort_keys=True))
            else:
                print(rv)
        except ExitException as e:
            print("ERROR: {}".format(str(e)))
            sys.exit(-1)
        except Exception as e:
            print(f"SOMETHING REALLY BAD HAPPENED\n{str(type(e))}"
                  f"!\nERROR: {e}",
                  file=sys.stderr)
            sys.exit(-2)

    return wrapper


def _output_type_command_wrapper(default_fields):
    def _output_type_command_wrapper_inner(func):
        @wraps(func)
        @click.option("-j", "--json", 'print_json', is_flag=True, default=False,
                      help="Print raw YAML output")
        @click.option("--csv", "print_csv", is_flag=True, default=False,
                      help="Print output as CSV format. Will ignore "
                           "--output-fields parameter if set")
        @click.option("--csv-dialect", default='excel',
                      help="Use this CSV dialect with CSV output")
        @click.option("--output-fields",
                      default=default_fields,
                      help="Override default fields in table format")
        @_command_wrapper
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return _output_type_command_wrapper_inner


def _dict_flat_to_nested(flat_dict, defaults=None):
    """
    Takes a "flat" dictionary, whose keys are of the form "one.two.three".
    It will return a nested dictionary with this content:
    {one: {two: {three: value}}}.

    :param flat_dict: The dictionary to convert to a nested one
    :param defaults: Default values for nested dict in (with flat (!) keys)
    :return: A nested python dictionary
    """
    tmp = DottedDict()
    if defaults is None:
        defaults = {}
    for key, val in defaults.items():
        tmp[key] = val
    for key, val in flat_dict.items():
        tmp[key] = val
    return tmp.to_python()


# from here: https://stackoverflow.com/a/6027615
def _dict_nested_to_flat(nested_dict, parent_key="", sep="."):
    """
    Takes a nested dictionary and converts it into a flat one.

    Like this: `{"one": {"two": "three}}` will become `{"one.two": "three"}`

    :param nested_dict:
    :param parent_key:
    :param sep:
    :return:
    """
    items = []
    for k, v in nested_dict.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(_dict_nested_to_flat(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _dict_get_dotted_keys(dict_inst, pre_path=""):
    rv = []
    for key in dict_inst.keys():
        tmp = dict_inst[key]
        if isinstance(tmp, dict):
            rv += _dict_get_dotted_keys(tmp, pre_path + key + ".")
        else:
            rv.append(pre_path + key)
    return rv


def _okta_get_groups_by_name(name, unique=False):
    groups = okta_manager.list_groups()
    groups = list(filter(
            lambda x: x["profile"]["name"].lower().find(name.lower()) != -1,
            groups))
    if unique and len(groups) != 1:
        raise ExitException("Group name must be unique. "
                            f"(found {len(groups)} matching groups).")
    return groups


@click.group(name="config")
def cli_config():
    """Manage okta-cli configuration"""
    pass


@cli_config.command(name="new", context_settings=CONTEXT_SETTINGS)
@click.option("-n", "--name", required=True, prompt=True,
              help="Name of the configuration to add.")
@click.option("-u", "--url", required=True, prompt=True,
              help="The base URL of Okta, e.g. 'https://my.okta.com'.")
@click.option("-t", "--token", required=True, prompt=True,
              help="The API token to use")
def config_new(name, url, token):
    global config
    try:
        config = load_config()
    except ExitException:
        config = dict(
                profiles={}
        )
    config["profiles"][name] = dict(
            url=url,
            token=token,
    )
    save_config(config)
    print("Profile '{}' added.".format(name))


@cli_config.command(name="list", context_settings=CONTEXT_SETTINGS)
def config_list():
    global config
    config = load_config()
    for name, conf in config["profiles"].items():
        print("{}  {}  {}".format(name, conf["url"],
                                  "*" * 3 + conf["token"][38:]))


@cli_config.command(name="use-context", context_settings=CONTEXT_SETTINGS)
@click.argument("profile-name")
@_command_wrapper
def config_use_context(profile_name):
    global config
    config = load_config()
    if profile_name not in config["profiles"]:
        raise ExitException("Unknown profile name: '{}'.".format(profile_name))
    config["default"] = profile_name
    save_config(config)
    return "Default profile set to '{}'.".format(profile_name)


@cli_config.command(name="current-context", context_settings=CONTEXT_SETTINGS)
@_command_wrapper
def config_current_context():
    global config
    config = load_config()
    if "default" not in config:
        return "No profile set."
    return "Current profile set to '{}'.".format(config["default"])


@click.group(name="pw")
def cli_pw():
    """Manage passwords"""
    pass


@cli_pw.command(name="reset", context_settings=CONTEXT_SETTINGS)
@click.argument("login-or-id")
@click.option("-n", "--no-email", is_flag=True)
@_command_wrapper
def pw_reset(login_or_id, no_email):
    """Reset the password of a user"""
    return okta_manager.reset_password(login_or_id, send_email=not no_email)


@cli_pw.command(name="expire", context_settings=CONTEXT_SETTINGS)
@click.argument("login-or-id")
@click.option("-t", "--temp-password", is_flag=True)
@_command_wrapper
def pw_expire(login_or_id, temp_password):
    """Expire the password of a user"""
    return okta_manager.expire_password(login_or_id,
                                        temp_password=temp_password)


@click.group(name="groups")
def cli_groups():
    """Group operations"""
    pass


@cli_groups.command(name="list", context_settings=CONTEXT_SETTINGS)
@click.option("-f", "--filter", 'api_filter', default="")
@click.option("-q", "--query", 'api_query', default="")
@_output_type_command_wrapper("id,type,profile.name")
def groups_list(api_filter, api_query, **kwargs):
    """List all defined groups"""
    return okta_manager.list_groups(filter_ex=api_filter, query_ex=api_query)


@cli_groups.command(name="get", context_settings=CONTEXT_SETTINGS)
@click.argument("name-or-id")
@click.option("-i", "--id", 'use_id', is_flag=True, default=False,
              help="Use Okta group ID instead of the group name")
@_output_type_command_wrapper("id,type,profile.name")
def groups_get(name_or_id, **kwargs):
    """Print only one group"""
    return _okta_get_groups_by_name(name_or_id, unique=True)[0]


@cli_groups.command(name="adduser", context_settings=CONTEXT_SETTINGS)
@click.option("-g", "--group", required=True,
              metavar="UID",
              help="The group ID to add a user to")
@click.option("-u", "--user", required=True,
              metavar="GID",
              help="The user ID to add to the group")
@_command_wrapper
def groups_adduser(group, user, **kwargs):
    """
    Adds a user to a group.

    Note that you must use Okta's user and group IDs.
    """
    rsp = okta_manager.call_okta_raw(
            f"/groups/{group}/users/{user}",
            REST.put)
    return f"User {user} added to group {group}"


@cli_groups.command(name="removeuser", context_settings=CONTEXT_SETTINGS)
@click.option("-g", "--group", required=True,
              metavar="UID",
              help="The group ID to add a user to")
@click.option("-u", "--user", required=True,
              metavar="GID",
              help="The user ID to remove from the group")
@_command_wrapper
def groups_removeuser(group, user, **kwargs):
    """
    Removes a user from a group.

    Note that you must use Okta's user and group IDs.
    """
    rsp = okta_manager.call_okta_raw(
            f"/groups/{group}/users/{user}",
            REST.delete)
    return f"User {user} removed from group {group}"


@cli_groups.command(name="users", context_settings=CONTEXT_SETTINGS)
@click.argument("name-or-id")
@click.option("-i", "--id", 'use_id', is_flag=True, default=False,
              help="Use Okta group ID instead of the group name")
@_output_type_command_wrapper("id,profile.firstName,profile.lastName,"
                              "profile.email")
def groups_list_users(name_or_id, use_id, **kwargs):
    """List all users in a group"""
    if not use_id:
        name_or_id = _okta_get_groups_by_name(name_or_id, unique=True)[0]["id"]
    return okta_manager.call_okta(f"/groups/{name_or_id}/users", REST.get)


@cli_groups.command(name="clear", context_settings=CONTEXT_SETTINGS)
@click.argument("name-or-id")
@click.option("-i", "--id", 'use_id', is_flag=True, default=False,
              help="Use Okta group ID instead of the group name")
@_command_wrapper
def groups_clear(name_or_id, use_id):
    """Remove all users from a group.

    This can take a while if the group is big."""
    if not use_id:
        name_or_id = _okta_get_groups_by_name(name_or_id, unique=True)[0]["id"]
    users = okta_manager.call_okta(f"/groups/{name_or_id}/users", REST.get)
    for user in users:
        user_id = user['id']
        user_login = user['profile']['login']
        print(f"Removing user {user_login} ... ", file=sys.stderr, end="")
        path = f"/groups/{name_or_id}/users/{user_id}"
        okta_manager.call_okta_raw(path, REST.delete)
        print("ok", file=sys.stderr)
    return "All users removed"


@click.group(name="apps")
def cli_apps():
    """Application operations"""
    pass


@cli_apps.command(name="list", context_settings=CONTEXT_SETTINGS)
@click.argument("partial_name", required=False, default=None)
@click.option("-f", "--filter", 'api_filter', default="")
@_output_type_command_wrapper("id,name,label")
def apps_list(api_filter, partial_name, **kwargs):
    """List all defined applications. If you give an optional command line
    argument, the apps are filtered by name using this string."""
    params = {}
    if api_filter:
        params = {"filter": api_filter}
    rv = okta_manager.call_okta("/apps", REST.get, params=params)
    # now filter by name, if given
    if partial_name:
        matcher = re.compile(partial_name)
        rv = list(filter(lambda x: matcher.search(x["name"]), rv))
    return rv


@cli_apps.command(name="users", context_settings=CONTEXT_SETTINGS)
@click.argument("app_id")
@click.option("-i", "--id", "use_id", is_flag=True,
              help="Use Okta app ID instead of app name")
@_output_type_command_wrapper("id,syncState,credentials.userName")
def apps_users(app_id, use_id, **kwargs):
    """List all users for an application"""
    if not use_id:
        apps = okta_manager.call_okta("/apps", REST.get)
        matcher = re.compile(app_id.lower())
        apps = list(filter(lambda x: matcher.search(x["name"].lower()), apps))
        if len(apps) != 1:
            raise ExitException(f"Found {len(apps)} matching apps. Must be 1!")
        use_app_id = apps[0]["id"]
    else:
        use_app_id = app_id
    return okta_manager.call_okta(f"/apps/{use_app_id}/users", REST.get)


@click.group(name="users")
def cli_users():
    """Add, update (etc.) users"""
    pass


@cli_users.command(name="list", context_settings=CONTEXT_SETTINGS)
@click.option("-m", "--match", 'matches', multiple=True)
@click.option("-p", "--partial", is_flag=True,
              help="Accept partial matches for match queries.")
@click.option("-f", "--filter", 'api_filter', default="")
@click.option("-s", "--search", 'api_search', default="")
@_output_type_command_wrapper("id,profile.login,profile.firstName,"
                              "profile.lastName,profile.email")
def users_list(matches, partial, api_filter, api_search, **kwargs):
    """Lists users (all or using various filters)"""
    users = okta_manager.list_users(
            filter_query=api_filter,
            search_query=api_search)
    filters_dict = {k: v for k, v in map(lambda x: x.split("="), matches)}
    return list(filter_users(users, filters=filters_dict, partial=partial))


@cli_users.command(name="get", context_settings=CONTEXT_SETTINGS)
@click.argument('login_or_id')
@click.option("-i", "--use-id", 'use_id', is_flag=True,
              help="Search by Okta ID instead of login field")
@_output_type_command_wrapper("id,profile.login,profile.firstName,"
                              "profile.lastName,profile.email")
def users_get(login_or_id, use_id, **kwargs):
    """List ONE user by login or Okta ID"""
    if use_id:
        rv = okta_manager.call_okta(f"/users/{login_or_id}", REST.get)
    else:
        query = f'profile.login eq "{login_or_id}"'
        rv = okta_manager.list_users(filter_query=query)
    return rv


@cli_users.command(name="groups", context_settings=CONTEXT_SETTINGS)
@click.argument("name-or-id")
@_output_type_command_wrapper("id,profile.name,profile.description")
def users_list_groups(name_or_id, **kwargs):
    """List all users in a group"""
    return okta_manager.call_okta(f"/users/{name_or_id}/groups", REST.get)


@cli_users.command(name="deactivate", context_settings=CONTEXT_SETTINGS)
@click.argument('login_or_id')
@click.option("-e", "--send-email", is_flag=True,
              help="Send email to admins if set")
@click.option("--no-confirmation", is_flag=True,
              help="Don't ask - DANGER!!")
@_command_wrapper
def users_deactivate(login_or_id, send_email, no_confirmation):
    """Deactivate a user (DESTRUCTIVE OPERATION)"""
    if not no_confirmation:
        check = input("DANGER!! Do you REALLY want to do this "
                      "(maybe use 'suspend' instead)?\n"
                      f"Then enter '{login_or_id}': ")
        if check != login_or_id:
            raise ExitException("Aborted.")
    okta_manager.deactivate_user(login_or_id, send_email)
    return f"User {login_or_id} deactivated."


@cli_users.command(name="unlock", context_settings=CONTEXT_SETTINGS)
@click.argument('login_or_id')
@_command_wrapper
def users_unlock(login_or_id):
    """Unlock a locked user"""
    okta_manager.call_okta(f"/users/{login_or_id}/lifecycle/unlock", REST.post)
    return f"User '{login_or_id}' unlocked."


@cli_users.command(name="delete", context_settings=CONTEXT_SETTINGS)
@click.argument('login_or_id')
@click.option("-e", "--send-email", is_flag=True,
              help="Send email to admins if set")
@click.option("--no-confirmation", is_flag=True,
              help="Don't ask - DANGER!!")
@_command_wrapper
def users_delete(login_or_id, send_email, no_confirmation):
    """Delete a user (DESTRUCTIVE OPERATION)"""
    if not no_confirmation:
        check = input("DANGER!! Do you REALLY want to do this?\n"
                      f"Then enter '{login_or_id}': ")
        if check != login_or_id:
            raise ExitException("Aborted.")
    okta_manager.delete_user(login_or_id, send_email)
    # .delete_user() does not return anything
    return f"User {login_or_id} deleted."


@cli_users.command(name="suspend", context_settings=CONTEXT_SETTINGS)
@click.argument('login_or_id')
@_command_wrapper
def users_suspend(login_or_id):
    """Suspend a user"""
    path = f"/users/{login_or_id}/lifecycle/suspend"
    rv = okta_manager.call_okta(path, REST.post)
    return rv


@cli_users.command(name="update", context_settings=CONTEXT_SETTINGS)
@click.argument('user_id')
@click.option('-s', '--set', 'set_fields', multiple=True)
@click.option('-c', '--context', default=None,
              help="Set a context (profile, credentials) to save typing")
@_command_wrapper
def users_update(user_id, set_fields, context):
    """Update a user object. see https://is.gd/DWHEvA for details.

    This is equivalent:

    \b
    okta-cli users update 012345 -s profile.lastName=Doe
    okta-cli users update 012345         -s lastName=Doe -c profile

    EXAMPLE: Update a profile field:

    \b
    okta-cli users update 012345 \\
       -s profile.email=me@myself.com

    EXAMPLE: Set a new password:

    \b
    okta-cli users update 012345 \\
       -s credentials.password.value="SoopaS3cret!"

    EXAMPLE: Update a recovery question:

    \b
    okta-cli users update 012345 \\
       -p credentials.recovery_question \\
       -s question="Who let the dogs out?" \\
       -s answer="Me."
    """
    fields_dict = {k: v for k, v in map(lambda x: x.split("=", 1), set_fields)}
    if context:
        fields_dict = {context + "." + k: v for k, v in fields_dict.items()}
    nested_dict = _dict_flat_to_nested(fields_dict)
    return okta_manager.update_user(user_id, nested_dict)


@cli_users.command(name="bulk-update", context_settings=CONTEXT_SETTINGS)
@click.argument('file')
@click.option('-s', '--set', 'set_fields', multiple=True,
              help="Set default field values for updates")
@click.option('-i', '--jump-to-index', metavar="IDX",
              default=0,
              help="Start with index IDX (0-based) and skip previous entries")
@click.option('-u', '--jump-to-user', metavar="USER_ID",
              default=None,
              help="Same as --jump-to-index, but starts from a specific user "
                   "ID instead of an index")
@click.option('-l', '--limit', metavar="NUM",
              default=0,
              help="Stop after NUM updates")
@click.option('-w', '--workers', metavar="NUM",
              default=25,
              help="use this many threads parallel, default:25")
@_command_wrapper
def users_bulk_update(file, set_fields, jump_to_index, jump_to_user, limit,
                      workers):
    """
    Bulk-update users from a CSV or Excel (.xlsx) file.

    Note that the CSV file *must* contain a "profile.login" OR an "id"
    column.
    """

    def excel_reader():
        wb = load_workbook(filename=file)
        rows = wb.active.rows

        # Get the header values as keys and move the iterator to the next item
        keys = [c.value for c in next(rows)]
        num_keys = len(keys)
        for row in rows:
            values = [c.value for c in row]
            rv = dict(zip(keys, values[:num_keys]))
            if any(rv.values()):
                yield rv

    def csv_reader():
        with open(file, "r", encoding="utf-8") as infile:
            dialect = csv.Sniffer().sniff(infile.read(4096))
            infile.seek(0)
            dr = csv.DictReader(infile, dialect=dialect)
            for row in dr:
                if any(row.values()):
                    yield row

    def file_reader():
        dr = excel_reader() \
            if splitext(file)[1].lower() == ".xlsx" else csv_reader()
        if jump_to_user:
            tmp = next(dr)
            while jump_to_user not in (tmp.get("profile.login", ""), tmp.get("id", "")):
                tmp = next(dr)
        elif jump_to_index:
            # prevent both being used at the same time :)
            for _ in range(jump_to_index):
                next(dr)
        _cnt = 0
        for row in dr:
            if limit and _cnt == limit:
                break
            yield row
            _cnt += 1

    def update_user_parallel(_row, index):
        # this is a closure, let's use the outer scope's variables
        for field in ("profile.login", "id"):
            if field in _row:
                user_id = _row.pop(field)
        # you can't set top-level fields. pop all of them.
        _row = {k: v for k, v in _row.items() if k.find(".") > -1}
        # fields_dict - from outer scope.
        final_dict = _dict_flat_to_nested(_row, defaults=fields_dict)
        try:
            upd_ok.append(okta_manager.update_user(user_id, final_dict))
        except RequestsHTTPError as e:
            upd_err.append((index + jump_to_index, final_dict, str(e)))

    print("Bulk update might take a while. Please be patient.", flush=True)

    upd_ok = []
    upd_err = []
    fields_dict = {k: v for k, v in map(lambda x: x.split("="), set_fields)}
    dr = file_reader()

    with ThreadPoolExecutor(max_workers=workers) as ex:
        runs = {idx: ex.submit(update_user_parallel, row, idx)
                for idx, row in enumerate(dr)}
        for job in as_completed(runs.values()):
            pass

    print(f"{len(runs)} - done.", file=sys.stderr)
    tmp = {"ok": upd_ok, "errors": upd_err}
    timestamp_str = dt.now().strftime("%Y%m%d_%H%M%S")
    rv = ""
    for name, results in tmp.items():
        if len(results):
            file_name = f"okta-bulk-update-{timestamp_str}-{name}.json"
            with open(file_name, "w") as outfile:
                outfile.write(json.dumps(results, indent=2, sort_keys=True))
                rv += f"{len(results):>4} {name:6} - {file_name}\n"
        else:
            rv += f"{len(results):>4} {name:6}\n"
    return rv + f"{len(upd_ok) + len(upd_err)} total"


@cli_users.command(name="add", context_settings=CONTEXT_SETTINGS)
@click.option('-s', '--set', 'set_fields', multiple=True)
@click.option('-r', '--read-csv', help="Read from CSV file", default=None)
@click.option('-a', '--activate/--no-activate',
              help="Set 'activation' flag, see Okta API docs")
@click.option('-p', '--provider/--no-provider',
              help="Set 'provider' flag, see Okta API docs")
@click.option('-n', '--nextlogin/--no-nextlogin',
              help="Set 'nextLogin' to 'changePassword', see Okta API docs")
@_command_wrapper
def users_add(set_fields, read_csv, activate, provider, nextlogin):
    """Add a user to Okta"""
    # first use and clean the fields dict from the command line
    fields_dict = {k: v for k, v in map(lambda x: x.split("="), set_fields)}
    # query parameters
    params = {}
    # set the flags
    if activate:
        params['activate'] = str(activate).upper()
    if provider:
        params['provider'] = str(provider).upper()
    if nextlogin:
        params['nextlogin'] = "changePassword"
    # when reading from csv, we iterate
    if read_csv:
        added = []
        with open(read_csv, "r", encoding="utf-8") as infile:
            dialect = csv.Sniffer().sniff(infile.read(4096))
            infile.seek(0)
            dr = csv.DictReader(infile, dialect=dialect)
            for row in dr:
                final_dict = _dict_flat_to_nested(
                        row, defaults=fields_dict)
                added.append(okta_manager.add_user(params, final_dict))
        return added
    # when creating directly, we don't :)
    else:
        final_dict = _dict_flat_to_nested(fields_dict)
        return okta_manager.add_user(params, final_dict)


@click.group(context_settings=CONTEXT_SETTINGS)
def cli_main():
    """
    Okta CLI helper.

    See subcommands for help: "okta-cli users --help" etc.

    If in doubt start with: "okta-cli config new --help"
    """
    pass


@cli_main.command(name="dump", context_settings=CONTEXT_SETTINGS)
@click.option('-d', '--dir', 'target_dir',
              help="Save in this directory", default=None)
@click.option("--no-user-list", is_flag=True)
@click.option("--no-app-users", is_flag=True)
@click.option("--no-group-users", is_flag=True)
@_command_wrapper
def cli_version(target_dir, no_user_list, no_app_users, no_group_users):
    """Dumps users, groups and applications (incl. users) into CSV files"""

    def save_in(save_dir, save_file, obj):
        if not isdir(save_dir):
            mkdir(save_dir)
        final_file = join(save_dir, save_file)
        with open(final_file, "w") as outfile:
            _dump_csv(obj, out=outfile)

    def save_in_csv(save_dir, save_file, obj, headers):
        if not isdir(save_dir):
            mkdir(save_dir)
        final_file = join(save_dir, save_file)
        with open(final_file, "w") as outfile:
            writer = csv.writer(outfile)
            writer.writerow(headers)
            for row in obj:
                writer.writerow(row)

    def get_users_for(obj_list, rest_path, workers=1):
        table = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            runs = {
                ex.submit(okta_manager.call_okta,
                          f"/{rest_path}/{obj['id']}/users",
                          REST.get,
                          params={"limit": 1000}):
                obj["id"]
                for obj in obj_list}
            for result in runs:
                gid = runs[result]
                table += [(gid, u["id"]) for u in result.result()]
        return table

    default_workers = 25

    if target_dir is None:
        target_dir = dt.strftime(dt.now(), "okta-dump-%Y%m%d%H%M%S")

    print("Please be patient, this can several minutes.")

    if no_user_list:
        print("Skipping list of users.")
    else:
        print("Saving user list ... ", end="", flush=True)
        dump_me = okta_manager.list_users()
        save_in(target_dir, "users.csv", dump_me)
        print("done.")

    for func, what, no_detail in (
            (okta_manager.list_groups, "group", no_group_users),
            (okta_manager.list_apps, "app", no_app_users)
    ):
        print(f"Saving {what} list ... ", end="", flush=True)
        dump_me = func()
        save_in(target_dir, f"{what}s.csv", dump_me)
        print("done.")

        if no_detail:
            print(f"Skipping list of {what} users.")
        else:
            print(f"Saving {what} users ... ", end="", flush=True)
            table = get_users_for(dump_me, f"{what}s", workers=default_workers)
            save_in_csv(target_dir, f"{what}_users.csv", table, (what, "user"))
            print("done.")


@cli_main.command(name="version", context_settings=CONTEXT_SETTINGS)
def cli_version():
    """Prints version number and exit"""
    print(VERSION)


cli_main.add_command(cli_config)
cli_main.add_command(cli_users)
cli_main.add_command(cli_pw)
cli_main.add_command(cli_groups)
cli_main.add_command(cli_apps)
