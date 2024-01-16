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

Every more complex function should have help texts available: `okta-cli users add -h`, or
maybe `okta-cli users update -h` or maybe `okta-cli apps add -h` ... those are probably the
most interesting ones.

```bash
$ pip install okta-cli                                # install :)

$ okta-cli config new \                               # create a new okta profile
           -n my-profile -\
           -u https://my.okta.url \
           -t API_TOKEN

$ okta-cli -h                                         # get help

$ okta-cli apps -h                                    # get help
$ okta-cli apps adduser \                             # assign an app to a user
           -a my_app_name -u 0109121 \
           -f profile.employeeId

$ okta-cli users -h                                   # get help
$ okta-cli users list --csv                           # list all users as csv
$ okta-cli users list \                               # search users with a query
           -f 'profile.email eq "my@email.com"'
$ okta-cli users update id012345678 \                 # update a field of a user record
           --set profile.email=my@other.email.com
$ okta cli users groups adduser \                     # add a user to a group
$ okta-cli users get my-login -vvvvv                  # see http debug output
$ okta-cli users bulk-add add-list.csv                # Bulk-ADD users
$ okta-cli users bulk-update update-list.xlsx         # Bulk-UPDATE users

$ okta-cli features -h                                # get help
$ okta-cli features list                              # list okta server-side features
$ okta-cli features enable "Recent Activity"          # enable an Okta feature
           -g app1_rollout \
           -u fred.flintstone@flintstones.com

$ okta-cli version                                    # print version and exit
```

## Configuration

Running `config new` (see above) will store a JSON configuration file in the directory determined by the `appdirs` module.

## CSV / Excel file formats

The commands `bulk-add` and `bulk-update` can read from CSV or Excel. Consider this:

**CSV:**

* the first line _MUST_ be a header line (yes, also in Excel).
* for the command `bulk-add` there _MUST_ be a `profile.login` column, and there _MUST NOT_ be an `id` column.
* for the command `bulk-update` there _MUST_ be either a `profile.login` or an `id` column, the latter has preference.
* all other will most probably refer to profile fields, and map to the add/update API call.
  * most probably you will want to have `profile.FIELD` columns (e.g. `profile.firstName`, `profile.zipCode`, ...).
  * you can see the valid standard field names here: https://developer.okta.com/docs/reference/api/schemas/#user-profile-base-subschema.
* all columns which do not contain a "." are _ignored_.

**Excel:**

* There _MUST NOT_ be any formulas.
* Behavior with more than one sheet is undefined.
* Apart from that, be aware of number formatting, which is _most probably_ not respected by `okta-cli`.
* Otherwise, the same restrictions as for csv files apply.

**Remarks:**

* Some fields have value limitations on the Okta side
  * e.g. `profile.preferredLanguage` must be a valid two-letter country code

**Example:**

In this example, the columns "country" and "gender" are ignored – their name does not contain a ".".

```csv
profile.login,profile.firstName,profile.lastName,profile.email,gender,profile.streetAddress,profile.zipCode,profile.city,country,profile.countryCode
ibrabben0@prlog.org,Iosep,Brabben,ibrabben0@prlog.org,Male,7931 Division Point,86983 CEDEX,Futuroscope,France,FR
```

(those fields are not part of Okta's standard field set, and this is an easy way to exclude columns from being used)

### CSV files with only one column

If for any reason you want to create a CSV file with only one column, do it like this:

```csv
profile.login,
my@email.com,
```

Note the trailing comma.

Reasoning: `okta-cli` tries to determine the column separator, and without one ... determination is tricky, and `okta-cli` will shamelessly crash.

## References

This project uses a few nice other projects:

- [Click](https://click.palletsprojects.com)
- [appdirs](https://pypi.org/project/appdirs/)
