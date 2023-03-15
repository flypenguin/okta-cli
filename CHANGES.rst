v18.0.3
=======

* add missing "six" dependency

v18.0.2
=======

* also build source distribution for pypi
* update my email :)
* internal "build system" fixes

v18.0.1
=======

* fix missing dotted library in published pypi lib (thanks to @sanitybit for pointing it out)

v18.0.0
=======

* Require Python >= 3.7 (mainly because of responses package)
* Inline dotted library, make compatible with Python 3.10
  (original library is no longer maintained it seems)

v17.3.1
=======

* make 'https://' mandatory for Okta URLs
* fix 'config COMMAND' crashes on wrongly or unconfigured default contexts

v17.3.0
=======

* add command 'groups apps' (PR by bousquf)
* add command 'user reactivate' (PR by josephbreihan)

v17.2.0
=======

* add parameter "-A" (array update) for "users update"

v17.1.0
=======

* Added logging basics. use "-vvvvv" for detailed http dumps

v17.0.0
=======

* [BREAKING] check for 'id' before profile.login when mass-updating profiles. enables update-possibility of the login field
  * Thanks @techjutsu-mikeb

v16.0.0
=======

* [BREAKING] expire passwords from 'pw set' by default
* update cli help texts
* print more error information on okta API errors

v15.1.0
=======

* fix commands 'user pw {reset,expire}'
* update text output of 'apps users'
* add command 'apps groups'
* add command 'apps removegroup'
* add command 'apps addgroup'
* add nicer error handling and output, especially for okta api errors
* add user STATUS field to default output for "users {get,list}"
* fix broken fuzzy lookup

v15.0.0
=======

* unify behavior of 'users groups'
* add command 'users apps'
* add command 'features list'
* add command 'features enable'
* add command 'features disable'
* add command 'features dependents'
* add command 'features dependencies'
* add "--colwidth" parameter to table output
* use sorted output now for functions returning lists
* various output changes
* various fixes, some breaking functionality

v14.3.0
=======

* add command 'users activate'

v14.2.1
=======

* remove debug output

v14.2.0
=======

* perform case-insensitive user searches for 'users list'
* update 'users list', add "-q", "-d" parameters

v14.1.0
=======

* (MINOR) adjust (and enhance) 'groups list' command to behave like 'apps list', specifically in regards to the partial name filtering
* unify case-insensitive filtering

v14.0.1
=======

* fix several internal bugs which broke 'pw reset', 'pw expire' and 'users add'

v14.0.0
=======

* [BREAKING] update 'apps list' command
* add command 'apps get'

v13.0.0
=======

* [BREAKING] update 'raw' command

v12.0.0
=======

* [BREAKING] update 'apps users' semantics to match the rest of the commands
* add command 'apps adduser'
* add command 'apps getuser'
* add command 'apps removeuser'

v11.4.1
=======

* fixed that 'groups delete' would find non-"OKTA_GROUP" groups

v11.4.0
=======

* internal code cleanup
* change and unify text output of a couple of methods
* probably removed some bugs

v11.3.0
=======

* same as 11.1.0

v11.2.0
=======

* same as 11.1.0

v11.1.0
=======

* 'apps list' - add '-m' parameter to match a specific field
* 'apps list' - add '-q' parameter to pass query parameter to okta API
* fix ugly bug breaking a bunch of methods
* fix 'groups adduser' output
* fix 'users add' command
* fix some docs

v11.0.0
=======

* many commands are now "smart" and filter things (groups, apps) by name and users by field

v10.0.1
=======

* fix help output for 'groups adduser' (PR from @dhutty-numo, thanks)

v10.0.0
=======

* change and clarify 'users add' semantics (docs & help, remove read from csv file)

v9.0.1
======

* internal updates

v9.0.0
======

* 'users get' - removed -i parameter
* 'users get' - make it work with any profile field

v8.0.0
======

* 'groups list' - will now only print OKTA_GROUPs, unless -a is specified
* 'groups list' - output is now sorted
* 'groups get' - parameter '-i' removed

v7.7.0
======

* add apps {add,activate,deactivate,delete} commands

v7.6.0
======

* add group {add,delete} commands

v7.5.0
======

* make 'dump' include DEPROVISIONED users
* update cli help texts
* fix 'okta-cli version'

v7.4.0
======

* add command "config delete" (delete a config)
* add command "config file" (print location of config file)
* move default profile check to where it's needed, fix a bug by doing this

v7.3.1
======

* fix inclusion of word file database

v7.3.0
======

* add "pw set -g" and "pw set -p" commands. "-g" auto-generated a password based on word lists

v7.2.1
======

* make "users list" a bit faster

v7.2.0
======

* add 'dump' command which dumps users, and apps / groups with their users
* internal cleanups

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
