# Okta-CLI

This is a python-based CLI tool for Okta. **It is not made or maintained by or in any way affiliated with anyone working at Okta.** It is mainly driven by the personal needs of its author, although the feature set is becoming quite complete now.

It basically is a CLI wrapper around the [Okta REST API](https://developer.okta.com/docs/reference/).

## Requirements

_REQUIRES_ Python 3.6+

## Quickstart

Every more complex function should have help texts available: `okta-cli users add -h`, or maybe `okta-cli users update -h` or maybe `okta-cli apps add -h` ... those are probably the most interesting ones.

```bash
$ pip install okta-cli
$ okta-cli config new -n my-profile -u https://my.okta.url -t API_TOKEN
$ okta-cli users list -f 'profile.email eq "my@email.com"'
$ okta-cli features list
$ okta cli users groups adduser -g app1_rollout -u fred.flintstone@flintstones.com
$ okta-cli apps adduser -a my_app_name -u 0109121 -f profile.employeeId
$ okta-cli users update id012345678 --set profile.email=my@other.email.com
$ okta-cli users bulk-update update-list.xlsx        # CSV is okay as well :)
$ okta-cli version
```

## Configuration

Running `config new` (see above) will store a JSON configuration file in the directory determined by the `appdirs` module.

## References

This project uses a few nice other projects:

- [Click](https://click.palletsprojects.com)
- [Dotted](https://pypi.org/project/dotted/)
- [appdirs](https://pypi.org/project/appdirs/)
