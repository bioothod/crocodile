#!/bin/bash
#check free mem
error_perc=20
warning_perc=30
total=`free |grep Mem |awk {' print $2 '}`
free=`free |grep buffers/cache |awk {' print $4 '}`
if [ $(($free * 100 / $total)) -le $error_perc ];then 
  state='error'
elif [ $(($free * 100 / $total)) -le $warning_perc ];then 
  state='warning'
else
  state='normal'
fi
echo "{'host':'`hostname -f`', 'service':'memory','metric':$free,'state':'$state'}"
