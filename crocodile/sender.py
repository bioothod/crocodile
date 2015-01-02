#!/usr/bin/env python
#getting list of conf.d directory
#executing them and sending results to all riemann instances
import bernhard, os, subprocess, socket, ast, time, re, logging

#for except in sender function
socket.setdefaulttimeout(2)

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

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
scripts_timeouts = {}
while True:
    timeout = 10
    for x in os.listdir(confd):
        # when script name starts with digits, consider it as timeout for this
        # script in seconds. 60-disk.py will be started once per 60 seconds,
        # by defualt scripts timeout is 10 seconds

        m = re.search('^\d+', x)
        if m != None:
            wake_up_time = scripts_timeouts.get(x)
            if wake_up_time != None:
                if time.time() < wake_up_time:
                    tm = wake_up_time - time.time()
                    if tm < timeout:
                        timeout = tm

                    continue

            tm = int(m.group(0))
            scripts_timeouts[x] = tm + time.time()

            if tm < timeout:
                timeout = tm
        try:
            out = run_process(confd+x)
            logging.info('%s: completed: out: \'%s\', timeout: %d', x, out, timeout)
            if len(out) == 0:
                continue
            q = ast.literal_eval(out)
            sender(q)
        except Exception as e:
            logging.error('%s: exception: out: \'%s\', timeout: %d, error: %s',
                    x, out, timeout, e)
            pass

    time.sleep(timeout)
