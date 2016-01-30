#!/usr/bin/python

import noscript_parser
import shutil
import docker
import logging
import os
import sys
import json
import time
import requests

logging.basicConfig(filename='/var/log/supervisor/test_writer.log',
        format='%(asctime)s %(levelname)s: test_writer: %(message)s',
        level=logging.INFO)
logging.getLogger().setLevel(logging.INFO)

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
                    'GOGC1': '100',
                    'GOTRACEBACK': 'crash',
                    'GODEBUG': 'gctrace=1,schedtrace=60000,scheddetail=1',
                    'GOMAXPROCS': 32
                }
        )

        nc = c.start(new_cnt['Id'],
                binds = {
                    self.acl_base_dir : {
                        'bind':     '/mnt/elliptics',
                        'ro':       False,
                    },
                },
                port_bindings = self.acl_port_mapping
        )

        logging.info("start_container: new container has been started: %s", new_cnt)

        state = {}
        state['restart_time'] = time.time()
        state['next_check_time'] = time.time() + 15.0

        self.write_previous(state)

        message = {}
        message['service'] = 'test_writer'
        message['host'] = self.host
        message['metric'] = 666
        message['state'] = 'error'
        message['description'] = 'new container has been started: %s' % (new_cnt)

        return message

    def copy_logs(self):
            c = docker.Client(base_url='unix://var/run/docker.sock')
            # only read container logs if we should not restart container
            # reading log may take a really long time (minute or so)
            for cnt in c.containers(limit = 10):
                if 'backrunner' in cnt['Command']:
                    id = cnt['Id']
                    try:
                        fail = '%s/log/%s.stderr.fail' % (self.acl_base_dir, id)
                        if not os.path.exists(fail):
                            stderr = c.logs(id, stderr=True, timestamps=True)
                            if len(stderr) != 0:
                                with open(fail, 'w') as f:
                                    f.write(stderr)

                            logging.info("copy_logs: container: %s, error log: %s, size: %d",
                                id, fail, len(stderr))
                    except Exception as e:
                        logging.error("copy_logs: could not read %s container's log: %s", id, e)

    def restart_proxy(self):
        try:
            need_new_container = True
            message = {}
            message['service'] = 'test_writer'
            message['host'] = self.host
            message['metric'] = 666
            message['state'] = 'error'

            c = docker.Client(base_url='unix://var/run/docker.sock')
            try:
                for cnt in c.containers():
                    if 'backrunner' in cnt['Command']:
                        id = cnt['Id']

                        message, need_restart = self.check_get()
                        if not need_restart:
                            logging.info("restart_proxy: container: %s, check_get() returned ok: message: %s, need_restart: %s",
                                id, message, need_restart)
                            need_new_container = False
                            break

                        c.stop(id, timeout=1)
                        logging.info("restart_proxy: container has been stopped: %s", id)
                        break
            except Exception as e:
                logging.error("restart_proxy: could not stop docker container: %s", e)

            logging.info("restart_proxy: need_new_container: %s", need_new_container)
            if need_new_container:
                # searching for the previous container ID to copy current log
                id = 'restart'
                for cnt in c.containers(limit = 10):
                    if 'backrunner' in cnt['Command']:
                        # if there was no running backrunner container, ID is not set
                        # set it to the last running container, it is needed for proper log rename

                        id = cnt['Id']
                        break

                t = time.strftime("%Y.%m.%d-%H:%M:%S")

                backrunner_profile = '%s/root/backrunner.profile' % (self.acl_base_dir)
                new_profile = '%s/root/backrunner.profile-%s' % (self.acl_base_dir, t)

                backrunner_log = '%s/log/backrunner.log' % (self.acl_base_dir)
                new_log = '%s/log/backrunner.log.fail-%s-%s' % (self.acl_base_dir, t, id)
                try:
                    shutil.move(backrunner_log, new_log)
                except:
                    pass

                try:
                    shutil.move(backrunner_profile, new_profile)
                except:
                    pass

                logging.info("restart_proxy: log and profile have been moved: %s -> %s, %s -> %s",
                        backrunner_log, new_log, backrunner_profile, new_profile)

                message = self.start_container(c)
        except Exception as e:
            logging.error("restart_proxy: could not start new docker container: %s", e)
            message['description'] = 'could not start new docker container: %s' % (e)

        return message

    def check_get(self):
        url = "http://%s:%d/ping/" % (self.host, self.acl_port)

        logging.info("check_get: checking %s url", url)

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

        logging.info("check_get: need_restart: %s, message: %s",
                need_restart, message)

        return message, need_restart

    def check_upload(self, timeout=5):
        data = "test upload at: %s" % (time.time())

        url = "http://%s:%d/nobucket_upload/test_writer.txt" % (self.host, self.acl_port)

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
                    if len(sgroups) < self.acl_success_groups:
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
            logging.error("could not connect to %s: %s", self.host, e)
            message['state'] = 'error'
            message['description'] = "%s" % e
            need_restart = True

        logging.info("check_upload: need_restart: %s, message: %s",
                need_restart, message)

        return message, need_restart

    def need_check(self):
        current_time = time.time()
        next_check_time = current_time

        prev = self.read_previous()
        next_check_time_str = prev.get('next_check_time')
        if next_check_time_str != None:
            next_check_time = float(next_check_time_str)

        will_check = current_time >= next_check_time
        logging.info("need_check: current-time: %f, next_check_time: %s, %s, will_check: %s",
                current_time, next_check_time_str, time.ctime(next_check_time), will_check)

        return will_check

    def upload_and_restart(self):
        need_check = self.need_check()
        if need_check:
            message, need_restart = self.check_upload(5)
            if need_restart:
                message = self.restart_proxy()

            logging.info("upload_and_restart: message: %s", message)
            self.send_all(message)

        self.copy_logs()

if __name__ == '__main__':
    t = test_writer(sys.argv[1], '/var/tmp/crocodile.test_writer.state')
    t.upload_and_restart()
