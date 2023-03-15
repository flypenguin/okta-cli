SHELL = bash

all:    checkclean clean build

test:
	pytest
.PHONY: test

.PHONY: push
push:
	git push
	git push --tags

.PHONY: upload
upload:
	twine upload dist/*

.PHONY: pypi
pypi:   build upload

.PHONY: build
build: clean
	rm -rf build/ dist/
	python setup.py sdist
	python setup.py bdist_wheel

.PHONY: clean
clean:
	find . -type d -name __pycache__ | xargs rm -rf
	find . -type f -name "*.pyc" -delete
	rm -rf dist/ build/
	rm -rf *.egg-info
	rm -rf ignoreme build dist
	rm -rf tmp

.PHONY: checkclean
checkclean:
	echo -e "\nCHECK IF BUILD DIR IS CLEAN ...\n"
	git diff-index --quiet HEAD --

.PHONY: bump_major
bump_major:
	bumpversion major

.PHONY: bump_minor
bump_minor:
	bumpversion minor

.PHONY: bump_patch
bump_patch:
	bumpversion patch

.PHONY: now-upload-message
now-upload-message:
	@echo -e "\nDONE.\nNow push & upload by executing ...\n"
	@echo -e "    make upload\n\nHave fun :)"

.PHONY: major
major: clean checkclean bump_major build now-upload-message

.PHONY: minor
minor: clean checkclean bump_minor build now-upload-message

.PHONY: patch
patch: clean checkclean bump_patch build now-upload-message

dockertest:
	@IMG="temp/$$(basename $$(pwd)):$$(date +%s)" ; \
	echo $$IMG ; \
	docker build . --no-cache --tag $$IMG ; \
	docker run $$IMG
.PHONY: test
