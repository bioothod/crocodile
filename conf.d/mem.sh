#!/bin/bash
#check free mem
ok_perc=10
total=`free -m |grep Mem |awk {' print $2 '}`
free=`free -m |grep Mem |awk {' print $4 '}`
if [ $(($free * 100 / $total)) -le $ok_perc ];then 
  state='warning'
else
  state='normal'
fi
echo "{'host':'`hostname -f`', 'service':'free-mem','metric':$free,'state':'$state'}"
