MAINTAINER Robert Gieseke <robert.gieseke@pik-potsdam.de>

USER root

RUN apt-get update && \
    apt-get install -y wine && \
    apt-get clean

USER main

RUN pip install pymagicc f90nml
