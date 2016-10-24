# XIA Config reader
import os
import re
import socket
import hashlib
import binascii
'''
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
'''
from netjoin_message_pb2 import SignedMessage

class NetjoinXIAConf(object):
    def __init__(self, hostname=socket.gethostname()):
        self.hostname = hostname.split('.')[0]
        cwd = os.getcwd()
        self.src_dir = cwd[:cwd.rindex('xia-core')+len('xia-core')]
        self.conf_dir = os.path.join(self.src_dir, "etc")
        self.key_dir = os.path.join(self.src_dir, "key")
        self.addrconfpattern = re.compile('^(\w+)\s+(\w+)\s+\((.+)\)')
        self.resolvconfpattern = re.compile('nameserver=(RE.+)')

	'''
    # Return serialized SignedMessage
    def sign(self, message):
        hid = self.get_hid()
        keyfilepath = os.path.join(self.key_dir, hid)
        key = RSA.importKey(open(keyfilepath).read())
        h = SHA.new(message)
        signer = PKCS1_v1_5.new(key)
        signature = signer.sign(h)
        signed_message = SignedMessage()
        signed_message.signature = signature
        signed_message.message = message
        return signed_message.SerializeToString()

    def verify(self, message, der_pubkey):
        signed_message = SignedMessage()
        signed_message.ParseFromString(message)

        key = RSA.importKey(der_pubkey)
        h = SHA.new(signed_message.message)
        verifier = PKCS1_v1_5.new(key)
        if verifier.verify(h, signed_message.signature):
            return True
        return False

    def get_der_key(self):
        hid = self.get_hid()
        return self.get_der_key_for_xid(hid)

    def get_der_key_for_xid(self, xid):
        key = None
        keyfilepath = os.path.join(self.key_dir, "{}.pub".format(xid))
        with open(keyfilepath, "r") as keyfile:
            key = RSA.importKey(keyfile.read())
        return key.exportKey('DER')

    def der_to_pem(self, der_key):
        key = RSA.importKey(der_key)
        return key.exportKey('PEM')

    def pem_key_hash_hex(self, pem_key):
        keylist = pem_key.split('\n')
        key_data = ''.join(keylist[1:-1])
        return hashlib.sha1(key_data).hexdigest()

    def pem_key_hash_hex_from_der(self, der_key):
        pem_key = self.der_to_pem(der_key)
        return self.pem_key_hash_hex(pem_key)

	'''
    def get_raw_hid(self):
        hid_hex_str = self.get_hid()
        return binascii.unhexlify(hid_hex_str)

    def raw_hid_to_hex(self, raw_hid):
        return binascii.hexlify(raw_hid)

    def get_raw_ad(self):
        ad_hex_str = self.get_ad()
        return binascii.unhexlify(ad_hex_str)

    def raw_ad_to_hex(self, raw_ad):
        return binascii.hexlify(raw_ad)

    def get_ad(self):
        ad, hid = self.get_ad_hid()
        return ad

    def get_hid(self):
        ad, hid = self.get_ad_hid()
        return hid

    def get_router_dag(self):
        router_dag = None
        ad, hid = self.get_ad_hid()
        if ad is not None and hid is not None:
            router_dag = "RE AD:{} HID:{}".format(ad, hid)
        return router_dag

    # Read address.conf looking for HID of this host
    def get_ad_hid(self):
        hid = None
        ad = None
        addrconfpath = os.path.join(self.conf_dir, "address.conf")
        with open(addrconfpath, "r") as addrconf:
            for line in addrconf:
                match = self.addrconfpattern.match(line)
                if not match:
                    continue

                host_name = match.group(1)
                if self.hostname != host_name:
                    continue
                host_type = match.group(2)
                hid = match.group(3)
                if "Router" in host_type:
                    ad, hid = hid.split(' ')
                break

        if ad:
            ad = ad[len("AD:"):]

        if hid:
            hid = hid[len("HID:"):]
        return (ad, hid)

    def get_ns_dag(self):
        ns_dag = None
        resolvconfpath = os.path.join(self.conf_dir, "resolv.conf")
        with open(resolvconfpath) as resolvconf:
            for line in resolvconf:
                match = self.resolvconfpattern.match(line)
                if not match:
                    continue

                ns_dag = match.group(1)
                break

        return ns_dag

    def get_swig_path(self):
        return os.path.join(self.src_dir, "api/lib")

    def get_clickcontrol_path(self):
        return os.path.join(self.src_dir, "bin")

if __name__ == "__main__":
    conf = NetjoinXIAConf()
    raw_hid = conf.get_raw_hid()
    print "Raw HID len: {}".format(len(raw_hid))
    hid = conf.raw_hid_to_hex(raw_hid)
    if not hid:
        print "FAILED: HID not found. Did you compile and run bin/xianet?"
        sys.exit(-1)
    der_key = conf.get_der_key_for_xid(hid)
    if not der_key:
        print "FAILED: Public key not found for HID:{}".format(hid)
        sys.exit(-1)
    print "DER key size: {}".format(len(der_key))
    pem_key = conf.der_to_pem(der_key)
    print "PEM key size: {}".format(len(pem_key))
    print "Hash of PEM key: {}".format(conf.pem_key_hash_hex(pem_key))
    print "Hash from DER: {}".format(conf.pem_key_hash_hex_from_der(der_key))
    print "HID: {}".format(hid)
    signed_message = conf.sign("test message")
    if not conf.verify(signed_message, conf.get_der_key()):
        print "FAILED"
    print "PASSED: NetjoinXIAConf"
