#!/usr/bin/python

import noscript_parser

import json
import logging
import requests
import socket
import sys
import time

logging.basicConfig(filename='/var/log/supervisor/discrepancy.log',
        format='%(asctime)s %(levelname)s: discrepancy: %(message)s',
        level=logging.DEBUG)

class stat_parser(noscript_parser.parser):
    def send_error_message(self, metric, description):
        message = {}
        message['service'] = 'discrepancy'
        message['host'] = self.host
        message['state'] = 'error'
        message['metric'] = metric
        message['description'] = description

        logging.error("send_error_message: %s", message['description'])
        self.send_all(message)

    def parse_groups_stats(self, bname, groups):
        class group_stat:
            def __init__(self):
                self.total = 0
                self.avail = 0
                self.removed = 0
                self.used = 0
                self.records_total = 0
                self.records_removed = 0
                self.records_corrupted = 0

            def update(self, vfs):
                self.total += int(vfs['Total'])
                self.avail += int(vfs['Avail'])
                self.removed += int(vfs['BackendRemovedSize'])
                self.used += int(vfs['BackendUsedSize'])
                self.records_total += int(vfs['RecordsTotal'])
                self.records_removed += int(vfs['RecordsRemoved'])
                self.records_corrupted += int(vfs['RecordsCorrupted'])

            def diff(self, other):
                diff = {}
                diff['used_space'] = abs((self.used - self.removed) - (other.used - other.removed))
                diff['used_records'] = abs((self.records_total - self.records_removed) - (other.records_total - other.records_removed))

                return diff

        stats = {}
        for group_id, group in groups.items():
            backends = group.get('Backends')
            if backends == None:
                raise Exception("group: %s: invalid json in reply: no 'Backends': %s" % (group_id, group))

            st = group_stat()
            for backend in backends:
                try:
                    error = int(backend['Stat']['error']['code'])
                    if error != 0:
                        # timeout error is quite common, do not send/expire this event
                        if error != 110:
                            self.send_error_message(int(error), "bucket: %s, group: %s, statistics error: %d" %
                                    (bname, group_id, error))

                        # if statistics contains an error, discrepancy will always be incorrect, stop processing this bucket
                        return
                except Exception as e:
                    raise Exception("group: %s: invalid json in reply: no 'Stat.error.code': %s, error: %s" % (group_id, backend, e))

                try:
                    vfs = backend['Stat']['VFS']
                    st.update(vfs)
                except Exception as e:
                    raise Exception("group: %s: invalid json in reply: no 'Stat.VFS': %s, error: %s" % (group_id, backend, e))

            stats[group_id] = st


        message = {}
        message['host'] = self.host

        base = None
        for group_id, st in stats.items():
            if st.records_corrupted != 0:
                self.send_error_message(st.records_corrupted, "bucket: %s, group: %s, corrupted records: %d" %
                        (bname, group_id, st.records_corrupted))

            # do not process zero stats, this can happen either if there is no data at all, and in this case discrepancy is zero,
            # or when there is no stat (node was down, client failed to read stat and so on), in this case discrepancy will
            # skyrocket and is meaningless
            if st.total == 0:
                return

            if base == None:
                base = st
                continue

            diff = base.diff(st)

            message['state'] = 'info'

            message['service'] = 'discrepancy space %s' % (bname)
            message['metric'] = diff['used_space']
            message['description'] = time.ctime()
            self.send_all(message)

            message['service'] = 'discrepancy records %s' % (bname)
            message['metric'] = diff['used_records']
            message['description'] = time.ctime()
            self.send_all(message)


    def parse_stats(self, text):
        j = json.loads(text)

        buckets = j.get('Buckets')
        if buckets == None:
            self.send_error_message(200, "invalid json in reply: no 'Buckets': '%s'" % text)
            return

        message = {}
        message['host'] = self.host

        for bname, bucket in buckets.items():
            groups = bucket.get('Group')
            if groups == None:
                self.send_error_message(200, "bucket: %s, invalid json in reply: no 'Group': '%s'" % (bname, bucket))
                continue

            meta = bucket.get('Meta')
            if meta == None:
                self.send_error_message(200, "bucket: %s, invalid json in reply: no 'Meta': '%s'" % (bname, bucket))
                continue

            meta_groups = meta.get('groups')
            if meta == None:
                self.send_error_message(200, "bucket: %s, invalid json in reply: no 'Meta.groups': '%s'" % (bname, bucket))
                continue

            if len(groups) != len(meta_groups):
                self.send_error_message(200, "bucket: %s: bucket is not fully not connected: connected: %s, must be: %s"
                        % (bname, groups, meta_groups))
                continue

            try:
                self.parse_groups_stats(bname, groups)
            except Exception as e:
                self.send_error_message(200, "bucket: %s: error: %s" % (bname, e))
                continue

    def stat(self):
        url = "http://%s:%d/stat/" % (self.host, self.acl_port)

        headers = {}
        if self.acl_user != '' and self.acl_token != '':
            headers['Authorization'] = 'riftv1 {0}:{1}'.format(
                    self.acl_user,
                    self.generate_signature(self.acl_token, 'GET', url))

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

        self.parse_stats(text)


if __name__ == '__main__':
    p = stat_parser(sys.argv[1])
    p.stat()
