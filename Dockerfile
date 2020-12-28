FROM jupyter/scipy-notebook:d113a601dbb8

MAINTAINER Robert Gieseke <rob.g@web.de>

USER root

RUN dpkg --add-architecture i386

RUN apt-get update && \
    apt-get install -y wine && \
    apt-get clean
RUN pip install pip --upgrade
RUN pip install pymagicc --pre

COPY . ${HOME}
USER root
RUN chown -R ${NB_UID} ${HOME}
USER ${NB_USER}
