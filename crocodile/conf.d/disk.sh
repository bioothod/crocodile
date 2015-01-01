#!/bin/bash
error_perc=85
warning_perc=80
state='normal'

space=`df -h`
while read -r line; do
	if test x"`echo $line | grep Filesystem`" != x""; then
		continue
	fi

	used=`echo $line | awk {'print $5'} | sed -e 's/%//g'`
	if test $used -ge $error_perc; then
		state='error'
		break
	elif test $used -ge $warning_perc; then
		state='warning'
	fi
done <<< "$space"


echo "{'host':'`hostname -f`', 'service':'disk', 'metric':$free, 'state':'$state', 'message': '$space'}"
