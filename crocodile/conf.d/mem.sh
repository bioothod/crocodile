#!/bin/bash
#check free mem
ok_perc=30
total=`free -m |grep Mem |awk {' print $2 '}`
free=`free -m |grep buffers/cache |awk {' print $3 '}`
if [ $(($free * 100 / $total)) -le $ok_perc ];then 
  state='warning'
else
  state='normal'
fi
echo "{'host':'`hostname -f`', 'service':'memory','metric':$free,'state':'$state'}"
