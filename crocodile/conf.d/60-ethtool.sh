#!/bin/bash

for eth in eth0 eth1; do
	ifconfig $eth > /dev/null || break
	ifconfig $eth | grep "inet addr" > /dev/null || break

	speed=`ethtool $eth | grep Speed | awk {'print $2'}`
	if [ $speed != "1000Mb/s" ]; then
		ethtool -s $eth speed 1000
		new_speed=`ethtool $eth | grep Speed | awk {'print $2'}`

		echo "{'host':'`hostname -f`', 'service':'ethtool', 'metric':$speed, 'state':'error', 'description':'eth: $eth, speed: $speed -> $new_speed'}"
	fi
done
