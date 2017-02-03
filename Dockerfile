MAINTAINER Robert Gieseke <robert.gieseke@pik-potsdam.de>

USER root

RUN dpkg --add-architecture i386

RUN apt-get update && \
    apt-get install -y wine && \
    apt-get clean

USER main

RUN  /home/main/anaconda/envs/python3/bin/pip install pymagicc
