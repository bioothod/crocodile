#!/bin/bash

apt-get update
apt-get install -y python-minimal python-pip
pip install protobuf bernhard
wget https://github.com/megacrab/tmp/blob/master/crocodile/checker.sh && bash checker.sh
rm setup.sh checker.sh
