#!/usr/bin/python

import elliptics
import noscript_parser
import logging
import socket
import sys

backend_log='/var/log/supervisor/backends.log'
#backend_log='/dev/stdout'

logging.basicConfig(filename=backend_log,
        format='%(asctime)s %(levelname)s: backends: %(message)s',
        level=logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)

class backends_parser(noscript_parser.parser):
    def __init__(self, addr):
        noscript_parser.parser.__init__(self, addr)

        self.port = 1025
        self.family = socket.AF_INET

        self.logger = elliptics.Logger(backend_log, elliptics.log_level.info)

        cfg = elliptics.Config()
        cfg.wait_timeout = 120
        cfg.check_timeout = 300
        cfg.io_thread_num = 1
        cfg.nonblocking_thread_num = 1
        cfg.net_thread_num = 1
        cfg.flags = elliptics.config_flags.no_route_list
        self.node = elliptics.Node(self.logger, cfg)

        self.address = elliptics.Address(host=self.host, port=self.port, family=self.family)
        self.node.add_remotes(self.address)

        self.session = elliptics.Session(self.node)

    def start_backend(self, st):
        nst = self.session.enable_backend(self.address, st.backend_id).get()[0].backends[0]
        logging.info("addr: %s, backend: %d, state: %d -> %d, err: %d",
                self.address, st.backend_id, st.state, nst.state, nst.last_start_err)

    def backends_stat(self):
        stopped = []

        statuses = self.session.request_backends_status(self.address).get()[0].backends
        for st in statuses:
            logging.debug("addr: %s: backend: %d, state: %s, defrag: %s, err: %d, ro: %d",
                    self.address, st.backend_id, st.state, st.defrag_state, st.last_start_err, st.read_only)

            if st.state != 1:
                stopped.append(st)
                try:
                    #self.start_backend(st)
                    pass
                except Exception as e:
                    msg = "addr: %s: could not start backend: %d, last-err: %d: %s" % (
                            self.address, st.backend_id, st.last_start_err, e)

                    logging.error(msg)
                    self.send_error_message('backends', 1, msg)

        logging.info("addr: %s: parsed backends: %d, stopped: %d", self.address, len(statuses), len(stopped))

        if len(stopped) != 0:
            msg = 'addr: %s, stopped backends: %d\n' % (self.address, len(stopped))
            for st in stopped:
                msg += '  backend: %d, state: %d, defrag: %d, ro: %d, err: %d\n' % (
                    st.backend_id, st.state, st.defrag_state, st.read_only, st.last_start_err)

            self.send_error_message('backends', len(stopped), msg)


if __name__ == '__main__':
    p = backends_parser(sys.argv[1])
    try:
        p.backends_stat()
    except Exception as e:
        logging.error("stat exception: %s", e)
        self.send_error_message('backends', 22, e)
