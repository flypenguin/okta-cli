# Okta-CLI

This is a python-based CLI tool for Okta. **It is not made or maintained by or in any way affiliated with anyone working at Okta.**

The current featureset is purely based on the author's needs, which currently are:

* list users (using API `search=` and `query=` functionality, and local filtering)
* update users

## Quickstart

```bash
$ pip install okta-cli (NOT YET WORKING CAUSE NOT YET PUBLISHED SORRY :)
$ okta-cli config new -n my-profile -u https://my.okta.url -t API_TOKEN
$ okta-cli users list -f 'email eq "my@email.com"'
$ okta-cli users update id012345678 --set email=my@other.email.com --set phone=01234/5678
```

## References

This project uses a couple of nice other projects:

* [Click](https://click.palletsprojects.com)
* [Dotted](https://pypi.org/project/dotted/)
