#!/bin/bash
#check free memory, grab a stack trace if process ate too much RAM

error_perc=20
warning_perc=30
total=`free -b |grep Mem |awk {' print $2 '}`
free=`free -b |grep buffers/cache |awk {' print $4 '}`
trace=""

if [ $(($free * 100 / $total)) -le $error_perc ]; then
	trace=`gdb -ex "set pagination 0" -ex "thread apply all bt" --batch -p $(pidof dnet_ioserv)`
	state='error'
elif [ $(($free * 100 / $total)) -le $warning_perc ]; then
	state='warning'
else
	state='normal'
fi

echo "{'host':'`hostname -f`', 'service':'memory', 'metric':$free, 'state':'$state', 'description':'$trace'}"
