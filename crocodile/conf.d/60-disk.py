#!/usr/bin/python

import noscript_parser
import bernhard, os, subprocess, socket, ast, sys, re

class disk_parser(noscript_parser.parser):

    def elliptics_check_defragmentation(self, path):
        """
        Checks $path/elliptics/data/data.stat file
        if it has been found, it tries to parse eblob stat there
        if succeeded, checks whether defragmentation is being running
        """

        defrag_in_progress = False
        defrag_description = 'no defragmentation process'

        stat_file = '%s/elliptics/data/data.stat' % (path)
        try:
            with open(stat_file, 'r') as st:
                stat_data = st.read()

                datasort_start_time = 0
                datasort_completion_time = 0

                m = re.search('datasort_start_time: (\d+)', stat_data)
                if m != None:
                    datasort_start_time = int(m.group(1))

                m = re.search('datasort_completion_time: (\d+)', stat_data)
                if m != None:
                    datasort_completion_time = int(m.group(1))

                if datasort_start_time > datasort_completion_time:
                    defrag_in_progress = True
                    defrag_description = 'defragmentation is in progress, started at %s' % (time.ctime(datasort_start_time))
                    logging.info("%s: %s", path, defrag_description)

        except Exception as e:
            pass

        return defrag_in_progress, defrag_description

    def disk_partitions(self, all=False):
        """Return all mountd partitions as a nameduple.
        If all == False return phyisical partitions only.
        """
        phydevs = []
        f = open("/proc/filesystems", "r")
        for line in f:
            if not line.startswith("nodev"):
                phydevs.append(line.strip())

        retlist = []
        f = open('/etc/mtab', "r")
        for line in f:
            if not all and line.startswith('none'):
                continue
            fields = line.split()
            device = fields[0]
            mountpoint = fields[1]
            fstype = fields[2]
            if not all and fstype not in phydevs:
                continue
            if device == 'none':
                device = ''
            ntuple = (device, mountpoint)
            retlist.append(ntuple)
        return retlist

    def disk_usage(self, dev, path):
        message = {}
        message['service'] = 'disk ' + dev

        try:
            """Return disk usage associated with path."""
            st = os.statvfs(path)
            free = (st.f_bavail * st.f_frsize)
            total = (st.f_blocks * st.f_frsize)
            used = (st.f_blocks - st.f_bfree) * st.f_frsize
            try:
                percent = ret = (float(used) / total) * 100
            except ZeroDivisionError:
                percent = 0

            defrag_in_progress, defrag_description = self.elliptics_check_defragmentation(path)

            attr = {}
            attr['total'] = total
            attr['used'] = used
            attr['free'] = free
            attr['used_percentage'] = percent
            attr['defrag_in_progress'] = defrag_in_progress
            attr['defrag_description'] = defrag_description

            message['metric'] = free
            message['attributes'] = attr
            message['state'] = 'info'

            if defrag_in_progress:
                if percent > 90:
                    message['state'] = 'error'
                elif percent > 86:
                    message['state'] = 'warning'
            else:
                if percent > 86:
                    message['state'] = 'error'
        except Exception as e:
            message['state'] = 'error'
            message['description'] = "exception: %s" % (e)

        self.send_all(message)

    def disk(self):
        for part in self.disk_partitions():
            self.disk_usage(part[0], part[1])

if __name__ == '__main__':
    p = disk_parser(sys.argv[1], '/var/tmp/crocodile.disk.parser')
    p.disk()
