#!/bin/bash
apt install wine-development
dpkg --add-architecture i386 && apt update
apt install wine32-development
