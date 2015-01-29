#!/usr/bin/python

import requests, json, time, sys, socket, bernhard
import logging
import os, io, fcntl
import re

re_WARN=re.compile('error|warning|fail|\(da[0-9]+:[a-z0-9]+:[0-9]+:[0-9]+:[0-9]+\)|Non-Fatal\ Error\ DRAM\ Controler|nf_conntrack')
re_IGNORE=re.compile('acpi|ehci_hcd|uses\ 32-bit\ capabilities|GHES:\ Poll\ interval|acpi_throttle[0-9]:\ failed\ to\ attach\ P_CNT|aer|aer_init:\ AER\ service\ init\ fails|aer:\ probe\ of|arplookup|(at [0-9a-f]+)? rip[: ][0-9a-f]+ rsp[: ][0-9a-f]+ error[: ]|Attempt\ to\ query\ device\ size\ failed|check_tsc_sync_source\ failed|failed\ SYNCOOKIE\ authentication|igb:|ipfw:\ pullup\ failed|Marking\ TSC\|mfi|MOD_LOAD|MSI\ interrupts|nfs\ send\ error\ 32\ |NO_REBOOT|optimal|page\ allocation\ failure|PCI\ error\ interrupt|pid\ [0-9]+|rebuild|Resume\ from\ disk\ failed|rwsem_down|smb|swap_pager_getswapspace|thr_sleep|uhub[0-9]|ukbd|usbd|EDID|radeon|drm:r100_cp_init|Opts: errors=remount-ro|nf_conntrack version')
re_CRIT=re.compile('I/O error|medium|defect|mechanical|retrying|broken|degraded|offline|failed|unconfigured_bad|conntrack:\ table\ full|Unrecovered read error|fs error|Medium Error|Drive ECC error')

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
        return

        logging.debug("send_all: %s", message)
        for c in self.clients:
            c.send(message)

    def dmesg(self):
        with io.open('/dev/kmsg', 'rt') as f:
            fd = f.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

            content = ''
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

                crit = re_CRIT.search(line)
                if crit != None:
                    content += line
                    continue

                warn = re_WARN.search(line)
                if warn != None:
                    content += line
                    continue

            if len(content) != 0:
                self.send_dmesg(content)

    def send_dmesg(self, msg):
        message = {}
        message['state'] = 'error'
        message['description'] = msg
        message['host'] = self.host
        message['service'] = 'dmesg'
        message['metric'] = 666

        self.send_all(message)

if __name__ == '__main__':
    p = parser(sys.argv[1])
    p.dmesg()
