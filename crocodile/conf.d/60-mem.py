#!/usr/bin/python

import noscript_parser

import logging
import psutil
import subprocess
import sys
import time

logging.basicConfig(filename='/var/log/supervisor/memory.log',
        format='%(asctime)s %(levelname)s: discrepancy: %(message)s',
        level=logging.INFO)
logging.getLogger().setLevel(logging.INFO)

class memory_parser(noscript_parser.parser):
    error = 60
    warning = 50
    ioserv = 'dnet_ioserv'
    backrunner = 'backrunner'

    def get_trace_raw(self, total_used_percent):
        out = ''
        for proc in psutil.process_iter():
            if proc.memory_percent() < self.warning:
                continue

            out = 'process: %s, total memory usage: %d, process memory usage: %d, warning: %d, error: %d\n' % (
                    proc.name(), proc.memory_percent(), self.warning, self.error, self.critical)
            if proc.memory_percent() > self.error or total_used_percent > self.error:
                out += '  PROCESS WILL BE KILLED\n\n\n'

            if proc.name() == self.backrunner:
                backrunner_profile = '%s/root/backrunner.profile' % (self.acl_base_dir)
                with open(backrunner_profile, 'r') as f:
                    out += f.read()

            if proc.name() == self.ioserv:
                args = ['/usr/bin/gdb', '-ex', 'set pagination 0', '-ex', 'thread apply all bt', '--batch', '-p', str(proc.pid)]
                p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                sdata, err = p.communicate()

                out += sdata
                out += '\n\n%s\n' % (str(proc.memory_info_ex()))
                for pg in proc.memory_maps():
                    out += '%s: rss: %d\n' % (pg.path, pg.rss)

            if total_used_percent > self.error:
                os.kill(proc.pid, signal.SIGKILL)
            elif proc.memory_percent() > self.error:
                os.kill(proc.pid, signal.SIGTERM)

        return out

    def get_trace(self, total_used_percent):
        out = ''
        try:
            out = self.get_trace_raw(total_used_percent)
        except Exception as e:
            logging.error("exception: %s", e)
            out = e

        return out

    def memory(self):
        sv = psutil.virtual_memory()

        message = {}
        message['service'] = 'memory'
        message['host'] = self.host
        message['state'] = 'normal'
        message['metric'] = sv.available
        message['description'] = ''

        if sv.percent > self.warning:
            message['state'] = 'warning'
            message['description'] = self.get_trace(sv.percent)

            if sv.percent > self.error:
                message['state'] = 'error'

        logging.info(message)
        self.send_all(message)

if __name__ == '__main__':
    p = memory_parser(sys.argv[1])
    p.memory()
