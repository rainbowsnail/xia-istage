/* ts=4 */
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
 @file Xsocket.c
 @brief Implements Xsocket()
*/

#include <sys/types.h>
#include <unistd.h>

#include "Xsocket.h"
#include "Xinit.h"
#include "Xutil.h"
#include <stdlib.h>
#include <libgen.h>
#include <limits.h>
#include <pthread.h>
#include <errno.h>

/*!
** @brief Create an XIA socket
**
** Creates an XIA socket of the specified type.
**
** @param family socket family, currently must be AF_XIA
** @param transport_type Valid values are:
**	\n SOCK_STREAM for reliable communications (SID)
**	\n SOCK_DGRAM for a ligher weight connection, but with
**	unguranteed delivery (SID)
**	\n SOCK_RAW for a raw socket that can have direct edits made to the header
**	\n SOCK_NONBLOCK may be or'd into the transport_type to create the socket in nonblocking mode
** @param for posix compatibility, currently ignored
**
** @returns socket id on success.
** @returns -1 on failure with errno set to an error compatible with those
** from the standard socket call.
**
** @warning In the current implementation, the returned socket is
** a normal UDP socket that is used to communicate with the click
** transport layer. Using this socket with normal unix socket
** calls (aside from select and poll) will cause unexpected behaviors.
** Attempting to pass a socket created with the the standard socket function
** to the Xsocket API will have similar results.
**
*/
int Xsocket(int family, int transport_type, int protocol)
{
	int rc;
	int sockfd;
	int block = TRUE;

	if (family != AF_XIA) {
		LOG("error: the Xsockets API only supports the AF_XIA family");
		errno = EAFNOSUPPORT;
		return -1;
	}

	if (transport_type & SOCK_CLOEXEC) {
		LOG("warning: SOCK_CLOEXEC is not currently supported in XIA");
	}

	if (transport_type & SOCK_NONBLOCK) {
		block = FALSE;
	}

	// get rid of the flags
	transport_type &= 0x0f;

	switch (transport_type) {
		case SOCK_STREAM:
		case SOCK_DGRAM:
		case SOCK_RAW:
			break;
		default:
			// invalid socket type requested
			LOG("error: invalid transport_type specified");
			errno = EINVAL;
			return -1;
	}


	if ((sockfd = MakeApiSocket(transport_type)) == -1) {
		LOGF("error creating Xsocket: %s", strerror(errno));
		return -1;
	}

	// protobuf message
	xia::XSocketMsg xsm;
	xsm.set_type(xia::XSOCKET);
	unsigned seq = seqNo(sockfd);
	xsm.set_sequence(seq);

	xia::X_Socket_Msg *x_socket_msg = xsm.mutable_x_socket();
	x_socket_msg->set_type(transport_type);

	if ((rc = click_send(sockfd, &xsm)) < 0) {
		LOGF("Error talking to Click: %s", strerror(errno));
		(_f_close)(sockfd);
		return -1;
	}

	// process the reply from click
	xsm.Clear();
	if (click_reply(sockfd, seq, &xsm) < 0) {
		LOGF("Error getting status from Click: %s", strerror(errno));
	}

	setID(sockfd, xsm.id());
	//LOGF("new id = %d\n", xsm.id());

	if (rc == 0) {
		setBlocking(sockfd, block);
		setProtocol(sockfd, protocol);
		return sockfd;
	}

	// close the control socket since the underlying Xsocket is no good
	freeSocketState(sockfd);
	(_f_close)(sockfd);
	return rc;
}
