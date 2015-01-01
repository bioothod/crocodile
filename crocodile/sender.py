#!/usr/bin/env python
#getting list of conf.d directory
#executing them and sending results to all riemann instances
import bernhard, os, subprocess, socket, ast, time

#for except in sender function
socket.setdefaulttimeout(2)

confd = '/etc/crocodile/conf.d/'
#list of riemann instances
rlist = {'ioremap.net':5555}

def run_process(scrpt):
    args = ",".join("{!s}:{!r}".format(key,val) for (key,val) in rlist.items())
    p = subprocess.Popen([scrpt, args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    return out

def sender(message):
    for rhost in rlist:
        try:
            c = bernhard.Client(host=rhost, port=rlist[rhost])
            c.send(message)
        except:
            pass

#checking/running/sending
while True:
    for x in os.listdir(confd):
        try:
            out = run_process(confd+x)
            if len(out) == 0:
                continue
            q = ast.literal_eval(out)
            sender(q)
        except Exception as e:
            print "Got exception running", x, ": ", e, ": ", out
            pass
    time.sleep(10)
