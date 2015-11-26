#!/usr/bin/python

import json
import logging
import noscript_parser
import requests
import sys
import time

logging.basicConfig(filename='/var/log/supervisor/rps.log',
        format='%(asctime)s %(levelname)s: rps: %(message)s',
        level=logging.INFO)
logging.getLogger().setLevel(logging.INFO)

class rps_parser(noscript_parser.parser):
    def send_exit(self):
        url = "http://%s:%d/exit/" % (self.host, self.acl_port)

        headers = {}
        if self.acl_user != '' and self.acl_token != '':
            headers['Authorization'] = 'riftv1 {0}:{1}'.format(
                    self.acl_user,
                    self.generate_signature(self.acl_token, 'GET', url))

        try:
            r = requests.get(url, headers=headers, timeout=5)
        except Exception as e:
            pass

    def parse_bucket_ctl_stat(self, bstat):
        stat_time = bstat.get('StatTime')
        if stat_time == None:
            logging.error("there is no 'StatTime' entry in the bucket ctl stat: %s", bstat)
            return

        config_time = bstat.get('ConfigTime')
        if config_time == None:
            logging.error("there is no 'ConfigTime' entry in the bucket ctl stat: %s", bstat)
            return

        current_time = bstat.get('CurrentTime')
        if current_time == None:
            logging.error("there is no 'CurrentTime' entry in the bucket ctl stat: %s", bstat)
            return

        stat_update_interval = bstat.get('StatUpdateInterval')
        if stat_update_interval == None:
            logging.error("there is no 'StatUpdateInterval' entry in the bucket ctl stat: %s", bstat)
            return

        config_update_interval = bstat.get('ConfigUpdateInterval')
        if config_update_interval == None:
            logging.error("there is no 'ConfigUpdateInterval' entry in the bucket ctl stat: %s", bstat)
            return

        stime = time.localtime(stat_time)
        ctime = time.localtime(current_time)
        conftime = time.localtime(config_time)

        max_stat_time_diff = 5 * stat_update_interval
        max_config_time_diff = 5 * config_update_interval

        def ts(tm):
            return time.strftime("%Y-%m-%d/%H:%M:%S/%z")

        if current_time > stat_time + max_stat_time_diff or current_time > config_time + max_config_time_diff:
            msg = ("stat_time: %s, config_time: %s, current_time: %s, stat-difference: %d seconds, "
                   "must be at most %d, config-time-difference: %d, must be at most: %d.") % (
                        ts(stime), ts(conftime), ts(ctime),
                        current_time-stat_time, max_stat_time_diff,
                        current_time-config_time, max_config_time_diff)
            logging.error(msg)
            message = {}
            message['host'] = self.host
            message['state'] = 'error'
            message['service'] = 'proxy_stat'
            message['metric'] = 0
            message['description'] = msg
            self.queue(message)

            self.send_exit()

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

    def get_errors(self, js):
        errors = js.get('errors')
        if errors == None:
            return

        ret = []
        for err in errors:
            status = err.get('Status')
            if status == None:
                continue
            if int(status) < 500:
                continue

            ret.append(err)

        return json.dumps(ret, indent=4, separators=(',', ': '))

    def parse_proxy_stats(self, text):
        j = json.loads(text)

        handlers = j.get('handlers')
        if handlers == None:
            self.send_error_message('rps', 200, "invalid json in reply: no 'handlers': '%s'" % text)
            return

        bctl = j.get('BucketCtlStat')
        if bctl:
            self.parse_bucket_ctl_stat(bctl)

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
                    message['description'] = self.get_errors(j)

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
