/*
** Copyright 2011 Carnegie Mellon University
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
  @file Xutil.h
  @brief header for internal helper functions
*/
#ifndef _Xutil_h
#define _Xutil_h

#define PATH_SIZE 4096

#ifdef DEBUG
#define LOG(s) fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, s)
#define LOGF(fmt, ...) fprintf(stderr, "%s:%d: " fmt"\n", __FILE__, __LINE__, __VA_ARGS__)
#else
#define LOG(s)
#define LOGF(fmt, ...)
#endif

#ifndef FALSE
#define FALSE 0
#endif
#ifndef TRUE
#define TRUE (!FALSE)
#endif

#define UNKNOWN_STATE 0
#define UNCONNECTED	  1
#define CONNECTING	  2
#define CONNECTED 	  3

// ID->Name mapping (SO_DEBUG, AF_XIA, etc...)
 typedef struct {
	size_t id;
	const char *name;
} idrec;


#define WOULDBLOCK() (errno == EAGAIN || errno == EWOULDBLOCK)

int click_send(int sockfd, xia::XSocketMsg *xsm);
int click_reply(int sockfd, unsigned seq, xia::XSocketMsg *msg);
int click_status(int sockfd, unsigned seq);

int validateSocket(int sock, int stype, int err);

// socket state functions for internal API use
// implementation is in state.c
void allocSocketState(int sock, int tt, unsigned short port);
void freeSocketState(int sock);
unsigned short getPort(int sock);
int getSocketType(int sock);
void setSocketType(int sock, int tt);
int getProtocol(int sock);
void setProtocol(int sock, int p);
int isSIDAssigned(int sock);
void setSIDAssigned(int sock);
int isTempSID(int sock);
void setTempSID(int sock, const char *sid);
const char *getTempSID(int sock);
int getConnState(int sock);
void setConnState(int sock, int conn);
void setBlocking(int sock, int blocking);
int isBlocking(int sock);
void setDebug(int sock, int debug);
int getDebug(int sock);
void setRecvTimeout(int sock, struct timeval *timeout);
void getRecvTimeout(int sock, struct timeval *timeout);
unsigned seqNo(int sock);
void cachePacket(int sock, unsigned seq, char *buf, unsigned buflen);
int getCachedPacket(int sock, unsigned seq, char *buf, unsigned buflen);
int connectDgram(int sock, sockaddr_x *addr);
void setID(int sock, unsigned);
unsigned getID(int sock);
int MakeApiSocket(int transport_type);
const sockaddr_x *dgramPeer(int sock);

int _xsendto(int sockfd, const void *buf, size_t len, int flags, const sockaddr_x *addr, socklen_t addrlen);
int _xrecvfromconn(int sockfd, void *buf, size_t len, int flags);

size_t _iovSize(const struct iovec *iov, size_t iovcnt);
size_t _iovPack(const struct iovec *iov, size_t iovcnt, char **buf);
int _iovUnpack(const struct iovec *iov, size_t iovcnt, char *buf, size_t len);

int _xrecvfromconn(int sockfd, void *buf, size_t len, int flags, int *iface);
int _xrecvfrom(int sockfd, void *rbuf, size_t len, int flags, sockaddr_x *addr, socklen_t *addrlen, int *iface);


extern "C" {
const char *xferFlags(size_t f);
const char *fcntlFlags(size_t f);
const char *fcntlCmd(int c);
const char *aiFlags(size_t f);
const char *pollFlags(size_t f);
const char *afValue(size_t f);
const char *optValue(size_t f);
const char *protoValue(size_t f);
}

#endif
