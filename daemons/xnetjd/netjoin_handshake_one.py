#!/usr/bin/python
#

from google.protobuf import text_format as protobuf_text_format
import struct
import logging
import jacp_pb2
import threading
import nacl.utils
import netjoin_session
from netjoin_xiaconf import NetjoinXIAConf
from netjoin_l2_handler import NetjoinL2Handler
from netjoin_message_pb2 import SignedMessage

# Build a HandshakeOne protobuf in response to a NetDescriptor beacon
class NetjoinHandshakeOne(object):

    def __init__(self, session, mymac, challenge=None):
        self.handshake_one = jacp_pb2.HandshakeOne()
        self.payload = jacp_pb2.HandshakeOne.HandshakeOneEncrypted.Payload()
        self.session = session
        self.conf = NetjoinXIAConf()
        self.challenge = challenge

        # No challenge, means AP got this handshake
        # It will use from_wire_handshake_one() to fill in everything
        if not self.challenge:
            return

        # Sign the challenge
        #signed_challenge = self.conf.sign(challenge)

        # Now fill in handshake_one
        h1 = self.handshake_one.encrypted
        h1.client_ephemeral_pubkey = session.auth.get_raw_verify_key()

        # Build the payload and add it to h1
        core = self.payload.core
        raw_mac = struct.pack("6B", mymac[0], mymac[1], mymac[2], mymac[3], mymac[4], mymac[5])
        core.client_l2_req.CopyFrom(self.session.l2_handler.build_request(raw_mac))
        core.client_l3_req.xip.single.ClientHID = self.conf.get_raw_hid()
        #core.client_l3_req.xip.single.ClientAIPPubKey = self.conf.get_der_key()
        core.client_l3_req.xip.single.configXIP.pxhcp.SetInParent()
        #core.client_l3_req.xip.single.XIPChallengeResponse = signed_challenge
        core.client_credentials.null.SetInParent()
        core.client_session_id = session.get_ID()

    def hex_client_hid(self):
        raw_hid = self.payload.core.client_l3_req.xip.single.ClientHID
        return self.conf.raw_hid_to_hex(raw_hid)

    def client_session_id(self):
        return self.payload.core.client_session_id

    def update_nonce(self):
        h1 = self.handshake_one.encrypted

        # Update the nonce
        h1.nonce = self.session.auth.get_nonce()

        # Update the hash of headers that includes the nonce
        # TODO: Convert to using methed get_hash_of_headers below
        data_to_hash = h1.nonce + h1.client_ephemeral_pubkey
        self.payload.hash_of_headers = self.session.auth.sha512(data_to_hash)

        # Serialize and encrypt the payload
        serialized_payload = self.payload.SerializeToString()
        encrypted_payload = self.session.auth.encrypt(serialized_payload, h1.nonce)

        # Add the encrypted data back to HandshakeOne
        h1.encrypted_data = encrypted_payload

    def handshake_one_str(self):
        return protobuf_text_format.MessageToString(self.handshake_one)

    def print_handshake_one(self):
        print self.handshake_one_str()

    def payload_str(self):
        return protobuf_text_format.MessageToString(self.payload)

    def print_payload(self):
        print self.payload_str()

    # wire_handshake_one is actually a serialized jacp_pb2.HandshakeOne
    def from_wire_handshake_one(self, wire_handshake_one):

        # Populate the internal handshake one protobuf
        self.handshake_one.CopyFrom(wire_handshake_one)

        # Record the client's public key into our auth session
        # NOTE: Our auth session is a shallow copy of announcer's auth session
        their_verify_key = self.handshake_one.encrypted.client_ephemeral_pubkey
        self.session.auth.set_their_raw_verify_key(their_verify_key)

        # Decrypt payload and make it available
        encrypted_payload = self.handshake_one.encrypted.encrypted_data
        serialized_payload = self.session.auth.decrypt(encrypted_payload)

        # Populate the internal payload after decrypting it
        self.payload.ParseFromString(serialized_payload)

    def get_hash_of_headers(self):
        h1 = self.handshake_one.encrypted
        data_to_hash = h1.nonce + h1.client_ephemeral_pubkey
        return self.session.auth.sha512(data_to_hash)

    def l2_type(self):
        l2_type_str = self.payload.core.client_l2_req.WhichOneof('l2_req')
        return NetjoinL2Handler.l2_str_to_type[l2_type_str]

    def is_l3_valid(self):

        # For now we just handle XIP requests
        #l3_req_type = self.payload.core.client_l3_req.WhichOneOf("l3_req")
        xip_l3_req = self.payload.core.client_l3_req.xip.single
        if not xip_l3_req:
            logging.error("No XIP L3 request")
            return False

        # Hash the pubkey
        #pubkey_hash = self.conf.pem_key_hash_hex_from_der(xip_l3_req.ClientAIPPubKey)

        # Make sure it matches HID
        hex_hid = self.conf.raw_hid_to_hex(xip_l3_req.ClientHID)
        #if hex_hid != pubkey_hash:
        #    logging.error("HID:{}, pubkey hash:{}".format(hex_hid, pubkey_hash))
        #    return False

        # Check signature
        #challenge_response = xip_l3_req.XIPChallengeResponse
        #der_pubkey = xip_l3_req.ClientAIPPubKey
        #if not self.conf.verify(challenge_response, der_pubkey):
        #    logging.error("Challenge incorrectly signed")
        #    return False

        # See if the message that was signed matches a recent gw_nonce
        #signed_message = SignedMessage()
        #signed_message.ParseFromString(challenge_response)
        #if not self.session.auth.is_recent_challenge(signed_message.message):
        #    logging.error("Response does not match a recent challenge")
        #    return False
        return True

    def is_valid(self):
        # Verify that headers were untouched in transit
        hash_of_headers = self.get_hash_of_headers()
        hash_in_payload = self.payload.hash_of_headers
        if hash_of_headers != hash_in_payload:
            logging.error("Headers have been tampered with")
            return False
        logging.debug("Headers have not been tampered")
        # Handle l3 credentials
        if not self.is_l3_valid():
            logging.error("L3 creds invalid")
            return False
        # Handle client credentials
        return True

if __name__ == "__main__":
    shutdown_event = threading.Event()
    session = netjoin_session.NetjoinSession(shutdown_event)
    session.daemon = True
    session.start()
    # Hack: setting their verify key same as ours
    session.auth.set_their_raw_verify_key(session.auth.get_raw_verify_key())
    mac = nacl.utils.random(6)
    handshake_one = NetjoinHandshakeOne(session, mac)
    handshake_one.update_nonce()
    serialized_handshake_one = handshake_one.handshake_one.SerializeToString()
    size = len(serialized_handshake_one)
    logging.debug("Serialized handshake one size: {}".format(size))
    handshake_one.print_handshake_one()
    shutdown_event.set()
    print "PASSED: handshake one test"
