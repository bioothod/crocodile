#!/usr/bin/python

import bernhard, os, subprocess, socket, ast, sys

#for except in sender function
socket.setdefaulttimeout(2)

def disk_partitions(all=False):
    """Return all mountd partitions as a nameduple.
    If all == False return phyisical partitions only.
    """
    phydevs = []
    f = open("/proc/filesystems", "r")
    for line in f:
        if not line.startswith("nodev"):
            phydevs.append(line.strip())

    retlist = []
    f = open('/etc/mtab', "r")
    for line in f:
        if not all and line.startswith('none'):
            continue
        fields = line.split()
        device = fields[0]
        mountpoint = fields[1]
        fstype = fields[2]
        if not all and fstype not in phydevs:
            continue
        if device == 'none':
            device = ''
        ntuple = (device, mountpoint)
        retlist.append(ntuple)
    return retlist

def disk_usage(clients, dev, path):
    """Return disk usage associated with path."""
    st = os.statvfs(path)
    free = (st.f_bavail * st.f_frsize)
    total = (st.f_blocks * st.f_frsize)
    used = (st.f_blocks - st.f_bfree) * st.f_frsize
    try:
        percent = ret = (float(used) / total) * 100
    except ZeroDivisionError:
        percent = 0

    message = {}
    message['host'] = socket.getfqdn()
    message['service'] = 'disk ' + dev
    message['metric'] = free
    message['state'] = 'ok'
    if percent > 85:
        message['state'] = 'error'
        send_all(clients, message)
    elif percent > 80:
        message['state'] = 'warning'
        send_all(clients, message)

def send_all(clients, message):
    for c in clients:
        c.send(message)

if __name__ == '__main__':
    rlist = {}
    for h in sys.argv[1].split(","):
        k, v = h.split(":")
        rlist[k] = v

    clients = []
    for rhost in rlist:
        try:
            c = bernhard.Client(host=rhost, port=rlist[rhost])
            clients.append(c)
        except:
            pass

    for part in disk_partitions():
        disk_usage(clients, part[0], part[1])
