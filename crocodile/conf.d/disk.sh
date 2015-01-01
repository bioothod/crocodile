#!/bin/bash
error_perc=85
warning_perc=80
state='normal'

space=`df -h`
msg='Ok'
while read -r line; do
	if test x"`echo $line | grep Filesystem`" != x""; then
		continue
	fi

	used=`echo $line | awk {'print $5'} | sed -e 's/%//g'`
	if test $used -gt $error_perc; then
		state='error'
		msg="$line"
		break
	elif test $used -gt $warning_perc; then
		state='warning'
		msg="$line"
	fi
done <<< "$space"


echo "{'host':'`hostname -f`', 'service':'disk', 'metric':$free, 'state':'$state', 'message': '$msg'}"
