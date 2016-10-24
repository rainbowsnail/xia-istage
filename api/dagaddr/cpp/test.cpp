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
#include "dagaddr.hpp"
#include "dagaddr.h"
#include <stdlib.h>
#include <cstdio>

const char *get_xid_str(int id);
void hex2str(char *strdst, size_t strdstlen, unsigned char *hexsrc, size_t hexsrclen);

void print_node(int i, node_t *node)
{
	char id[100];
	int j;

	hex2str(id, 100, node->s_xid.s_id, XID_SIZE);
	printf("Node[%d] (%s%s)\n\t", i, get_xid_str(node->s_xid.s_type), id);
	for(j = 0; j < EDGES_MAX; j++) {
		printf("%d\t",node->s_edge[j]);
	}
	printf("\n");

}

void print_sockaddrx(sockaddr_x *addr)
{
	int i;

	for(i = 0; i <= addr->sx_addr.s_count; i++) {
		node_t *node;

		node = &addr->sx_addr.s_addr[i];
		print_node(i, node);
	}
}

void test_c(void)
{
	sockaddr_x addr, addr1;
	char ad[] = "AD:0606060606060606060606060606060606060606";
	char hid[] = "HID:0101010101010101010101010101010101010101";
	char cid[] = "CID:0202020202020202020202020202020202020202";
	char url[256];

	memset(&addr, 0, sizeof(sockaddr_x));
	// dag_add_nodes(&addr, 3, ad, hid, cid);
	// dag_set_intent(&addr, 2);
	// dag_add_path(&addr, 2, 0, 2);
	// dag_add_path(&addr, 3, 0, 1, 2);
	memset(&addr, 0, sizeof(sockaddr_x));
	dag_add_node(&addr, ad);
	dag_add_node(&addr, hid);
	dag_add_node(&addr, cid);

	dag_set_intent(&addr, 2);

	dag_add_edge(&addr, 0, 1);
	dag_add_edge(&addr, 1, 2);
	dag_set_fallback(&addr, 0);


	Graph g1(&addr);

	printf("I have an address which looks like: \n");

	g1.print_graph();
	printf("Converting to URL\n");

 	dag_to_url(url, 256, &addr);
	printf("Got URL from DAG as: %s\n", url);

 	url_to_dag(&addr1, url, 256);
	printf("Got Dag from URL. Drawing graph from received Dag\n");
 	Graph g(&addr1);
 	g.print_graph();

	// Node n_ad(ad);
	// Node n_hid(hid);
	// Node n_cid(cid);
	// Node n_src;

	// Graph g2 = n_src * n_ad * n_hid * n_cid;
	// Graph g3 = n_src * n_cid;

	// Graph g4 = g3 + g2;
	// Graph g5 = g2 + g3;
	// g4.print_graph();
	// g4.fill_sockaddr(&addr1);
	// print_sockaddrx(&addr1);

	// g5.print_graph();
	// g5.fill_sockaddr(&addr1);
	// print_sockaddrx(&addr1);
	
}

int main()
{
	Node n_src;
	Node n_ad(Node::XID_TYPE_AD, "0606060606060606060606060606060606060606");
	Node n_hid(Node::XID_TYPE_HID, "0101010101010101010101010101010101010101");
	Node n_cid(Node::XID_TYPE_CID, "0202020202020202020202020202020202020202");

	printf("n_ad: %s\n", n_ad.to_string().c_str());
	printf("n_hid: %s\n", n_hid.to_string().c_str());
	printf("n_cid: %s\n\n", n_cid.to_string().c_str());

	// Path directly to n_cid
	// n_src -> n_cid
	printf("g0 = n_src * n_cid\n");
	Graph g0 = n_src * n_cid;
	g0.print_graph();
	printf("\n");

	// Path to n_cid through n_hid
	// n_src -> n_hid -> n_cid
	printf("g1 = n_src * n_ad * n_cid\n");
	Graph g1 = n_src * n_ad * n_cid;
	g1.print_graph();
	printf("\n");

	// Path to n_cid through n_ad then n_hid
	// n_src -> n_ad -> n_hid -> n_cid
	printf("g2 = n_src * n_ad * n_hid * n_cid\n");
	Graph g2 = n_src * n_ad * n_hid * n_cid;
	g2.print_graph();
	printf("\n");

	// Combine the above three paths into a single DAG;
	// g1 and g2 become fallback paths from n_src to n_cid
	printf("g3 = g0 + g1 + g2\n");
	Graph g3 = g0 + g1 + g2;
	g3.print_graph();
	printf("\n");

	// Get a DAG string version of the graph that could be used in an
	// XSocket API call
	const char* dag_string = g3.dag_string().c_str();
	printf("%s\n", dag_string);

	// Create a DAG from a string (which we might have gotten from an Xsocket
	// API call like XrecvFrom)
	Graph g4 = Graph(dag_string);
	g4.print_graph();
	printf("\n");

	// TODO: cut here in the example version; stuff below is for testing

	printf("\n\n");
	printf("g5 = g3 * (SID0 + SID1) * SID2\n");
	Graph g5 = g3 * (Node(Node::XID_TYPE_SID, "0303030303030303030303030303030303030303") + Node(Node::XID_TYPE_SID, "0404040404040404040404040404040404040404")) * Node(Node::XID_TYPE_SID, "0505050505050505050505050505050505050505");
	g5.print_graph();
	printf("\n");
	printf("%s\n\n", g5.dag_string().c_str());
	
	printf("g5_prime = Graph(g5.dag_string())\n");
	Graph g5_prime = Graph(g5.dag_string());
	g5_prime.print_graph();
	printf("\n\n");

	printf("g5_prime2 = Graph(g3)\n");
	Graph g5_prime2 = Graph(g3);
	printf("%s\n\n", g5_prime2.dag_string().c_str());
	printf("g5_prime2 *= SID0\n");
	g5_prime2 *= Node(Node::XID_TYPE_SID, "0303030303030303030303030303030303030303");
	printf("%s\n\n", g5_prime2.dag_string().c_str());
	printf("g5_double = g5 * g3\n");
	Graph g5_double = g5 * g3;
	printf("%s\n\n", g5_double.dag_string().c_str());





	Node n_ad2(Node::XID_TYPE_AD, "0707070707070707070707070707070707070707");
	Node n_hid2(Node::XID_TYPE_HID, "0808080808080808080808080808080808080808");
	Node n_sid("SID:0909090909090909090909090909090909090909");

	printf("g6 = g3 * ((n_cid * n_sid) + (n_cid * n_ad2 * n_sid) + (n_cid * n_ad2 * n_hid2 * n_sid))\n");
	Graph g6 = g3 * ((n_cid * n_sid) + (n_cid * n_ad2 * n_sid) + (n_cid * n_ad2 * n_hid2 * n_sid));
	printf("%s\n\n", g6.dag_string().c_str());

	printf("Testing is_final_intent vvv\n");

	printf("g3.is_final_intent(n_cid): %s\n", (g3.is_final_intent(n_cid))?"true":"false");
	printf("g3.is_final_intent(n_hid): %s\n", (g3.is_final_intent(n_hid))?"true":"false");
	printf("g3.is_final_intent(n_ad): %s\n", (g3.is_final_intent(n_ad))?"true":"false");
	
	printf("g3.is_final_intent(n_cid.id_string()): %s\n", (g3.is_final_intent(n_cid.id_string()))?"true":"false");
	printf("g3.is_final_intent(n_hid.id_string()): %s\n", (g3.is_final_intent(n_hid.id_string()))?"true":"false");
	printf("g3.is_final_intent(n_ad.id_string()): %s\n", (g3.is_final_intent(n_ad.id_string()))?"true":"false");

	printf("Testing is_final_intent ^^^\n\n\n");

	printf("Testing next_hop vvv\n");

	printf("g5.next_hop(n_src):\n%s\n", g5.next_hop(n_src).dag_string().c_str());
	printf("g5.next_hop(n_cid):\n%s\n", g5.next_hop(n_cid).dag_string().c_str());
	printf("g6.next_hop(n_src):\n%s\n", g6.next_hop(n_src).dag_string().c_str());
	printf("g6.next_hop(n_cid):\n%s\n\n", g6.next_hop(n_cid).dag_string().c_str());

	printf("g5.next_hop(n_src.id_string()):\n%s\n", g5.next_hop(n_src.id_string()).dag_string().c_str());
	printf("g5.next_hop(n_cid.id_string()):\n%s\n", g5.next_hop(n_cid.id_string()).dag_string().c_str());
	printf("g6.next_hop(n_src.id_string()):\n%s\n", g6.next_hop(n_src.id_string()).dag_string().c_str());
	printf("g6.next_hop(n_cid.id_string()):\n%s\n", g6.next_hop(n_cid.id_string()).dag_string().c_str());

	printf("Testing next_hop ^^^\n\n\n");


	printf("Testing first_hop vvv\n");

	printf("g5.first_hop():\n%s\n", g5.first_hop().dag_string().c_str());
	printf("g6.first_hop():\n%s\n", g6.first_hop().dag_string().c_str());

	printf("Testing first_hop ^^^\n\n\n");
	
	
	printf("Testing next_hop ^^^\n\n\n");


	printf("Testing construct_from_re_string vvv\n");

	Graph g7 = Graph("RE AD:1000000000000000000000000000000000000000 HID:0000000000000000000000000000000000000000 SID:1110000000000000000000000000000000001113");
	printf("Graph(\"RE AD:1000000000000000000000000000000000000000 HID:0000000000000000000000000000000000000000 SID:1110000000000000000000000000000000001113\")\n%s\n", g7.dag_string().c_str());
	Graph g8 = Graph("RE ( AD:1000000000000000000000000000000000000000 HID:0000000000000000000000000000000000000000 ) SID:1110000000000000000000000000000000001113");
	printf("Graph(\"RE ( AD:1000000000000000000000000000000000000000 HID:0000000000000000000000000000000000000000 ) SID:1110000000000000000000000000000000001113\")\n%s\n", g8.dag_string().c_str());
	//Graph g9 = Graph("RE ( IP:4500000000010000fafa00000000000000000000 ) AD:1000000000000000000000000000000000000000 HID:0000000000000000000000000000000000000000 SID:0f00000000000000000000000000000000008888");
	//printf("Graph(\"RE ( IP:4500000000010000fafa00000000000000000000 ) AD:1000000000000000000000000000000000000000 HID:0000000000000000000000000000000000000000 SID:0f00000000000000000000000000000000008888\")\n%s\n", g9.dag_string().c_str());

	printf("Testing construct_from_re_string ^^^\n\n\n");
	

	printf("Testing sockaddr_x vvv\n");

	sockaddr_x *s = (sockaddr_x*)malloc(sizeof(sockaddr_x));
	g6.fill_sockaddr(s);
	Graph g6_prime = Graph(s);
	printf("g6_prime.dag_string().c_str():\n%s\n", g6_prime.dag_string().c_str());

	g7.fill_sockaddr(s);
	Graph g7_prime = Graph(s);
	printf("g7_prime.dag_string().c_str():\n%s\n", g7_prime.dag_string().c_str());

	printf("Testing sockaddr_x ^^^\n\n\n");

	printf("Testing replace_final_intent vvv\n");
	Graph g6_new_intent = Graph(g6);
	g6_new_intent.replace_final_intent(n_cid);
	printf("g6_new_intent.dag_string().c_str():\n%s\n", g6_new_intent.dag_string().c_str());
	printf("Testing replace_final_intent ^^^\n\n\n");
	
	
	printf("Testing get_final_intent vvv\n");
	printf("Final intent of g6_new_intent: %s\n", g6_new_intent.get_final_intent().id_string().c_str());
	printf("Testing get_final_intent ^^^\n\n\n");



	printf("Testing string parse error checking vvv\n");

	printf("Testing IP parsing\n");
	Graph g10 = Graph("RE ( IP:192.168.0.1 ) AD:1000000000000000000000000000000000000000 HID:0000000000000000000000000000000000000000 SID:1110000000000000000000000000000000001113");
	printf("g10.dag_string().c_str():\n%s\n", g10.dag_string().c_str());

	printf("\nTesting 4ID parsing\n");
	Graph g11 = Graph("RE ( IP:4500000000010000fafa000000000000c0a80001 ) AD:1000000000000000000000000000000000000000 HID:0000000000000000000000000000000000000000 SID:1110000000000000000000000000000000001113");
	printf("g11.dag_string().c_str():\n%s\n", g11.dag_string().c_str());
	
	
	printf("\nTesting bogus XID type\n");
	Graph g12 = Graph("RE QD:1000000000000000000000000000000000000000 HID:0000000000000000000000000000000000000000 SID:1110000000000000000000000000000000001113");
	printf("g12.dag_string().c_str():\n%s\n", g12.dag_string().c_str());
	
	
	printf("\nTesting short (<40 char) XID string\n");
	Graph g13 = Graph("RE AD:10000000000000000000000000000000000 HID:0000000000000000000000000000000000000000 SID:1110000000000000000000000000000000001113");
	printf("g13.dag_string().c_str():\n%s\n", g13.dag_string().c_str());
	
	printf("\nTesting non-hex XID string\n");
	Graph g14 = Graph("RE AD:10000hello0world0qrsxyz00000000000000000 HID:0000000000000000000000000000000000000000 SID:1110000000000000000000000000000000001113");
	printf("g14.dag_string().c_str():\n%s\n", g14.dag_string().c_str());

	printf("Testing string parse error checking ^^^\n\n\n");

	test_c();

	return 0;
}
