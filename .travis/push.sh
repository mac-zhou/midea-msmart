#!/bin/sh

git config --global user.email "travis@travis-ci.org"
git config --global user.name "Travis CI"

bumpversion patch --no-tag --allow-dirty --no-commit --list > .temp
CURRENT_VERSION=`cat .temp | grep current_version | sed -r s,"^.*=",,`
NEW_VERSION=`cat .temp | grep new_version | sed -r s,"^.*=",,`

git add .bumpversion.cfg
git add custom_components.json
git add midea.py
git add setup.py

git commit -m "[ci skip] Version Changed from ${CURRENT_VERSION} -> ${NEW_VERSION}"
git remote add origin-build https://${GH_TOKEN}@github.com/NeoAcheron/midea-ac-py.git > /dev/null 2>&1
git push --quiet --set-upstream origin-build master 
