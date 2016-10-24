
/*
** Copyright 2013 Carnegie Mellon University
**
** Licensed under the Apache License, Version 2.0 (the "License");
** you may not use this file except in compliance with the License.
** You may obtain a copy of the License at
**
**    http://www.apache.org/licenses/LICENSE-2.0
**
** Unless required by applicable law or agreed to in writing, software
** distributed under the License is distributed on an "AS IS" BASIS,
** WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
** See the License for the specific language governing permissions and
** limitations under the License.
*/
/*!
  @file xia.h
  @brief Common XIA structures and constants
*/

#ifndef XIA_H
#define XIA_H

#define SOURCE_DIR "xia-core"

#define BUF_SIZE 4096

#define AF_XIA		40

#define EDGES_MAX	4
#define EDGE_UNUSED 127u
#define XID_SIZE	20
#define NODES_MAX	20
#define MAX_XID_TYPE_STR 8
#define XIA_XID_STR_SIZE (XID_SIZE*2)+MAX_XID_TYPE_STR
#define XIA_MAX_DAG_STR_SIZE XIA_XID_STR_SIZE*NODES_MAX

enum XID_TYPE {
	XID_TYPE_AD = 0x10,  // TODO: why does swig complain when these are uint32_t?
	XID_TYPE_HID = 0x11,
	XID_TYPE_CID = 0x12,
	XID_TYPE_SID = 0x13,
	XID_TYPE_IP = 0x14,
	XID_TYPE_DUMMY_SOURCE = 0xff,
};

typedef struct {
	unsigned int  s_type;
	unsigned char s_id[XID_SIZE];
} xid_t;

typedef struct {
	xid_t         s_xid;
	unsigned char s_edge[EDGES_MAX];
} node_t;

typedef struct {
	unsigned char s_count;
	node_t        s_addr[NODES_MAX];
} x_addr_t;


typedef struct {
	// common sockaddr fields
#ifdef __APPLE__
	unsigned char sx_len; // not actually large enough for sizeof(sockaddr_x)
	unsigned char sx_family;
#else
	unsigned short sx_family;
#endif

	// XIA specific fields
	x_addr_t      sx_addr;
} sockaddr_x;

#endif // XIA_H

