// -*- c-basic-offset: 4; related-file-name: "fromdpdkdevice.hh" -*-
/*
 * fromdpdkdevice.{cc,hh} -- element reads packets live from network via
 * Intel's DPDK
 *
 * Copyright (c) 2014-2015 Cyril Soldani, University of Liège
 * Copyright (c) 2015 Tom Barbette, University of Liège
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, subject to the conditions
 * listed in the Click LICENSE file. These conditions include: you must
 * preserve this copyright notice, and you cannot mention the copyright
 * holders in advertising related to the Software without their permission.
 * The Software is provided WITHOUT ANY WARRANTY, EXPRESS OR IMPLIED. This
 * notice is a summary of the Click LICENSE file; the license in that file is
 * legally binding.
 */

#include <click/config.h>

#include <click/args.hh>
#include <click/error.hh>
#include <click/standard/scheduleinfo.hh>

#include "fromdpdkdevice.hh"

CLICK_DECLS

FromDPDKDevice::FromDPDKDevice() :
    _port_id(0), _queue_id(0), _promisc(true), _burst_size(32), _count(0),
    _task(this)
{
}

FromDPDKDevice::~FromDPDKDevice()
{
}

int FromDPDKDevice::configure(Vector<String> &conf, ErrorHandler *errh)
{
    int n_desc = -1;

    if (Args(conf, this, errh)
        .read_mp("PORT", _port_id)
        .read_p("QUEUE", _queue_id)
        .read("PROMISC", _promisc)
        .read("BURST", _burst_size)
        .read("NDESC", n_desc)
        .complete() < 0)
        return -1;

    return DPDKDevice::add_rx_device(
        _port_id, _queue_id, _promisc, (n_desc > 0) ? n_desc : 256, errh);
}

int FromDPDKDevice::initialize(ErrorHandler *errh)
{
    ScheduleInfo::initialize_task(this, &_task, true, errh);

    return DPDKDevice::initialize(errh);
}

void FromDPDKDevice::cleanup(CleanupStage)
{
}

bool FromDPDKDevice::run_task(Task * t)
{
    struct rte_mbuf *pkts[_burst_size];

    unsigned n = rte_eth_rx_burst(_port_id, _queue_id, pkts, _burst_size);
    for (unsigned i = 0; i < n; ++i) {
        rte_prefetch0(rte_pktmbuf_mtod(pkts[i], void *));
        WritablePacket *p =
            Packet::make(rte_pktmbuf_mtod(pkts[i], unsigned char *),
                         rte_pktmbuf_data_len(pkts[i]), DPDKDevice::free_pkt,
                         pkts[i]);
        p->set_packet_type_anno(Packet::HOST);

        output(0).push(p);
    }
    _count += n;

    /* We reschedule directly, as we cannot know if there is actually packet
     * available and DPDK has no select mechanism*/
    t->fast_reschedule();

    return n;
}

String FromDPDKDevice::count_handler(Element *e, void *)
{
    FromDPDKDevice *fnd = static_cast<FromDPDKDevice *>(e);
    return String(fnd->_count);
}

int FromDPDKDevice::reset_count_handler(const String &, Element *e, void *,
                                        ErrorHandler *)
{
    FromDPDKDevice *fnd = static_cast<FromDPDKDevice *>(e);
    fnd->_count = 0;
    return 0;
}

void FromDPDKDevice::add_handlers()
{
	add_read_handler("count", count_handler, 0);
	add_write_handler("reset_count", reset_count_handler, 0,
                          Handler::BUTTON);
}

CLICK_ENDDECLS
ELEMENT_REQUIRES(userlevel dpdk)
EXPORT_ELEMENT(FromDPDKDevice)
ELEMENT_MT_SAFE(FromDPDKDevice)
