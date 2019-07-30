# Okta-CLI

This is a python-based CLI tool for Okta. **It is not made or maintained by or in any way affiliated with anyone working at Okta.**

The feature set is quite complete, but based on the authors needs, which currently are:

- user functions
  - list users (using API `search=` and `query=` functionality, and local filtering)
  - update users
  - bulk-update users, with parallel threads (hundreds of updates in seconds)
- group functions (add users, remove users, list groups, list members)

## NOTE

_REQUIRES_ Python 3.6+

## Quickstart

```bash
$ pip install okta-cli
$ okta-cli config new -n my-profile -u https://my.okta.url -t API_TOKEN
$ okta-cli users list -f 'email eq "my@email.com"'
$ okta-cli users update id012345678 --set email=my@other.email.com --set phone=01234/5678
$ okta-cli users bulk-update update-list.xlsx        # CSV is okay as well :)
$ okta-cli groups adduser -g 01231324 -u 0129353892
$ okta-cli groups removeuser -g ... -u ...
```

## References

This project uses a couple of nice other projects:

- [Click](https://click.palletsprojects.com)
- [Dotted](https://pypi.org/project/dotted/)
