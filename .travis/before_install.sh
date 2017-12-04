#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    brew install wine
else
    sudo dpkg --add-architecture i386
    sudo add-apt-repository ppa:ubuntu-wine/ppa -y
    sudo apt-get update
    sudo apt-get install --no-install-recommends -y wine1.8
fi
pip install pytest pytest-cov codecov
