#!/usr/bin/python

import requests, json, time, sys, socket, bernhard
import logging
import os
import re

logging.basicConfig(filename='/var/log/supervisor/rps.log',
        format='%(asctime)s %(levelname)s: rps: %(message)s',
        level=logging.DEBUG)

access_log_regexp = re.compile("(?P<prefix>.+): (?P<date>\\d+/\\d+/\\d+ \\d+:\\d+:\\d+)\\.(?P<usec>\\d+) access_log: method: '(?P<method>\\w+)', path: '(?P<path>.+)', encoded-uri: '(?P<uri>.+)', status: (?P<status>\\d+), size: (?P<size>\\d+), time: (?P<duration>[0-9\\.]+) ms, err: '(?P<error>\\w+)'")

acl_file = '/etc/crocodile/acl.json'
#acl_file = '/tmp/acl.json'
acl_base_dir = '/home/admin/elliptics'

def load_acl():
    try:
        with open(acl_file, 'r') as f:
            j = json.load(f)
            global acl_base_dir

            base = j.get('base')
            if base != None:
                acl_base_dir = str(base)
    except Exception as e:
        logging.error("load_acl: file: %s, exception: %s", acl_file, e)
        pass

class entry:
    def __init__(self):
        self.date = time.time()
        self.method = ''
        self.path = ''
        self.status = ''
        self.size = ''
        self.duration = ''

    def __str__(self):
        return "%s: path: %s, status: %s, size: %d" % (time.ctime(self.date), self.path, self.status, self.size)

class metric:
    def __init__(self, name):
        self.name = name
        self.requests = 0
        self.duration = 0
        self.size = 0
        self.status = {}

        self.status[200] = 0
        self.status[300] = 0
        self.status[400] = 0
        self.status[500] = 0

    def push(self, e):
        self.size += e.size
        self.requests += 1
        self.duration += e.duration
        if 200 <= e.status < 300:
            self.status[200] += 1
        elif 300 <= e.status < 400:
            self.status[300] += 1
        elif 400 <= e.status < 500:
            self.status[400] += 1
        elif 500 <= e.status < 600:
            self.status[500] += 1

    def message(self):
        message = {}
        message['host'] = socket.getfqdn()
        message['state'] = 'info'

        return message

class estimator:
    def __init__(self, clients, timing):
        self.clients = clients
        self.timing = timing
        self.metrics = {}
        prefix = ['/get/', '/upload/', '/nobucket_upload/', '/delete/']
        for p in prefix:
            self.metrics[p] = metric(p)

    def push(self, e):
        for k, m in self.metrics.iteritems():
            if e.path.startswith(k):
                self.metrics[k].push(e)
                return

    def send_all(self, message):
        logging.info(message)

        if message['metric'] != 0:
            for c in self.clients:
                c.send(message)

    def send(self):
        for k, m in self.metrics.iteritems():
            message = m.message()

            for status, reqs in m.status.iteritems():
                message['service'] = 'rps %s %s' % (status, m.name)
                message['metric'] = reqs / self.timing
                self.send_all(message)

            message['service'] = 'bps %s' % (m.name)
            message['metric'] = m.size / self.timing
            self.send_all(message)

def parse_chunk(chunk, boundary_ts):
    for m in access_log_regexp.finditer(chunk):
        tm = time.mktime(time.strptime(m.group('date'), '%Y/%m/%d %H:%M:%S'))

        e = entry()
        e.date = tm
        e.method = m.group('method')
        e.path = m.group('path')
        e.status = int(m.group('status'))
        e.size = int(m.group('size'))
        e.duration = float(m.group('duration'))

        yield e

        if tm < boundary_ts:
            return

def read_and_parse(clients, timing):
    load_acl()

    logfile = '%s/log/backrunner.log' % (acl_base_dir)

    boundary_timestamp = time.time() - timing

    bsize = 1024 * 16

    est = estimator(clients, timing)

    with open(logfile, 'r') as f:
        f.seek(0, os.SEEK_END)

        need_exit = False

        while not need_exit:
            f.seek(-bsize, os.SEEK_CUR)
            offset = f.tell()
            chunk = f.read(bsize)
            f.seek(-bsize, os.SEEK_CUR)

            # we do not really care if chunk boundary splits access_log line into parts

            for e in parse_chunk(chunk, boundary_timestamp):
                if e.date < boundary_timestamp:
                    need_exit = True
                    break

                est.push(e)

            # we are at the beginning of the file
            if len(chunk) != bsize:
                need_exit = True
                break

    est.send()

if __name__ == '__main__':
    tm = 5
    m = re.search('^\d+', sys.argv[0])
    if m != None:
        tm = int(m.group(0))

    rlist = {}
    for h in sys.argv[1].split(","):
        k, v = h.split(":")
        rlist[k] = v

    clients = []
    for rhost in rlist:
        try:
            c = bernhard.Client(host=rhost, port=rlist[rhost])
            clients.append(c)
        except Exception as e:
            print "disk: host: %s, port: %s, exeption: %s" % (rhost,
                    rlist[rhost], e)
            pass

    read_and_parse(clients, tm)
