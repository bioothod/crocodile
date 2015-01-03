#!/usr/bin/env python
#getting list of conf.d directory
#executing them and sending results to all riemann instances
import bernhard, os, subprocess, socket, ast, time, re, logging

#for except in sender function
socket.setdefaulttimeout(5)

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

confd = '/etc/crocodile/conf.d/'
#list of riemann instances
rlist = {'ioremap.net':5555}
sender_clients = []

def init_clients():
    global sender_clients
    sender_clients = []
    for rhost in rlist:
        c = bernhard.Client(host=rhost, port=rlist[rhost])
        sender_clients.append(c)

def run_process(scrpt):
    args = ",".join("{!s}:{!r}".format(key,val) for (key,val) in rlist.items())
    p = subprocess.Popen([scrpt, args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    return out

def sender(message):
    for c in sender_clients:
        try:
            c.send(message)
        except Exception as e:
            logging.Error("exception: could not sent message '%s': %s" %
                    (message, e))

#checking/running/sending
scripts_timeouts = {}
while True:
    timeout = 10
    init_clients()
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
            logging.info('%s: completed: out: \'%s\'', x, out)
            if len(out) == 0:
                continue
            q = ast.literal_eval(out)
            sender(q)
        except Exception as e:
            logging.error('%s: exception: out: \'%s\', error: %s',
                    x, out, e)
            pass

    time.sleep(timeout)
