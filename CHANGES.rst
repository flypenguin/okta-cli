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
