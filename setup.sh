#!/bin/bash

#curl -sSL https://get.docker.com/ubuntu/ | sh
curl -sSL https://get.docker.com/ | sh

apt-get update
apt-get install docker-engine
apt-get install -y python-minimal git python-dev python-setuptools elliptics gdb ntp
easy_install pip
pip install distribute --upgrade
pip install protobuf bernhard distribute supervisor docker-py psutil
pip install --upgrade psutil
wget https://raw.githubusercontent.com/bioothod/crocodile/master/crocodile/checker.sh
bash checker.sh
rm setup.sh checker.sh
