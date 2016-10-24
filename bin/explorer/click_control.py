#!/usr/bin/env python
#
# Copyright 2012 Carnegie Mellon University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import sys
import time
import re
import telnetlib
import requests

# default Click host and port
CLICK = "localhost"
CLICK_PORT = 7777

# Minimum Click version required
MAJOR = 1
MINOR = 3

# principal types
DOMAIN = 1
HOST = 2
SERVICE = 3
CONTENT = 4
IPV4 = 5


#
# converts a string to a principal type number
#
def get_principal_from_string(principal_string):
    principal_string = principal_string.lower()
    if 'content' in principal_string or 'cid' in principal_string:
        return CONTENT
    elif 'service' in principal_string or 'sid' in principal_string:
        return SERVICE
    elif 'host' in principal_string or 'hid' in principal_string:
        return HOST
    elif 'domain' in principal_string or 'ad' in principal_string:
        return DOMAIN
    elif 'ip' in principal_string or '4id' in principal_string:
        return IPV4
    else:
        print 'Unrecognized principal type: %s' % principal_string
        return -1

#
# converts a principal type number into a string
#
def string_for_principal_type(principal_type):
    if principal_type == DOMAIN:
        return 'Domain'
    elif principal_type == HOST:
        return 'Host'
    elif principal_type == SERVICE:
        return 'Service'
    elif principal_type == CONTENT:
        return 'Content'
    elif principal_type == IPV4:
        return 'IPv4'
    else:
        raise Exception('Unknown principal type: %d', principal_type)

#
# print the message if configured to be noisy
#
def say(msg):
    if options.verbose:
        print msg

#
# click controler interface
#
class ClickControl:
    connected = False
    csock = None

    #
    # print an error message and exit the app with an error
    #
    def errorExit(self, msg):
        print msg
        self.shutdown()
        sys.exit(-1)


    #
    # get the ciick statuscode and message
    # some operations get 2 lines of status message with the code on each
    # and the second line is more useful, so the caller can specify if we should
    # die on error, or keep going and loop back for the 2nd line
    #
    def checkStatus(self, die):
        rc = self.csock.read_until("\n")
        rc = rc.strip()

        # some result code lines are in the form of 'nnn msg' and some are nnn-msg'
        # so ignore the odd character by slicing round it
        code = int(rc[:3])
        msg = rc[4:-1]
        if (die and code != 200):
            self.errorExit("error %d: %s" % (code, msg))
        return code


    #
    # read the length of data sent by click so we can consume the right
    # amout of text
    #
    def readLength(self):
        text = self.csock.read_until("\n")
        text.strip()
        (data, length) = text.split()
        if data != "DATA":
            self.errorExit("error retreiving data length")
        return int(length)


    #
    # connect to the click control socket
    #
    def connect(self):
        global options

        try:
            self.csock = telnetlib.Telnet(CLICK, CLICK_PORT)
            self.connected = True

            data = self.csock.read_until("\n")
        except:
            self.errorExit("Unable to connect to Click")

        # make sure it's really click we're talking to
        data = data.strip()
        [name, ver] = data.split("/")
        [major, minor] = ver.split(".")
        if name != "Click::ControlSocket":
            self.errorExit("Socket is not a click ControlSocket")
        if int(major) < MAJOR or (int(major) == MAJOR and int(minor) < MINOR):
            self.errorExit("Click version %d.%d or higher is required" % (MAJOR, MINOR))


    #
    # send a read command to click and return the resulting text
    #
    def readData(self, cmd):
        self.csock.write("READ %s\n" % (cmd))
        code = self.checkStatus(False)

        if code != 200:
            return None
        length = self.readLength()
        buf = ""
        while len(buf) < length:
            buf += self.csock.read_some()
        return buf

    #
    # send a write command to click and verify it worked OK
    #
    def writeData(self, cmd):
        self.csock.write("WRITE %s\n" % (cmd))
        code = self.checkStatus(False)
    
        # the click write handler returns 2 lines of status on an error, and the
        #second line contains a more useful message, so call it again
        if code != 200:
            self.checkStatus(True)


    #
    # close the connection to click
    #
    def shutdown(self):
        if (self.connected):
            self.csock.write("quit\n")


#
# XIA Route table entry
#
class Route:
    def __init__(self, kind, text):
        self.kind = kind
        (self.xid, self.port, self.nexthop, self.flags) = text.split(',')


    def __repr__(self):
        return "Route(kind=%s, xid=%s, port=%s, flags=%s, nexthop=%s)" % (self.kind, self.xid, self.port, self.flags, self.nexthop)


#
# XIA Host/Router definition
#
class Router:
    def __init__(self, name, num_ports):
        self.name = name
        self.num_ports = num_ports
        self.hid = None
        self.ad = None
        self.routes = []
        self.connections = []
        self.nextStats = {}
        self.finalStats = {}
        self.nextStatsIp = {}
        self.finalStatsIp = {}
        self.ports = []

        for port in range(0, 4):
            k = '%d:IN' % (port)
            self.finalStatsIp[k] = Stats('final')
            self.nextStatsIp[k] = Stats('next')
            k = '%d:OUT' % (port)
            self.finalStatsIp[k] = Stats('final')
            self.nextStatsIp[k] = Stats('next')


    def addRoute(self, r):
        self.routes.append(r)
        port = int(r.port)
        kind = r.kind
        next = r.nexthop

        # ignore fallback, etc ports
        if port > 4 or port < 0:
            return

        # if port is 4, get our ad or hid from the route line
        if port == 4:
            if kind == 'AD':
                self.ad = r.xid
            elif kind == 'HID':
                self.hid = r.xid
            return

        if kind == 'IP':
            if port >= 0 and port <= 3:
                if next == None or next == '':
                    next = '-'

        elif port >= 0 and port <= 3:
            kind = 'XID'
            if next == None:
                return

        if port not in self.nextStats:
            self.nextStats[port] = Stats('next')
        if port not in self.finalStats:
            self.finalStats[port] = Stats('final')
        if port not in self.ports:
            self.ports.append(port)

        c = Connection(port, kind, next)
        self.addConnection(c)


    def addConnection(self, c):
        for cc in self.connections:
            if cc.port == c.port and cc.next == c.next and cc.kind == c.kind:
                return
        self.connections.append(c)


    def reset(self):
        self.connections = []
        self.routes = []


    def __repr__(self):
        first = 1
        s = "Router(name=%s, hid=%s, ad=%s, connections=[" % (self.name, self.hid, self.ad)
        for c in self.connections:
            if first:
                first = 0
            else:
                s += ', '
            s += repr(c)
        s += '])'
        return s


    def csv(self):
        s = ''
        for c in self.connections:
            s += "%s,%s,%s,%s\n" % (self.name, self.ad, self.hid, c.csv())
        return s

    def proc_path(self):
        pass

    def cache_path(self):
        pass

    def print_path(self, port, direction):
        pass

    def route_table_path(self, principal_type):
        table_string = ''
        if principal_type == DOMAIN:
            table_string = 'rt_AD'
        elif principal_type == HOST:
            table_string = 'rt_HID'
        elif principal_type == SERVICE:
            table_string = 'rt_SID'
        elif principal_type == CONTENT:
            table_string = 'rt_CID'
        elif principal_type == IPV4:
            table_string = 'rt_IP'
        else:
            raise Exception('Unknown principal type: %d', principal_type)

        return '%s/%s' % (self.proc_path(), table_string)

    def get_routes(self, click, kind):
        pass

    def set_verbosity_for_port(self, click, port, verbosity):
        port = int(port)
        verbosity = int(verbosity)
        click.writeData("%s.verbosity %d" % (self.print_path(port, 'in'), verbosity))
        click.writeData("%s.verbosity %d" % (self.print_path(port, 'out'), verbosity))
        self.get_verbosity_for_port(click, port)

    def get_verbosity_for_port(self, click, port):
        port = int(port)
        v_in = click.readData("%s.verbosity" % (self.print_path(port, 'in')))
        v_out = click.readData("%s.verbosity" % (self.print_path(port, 'out')))
        print '%s\tPort %d Verbosity:  In: %s  Out: %s' % (self.name, port, v_in, v_out)

    def set_malicious_cache(self, click, malicious):
        click.writeData("%s.malicious %d" % (self.cache_path(), malicious))

    def get_malicious_cache(self, click):
        return click.readData("%s.malicious" % (self.cache_path()))


    def get_principal_type_enabled(self, click, principal_type):
        enabled = click.readData('%s.enabled' % self.route_table_path(principal_type))
        print '%s\t%s enabled: %s' % (self.name, string_for_principal_type(principal_type), enabled)

    def set_principal_type_enabled(self, click, principal_type, enabled):
        enabled = int(enabled)
        click.writeData('%s.enabled %d' % (self.route_table_path(principal_type), enabled))
        self.get_principal_type_enabled(click, principal_type)


# TODO: Eventually remove this class
class LegacyRouter(Router):
    def get_routes(self, click, kind):
        return click.readData("%s/n/proc/rt_%s/rt.list" % (self.name, kind))

    def proc_path(self):
        return '%s/n/proc' % self.name

    def cache_path(self):
        return '%s/cache' % self.name

    def print_path(self, port, direction):
        return '%s/%s%d_print' % (self.name, direction, port)

class MattRouter(Router):
    def get_routes(self, click, kind):
        return click.readData("%s/xrc/n/proc/rt_%s.list" % (self.name, kind))

    def proc_path(self):
        return '%s/xrc/n/proc' % self.name

    def cache_path(self):
        return '%s/xrc/cache' % self.name

    def print_path(self, port, direction):
        pass


# Legacy router subclasses
class EndHost(LegacyRouter):
    pass

class XRouter(LegacyRouter):
    pass

class DualRouter(LegacyRouter):
    pass

# Matt router subclasses
class XIARouter(MattRouter):
    def print_path(self, port, direction):
        return '%s/xlc%d/print_%s' % (self.name, port, direction)

class XIAEndHost(MattRouter):
    def print_path(self, port, direction):
        return '%s/xlc/print_%s' % (self.name, direction)

class MattDualElement(MattRouter):
    def print_path_ip(self, port, direction):
        pass

    def set_verbosity_for_port(self, click, port, verbosity):
        port = int(port)
        verbosity = int(verbosity)
        click.writeData("%s.verbosity %d" % (self.print_path(port, 'in'), verbosity))
        click.writeData("%s.verbosity %d" % (self.print_path(port, 'out'), verbosity))
        click.writeData("%s.verbosity %d" % (self.print_path_ip(port, 'in'), verbosity))
        click.writeData("%s.verbosity %d" % (self.print_path_ip(port, 'out'), verbosity))
        self.get_verbosity_for_port(click, port)

class XIADualRouter(MattDualElement):
    def print_path(self, port, direction):
        return '%s/dlc%d/xlc/print_%s' % (self.name, port, direction)

    def print_path_ip(self, port, direction):
        return '%s/dlc%d/iplc/print_%s' % (self.name, port, direction)

class XIADualEndHost(MattDualElement):
    def print_path(self, port, direction):
        return '%s/dlc/xlc/print_%s' % (self.name, direction)
    
    def print_path_ip(self, port, direction):
        return '%s/dlc/iplc/print_%s' % (self.name, direction)

#
# route info disitlled into an easier to manage object
#
class Connection:
    def __init__(self, port, kind, next):
        self.port = port
        self.kind = kind
        self.next = next


    def __repr__(self):
        return "Connection(kind=%s, port=%d, next=%s)" % (self.kind, self.port, self.next)


    def csv(self):
        return "%d,%s,%s" % (self.port, self.kind, self.next)
#
# XIA routers/hosts
#
class DeviceList:

    def __init__(self):
        self.devices = {}
        self.dualStack = False

    def add(self, name, r):
        self.devices[name] = r


    def parse(self, conf):
        #if conf.find('dualrouter') >= 0:
        #    self.dualStack = True

        # remove commented lines
        conf = re.sub('//.*\n', '', conf)
        conf = re.sub('/\*.*\*/', '', conf)

        entries = conf.split(";")
        for entry in entries:
            entry = entry.strip()

            if entry.find('::') >= 0:
                device = entry.split('::')[0].strip()
                type = entry.split('::')[1].split('(')[0].strip()
                obj = None

                if type == 'EndHost':
                    obj = EndHost(device, 1)
                elif type == 'XRouter4Port':
                    obj = XRouter(device, 1)
                elif type == 'DualRouter4Port':
                    obj = DualRouter(device, 4)
                elif type == 'XIARouter2Port':
                    obj = XIARouter(device, 2)
                elif type == 'XIARouter4Port':
                    obj = XIARouter(device, 4)
                elif type == 'XIAEndHost':
                    obj = XIAEndHost(device, 1)
                elif type == 'XIADualRouter2Port':
                    obj = XIADualRouter(device, 2)
                elif type == 'XIADualRouter4Port':
                    obj = XIADualRouter(device, 4)
                elif type == 'XIADualEndHost':
                    obj = XIADualEndHost(device, 1)
                else:
                    print 'WARNING Unsupported Device: %s' % type
                    continue

                self.add(device, obj)
                    

            #if entry.find("/cache ::") > 0:
            #    # hacky way of finding the devices that are configured
            #    sep = entry.find("/")
            #    dev = entry[:sep]
            #    r = Router(dev)
            #    self.add(dev, r)


    def resetRoutes(self):
        for d in self.devices.itervalues():
            d.reset()


    def getList(self):
        return self.devices


    def __repr__(self):
        first = 1
        s = "DeviceList({"
        for r in self.devices:
            if first:
                first = 0
            else:
                s += ', '
            s += r + " : " + repr(self.devices[r])
        s += '})'
        return s


    def csv(self):
        s = ''
        for d in self.devices.itervalues():
            s += d.csv()
        return s

#
# statistics
#
class Stats:
    def __init__(self, name):
        self.data = {}
        self.last = {}
        self.name = name
        self.timestamp = 0
        for xid in ('AD', 'HID', 'SID', 'CID', 'IP', 'UNKNOWN'):
            self.data[xid] = 0
            self.last[xid] = 0


    def update(self, text, name):
        cur = time.time()

        (ad, hid, sid, cid, ip, unknown) = text.split()
        ad = int(ad)
        hid = int(hid)
        sid = int(sid)
        cid = int(cid)
        ip = int(ip)
        unknown = int(unknown)

        if self.timestamp != 0:
            elapsed = int(max(1, cur - self.timestamp))
            self.data['AD'] = (ad - self.last['AD']) / elapsed
            self.data['HID'] = (hid - self.last['HID']) / elapsed
            self.data['SID'] = (sid - self.last['SID']) / elapsed
            self.data['CID'] = (cid - self.last['CID']) / elapsed
            self.data['IP'] = (ip - self.last['IP']) /elapsed
            self.data['UNKNOWN'] = (unknown - self.last['UNKNOWN']) / elapsed

        self.timestamp = cur
        self.last['AD'] = ad
        self.last['HID'] = hid
        self.last['SID'] = sid
        self.last['CID'] = cid
        self.last['IP'] = ip
        self.last['UNKNOWN'] = unknown


    def csv(self):
        return "%d,%d,%d,%d,%d,%d,0,0,0,0,0,0" % (self.data['AD'], self.data['HID'], self.data['SID'], self.data['CID'], self.data['IP'], self.data['UNKNOWN'])



##TODO: do we really need thes functions here?
#
# get the route entries for each of the devices and populate the router objects
#
def updateRoutes(devices, click):
    devices.resetRoutes()
    for device in devices.devices.itervalues():
        for kind in ('AD', 'HID', 'IP'):
            lines = device.get_routes(click, kind)

            for line in lines.splitlines():
                rt = Route(kind, line)
                device.addRoute(rt)

    return devices.csv()


def getCounts(s):
    if s == None:
        return None

    counts = s.splitlines()
    if len(counts) == 1:
        ip = counts[0][7:]
        s = "0 0 0 0 %s 0" % (ip)

    else:
        ad, hid, sid, cid, ip, unknown = s.splitlines()
        ad  = ad[7:]
        hid = hid[7:]
        sid = sid[7:]
        cid = cid[7:]
        ip  = ip[7:]
        unknown = unknown[7:]
        s = "%s %s %s %s %s %s" % (ad, hid, sid, cid, ip, unknown)

    return s


def updateDualStats(click, kind):
    s = ''
    for device in devices.devices.itervalues():
        for port in range(0, 4):

            counts = getCounts(click.readData("%s/dualrouter_%s_%d.count" % (device.name, kind, port)))
            fromip = getCounts(click.readData("%s/dualrouter_fromip_%s_%d.count" % (device.name, kind, port)))

            kin = '%d:IN' % (port)
            kout = '%d:OUT' % (port)

            if kind == 'final':
                if counts != None:
                    device.finalStatsIp[kout].update(counts, device.name)
                    s += '%s,%s,%d,OUT,%s\n' % (kind, device.hid, port, device.finalStatsIp[kout].csv())
                if fromip != None:
                    device.finalStatsIp[kin].update(fromip, device.name)
                    s += '%s,%s,%d,IN,%s\n' % (kind, device.hid, port, device.finalStatsIp[kin].csv())

            else:
                if counts != None:
                    device.nextStatsIp[kout].update(counts, device.name)
                    s += '%s,%s,%d,OUT,%s\n' % (kind, device.hid, port, device.nextStatsIp[kout].csv())
                if fromip != None:
                    device.nextStatsIp[kin].update(fromip, device.name)
                    s += '%s,%s,%d,IN,%s\n' % (kind, device.hid, port, device.nextStatsIp[kin].csv())


    return s


def updateStats(click, kind):
    s = ''
    for device in devices.devices.itervalues():
        for port in device.ports:

            counts = getCounts(click.readData("%s_%s_%d.count" % (device.name, kind, port)))

            if counts == None:
                continue
                
            if kind == 'final':
                device.finalStats[port].update(counts, device.name)
                txt= '%s,%s,%d,OUT,%s\n' % (kind, device.hid, port, device.finalStats[port].csv())
                s += txt

            else:
                device.nextStats[port].update(counts, device.name)
                s += '%s,%s,%d,OUT,%s\n' % (kind, device.hid, port, device.nextStats[port].csv())

    return s



def sendData(path, data):
    global base_url

    try:
        req = requests.put(base_url + path, data=data)
    except:
        say ('PUT ' + path + ' failed')


#
# go speed racer go!
#
def main():
    global devices
    global options
    global base_url

    parser = OptionParser()
    parser.add_option("-c", "--click", dest="click", help="Click instance address", default=CLICK)
    parser.add_option("-s", "--server", dest="host", help="Stats server host", default=STATS_HOST)
    parser.add_option("-p", "--port", dest="port", help="Stats server port", default=PORT)
    parser.add_option("-i", "--interval", dest="stats_interval", type='int', help="stats update interval", default=STATS_INTERVAL)
    parser.add_option("-r", "--rinterval", dest="route_interval", type='int', help="connections update interval", default=ROUTE_INTERVAL)
    parser.add_option("-v", "--verbose", dest="verbose", help="print status messages", default=False, action="store_true")
    (options, args) = parser.parse_args()

    click = ClickControl()
    click.connect()

    # get the list of hosts/routers from clock
    devices = DeviceList()
    devices.parse(click.readData("flatconfig"))



    click.shutdown()


if __name__ == "__main__":
    main()
