"""
Packet Observer - Kernel-Level Network Emulator

This module captures real packets from the Linux kernel using tcpdump.
All packet events are READ-ONLY observations that NEVER affect packet delivery.

CRITICAL: Packet capture is passive. Visualization consumes events, not drives them.
"""

import subprocess
import threading
import logging
import re
import time
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass
from datetime import datetime
from queue import Queue
from enum import Enum

logger = logging.getLogger(__name__)


class PacketProtocol(Enum):
    """Network protocols"""
    ICMP = "ICMP"
    TCP = "TCP"
    UDP = "UDP"
    ARP = "ARP"
    DNS = "DNS"
    OTHER = "OTHER"


class PacketType(Enum):
    """Specific packet types"""
    # ICMP
    ICMP_ECHO_REQUEST = "icmp_echo_request"
    ICMP_ECHO_REPLY = "icmp_echo_reply"
    ICMP_DEST_UNREACHABLE = "icmp_dest_unreachable"
    ICMP_TTL_EXCEEDED = "icmp_ttl_exceeded"
    
    # TCP
    TCP_SYN = "tcp_syn"
    TCP_SYN_ACK = "tcp_syn_ack"
    TCP_ACK = "tcp_ack"
    TCP_FIN = "tcp_fin"
    TCP_RST = "tcp_rst"
    
    # ARP
    ARP_REQUEST = "arp_request"
    ARP_REPLY = "arp_reply"
    
    # DNS
    DNS_QUERY = "dns_query"
    DNS_RESPONSE = "dns_response"
    
    # Other
    OTHER = "other"


@dataclass
class PacketEvent:
    """
    Represents a captured packet event from the kernel.
    This is a READ-ONLY observation.
    """
    timestamp: float          # Unix timestamp (seconds.microseconds)
    namespace: str            # Namespace where captured
    interface: str            # Interface where captured
    protocol: PacketProtocol
    packet_type: PacketType
    
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_mac: Optional[str] = None
    dst_mac: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    
    ttl: Optional[int] = None
    size: int = 0
    
    # ICMP specific
    icmp_seq: Optional[int] = None
    icmp_id: Optional[int] = None
    
    # TCP specific
    tcp_flags: Optional[str] = None
    
    # Raw packet data
    raw_line: str = ""


class PacketObserver:
    """
    Captures packets from a network namespace using tcpdump.
    
    Uses kernel-level packet capture:
    - tcpdump with libpcap
    - Passive observation (XDP_PASS mode)
    - Real kernel timestamps
    - No packet modification or dropping
    """
    
    def __init__(self, namespace: str, interface: str,
                 packet_callback: Optional[Callable[[PacketEvent], None]] = None):
        """
        Initialize packet observer.
        
        Args:
            namespace: Network namespace to observe
            interface: Interface to capture on
            packet_callback: Function to call for each packet
        """
        self.namespace = namespace
        self.interface = interface
        self.packet_callback = packet_callback
        
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self.packet_queue = Queue()
        
        self.reader_thread: Optional[threading.Thread] = None
        self.parser_thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start packet capture"""
        if self.running:
            logger.warning(f"Observer already running for {self.namespace}:{self.interface}")
            return
        
        try:
            # Build tcpdump command
            cmd = [
                'sudo', 'ip', 'netns', 'exec', self.namespace,
                'tcpdump',
                '-i', self.interface,
                '-l',           # Line buffered output
                '-n',           # No DNS resolution
                '-tt',          # Unix timestamp
                '-e',           # Ethernet header
                '-v',           # Verbose
                '-s', '96',     # Capture first 96 bytes (headers only)
                'not', 'port', '22'  # Exclude SSH
            ]
            
            logger.info(f"Starting packet capture: {self.namespace}:{self.interface}")
            
            # Start tcpdump process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=1,
                universal_newlines=True
            )
            
            self.running = True
            
            # Start reader thread
            self.reader_thread = threading.Thread(
                target=self._read_loop,
                daemon=True
            )
            self.reader_thread.start()
            
            # Start parser thread
            self.parser_thread = threading.Thread(
                target=self._parse_loop,
                daemon=True
            )
            self.parser_thread.start()
            
            logger.info(f"Packet capture started: {self.namespace}:{self.interface}")
            
        except Exception as e:
            logger.error(f"Failed to start packet capture: {e}")
            self.running = False
            raise RuntimeError(f"Packet capture failed: {e}")
    
    def _read_loop(self):
        """Read tcpdump output line by line"""
        try:
            while self.running and self.process:
                line = self.process.stdout.readline()
                
                if not line:
                    # EOF - process terminated
                    logger.info(f"tcpdump process ended: {self.namespace}:{self.interface}")
                    self.running = False
                    break
                
                # Queue line for parsing
                self.packet_queue.put(line.strip())
                
        except Exception as e:
            logger.error(f"Error reading tcpdump output: {e}")
            self.running = False
    
    def _parse_loop(self):
        """Parse tcpdump output and create packet events"""
        while self.running:
            try:
                # Get line from queue (with timeout)
                line = self.packet_queue.get(timeout=0.1)
                
                # Parse packet
                packet_event = self._parse_packet_line(line)
                
                if packet_event:
                    # Call callback if registered
                    if self.packet_callback:
                        try:
                            self.packet_callback(packet_event)
                        except Exception as e:
                            logger.error(f"Packet callback error: {e}")
                
            except:
                continue  # Timeout or empty queue
    
    def _parse_packet_line(self, line: str) -> Optional[PacketEvent]:
        """
        Parse a tcpdump output line into a PacketEvent.
        
        Example formats:
        - ICMP: "1641234567.123456 00:11:22:33:44:55 > 66:77:88:99:aa:bb, IP 10.0.1.10 > 10.0.1.20: ICMP echo request, id 1234, seq 1"
        - TCP:  "1641234567.123456 ... IP 10.0.1.10.8080 > 10.0.1.20.80: Flags [S], seq 12345"
        - ARP:  "1641234567.123456 ... ARP, Request who-has 10.0.1.20 tell 10.0.1.10"
        """
        try:
            # Extract timestamp (first field)
            timestamp_match = re.match(r'^(\d+\.\d+)', line)
            if not timestamp_match:
                return None
            
            timestamp = float(timestamp_match.group(1))
            
            # Determine protocol
            protocol = PacketProtocol.OTHER
            packet_type = PacketType.OTHER
            
            src_ip = None
            dst_ip = None
            src_mac = None
            dst_mac = None
            ttl = None
            icmp_seq = None
            icmp_id = None
            tcp_flags = None
            
            # Parse MAC addresses
            mac_match = re.search(r'([0-9a-f:]{17}) > ([0-9a-f:]{17})', line)
            if mac_match:
                src_mac = mac_match.group(1)
                dst_mac = mac_match.group(2)
            
            # Parse ICMP
            if 'ICMP' in line:
                protocol = PacketProtocol.ICMP
                
                # Extract IPs
                ip_match = re.search(r'IP (\d+\.\d+\.\d+\.\d+) > (\d+\.\d+\.\d+\.\d+)', line)
                if ip_match:
                    src_ip = ip_match.group(1)
                    dst_ip = ip_match.group(2)
                
                # Determine ICMP type
                if 'echo request' in line:
                    packet_type = PacketType.ICMP_ECHO_REQUEST
                    seq_match = re.search(r'seq (\d+)', line)
                    id_match = re.search(r'id (\d+)', line)
                    if seq_match:
                        icmp_seq = int(seq_match.group(1))
                    if id_match:
                        icmp_id = int(id_match.group(1))
                        
                elif 'echo reply' in line:
                    packet_type = PacketType.ICMP_ECHO_REPLY
                    seq_match = re.search(r'seq (\d+)', line)
                    id_match = re.search(r'id (\d+)', line)
                    if seq_match:
                        icmp_seq = int(seq_match.group(1))
                    if id_match:
                        icmp_id = int(id_match.group(1))
                        
                elif 'time exceeded' in line or 'ttl' in line.lower():
                    packet_type = PacketType.ICMP_TTL_EXCEEDED
                    
                elif 'unreachable' in line:
                    packet_type = PacketType.ICMP_DEST_UNREACHABLE
            
            # Parse TCP
            elif 'tcp' in line.lower() or 'Flags' in line:
                protocol = PacketProtocol.TCP
                
                # Extract IPs and ports
                tcp_match = re.search(r'IP (\d+\.\d+\.\d+\.\d+)\.(\d+) > (\d+\.\d+\.\d+\.\d+)\.(\d+)', line)
                if tcp_match:
                    src_ip = tcp_match.group(1)
                    src_port = int(tcp_match.group(2))
                    dst_ip = tcp_match.group(3)
                    dst_port = int(tcp_match.group(4))
                
                # Parse TCP flags
                flags_match = re.search(r'Flags \[([SFPRU\.]+)\]', line)
                if flags_match:
                    tcp_flags = flags_match.group(1)
                    
                    if 'S' in tcp_flags and 'A' not in tcp_flags:
                        packet_type = PacketType.TCP_SYN
                    elif 'S' in tcp_flags and 'A' in tcp_flags:
                        packet_type = PacketType.TCP_SYN_ACK
                    elif 'F' in tcp_flags:
                        packet_type = PacketType.TCP_FIN
                    elif 'R' in tcp_flags:
                        packet_type = PacketType.TCP_RST
                    elif 'A' in tcp_flags:
                        packet_type = PacketType.TCP_ACK
            
            # Parse ARP
            elif 'ARP' in line:
                protocol = PacketProtocol.ARP
                
                if 'Request' in line:
                    packet_type = PacketType.ARP_REQUEST
                    # Extract IPs from "who-has X tell Y"
                    arp_match = re.search(r'who-has (\d+\.\d+\.\d+\.\d+) tell (\d+\.\d+\.\d+\.\d+)', line)
                    if arp_match:
                        dst_ip = arp_match.group(1)
                        src_ip = arp_match.group(2)
                        
                elif 'Reply' in line:
                    packet_type = PacketType.ARP_REPLY
                    arp_match = re.search(r'(\d+\.\d+\.\d+\.\d+) is-at', line)
                    if arp_match:
                        src_ip = arp_match.group(1)
            
            # Parse UDP (potential DNS)
            elif 'UDP' in line:
                protocol = PacketProtocol.UDP
                
                # Check if DNS (port 53)
                if '.53 >' in line or '> .53:' in line:
                    protocol = PacketProtocol.DNS
                    if '>' in line and '.53:' in line:
                        packet_type = PacketType.DNS_QUERY
                    else:
                        packet_type = PacketType.DNS_RESPONSE
            
            # Extract TTL
            ttl_match = re.search(r'ttl (\d+)', line)
            if ttl_match:
                ttl = int(ttl_match.group(1))
            
            # Create packet event
            packet_event = PacketEvent(
                timestamp=timestamp,
                namespace=self.namespace,
                interface=self.interface,
                protocol=protocol,
                packet_type=packet_type,
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_mac=src_mac,
                dst_mac=dst_mac,
                ttl=ttl,
                icmp_seq=icmp_seq,
                icmp_id=icmp_id,
                tcp_flags=tcp_flags,
                raw_line=line
            )
            
            return packet_event
            
        except Exception as e:
            logger.error(f"Error parsing packet line: {e}\nLine: {line}")
            return None
    
    def stop(self):
        """Stop packet capture"""
        if not self.running:
            return
        
        logger.info(f"Stopping packet capture: {self.namespace}:{self.interface}")
        
        self.running = False
        
        # Terminate tcpdump process
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
        
        # Wait for threads
        if self.reader_thread:
            self.reader_thread.join(timeout=1)
        if self.parser_thread:
            self.parser_thread.join(timeout=1)
        
        logger.info(f"Packet capture stopped: {self.namespace}:{self.interface}")
    
    def is_running(self) -> bool:
        """Check if observer is running"""
        return self.running


class PacketObserverManager:
    """
    Manages multiple packet observers across namespaces and interfaces.
    """
    
    def __init__(self):
        self.observers: Dict[str, PacketObserver] = {}
        self.global_callback: Optional[Callable] = None
    
    def set_global_callback(self, callback: Callable[[PacketEvent], None]):
        """Set a global callback for all packet events"""
        self.global_callback = callback
    
    def start_observer(self, namespace: str, interface: str) -> str:
        """
        Start observing packets on a namespace:interface.
        
        Returns:
            Observer ID
        """
        observer_id = f"{namespace}:{interface}"
        
        if observer_id in self.observers:
            logger.warning(f"Observer already exists: {observer_id}")
            return observer_id
        
        # Create observer with global callback
        observer = PacketObserver(
            namespace=namespace,
            interface=interface,
            packet_callback=self.global_callback
        )
        
        observer.start()
        self.observers[observer_id] = observer
        
        logger.info(f"Started observer: {observer_id}")
        return observer_id
    
    def stop_observer(self, observer_id: str):
        """Stop an observer"""
        if observer_id not in self.observers:
            logger.warning(f"Observer not found: {observer_id}")
            return
        
        observer = self.observers[observer_id]
        observer.stop()
        del self.observers[observer_id]
        
        logger.info(f"Stopped observer: {observer_id}")
    
    def stop_all(self):
        """Stop all observers"""
        logger.info("Stopping all packet observers...")
        for observer_id in list(self.observers.keys()):
            self.stop_observer(observer_id)
        logger.info("All observers stopped")
    
    def list_observers(self) -> List[Dict]:
        """List all active observers"""
        return [
            {
                'observer_id': obs_id,
                'namespace': obs.namespace,
                'interface': obs.interface,
                'running': obs.is_running()
            }
            for obs_id, obs in self.observers.items()
        ]


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    def packet_handler(packet: PacketEvent):
        """Example packet handler"""
        print(f"[{packet.timestamp}] {packet.protocol.value}: "
              f"{packet.src_ip} -> {packet.dst_ip} ({packet.packet_type.value})")
    
    # Note: Requires namespace and interface to exist
    # Create namespace: sudo ip netns add test-ns
    # Create interface: sudo ip netns exec test-ns ip link set lo up
    
    manager = PacketObserverManager()
    manager.set_global_callback(packet_handler)
    
    try:
        # Start observer
        observer_id = manager.start_observer("test-ns", "lo")
        
        # Let it run for a bit
        time.sleep(5)
        
    finally:
        # Cleanup
        manager.stop_all()
