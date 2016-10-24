#!/usr/bin/env python
#ts=4
#
# Copyright 2011 Carnegie Mellon University
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
import os
import sys
import getopt
import datetime
import telnetlib

APP_VERSION="0.9"
TITLE="XIA Route version %s"

# default Click host and port (can be changed on cmd line)
HOST="localhost"
PORT=7777

# Minimum Click version required
MAJOR=1
MINOR=3

#
# class for managing command line configuration options
#
class Options:
	""" xroute configuration options"""
	def __init__(self):
		self.__haveAction = False
		self._host = HOST
		self._port = PORT
		self._printTables = False
		self._printNames = False
		self._verbose = False
		self._commandFile = None
		self._dumpFile = None
		self._add = []
		self._remove = []
		self._devices = []
		self._types = []

	#
	# parse the command line so we can do stuff
	#
	def getOptions(self, argstr):
		try:
			# FIXME: make the option names more meaningful
			shortopt = "hpnvif:d:a:r:"
			opts, args = getopt.getopt(argstr, shortopt, 
				["help", "print", "names", "verbose",
				"host=", "port=", "file=", "dump=", "add=", "remove=",
				"device=", "type="])
		except getopt.GetoptError, err:
			# print	 help information and exit:
			print str(err) # will print something like "option -a not recognized"
			self.help()
			sys.exit(2)

		for o, a in opts:
			if o in ("-h", "--help"):
				self.help()
			elif o in ("-p", "--print"):
				self._printTables = True
			elif o in ("-n", "--names"):
				self._printNames = True
				self.__haveAction = True
			elif o in ("-v", "--verbose"):
				self._verbose = True
			elif o in ("-f", "--file"):
				self._commandFile = a
				self.__haveAction = True
			elif o in ("-d", "--dump"):
				self._dumpFile = a
				self.__haveAction = True
			elif o in ("-a", "--add"):
				self._add.append(a)
				self.__haveAction = True
			elif o in ("-r", "--remove"):
				self._remove.append(a)
				self.__haveAction = True
			elif o in ("--host"):
				self._host = a
			elif o in ("--port"):
				self._port = a
			elif o in ("--device"):
				self._devices.append(a)
			elif o in ("--type"):
				self._types.append(a)
			else:
			 	assert False, "unhandled option"

	#
	# display helpful information
	#
	def help(self):
		print """
usage: xroute [-hpnvif:d:a:r:] [commands]
where:
  -h <host>        : specify the click host address
  --host=<host>

  --port=<port>    : specify the click control port

  --device=<device>: only output info for the specified device (router0)
	                 can be specified multiple times on the command line

  --type=<xid>     : only output information for the specified XID type
                     can be specified multile times on the command line

  -p               : print the route tables to stdout (default action)
  --print

  -n               : print the known alias:xid mappings to stdout
  --names

  -v               : always print the full XID even if an alias exists
  --verbose

  -f <file>        : read add/delete commands from a config file
  --file=<file>      commands are in the form of:
                     add/update:
                       cmd device,type,xid,port[,nexthop,flags]
                       add router1,AD,AD0,1
                       add router0,HID,-,0,HID1,0
                     delete:
                       del host1,CID,CID:0000000000000000000000000000000000000000

  -d <file>        : dump a command file contining the current route tables
  --dump=<file>      the file format will be the same as the above command

  -a <entry>       : add a route, can be specified multipe times
  --add=<entry>      format of entry is the same as above except the add/del
                     prefix is not used

  -r <entry>       : remove a route, can be specified multipe times
  --remove=<entry>   format of entry is the same as above except the add/del
                     prefix is not used
"""
		sys.exit()
	#
	# check to see if the route tables should be printed to the screen
	#
	def printTables(self):
		p = False
		if self._printTables == True or self.__haveAction == False:
			p = True
		return p
	
	#
	# getter methods
	#
	def printNames(self):
		return self._printNames

	def host(self):
		return self._host
	
	def port(self):
		return self._port

	def commandFile(self):
		return self._commandFile
	
	def dumpFile(self):
		return self._dumpFile

	def verbose(self):
		return self._verbose
	
	def addCommands(self):
		return self._add
	
	def removeCommands(self):
		return self._remove
	
	def devices(self):
		return self._devices

	def types(self):
		return self._types

#
# contains the configuration information
# retrieved from click
# data here is aquired by parsing the result of the flatconfig click command
# currently we don't do a lot with it
#
class RouterConfig:
	"""router configuration"""
	
	def __init__(self, flat):
		self._devices = []
		self._xids = {}
		self._xaliases = {}

		entries = flat.split(";")
		for entry in entries:
			entry = entry.strip()

			# FIXME: should this be case insensitive?
			if entry.startswith("XIAXIDInfo"):
				self.handleXIDs(entry)
			elif entry.find("/cache ::") > 0:
				# hacky way of finding the devices that are configured
				self.addDevice(entry)
			else:
				# get other config stuff out of here at some point
				None
	#
	# read the list of alias:XID mappings that click knows about
	#
	def handleXIDs(self, list):
		entries = list.splitlines()
		for entry in entries:
			entry = entry.strip()

			# valid alias lines end with a comma
			if entry.find(",") > 0:
				entry = entry.rstrip(",")
				(alias, xid) = entry.split()
			
				# create hash maps to go in both directions
				self._xids[xid] = alias
				self._xaliases[alias] = xid
	#
	# found a device entry, add it to our device list if we dont' have it already
	#
	def addDevice(self, text):
		sep = text.find("/")
		dev = text[:sep]
		found = False
		for d in self._devices:
			if d == dev:
				found = True
		if found == False:
			self._devices.append(dev)

	#
	# getter methods
	#
	def devices(self):
		return self._devices

	def XIDs(self):
		return self._xids

	def aliases(self):
		return self._xaliases

	def getXID(self, alias):
		xid = alias
		if alias in self._xaliases:
			xid = self._xaliases[alias]
		return xid

	def getAlias(self, xid):
		alias = xid
		if xid in self._xids:
			alias = self._xids[xid]
		return alias

#
# The main body of the xroute app
# 
class XrouteApp:
	connected = False	
	csock = None
	devices = []
	types = []
	
	#
	# the main logic of the xroute app
	#
	def run(self, args):
		# get the command line options
		self.options = Options()
		self.options.getOptions(args)

		# connect to click and parse the click configuration into our config object
		self.connectToClick()
		self.config = RouterConfig(self.readData("flatconfig"))

		# if specified by the user, only get info for the specified devices (router0,...)
		if (len(self.options.devices()) > 0):
			self.devices = self.options.devices()
		else:
			self.devices = self.config.devices()

		# if specified by the user, only get info for the specified XID types (AD, HID,...)
		if (len(self.options.types())):
			self.types = self.options.types()
		else:
			self.types = [ "AD", "HID", "SID", "CID", "IP" ];

		# do the actions (if any) in the specified config file
		if (self.options.commandFile() != None):
			self.updateFromFile()

		# do the individual add commands specfied on the cmd line
		cmds = self.options.addCommands()
		if len(cmds) > 0:
			for cmd in cmds:
				self.addRoute(cmd)

		# do the individual delete commands specfied on the cmd line
		cmds = self.options.removeCommands()
		if len(cmds) > 0:
			for cmd in cmds:
				self.deleteRoute(cmd)

		# if specified, save the current click route tables to a file
		if (self.options.dumpFile()):
			self.dumpCommands()

		# if requested, print the aliases from the click configuration to stdout
		if self.options.printNames():
			self.printXIDs()

		# if needed, print the click route tables to stdout
		if self.options.printTables():
			for device in self.devices:
				print(self.getRouteTable(device))

		self.shutdown()

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
	# print the list of known alias to XID mappings to stdout
	#
	def printXIDs(self):
		print
		print "XID mappings"
		print "-" * 80
		for alias, xid in self.config.aliases().iteritems():
			print "%-10s -> %s" % (alias, xid)

	#
	# read the length of data sent by click so we can consume the right
	# amout of text
	#
	def readLength(self):
		text = self.csock.read_until("\n")
		text.strip()
		(data, length) = text.split()
		if data != "DATA":
			self.errorExit(tn, "error retreiving data length")
		return int(length)

	#
	# connect to the click control socket
	#
	def connectToClick(self):
		try:
			self.csock = telnetlib.Telnet(self.options.host(), self.options.port())
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
		self.checkStatus(True)

		length = self.readLength()
		buf=""
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
	# display type of click port
	#
	# FIXME: can we count on this always being true?
	#
	def portType(self, port):
		pt = ""
		if port == "-2":
			pt = " (self)"
		elif port == "5":
			pt = " (fallback)"
		return pt

	#
	# print the specified route table to stdout
	#
	def printTable(self, device, table):
		tfmt = "%s/xrc/n/proc/rt_%s.list"
		data = self.readData(tfmt % (device, table))

		text = ""
		routes = data.split("\n")
		for route in routes:
			parts = route.split(",")

			if len(parts) != 4:
				if len(parts) > 1:
					print "invalid route line: %d %s\n" % (len(parts), route)
				continue	
			xid = parts[0]
			port = parts[1]
			nexthop = parts[2]
			flags = int(parts[3])

			if port != -1:
				if xid == "-":
					xid = "(default)"
				elif self.options.verbose() == False:
					xid = self.config.getAlias(xid)

				text += "%-5s %-45s %2s%-11s %08x %s\n" % (table, xid, 
						port, self.portType(port), flags, nexthop) 


#		print "text = %s" % (text)

		return text

	#
	# format the route table header and loop through the requested XID tables
	#
	def getRouteTable(self, device):
		text  = device
		text += "\n"
		text += "%-5s %-45s %-13s %-8s NEXT HOP\n" % ("TYPE", "XID", "PORT", "FLAGS")
		text +=  "-" * 120
		text += "\n"

		# only print the XID types requested by the user
		for table in self.types:
			text += self.printTable(device, table)
		return text

	#
	# send an individual delete route command to click
	#
	# only minor error checking is done here, click will do the rest of it
	#
	def deleteRoute(self, text):
		try:
			(device, table, xid) = text.split(",")
		except:
			self.errorExit("Invalid format for delete command")

		found = False
		for d in self.devices:
			if d == device:
				found = True
		if found == False:
			self.errorExit("device %s unknown" % (device));
		if table not in ("AD", "HID", "SID", "CID", "IP"):
			self.errorExit("invaid XID type specified")
		if (xid == None or xid == ""):
			self.errorExit("XID not specified")
		if xid == "default":
			xid = "-";
		else:
			# in case we were passed an alias, try to map to an xid
			xid = self.config.getXID(xid)

		cmd = "%s/xrc/n/proc/rt_%s.remove %s" % (device, table, xid)
		self.writeData(cmd)
		print "%s: deleted route for %s:%s" % (device, table, self.config.getAlias(xid))


	#
	# send an individual add route command to click
	#
	# only minor error checking is done here, click will do the rest of it
	#
	def addRoute(self, text):
		parts = text.split(",")
		if len(parts)  < 4 or len(parts) > 6:
			self.errorExit("Invalid format for add route command")

		device = parts[0]
		table = parts[1]
		xid = parts[2]
		port = parts[3]

		if len(parts) >= 5:
			nexthop = parts[4]
		else:
			nexthop = ""

		if len(parts) == 6:
			flags = parts[5]
		else:
			flags = 0
			
		found = False
		for d in self.devices:
			if d == device:
				found = True
		if found == False:
			self.errorExit("device %s unknown" % (device));
		if table not in ("AD", "HID", "SID", "CID", "IP"):
			self.errorExit("invaid XID type specified")
		if (xid == None or xid == ""):
			self.errorExit("XID not specified")
		if xid == "default":
			xid = "-";
		if (port == None or port == ""):
			self.errorExit("port not specified")

		cmd = "%s/xrc/n/proc/rt_%s.set4 %s,%s,%s,%s" % (device, table, xid, port, nexthop, flags)
		print cmd

		self.writeData(cmd)
		print "%s: added route for %s:%s" % (device, table, self.config.getAlias(xid))


	#
	# read a command file and add / delete routes as specified
	#
	# format of the file is:
	# <cmd> <device>,<xid type>,<xid>,[port]
	#  add router0,AD,AD1,1
	#  add router1,AD,AD:0123456789012345678901234567890123456789,1
	#  add router1,HID,-,1
	#  del router0,CID,CID0
	#
	# blank lines or lines starting with # are ignored
	#
	def updateFromFile(self):
		try:
			f = open(self.options.commandFile(), 'r')
		except:
			self.errorExit("unable to open file: %s" % (self.options.commandFile()))

		for line in f:
			line = line.strip()
			if (line == "" or line[:1] == "#"):
				None
			elif (line[:4] == "add "):
				cmd = line[4:].strip()
				self.addRoute(cmd)

			elif line[:4] == "del ":
				cmd = line[4:].strip()
				self.deleteRoute(cmd)
			else:
				self.errorExit("invalid xroute command : %s" % (line))

		f.close()

	#
	# write a command file contining the current router config
	#
	# file format is the same as in the updateFromFile function above
	#
	# the entire set of routing table swill be exported unless the user
	# specified particular devides or xid types on the command line
	#
	def dumpCommands(self):
		tfmt = "%s/xrc/n/proc/rt_%s.list"
		ts = datetime.datetime.now()
		devices = self.config.devices()

		try:
			f = open(self.options.dumpFile(), "w")
		except:
			self.errorExit("Unable to open output file (%s)" % (self.options.dumpFile()))

		f.write("\n# XIA router config generated from %s on %s\n" % 
				(os.uname()[1], ts.strftime("%Y-%m-%d %H:%M")))
		f.write("#\n")
		f.write("# Alias mappings from the xia click configuration\n")

		for alias, xid in sorted(self.config.aliases().iteritems()):
			f.write("# %-10s -> %s\n" % (alias, xid))

		for device in self.devices:
			f.write("\n")
			for table in self.types:
				data = self.readData(tfmt % (device, table))
				routes = data.split("\n")
				for route in routes:
					(xid, sep, port) = route.partition(";")
					if sep != "" and port != "-1":
						# FIXME: is using aliases here a good idea?
						xid = self.config.getAlias(xid)
						text = "add %s,%s,%s,%s\n" % (device, table, xid, port)
						f.write(text)

		f.close()

	#
	# close the connection to click
	#
	def shutdown(self):
		if (self.connected):
			self.csock.write("quit\n")


#
# let's do this thing
#
def main():
	print TITLE % (APP_VERSION)

	xroute = XrouteApp()
	xroute.run()

if __name__ == "__main__":
    main()
