#!/usr/bin/env python2.7
#

import os
import sys
import logging
import argparse
import threading

# Include daemons/xnetjd in path so network joining py modules can be loaded
srcdir = os.getcwd()[:os.getcwd().rindex('xia-core')+len('xia-core')]
sys.path.append(os.path.join(srcdir, "daemons/xnetjd"))

# Put XIA API in path
from netjoin_xiaconf import NetjoinXIAConf
conf = NetjoinXIAConf()
sys.path.append(conf.get_swig_path())
sys.path.append(conf.get_clickcontrol_path())

from netjoin_policy import NetjoinPolicy
from netjoin_receiver import NetjoinReceiver
from netjoin_announcer import NetjoinAnnouncer
from netjoin_authsession import NetjoinAuthsession

# Setup logging for this application
logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(module)s %(levelname)s: %(message)s')

# Argument parser
def parse_args():
    parser = argparse.ArgumentParser(description="XIA Network Joining Manager")
    parser.add_argument("-c", "--client",
            help="process network discovery beacons", action="store_true")
    parser.add_argument("-a", "--accesspoint",
            help="announce network on all interfaces", action="store_true")
    parser.add_argument("-i", "--beacon_interval",
            help="beacon interval in seconds(float)", type=float, default=0.5)
    parser.add_argument("--hostname",
            help="click hostname", type=str)
    return parser.parse_args()

# Parse arguments and launch necessary threads
def main():

    # Parse user provided arguments
    args = parse_args()

    # All threads must listen for this event and exit gracefully when set
    shutdown_event = threading.Event()

    # List of all threads
    threads = []

    # Initialize the policy module
    # For now we have one policy for all beacons.
    # TODO: Pass list of auth providers
    policy = NetjoinPolicy()

    announcer = None
    if args.accesspoint:
        logging.debug("Announcing network and listening for join requests")
        # Start an auth session for announcer
        announcer = NetjoinAnnouncer(args.beacon_interval, shutdown_event)
        announcer.announce()

    if args.client:
        logging.debug("Listening for network announcements")

    # Start a new thread to listen for messages
    receiver = NetjoinReceiver(args.hostname, policy, announcer, shutdown_event)
    receiver.daemon = True
    receiver.start()
    threads.append(receiver)

    # We block here until the user interrupts or kills the program
    try:
        for thread in threads:
            while thread.is_alive():
                thread.join(timeout=1.0)
    except (KeyboardInterrupt, SystemExit):
        shutdown_event.set()

if __name__ == "__main__":
    main()
