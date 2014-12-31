#!/bin/bash

apt-get update >/dev/null
apt-get install -y python-minimal python-pip git dos2unix
pip install protobuf bernhard supervisor
wget https://raw.githubusercontent.com/megacrab/tmp/master/crocodile/checker.sh
dos2unix checker.sh
bash checker.sh
rm setup.sh checker.sh
