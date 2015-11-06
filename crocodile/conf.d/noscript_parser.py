#!/usr/bin/python

import json, time, sys, socket, bernhard
import copy
import logging
import hmac
import hashlib
import urlparse
import urllib

#for except in sender function
socket.setdefaulttimeout(5)

class parser:
    def __init__(self, addresses, previous=None):
        self.acl_file = '/etc/crocodile/acl.json'
        self.acl_user = ''
        self.acl_token = ''
        self.acl_base_dir = '/home/admin/elliptics'
        self.acl_port = 80
        self.acl_success_groups = 2
        self.acl_port_mapping = {
                80 : 80
        }
        self.clients = []
        self.host = socket.getfqdn()
        self.previous = previous

        self.messages = []

        self.load_acl()

        rlist = {}
        for h in addresses.split(","):
            k, v = h.split(":")
            rlist[k] = v

        for rhost in rlist:
            try:
                c = bernhard.Client(host=rhost, port=rlist[rhost])
                self.clients.append(c)
            except Exception as e:
                logging.error("init: host: %s, port: %s, exeption: %s" % (rhost, rlist[rhost], e))
                pass

    def load_acl(self):
        try:
            with open(self.acl_file, 'r') as f:
                j = json.load(f)
                self.acl_user = str(j['user'])
                self.acl_token = str(j['token'])
                port = j.get('port')
                if port != None:
                    self.acl_port = int(port)

                success_groups = j.get('success_groups')
                if success_groups != None:
                    self.acl_success_groups = int(success_groups)

                pm = j.get('port_mapping')
                if pm != None:
                    self.acl_port_mapping = {}
                    for k, v in pm.items():
                        self.acl_port_mapping[int(k)] = int(v)

                base = j.get('base')
                if base != None:
                    self.acl_base_dir = str(base)
        except Exception as e:
            logging.error("load_acl: file: %s, exception: %s", self.acl_file, e)
            pass


    def uptime(self):
        with open('/proc/uptime') as f:
            return float(f.readline().split()[0])
        return 0.0

    def read_previous(self):
        try:
            with open(self.previous, 'rt') as f:
                return json.load(f)
        except:
            return dict()

    def write_previous(self, prev):
        with open(self.previous, 'wt') as f:
            json.dump(prev, f)

    def send_error_message(self, service, metric, description):
        message = {}
        message['service'] = service
        message['host'] = self.host
        message['state'] = 'error'
        message['metric'] = metric
        message['description'] = description

        logging.error("send_error_message: service: %s, %s", service, message['description'])
        self.send_all(message)

    def send_all(self, message):
        logging.info("send_all: %s", message)

        message['host'] = self.host

        for c in self.clients:
            c.send(message)

    def queue(self, message):
        self.messages.append(copy.deepcopy(message))

    def send_queued_messages(self):
        logging.info("send_queued_message: sending %d messages", len(self.messages))
        for c in self.clients:
            c.send(*self.messages)

    def generate_signature(self, key, method, url, headers=None):
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

