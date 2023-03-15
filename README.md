# Okta-CLI

**NOW WITH HOMEBREW TAP ON A MAC - SEE "INSTALLATION" BELOW :))**

This is a python-based CLI tool for Okta.
**It is not made or maintained by or in any way affiliated with anyone working at Okta.**
It is mainly driven by the personal needs of its author, although the feature set is becoming quite complete now.

It basically is a CLI wrapper around the [Okta REST API](https://developer.okta.com/docs/reference/).

**NOTE:** This is _not_ the same as Okta's own [`okta`](https://cli.okta.com/) CLI interface.
The latter is apparently used for setting up the source for development projects.

## Requirements

- A Mac or Linux machine, it _might_ work on Windows (untested)
- Python 3.7+, for the change log see [CHANGES.rst](CHANGES.rst).
- unfortunately **Python 3.11 is not _yet_ supported** due to a dependency.

## Installation

### Mac & homebrew

```bash
brew tap flypenguin/okta-cli
brew install okta-cli
```

### All others

- create a python virtualenv: `mkvirtualenv okta-cli`
- `pip install okta-cli`
- start using it: `okta-cli config new`

## Quickstart

Every more complex function should have help texts available: `okta-cli users add -h`, or maybe `okta-cli users update -h` or maybe `okta-cli apps add -h` ... those are probably the most interesting ones.

```bash
$ pip install okta-cli                                # install :)
$ okta-cli config new \                               # create a new okta profile
           -n my-profile -\
           -u https://my.okta.url \
           -t API_TOKEN
$ okta-cli users list \                               # search users with a query
           -f 'profile.email eq "my@email.com"'
$ okta-cli features list                              # list okta server-side features
$ okta-cli features enable "Recent Activity"          # enable an Okta feature
$ okta cli users groups adduser \                     # add a user to a group
           -g app1_rollout \
           -u fred.flintstone@flintstones.com
$ okta-cli apps adduser \                             # assign an app to a user
           -a my_app_name -u 0109121 \
           -f profile.employeeId
$ okta-cli users update id012345678 \                 # update a field of a user record
           --set profile.email=my@other.email.com
$ okta-cli users bulk-update update-list.xlsx         # CSV is okay as well :)
$ okta-cli version                                    # print version and exit
$ okta-cli users get my-login -vvvvv                  # see http debug output
```

## Configuration

Running `config new` (see above) will store a JSON configuration file in the directory determined by the `appdirs` module.

## References

This project uses a few nice other projects:

- [Click](https://click.palletsprojects.com)
- [appdirs](https://pypi.org/project/appdirs/)
