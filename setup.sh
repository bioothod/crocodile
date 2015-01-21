#!/bin/bash

apt-get update >/dev/null
apt-get install -y python-minimal git lxc-docker python-dev
easy_install pip
pip install protobuf bernhard supervisor docker-py psutil
wget https://raw.githubusercontent.com/bioothod/crocodile/master/crocodile/checker.sh
bash checker.sh
rm setup.sh checker.sh
