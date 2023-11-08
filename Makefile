SHELL = bash

all:    checkclean clean build


_bump:
	bump-my-version bump $(BUMP_WHAT)
.PHONY: _bump


_checkclean:
	echo -e "\nCHECK IF BUILD DIR IS CLEAN ...\n"
	git diff-index --quiet HEAD --
.PHONY: _checkclean
.SILENT: _checkclean


_print_upload_message:
	@echo -e "\nDONE.\nNow push & upload by executing ...\n"
	@echo -e "    make upload\n\nHave fun :)"
.PHONY: _print_upload_message


%.txt: %.in
	pip-compile -q --output-file "$@" "$<"

requirements-dev.txt: requirements.txt

requirements: requirements.txt requirements-dev.txt
.PHONY: requirements


test:
	pytest
.PHONY: test


.PHONY: clean
clean:
	find . -type d -name __pycache__ | xargs rm -rf
	find . -type f -name "*.pyc" -delete
	rm -rf dist/ build/
	rm -rf *.egg-info
	rm -rf ignoreme build dist
	rm -rf tmp


.PHONY: build
build: clean test
	python -m build --wheel


.PHONY: push
push:
	git push
	git push --tags


.PHONY: upload
upload: push
	twine upload dist/*


# now let's get to the ones we use most often :)


major: BUMP_WHAT := major
major: _checkclean _bump build _print_upload_message
.PHONY: major


minor: BUMP_WHAT := minor
minor: _checkclean _bump build _print_upload_message
.PHONY: minor


patch: BUMP_WHAT := patch
patch: _checkclean _bump build _print_upload_message
.PHONY: patch
