#!/bin/sh

echo Currently on branch `git branch`

bumpversion patch --no-tag --allow-dirty --no-commit --list > .temp
CURRENT_VERSION=`cat .temp | grep current_version | sed -r s,"^.*=",,`
NEW_VERSION=`cat .temp | grep new_version | sed -r s,"^.*=",,`

git add .bumpversion.cfg
git add custom_components.json
git add midea.py
git add setup.py
git add midea/*.py

git commit -m "[ci skip] Version Changed from ${CURRENT_VERSION} -> ${NEW_VERSION}"
git tag "v${NEW_VERSION}"
