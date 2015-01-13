#!/usr/bin/python

import requests, json, time, sys, socket, bernhard
import hmac
import hashlib
import urlparse
import urllib
import shutil
import docker
import logging
import os

logging.basicConfig(filename='/var/log/supervisor/test_writer.log',
        format='%(asctime)s %(levelname)s: test_writer: %(message)s',
        level=logging.DEBUG)


acl_file = '/etc/crocodile/acl.json'
#acl_file = '/tmp/acl.json'
acl_user = ''
acl_token = ''
acl_base_dir = '/home/admin/elliptics'
acl_port = 80
acl_success_groups = 2

def load_acl():
    try:
        with open(acl_file, 'r') as f:
            j = json.load(f)
            global acl_user, acl_token, acl_port, acl_base_dir, acl_success_groups
            acl_user = str(j['user'])
            acl_token = str(j['token'])
            port = j.get('port')
            if port != None:
                acl_port = int(port)

            success_groups = j.get('success_groups')
            if success_groups != None:
                acl_success_groups = int(success_groups)

            base = j.get('base')
            if base != None:
                acl_base_dir = str(base)
    except Exception as e:
        logging.error("load_acl: file: %s, exception: %s", acl_file, e)
        pass

def generate_signature(key, method, url, headers=None):
    parsed_url = urlparse.urlparse(url)
    queries = urlparse.parse_qsl(parsed_url.query)
    queries.sort()
    text = ''
    text += method + '\n'
    text += parsed_url.path
    if len(queries) > 0:
        text += '?' + urllib.urlencode(queries)
    text += '\n'
    if headers:
        headers = map(lambda x: (x[0].lower(), x[1]), headers.iteritems())
        headers = filter(lambda x: x[0].startswith('x-ell-'), headers)
        headers.sort()

        for header in headers:
            text += header[0] + ':' + header[1] + '\n'
    return hmac.new(key, text, hashlib.sha512).hexdigest()

def start_container(c):
    start_params = {
        'Image': 'reverbrain/backrunner:latest',
        'Ports': [80],
        'Command': '/root/go/bin/backrunner -config /mnt/elliptics/etc/backrunner.conf -buckets /mnt/elliptics/etc/buckets.production',
    }

    new_cnt = c.create_container(
            image           = start_params['Image'],
            command         = start_params['Command'],
            ports           = start_params['Ports'],
            volumes         = ['/mnt/elliptics'],
            environment     = {
                'GOGC1': '200',
            }
    )

    nc = c.start(new_cnt['Id'],
            binds = {
                acl_base_dir : {
                    'bind':     '/mnt/elliptics',
                    'ro':       False,
                },
            },
            port_bindings = {
                80: 80,
            },
            restart_policy = {
                'Name': 'on-failure'
            },
    )

    logging.info("new container has been started: %s", new_cnt)

    message = {}
    message['service'] = 'test_writer'
    message['host'] = socket.getfqdn()
    message['metric'] = 666
    message['state'] = 'error'
    message['description'] = 'new container has been started: %s' % (new_cnt)

    return message

def restart_proxy(clients):
    try:
        need_new_container = True
        message = {}
        message['service'] = 'test_writer'
        message['host'] = socket.getfqdn()
        message['metric'] = 666
        message['state'] = 'error'

        id = 'restart'
        stderr = ''
        c = docker.Client(base_url='unix://var/run/docker.sock')
        try:
            for cnt in c.containers():
                if 'backrunner' in cnt['Command']:
                    id = cnt['Id']
                    for idx in range(5):
                        message, need_restart = check_upload()
                        if not need_restart:
                            need_new_container = False
                            break
                        time.sleep(1)

                    if need_restart:
                        c.stop(id)
                        stderr = c.logs(id, stderr=True)
                        logging.info("restart: container has been stopped: %s", id)
                        break
        except Exception as e:
            logging.error("restart: could not restart docker container: %s", e)

        if need_new_container:
            backrunner_log = '%s/log/backrunner.log' % (acl_base_dir)
            base = os.path.dirname(backrunner_log)
            new_log = '%s/%s.backrunner.log.%d' % (base, id, time.time())
            try:
                shutil.move(backrunner_log, new_log)
                if len(stderr) != 0:
                    with open('%s/%s.stderr' % (base, id), 'w') as f:
                        f.write(stderr)

                logging.info("restart: log file has been moved: %s -> %s",
                        backrunner_log, new_log)
            except:
                pass


            message = start_container(c)
    except Exception as e:
        logging.error("restart: could not start new docker container: %s", e)
        message['description'] = 'could not start new docker container: %s' % (e)

    return message

def check_upload():
    load_acl()
    data = "test upload at: %s" % (time.time())

    host = socket.getfqdn()
    url = "http://%s:%d/nobucket_upload/test_writer.txt" % (host, acl_port)

    headers = {}
    if acl_user != '' and acl_token != '':
        headers['Authorization'] = 'riftv1 {0}:{1}'.format(
                acl_user,
                generate_signature(acl_token, 'POST', url))

    message = {}
    message['service'] = 'test_writer'
    message['host'] = host

    need_restart = False

    try:
        r = requests.post(url, data=data, headers=headers, timeout=5)
        message['metric'] = r.status_code
        message['state'] = 'info'

        if r.status_code != requests.codes.ok:
            message['state'] = 'error'
            message['description'] = "%s" % r.text

            # this error means proxy is not connected to any remote node,
            # restart it, probably there was error with iptables and docker
            # daemon
            if 'insufficient results count due to checker' in r.text:
                need_restart = True

        if r.status_code == requests.codes.ok:
            rep = r.json()
            try:
                sgroups = rep['reply']['success-groups']
                egroups = rep['reply']['error-groups']
                if len(sgroups) != acl_success_groups:
                    message['state'] = 'error'
                    message['description'] = "not enough success results: %d instead of 2: %s" % (len(sgroups), r.text)
                if len(egroups) != 0:
                    message['state'] = 'error'
                    message['description'] = "there are %d error results: %s" % (len(egroups), r.text)
            except Exception as e:
                    message['state'] = 'error'
                    message['description'] = "could not parse reply: '%s': %s" % (r.text, e)

    except Exception as e:
        message['state'] = 'error'
        message['description'] = "%s" % e
        need_restart = True

    logging.debug("check: need_restart: %s, message: %s",
            need_restart, message)

    return message, need_restart

def upload_and_restart(clients):
    message, need_restart = check_upload()
    if need_restart:
        message = restart_proxy(clients)

    logging.info("upload_and_restart: message: %s", message)
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
        except Exception as e:
            print "disk: host: %s, port: %s, exeption: %s" % (rhost,
                    rlist[rhost], e)
            pass

    upload_and_restart(clients)
