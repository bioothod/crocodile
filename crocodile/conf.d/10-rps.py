#!/usr/bin/python

import noscript_parser
import requests
import logging
import sys
import json

logging.basicConfig(filename='/var/log/supervisor/rps.log',
        format='%(asctime)s %(levelname)s: rps: %(message)s',
        level=logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)

class rps_parser(noscript_parser.parser):
    def proxy_stat(self):
        url = "http://%s:%d/proxy_stat/" % (self.host, self.acl_port)

        headers = {}
        if self.acl_user != '' and self.acl_token != '':
            headers['Authorization'] = 'riftv1 {0}:{1}'.format(
                    self.acl_user,
                    self.generate_signature(self.acl_token, 'GET', url))

        text = ''
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code != requests.codes.ok:
                self.send_error_message('rps', r.status_code, "invalid status code: %d: %s" % (r.status_code, r.text))
                return
            text = r.text
        except Exception as e:
            self.send_error_message('rps', 666, "could not read proxy stat: %s" % e)
            return

        self.parse_proxy_stats(text)

    def parse_proxy_stats(self, text):
        j = json.loads(text)

        handlers = j.get('handlers')
        if handlers == None:
            self.send_error_message('rps', 200, "invalid json in reply: no 'handlers': '%s'" % text)
            return

        message = {}
        message['host'] = self.host

        for hname, metric in handlers.items():
            RS = metric.get('RS')
            if RS == None:
                self.send_error_message('rps', 200, "%s: invalid json in reply: no 'RS' in metric: '%s'" % (hname, text))
                break

            for status, rs in RS.items():
                bps = rs.get('BPS')
                if bps == None:
                    break
                rps = rs.get('RPS')
                if rps == None:
                    break

                message['state'] = 'info'
                if status == '500':
                    message['state'] = 'error'

                message['service'] = 'bps %s %s' % (status, hname)
                message['metric'] = bps
                self.queue(message)

                message['service'] = 'rps %s %s' % (status, hname)
                message['metric'] = rps
                self.queue(message)

if __name__ == '__main__':
    p = rps_parser(sys.argv[1])
    p.proxy_stat()
    p.send_queued_messages()
