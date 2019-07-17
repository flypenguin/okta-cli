v7.1.0
======

* parallelize user bulk-update calls to be much faster

v7.0.2
======

* (invisible) some internal updates
* bulk-update prints final number of upd. users at the end

v7.0.1
======

* (invisible) update internal communications path for querying okta

v7.0.0
======

* write output of bulk-update to log files instead of stdout

v6.0.0
======

* rename "users update-csv" to "users bulk-update"

v5.2.0
======

* add excel file reading for 'users update-csv'

v5.1.0
======

* add 'groups removeuser' command
* add 'users groups' command

v5.0.1
======

* add missing changes docs for 5.0.0 (everything below is 5.0.0)
* add 'groups adduser' command
* remove filter expression convenience optimizer (major bump)
* various internal fixes

v4.0.1
======

* fix bug in CSV output (was "" for all nested fields, e.g. "profile.login")

v4.0.0
======

* add CSV output
* rename --text-fields parameter to --output-fields

v3.0.1
======

* internal change in handling "--json/--text-fields" parameters
* fix missing import (which shouldn't be there)

3.0.0
======

* add table output to some commands and make it default
* fix wrongly named "--yaml" parameter (now "--json")
* add command 'users unlock'
* fix bug in tabular output for non-existing / unfilled fields

v2.3.1
======

* make -h work everywhere
* fix users delete / deactivate commands

v2.3.0
======

* add 'groups users' command
* add 'groups clear' command

v2.2.0
======

* add 'users get' command (lists ONE user by login or Okta ID)
* add 'users deactivate' command
* add 'users suspend' command
* add 'users delete' command
* add 'pw expire' command which expires a password of a user

v2.1.0
======

* add 'users update-csv' command
* add 'groups list' command
* add 'apps list' command
* add 'apps users' command

v2.0.0
======

* 'users update' can now update all fields, including security question and
  password (BREAKING CHANGE)
* add 'pw reset' command

v1.0.2
======

* update quickstart docs (did still say "pip install" would not work,
  it does now :)

v2.3.1
======

* make -h work everywhere
* fix users delete / deactivate commands

v2.3.0
======

* add 'groups users' command
* add 'groups clear' command

v2.2.0
======

* add 'users get' command (lists ONE user by login or Okta ID)
* add 'users deactivate' command
* add 'users suspend' command
* add 'users delete' command
* add 'pw expire' command which expires a password of a user

v2.1.0
======

* add 'users update-csv' command
* add 'groups list' command
* add 'apps list' command
* add 'apps users' command

v2.0.0
======

* 'users update' can now update all fields, including security question and
  password (BREAKING CHANGE)
* add 'pw reset' command

v1.0.2
======

* update quickstart docs (did still say "pip install" would not work,
  it does now :)

v1.0.1
======

* add help texts in setup.py
