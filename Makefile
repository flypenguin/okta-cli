SHELL = bash

all:    checkclean clean build

test:
	pytest
.PHONY: test

.PHONY: checkclean
checkclean:
	echo -e "\nCHECK IF BUILD DIR IS CLEAN ...\n"
	git diff-index --quiet HEAD --

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
	rm -rf build/ dist/
	python setup.py sdist
	python setup.py bdist_wheel

.PHONY: push
push:
	git push
	git push --tags

.PHONY: upload
upload: push
	twine upload dist/*

.PHONY: now-upload-message
now-upload-message:
	@echo -e "\nDONE.\nNow push & upload by executing ...\n"
	@echo -e "    make upload\n\nHave fun :)"

# now let's get to the ones we use most often :)

.PHONY: bump_major
bump_major:
	bumpversion major

.PHONY: bump_minor
bump_minor:
	bumpversion minor

.PHONY: bump_patch
bump_patch:
	bumpversion patch

.PHONY: major
major: checkclean bump_major build now-upload-message

.PHONY: minor
minor: checkclean bump_minor build now-upload-message

.PHONY: patch
patch: checkclean bump_patch build now-upload-message

dockertest:
	@IMG="temp/$$(basename $$(pwd)):$$(date +%s)" ; \
	echo $$IMG ; \
	docker build . --no-cache --tag $$IMG ; \
	docker run $$IMG
.PHONY: test
