
import socket
import struct
import json
import os
import argparse
import signal
import sys

# DNS Constants
DNS_QUERY_PORT = 53
DNS_TYPE_A = 1
DNS_CLASS_IN = 1

def load_records(record_file):
    try:
        if os.path.exists(record_file):
            with open(record_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading records: {e}")
    return {}

def build_response(data, records):
    # Parse Header
    # ID (2), Flags (2), QDCOUNT (2), ANCOUNT (2), NSCOUNT (2), ARCOUNT (2)
    tid, flags, qdcount, ancount, nscount, arcount = struct.unpack('!HHHHHH', data[:12])
    
    # We only handle standard queries (Opcode 0)
    # Get Query Name
    offset = 12
    qname_parts = []
    original_offset = offset
    
    while True:
        length = data[offset]
        if length == 0:
            offset += 1
            break
        offset += 1
        qname_parts.append(data[offset:offset+length].decode('utf-8'))
        offset += length
        
    qname = ".".join(qname_parts)
    qtype, qclass = struct.unpack('!HH', data[offset:offset+4])
    
    print(f"Query: {qname} (Type: {qtype})")
    
    # Lookup
    # Try exact match first, then with .local or similar if needed
    # Our simple records are just "hostname" -> "ip"
    # But DNS queries often come as "hostname."
    key = qname.rstrip('.')
    ip_address = records.get(key)
    
    # Response Header
    # QR=1(Response), AA=1(Authoritative), RA=0, RCODE=0(Success) or 3(NXDOMAIN)
    # Flags: 1 0000 1 0 0 0000 0000 -> 0x8400 (if found)
    # Flags: 1 0000 1 0 0 0000 0011 -> 0x8403 (if not found)
    
    answers = []
    
    if ip_address and qtype == DNS_TYPE_A:
        resp_flags = 0x8400
        # Build Answer
        # Name Ptr (0xC000 | 12) -> Points to start of question name
        ans_name = 0xC00c 
        ans_type = DNS_TYPE_A
        ans_class = DNS_CLASS_IN
        ans_ttl = 60
        ans_len = 4
        ans_data = socket.inet_aton(ip_address) # 4 bytes
        
        answer_bytes = struct.pack('!HHHLH4s', ans_name, ans_type, ans_class, ans_ttl, ans_len, ans_data)
        answers.append(answer_bytes)
    else:
        resp_flags = 0x8403 # NXDOMAIN
        print(f"  -> Not found")

    # Re-pack Header
    # QR=1, Opcode=0, AA=1, TC=0, RD=1(copy), RA=0, Z=0, RCODE=...
    # Keep RD bit from request
    resp_flags = 0x8000 | (0x0100 if (flags & 0x0100) else 0) | (0x0400) # AA=1
    if not ip_address:
         resp_flags |= 0x0003 # NXDOMAIN
    
    header = struct.pack('!HHHHHH', tid, resp_flags, qdcount, len(answers), 0, 0)
    
    # Response = Header + Question (copied) + Answers
    response = header + data[12:offset+4]
    for ans in answers:
        response += ans
        
    return response

def main():
    parser = argparse.ArgumentParser(description='Simple DNS Server')
    parser.add_argument('--records', required=True, help='Path to JSON file with DNS records')
    args = parser.parse_args()

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("Shutting down DNS server...")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(('0.0.0.0', DNS_QUERY_PORT))
        print(f"DNS Server listening on 0.0.0.0:{DNS_QUERY_PORT}")
        print(f"Reading records from {args.records}")
        
        while True:
            try:
                data, addr = sock.recvfrom(512)
                records = load_records(args.records)
                response = build_response(data, records)
                sock.sendto(response, addr)
            except Exception as e:
                print(f"Error handling request: {e}")
                
    except OSError as e:
        print(f"Failed to bind port {DNS_QUERY_PORT}: {e}")
        sys.exit(1)
    finally:
        sock.close()

if __name__ == '__main__':
    main()
