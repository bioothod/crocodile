#!/bin/bash
error_perc=85
warning_perc=80
state='normal'

space=`df -t ext4`
echo "["
while read -r line; do
	if test x"`echo $line | grep Filesystem`" != x""; then
		continue
	fi

	avail=`echo $line | awk {'print $4'}`
	disk=`echo $line | awk {'print $1'}`
	used=`echo $line | awk {'print $5'} | sed -e 's/%//g'`
	if test $used -gt $error_perc; then
		state='error'
	elif test $used -gt $warning_perc; then
		state='warning'
	fi

	echo "{'host':'`hostname -f`', 'service':'$disk', 'metric':'$avail', 'state':'$state', 'description': ''}"
done <<< "$space"
echo "]"
