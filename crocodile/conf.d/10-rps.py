#!/usr/bin/python

import requests, json, time, sys, socket, bernhard
import logging

logging.basicConfig(filename='/var/log/supervisor/rps.log',
        format='%(asctime)s %(levelname)s: rps: %(message)s',
        level=logging.DEBUG)

class parser:
    def __init__(self, addresses):
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

    def send_all(self, message):
        logging.debug("send_all: %s", message)
        for c in self.clients:
            c.send(message)

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

    def send_error_message(self, metric, description):
        message = {}
        message['service'] = 'rps'
        message['host'] = self.host
        message['state'] = 'error'
        message['metric'] = metric
        message['description'] = description

        logging.error("send_error_message: %s", message['description'])
        self.send_all(message)

    def proxy_stat(self):
        url = "http://%s:%d/proxy_stat/" % (self.host, self.acl_port)

        headers = {}
        if self.acl_user != '' and self.acl_token != '':
            headers['Authorization'] = 'riftv1 {0}:{1}'.format(
                    self.acl_user,
                    generate_signature(self.acl_token, 'GET', url))

        text = ''
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code != requests.codes.ok:
                self.send_error_message(r.status_code, "invalid status code: %d: %s" % (r.status_code, r.text))
                return
            text = r.text
        except Exception as e:
            self.send_error_message(666, "could not read proxy stat: %s" % e)
            return

        self.parse_proxy_stats(text)

    def parse_proxy_stats(self, text):
        j = json.loads(text)

        handlers = j.get('handlers')
        if handlers == None:
            self.send_error_message(200, "invalid json in reply: no 'handlers': '%s'" % text)
            return

        message = {}
        message['host'] = self.host
        message['state'] = 'info'

        for hname, counters in handlers.items():
            bps = counters.get('bps')
            if bps == None:
                self.send_error_message(200, "invalid json in reply: no 'bps': '%s'" % text)
                return

            message['service'] = 'bps %s' % (hname)
            message['metric'] = bps
            self.send_all(message)

            rps = counters.get('rps')
            if rps == None:
                self.send_error_message(200, "invalid json in reply: no 'rps': '%s'" % text)
                return

            if len(rps) != 0:
                for status, cnt in rps.items():
                    message['service'] = 'rps %s %s' % (status, hname)
                    message['metric'] = cnt
                    self.send_all(message)


if __name__ == '__main__':
    p = parser(sys.argv[1])
    p.proxy_stat()
