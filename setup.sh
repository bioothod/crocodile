#!/bin/bash

apt-get update
apt-get install -y python-minimal python-pip git dos2unix
pip install protobuf bernhard
wget https://raw.githubusercontent.com/megacrab/tmp/master/crocodile/checker.sh
dos2unix checker.sh
bash checker.sh
rm setup.sh checker.sh
