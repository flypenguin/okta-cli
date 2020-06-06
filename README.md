# Okta-CLI

This is a python-based CLI tool for Okta. **It is not made or maintained by or in any way affiliated with anyone working at Okta.**

The feature set is quite complete, but based on the author's needs, which currently are:

- user functions
  - list users (using API `search=` and `query=` functionality, and local filtering)
  - update users
  - bulk-update users, with parallel threads (hundreds of updates in seconds)
- group functions (add users, remove users, list groups, list members)
- handling of multiple Okta instances (e.g. a test cell, a production cell, a personal cell, ...)
- updates and (now really fast) bulk-updates of user profiles (using CSV or Excel files)
- export of profile data (into CSV or JSON)

## NOTE

_REQUIRES_ Python 3.6+

## Quickstart

```bash
$ pip install okta-cli
$ okta-cli config new -n my-profile -u https://my.okta.url -t API_TOKEN
$ okta-cli users list -f 'profile.email eq "my@email.com"'
$ okta-cli users update id012345678 --set email=my@other.email.com --set phone=01234/5678
$ okta-cli users bulk-update update-list.xlsx        # CSV is okay as well :)
$ okta-cli groups adduser -g 01231324 -u 0129353892
$ okta-cli groups removeuser -g ... -u ...
```

## Config

Running `config new` (see above) will store a JSON configuration file
in the directory determined by the `appdirs` module.

## References

This project uses a few nice other projects:

- [Click](https://click.palletsprojects.com)
- [Dotted](https://pypi.org/project/dotted/)
- [appdirs](https://pypi.org/project/appdirs/)
