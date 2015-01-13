#!/bin/bash

apt-get update >/dev/null
apt-get install -y python-minimal python-pip git
pip install protobuf bernhard supervisor
wget https://raw.githubusercontent.com/bioothod/crocodile/master/crocodile/checker.sh
bash checker.sh
rm setup.sh checker.sh
