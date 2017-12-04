#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    brew install python3 wine
    python3 -m venv venv
    ./venv/bin/pip install pytest pytest-cov codecov
    ./venv/bin/pip .
else
    sudo dpkg --add-architecture i386
    sudo add-apt-repository ppa:ubuntu-wine/ppa -y
    sudo apt-get update
    sudo apt-get install --no-install-recommends -y wine1.8
    pip install pytest pytest-cov codecov
fi
