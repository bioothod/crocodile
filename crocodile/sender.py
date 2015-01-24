#!/usr/bin/env python
#getting list of conf.d directory
#executing them and sending results to all riemann instances
import bernhard, os, subprocess, socket, ast, time, re, logging
import signal, os, psutil

#for except in sender function
socket.setdefaulttimeout(5)

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

confd = '/etc/crocodile/conf.d/'
#list of riemann instances
rlist = {'ioremap.net':5555}
sender_clients = []

class Alarm(Exception):
    pass

def alarm_handler(signum, frame):
    raise Alarm

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

    return out, err

def sender(message):
    for c in sender_clients:
        try:
            c.send(message)
        except Exception as e:
            logging.Error("exception: could not sent message '%s': %s" %
                    (message, e))

def kill_children():
    parent_pid = os.getpid()
    try:
        p = psutil.Process(parent_pid)

        child_pid = p.get_children(recursive=True)
        for pid in child_pid:
            os.kill(pid.pid, signal.SIGKILL)

    except Exception as e:
        logging.error("Caught exception when killing children of %d" % (parent_pid))
        logging.error("Killing self :(")
        os.kill(0, signal.SIGKILL)
        return

# setup sigalrm as a dirty hack to workaround stuck processes
# if process stuck, we will kill all children, and if this fails,
# we send signal to 0 pid, i.e. whole process group of the calling process
# cron should restart us in several minutes
signal.signal(signal.SIGALRM, alarm_handler)

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

        out = ''
        err = ''
        try:
            # The whole script processing should complete in 20 seconds
            signal.alarm(20)

            start = time.time()
            out, err = run_process(confd+x)
            finish = time.time()

            logging.info('%s: completed: stdout: \'%s\', stderr: \'%s\', time: %f sec',
                    x, out, err, finish - start)

            if len(out) != 0:
                q = ast.literal_eval(out)
                sender(q)

            signal.alarm(0) # reset signal
        except Exception as e:
            logging.error('%s: exception: stdout: \'%s\', stderrr: \'%s\', error: %s', x, out, err, e)

            kill_children()
            pass

    if timeout > 10:
        timeout = 10

    logging.info("sender: sleeping for %d seconds", timeout)
    time.sleep(timeout)
