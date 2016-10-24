#include <pthread.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/un.h>
#include <syslog.h>
#include "Xsocket.h"
#include <iostream>
#include "controller.h"
#include "cache.h"
#include "cid.h"
#include <clicknet/xia.h>
#include <clicknet/xtcp.h>

#define CACHE_SOCK_NAME "/tmp/xcache-click.sock"

void xcache_cache::spawn_thread(struct cache_args *args)
{
	pthread_t cache;

	pthread_create(&cache, NULL, run, (void *)args);
}

int xcache_cache::create_click_socket()
{
	int s;

	if ((s = socket(AF_UNIX, SOCK_DGRAM, 0)) == -1) {
		syslog(LOG_ERR, "can't create click socket: %s", strerror(errno));
		return -1;
	}

	sockaddr_un sa;
	memset(&sa, 0, sizeof(sa));
	sa.sun_family = AF_UNIX;
	strcpy(sa.sun_path, CACHE_SOCK_NAME);

	if (bind(s, (struct sockaddr *)&sa, sizeof(sa)) == -1) {
		syslog(LOG_ERR, "unable to bind: %s", strerror(errno));
		return -1;
	}

	syslog(LOG_INFO, "Created cache socket on %s\n", CACHE_SOCK_NAME);

	return s;
}

void xcache_cache::unparse_xid(struct click_xia_xid_node *node, std::string &xid)
{
	char hex[41];
	unsigned char *id = node->xid.id;
	char *h = hex;

	while (id - node->xid.id < CLICK_XIA_XID_ID_LEN) {
		sprintf(h, "%02x", (unsigned char)*id);
		id++;
		h += 2;
	}

	hex[CLICK_XIA_XID_ID_LEN * 2] = 0;
	xid = std::string(hex);
}

int xcache_cache::validate_pkt(char *pkt, size_t len, std::string &cid, std::string &sid, struct xtcp **xtcp)
{
	struct click_xia *xiah = (struct click_xia *)pkt;
	struct xtcp *x;
	unsigned total_nodes;
	size_t xip_size;

	*xtcp = NULL;

	if ((len < sizeof(struct click_xia)) || (htons(xiah->plen) > len) ) {
		// packet is too small, this had better not happen!
		return PACKET_INVALID;
	}

	total_nodes = xiah->dnode + xiah->snode;
	xip_size = sizeof(struct click_xia) + (total_nodes * sizeof(struct click_xia_xid_node));
	x = (struct xtcp *)(pkt + xip_size);

	// we only see the flow from server to client, so we'll never see a plain SYN here
	// FIXME: we should probably be smart enough to deal with other flags like RST here eventually
	if (x->th_flags == XTH_ACK) {
		ushort hlen = (ushort)(x->th_off) << 2;

		if (hlen == ntohs(xiah->plen)) {
			// it's empty and not a SYN-ACK or FIN
			// so we can ignore it
			return PACKET_NO_DATA;
		}
	}

	 // get the associated client SID and destination CID
	for (unsigned i = 0; i < total_nodes; i++) {
		unsigned type = htonl(xiah->node[i].xid.type);

		if (type == CLICK_XIA_XID_TYPE_CID) {
			unparse_xid(&xiah->node[i], cid);
		} else if (type == CLICK_XIA_XID_TYPE_SID) {
			unparse_xid(&xiah->node[i], sid);
		}
	}

	if (xiah->nxt != CLICK_XIA_NXT_XSTREAM) {
		syslog(LOG_INFO, "%s: not a stream packet, ignoring...", cid.c_str());
		return PACKET_INVALID;
	}

	// syslog(LOG_INFO, "XIA version = %d\n", xiah->ver);
	// syslog(LOG_INFO, "XIA plen = %d len = %d\n", htons(xiah->plen), len);
	// syslog(LOG_INFO, "XIA nxt = %d\n", xiah->nxt);
	// syslog(LOG_INFO, "tcp->th_ack = %u\n", ntohl(x->th_ack));
	// syslog(LOG_INFO, "tcp->th_seq = %u\n", ntohl(x->th_seq));
	// syslog(LOG_INFO, "tcp->th_flags = %08x\n", ntohs(x->th_flags));
	// syslog(LOG_INFO, "tcp->th_off = %d\n", x->th_off);

	*xtcp = x;
	return PACKET_OK;
}

xcache_meta* xcache_cache::start_new_meta(struct xtcp *tcp, std::string &cid, std::string &sid)
{
	// if it's not a syn-ack we don't know how much content has already gone by
	if (!(ntohs(tcp->th_flags) & XTH_SYN)) {
		syslog(LOG_INFO, "skipping %s: partial stream received", cid.c_str());
		return NULL;
	}

	// FIXME: this should be wrapped in a mutex
	struct cache_download *download;
	xcache_meta *meta = new xcache_meta(cid);

	meta->set_state(OVERHEARING);
	meta->set_seq(ntohl(tcp->th_seq));
	meta->set_dest_sid(sid);

	download = (struct cache_download *)calloc(sizeof(struct cache_download), 1);
	ongoing_downloads[cid] = download;

	return meta;
}

void xcache_cache::process_pkt(xcache_controller *ctrl, char *pkt, size_t len)
{
	int rc;
	struct xtcp *tcp;
	std::string cid = "";
	std::string sid = "";
	size_t payload_len;
	size_t offset;
	xcache_meta *meta;
	struct cache_download *download;
	std::map<std::string, struct cache_download *>::iterator iter;

	syslog(LOG_DEBUG, "CACHE RECVD PKT\n");

	rc = validate_pkt(pkt, len, cid, sid, &tcp);
	switch (rc) {
	case PACKET_OK:
		// keep going, it's either a SYN-ACK or contains data
		break;

	case PACKET_NO_DATA:
		// it's a pure ACK, we can ignore it
		syslog(LOG_INFO, "data packet is empty!");
		return;

	case PACKET_INVALID:
	default:
		// the packet is not not a stream pkt or is malformed
		// we shouldn't see this in real usage
		syslog(LOG_ERR, "packet doesn't contain valid cid data");
		return;
	}

	char *payload = (char *)tcp + ((ushort)(tcp->th_off) << 2);
	payload_len = len + (size_t)(pkt - payload);
	syslog(LOG_DEBUG, "%s Payload length = %lu\n", cid.c_str(), payload_len);

	if (!(meta = ctrl->acquire_meta(cid))) {
		syslog(LOG_INFO, "ACCEPTING: New Meta CID=%s", cid.c_str());
		ctrl->add_meta(start_new_meta(tcp, cid, sid));

		// it's a syn-ack so there's no data to handle yet
		return;
	}

	switch (meta->state()) {
		case OVERHEARING:
			// drop into the code below the switch
			break;

		case AVAILABLE:
			ctrl->release_meta(meta);
			syslog(LOG_INFO, "This CID is already in the cache: %s", cid.c_str());
			return;

		case FETCHING:
			// FIXME: this probably should not be a state, but rather a count of
			// number of concurrent accessors of this chunk.
			// fetching should never be an issue here, but only when deleting
			// content to be sure it is safe to remove.
			ctrl->release_meta(meta);
			syslog(LOG_INFO, "Already fetching this CID: %s", cid.c_str());
			return;

		case EVICTING:
			ctrl->release_meta(meta);
			syslog(LOG_INFO, "The CID is in process of being evicted: %s", cid.c_str());
			return;

		default:
			syslog(LOG_ERR, "Some Unknown STATE FIX IT CID=%s", cid.c_str());
			ctrl->release_meta(meta);
			return;
	}

	if (meta->dest_sid() != sid) {
		// Another stream is already getting this chunk.
		//  so we can ignore this stream's data
		//  otherwise we'll have memory overrun issues due to different sequence #s
		syslog(LOG_INFO, "don't cross the streams!");
		ctrl->release_meta(meta);
		return;
	}

	// get the initial sequence number for this stream
	uint32_t initial_seq = meta->seq();
	ctrl->release_meta(meta);

	iter = ongoing_downloads.find(cid);
	if (iter == ongoing_downloads.end()) {
		// Something bad happened!
		// we should close this meta up
		syslog(LOG_ERR, "Unable to find download buffer for %s", cid.c_str());
		return;
	}
	//syslog(LOG_INFO, "Download Found\n");
	download = iter->second;

	// We got "payload" of length "payload_len"
	// This is at offset ntohl(tcp->th_seq) in total chunk
	// Adjusted sequence numbers from 1 to sizeof(struct cid_header)
	//  constitute the CID header. Everything else is payload
	if (payload_len == 0) {
		// control packet
		goto skip_data;
	}

	// FIXME: this doesn't deal with the case where the sequence number wraps.
	// factor out the random start value of the seq #
	offset = ntohl(tcp->th_seq) - initial_seq;
	//syslog(LOG_INFO, "initial=%u, seq = %u offset = %lu\n", initial_seq, ntohl(tcp->th_seq), offset);

	// get the cid header if we don't already have it
	// incrementally build the header if the packet size
	//  is less than header size
	if (offset < sizeof(struct cid_header)) {
		if ((offset + payload_len) >= sizeof(struct cid_header)) {
			len = sizeof(struct cid_header) - offset;
		} else {
			len = payload_len;
		}

		memcpy((char *)&download->header + offset, payload, len);
		payload += len;
		offset += len;
		payload_len -= len;
	}

	// there's data, append it to the download buffer
	if (offset >= sizeof(struct cid_header)) {
		if (download->data == NULL) {
			download->data = (char *)calloc(ntohl(download->header.length), 1);
		}
		memcpy(download->data + offset - sizeof(struct cid_header), payload, payload_len);
	}

skip_data:
	if ((ntohs(tcp->th_flags) & XTH_FIN)) {
		// FIN Received, cache the chunk

		if (compute_cid(download->data, ntohl(download->header.length)) == cid) {
			syslog(LOG_INFO, "chunk is valid: %s", cid.c_str());

			meta->set_ttl(ntohl(download->header.ttl));
			meta->set_created();

			xcache_req *req = new xcache_req();
			req->type = xcache_cmd::XCACHE_CACHE;
			req->cid = strdup(cid.c_str());
			req->data = download->data;
			req->datalen = ntohl(download->header.length);
			ctrl->enqueue_request_safe(req);

			/* Perform cleanup */
			ongoing_downloads.erase(iter);
			free(download);
		} else {
			// FIXME: leave this open in case more data is on the wire
			// and let garbage collection handle it eventually? or nuke it now?
			syslog(LOG_ERR, "Invalid chunk, discarding: %s", cid.c_str());
		}
	}
}

void *xcache_cache::run(void *arg)
{
	struct cache_args *args = (struct cache_args *)arg;
	int s, ret;
	char buffer[XIA_MAXBUF];

	(void)args;

	if ((s = create_click_socket()) < 0) {
		syslog(LOG_ALERT, "Failed to create a xcache:click socket\n");
		pthread_exit(NULL);
	}

	do {
		syslog(LOG_DEBUG, "Cache listening for data from click\n");
		ret = recvfrom(s, buffer, XIA_MAXBUF, 0, NULL, NULL);
		if(ret < 0) {
			syslog(LOG_ERR, "Error while reading from socket: %s\n", strerror(errno));
			pthread_exit(NULL);
		} else if (ret == 0) {
			// we should probably error out here too
			syslog(LOG_ERR, "no data: %s\n", strerror(errno));
			continue;
		}

		syslog(LOG_DEBUG, "Cache received a message of size = %d\n", ret);
		args->cache->process_pkt(args->ctrl, buffer, ret);

	} while(1);
}
