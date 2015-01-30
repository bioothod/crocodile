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

class test_writer(noscript_parser.parser):
    def start_container(self, c):
        start_params = {
            'Image': 'reverbrain/backrunner:latest',
            'Ports': self.acl_port_mapping.keys(),
            'Command': '/root/go/bin/backrunner -config /mnt/elliptics/etc/backrunner.conf -buckets /mnt/elliptics/etc/buckets.production',
        }

        new_cnt = c.create_container(
                image           = start_params['Image'],
                command         = start_params['Command'],
                ports           = start_params['Ports'],
                volumes         = ['/mnt/elliptics'],
                environment     = {
                    'GOGC': '200',
                    'GOTRACEBACK': 'crash',
                    'GODEBUG': 'invalidptr=0'
                }
        )

        nc = c.start(new_cnt['Id'],
                binds = {
                    self.acl_base_dir : {
                        'bind':     '/mnt/elliptics',
                        'ro':       False,
                    },
                },
                port_bindings = self.acl_port_mapping,
                restart_policy = {
                    'Name': 'on-failure'
                },
        )

        logging.info("new container has been started: %s", new_cnt)

        message = {}
        message['service'] = 'test_writer'
        message['host'] = self.host
        message['metric'] = 666
        message['state'] = 'error'
        message['description'] = 'new container has been started: %s' % (new_cnt)

        return message

    def restart_proxy(self):
        try:
            need_new_container = True
            message = {}
            message['service'] = 'test_writer'
            message['host'] = self.host
            message['metric'] = 666
            message['state'] = 'error'

            id = 'restart'
            stderr = ''
            c = docker.Client(base_url='unix://var/run/docker.sock')
            try:
                for cnt in c.containers():
                    if 'backrunner' in cnt['Command']:
                        id = cnt['Id']

                        time.sleep(1)
                        message, need_restart = self.check_get()
                        if not need_restart:
                            need_new_container = False
                            break

                        if need_restart:
                            c.stop(id)
                            stderr = c.logs(id, stderr=True, timestamps=True)
                            logging.info("restart: container has been stopped: %s", id)
                            break
            except Exception as e:
                logging.error("restart: could not restart docker container: %s", e)

            if need_new_container:
                backrunner_log = '%s/log/backrunner.log' % (self.acl_base_dir)
                base = os.path.dirname(backrunner_log)
                new_log = '%s/%s.backrunner.log.fail' % (base, id)
                try:
                    shutil.move(backrunner_log, new_log)
                    if len(stderr) != 0:
                        with open('%s/%s.stderr.fail' % (base, id), 'w') as f:
                            f.write(stderr)

                    logging.info("restart: log file has been moved: %s -> %s",
                            backrunner_log, new_log)
                except:
                    pass


                message = self.start_container(c)
        except Exception as e:
            logging.error("restart: could not start new docker container: %s", e)
            message['description'] = 'could not start new docker container: %s' % (e)

        return message

    def check_get(self):
        data = "test get at: %s" % (time.time())

        url = "http://%s:%d/ping/" % (self.host, self.acl_port)

        headers = {}
        if self.acl_user != '' and self.acl_token != '':
            headers['Authorization'] = 'riftv1 {0}:{1}'.format(
                    self.acl_user,
                    self.generate_signature(self.acl_token, 'GET', url))

        message = {}
        message['service'] = 'test_writer'
        message['host'] = self.host

        need_restart = False

        try:
            r = requests.get(url, headers=headers, timeout=5)
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

        except Exception as e:
            message['state'] = 'error'
            message['description'] = "%s" % e
            need_restart = True

        logging.debug("check_get: need_restart: %s, message: %s",
                need_restart, message)

        return message, need_restart

    def check_upload(self, timeout=5):
        data = "test upload at: %s" % (time.time())

        url = "http://%s:%d/nobucket_upload/test_writer.txt" % (self.host, acl_port)

        headers = {}
        if self.acl_user != '' and self.acl_token != '':
            headers['Authorization'] = 'riftv1 {0}:{1}'.format(
                    self.acl_user,
                    self.generate_signature(self.acl_token, 'POST', url))

        message = {}
        message['service'] = 'test_writer'
        message['host'] = self.host

        need_restart = False

        try:
            r = requests.post(url, data=data, headers=headers, timeout=timeout)
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
                        message['state'] = 'warning'
                        message['description'] = "not enough success results: %d instead of %d: %s" % (len(sgroups), self.acl_success_groups, r.text)
                    if len(egroups) != 0:
                        message['state'] = 'warning'
                        message['description'] = "there are %d error results: %s" % (len(egroups), r.text)
                    if len(sgroups) < self.acl_success_groups / 2:
                        message['state'] = 'error'
                        message['description'] = "not enough success results (less than a half of all groups): %d instead of (maximum) %d: %s" % (len(sgroups), self.acl_success_groups, r.text)
                except Exception as e:
                        message['state'] = 'error'
                        message['description'] = "could not parse reply: '%s': %s" % (r.text, e)

        except Exception as e:
            message['state'] = 'error'
            message['description'] = "%s" % e
            need_restart = True

        logging.debug("check_upload: need_restart: %s, message: %s",
                need_restart, message)

        return message, need_restart

    def upload_and_restart(self):
        message, need_restart = self.check_upload(5)
        if need_restart:
            message = self.restart_proxy()

        logging.info("upload_and_restart: message: %s", message)
        self.send_all(message)

if __name__ == '__main__':
    t = test_writer(sys.argv[1])
    t.upload_and_restart()
