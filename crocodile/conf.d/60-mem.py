#!/usr/bin/python

import noscript_parser

import logging
import psutil
import subprocess
import sys
import time

logging.basicConfig(filename='/var/log/supervisor/memory.log',
        format='%(asctime)s %(levelname)s: discrepancy: %(message)s',
        level=logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)

class memory_parser(noscript_parser.parser):
    error = 80
    warning = 70
    ioserv = 'dnet_ioserv'

    def get_trace(self):
        out = ''
        for proc in psutil.process_iter():
            if proc.name() == self.ioserv:
                if proc.memory_percent() > self.warning:
                    args = ['/usr/bin/gdb', '-ex', 'set pagination 0', '-ex', 'thread apply all bt', '--batch', '-p', str(proc.pid)]
                    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    out, err = p.communicate()

                    out += '\n\n%s\n' % (str(proc.memory_info_ex()))
                    for pg in proc.memory_maps():
                        out += '%s: rss: %d\n' % (pg.path, pg.rss)
                break

        return out

    def memory(self):
        sv = psutil.virtual_memory()

        message = {}
        message['service'] = 'memory'
        message['host'] = self.host
        message['state'] = 'normal'
        message['metric'] = sv.available
        message['description'] = ''

        if sv.percent > self.error:
            message['state'] = 'error'
            message['description'] = self.get_trace()
        elif sv.percent > self.warning:
            message['state'] = 'warning'
            message['description'] = self.get_trace()

        logging.info(message)
        self.send_all(message)

if __name__ == '__main__':
    p = memory_parser(sys.argv[1])
    p.memory()
