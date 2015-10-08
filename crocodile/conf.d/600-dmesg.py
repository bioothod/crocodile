#!/usr/bin/python

#import sys, os
#sys.path.append(os.path.dirname(os.path.abspath(sys.argv[0])))
import noscript_parser

import sys
import re
import os, io, fcntl
import time
import logging

logging.basicConfig(filename='/var/log/supervisor/dmesg.log',
        format='%(asctime)s %(levelname)s: dmesg: %(message)s',
        level=logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)

re_WARN=re.compile('error|warning|fail|\(da[0-9]+:[a-z0-9]+:[0-9]+:[0-9]+:[0-9]+\)|Non-Fatal Error DRAM Controler|nf_conntrack')
re_IGNORE=re.compile('dracut: Remounting|ACPI|acpi|ehci_hcd|uses 32-bit capabilities|GHES: Poll interval|acpi_throttle[0-9]: failed to attach P_CNT|aer|aer_init: AER service init fails|aer: probe of|arplookup|(at [0-9a-f]+)? rip[: ][0-9a-f]+ rsp[: ][0-9a-f]+ error[: ]|Attempt to query device size failed|check_tsc_sync_source failed|failed SYNCOOKIE authentication|igb:|ipfw: pullup failed|Marking TSC|mfi|MOD_LOAD|MSI interrupts|nfs send error 32 |NO_REBOOT|optimal|page allocation failure|PCI error interrupt|pid [0-9]+|rebuild|Resume from disk failed|rwsem_down|smb|swap_pager_getswapspace|thr_sleep|uhub[0-9]|ukbd|usbd|EDID|radeon|drm:r100_cp_init|Opts: errors=remount-ro|nf_conntrack version|nf_conntrack: falling back to vmalloc|Fast TSC calibration failed|ioapic: probe of')
re_CRIT=re.compile('I/O error|medium|defect|mechanical|retrying|broken|degraded|offline|failed|unconfigured_bad|conntrack: table full|Unrecovered read error|fs error|Medium Error|Drive ECC error|Out of memory|Killed process|oom-killer')
re_dmesg_line=re.compile('^(\d+),(\d+),(?P<timestamp>\d+),(.*);')

class dmesg_parser(noscript_parser.parser):
    def check_line(self, line):
        m = re_dmesg_line.search(line)
        if m != None:
            ts = int(m.group('timestamp'))
            prev_ts = 0
            prev_update_time = 0

            prev = self.read_previous()
            tmp = prev.get('timestamp')
            if tmp != None:
                prev_ts = int(tmp)

            tmp = prev.get('update_time')
            if tmp != None:
                prev_update_time = float(tmp)

            #print "ts: %d, prev_ts: %d, >: %s: %s" % (ts, prev_ts, ts > prev_ts, line)

            # collect given dmesg line if it was printed after previous collection
            # or after an hour after previous update
            # do not print dmesg data which is more than day old

            line_time = time.time() - self.uptime() + ts / 1000000
            if line_time < time.time() - 3600 * 24:
                return False

            if ts > prev_ts or time.time() > prev_update_time + 3600:
                prev['timestamp'] = ts
                prev['update_time'] = time.time()
                self.write_previous(prev)
                return True

        return False

    def dmesg(self):
        with io.open('/dev/kmsg', 'rt') as f:
            fd = f.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

            content = ''
            total_lines = 0
            while True:
                try:
                    line = f.readline()
                except io.BlockingIOError:
                    break

                if not line:
                    break

                ignore = re_IGNORE.search(line)
                if ignore != None:
                    continue

                prefix = "CRITICAL"
                crit = re_CRIT.search(line)
                if crit == None:
                    warn = re_WARN.search(line)
                    if warn == None:
                        continue
                    prefix = "WARNING"

                total_lines += 1
                if self.check_line(line):
                    content += "%s: %s" % (prefix, line)

            if len(content) != 0:
                self.send_dmesg(content, total_lines)

    def send_dmesg(self, msg, total_lines):
        message = {}
        message['state'] = 'error'
        message['description'] = msg
        message['service'] = 'dmesg'
        message['metric'] = total_lines

        self.send_all(message)

if __name__ == '__main__':
    p = dmesg_parser(sys.argv[1], '/var/tmp/crocodile.dmesg.parser')
    try:
        p.dmesg()
    except Exception as e:
        p.send_error_message('dmesg', 666, "dmesg exception: %s" % e)
