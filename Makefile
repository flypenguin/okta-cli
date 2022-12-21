all:    checkclean clean build

.PHONY: pypi
pypi:   clean build upload

.PHONY: upload
upload:
	twine upload dist/*

.PHONY: build
build:
	rm -rf build/ dist/
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

.PHONY: push
push:
	git push
	git push --tags

.PHONY: major
major: clean checkclean bump_major build push upload

.PHONY: minor
minor: clean checkclean bump_minor build push upload

.PHONY: patch
patch: clean checkclean bump_patch build push upload

dockertest:
	@IMG="temp/$$(basename $$(pwd)):$$(date +%s)" ; \
	echo $$IMG ; \
	docker build . --no-cache --tag $$IMG ; \
	docker run $$IMG
.PHONY: test
