"""
Topology Manager - Kernel-Level Network Emulator

This module orchestrates the complete network topology using:
- NamespaceManager (devices)
- LinkManager (connections)
- PTYManager (terminals)
- PacketObserver (monitoring)

CRITICAL: All network behavior comes from the Linux kernel.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import ipaddress
import json
import os
import subprocess
import shlex
import random

from namespace_manager import NamespaceManager, DeviceType, NetworkNamespace
from link_manager import LinkManager, Link, LinkType
from pty_manager import PTYManager, PTYSession
from packet_observer import PacketObserverManager, PacketEvent

logger = logging.getLogger(__name__)


@dataclass
class Device:
    """High-level device representation"""
    name: str
    device_type: DeviceType
    namespace: NetworkNamespace
    interfaces: List[str] = field(default_factory=list)
    ip_addresses: Dict[str, str] = field(default_factory=dict)  # interface -> IP
    default_gateway: Optional[str] = None
    pty_session_id: Optional[str] = None
    services: List[Any] = field(default_factory=list)  # List of subprocess.Popen objects
    x: int = 400
    y: int = 300


@dataclass
class TopologyLink:
    """High-level link representation"""
    link_id: str
    device_a: str
    interface_a: str
    device_b: str
    interface_b: str
    latency_ms: float
    jitter_ms: float = 0.0
    bandwidth_mbps: Optional[float] = None
    packet_loss_percent: float = 0.0


class IPAllocator:
    """
    Simple IP address allocator for automatic IP assignment.
    Allocates IPs from private ranges.
    """
    
    def __init__(self):
        self.networks: Dict[str, ipaddress.IPv4Network] = {}
        self.allocated: Dict[str, List[str]] = {}
        self.next_network_id = 1
    
    def create_network(self, prefix_len: int = 24) -> str:
        """
        Create a new network for a link/subnet.
        
        Returns:
            Network ID (e.g., "net1")
        """
        network_id = f"net{self.next_network_id}"
        self.next_network_id += 1
        
        # Use 10.0.x.0/24 networks
        network_addr = f"10.0.{self.next_network_id - 1}.0/{prefix_len}"
        network = ipaddress.IPv4Network(network_addr)
        
        self.networks[network_id] = network
        self.allocated[network_id] = []
        
        logger.info(f"Created network: {network_id} ({network})")
        return network_id
    
    def allocate_ip(self, network_id: str) -> str:
        """
        Allocate an IP from a network.
        
        Returns:
            IP address as string
        """
        if network_id not in self.networks:
            raise ValueError(f"Network '{network_id}' does not exist")
        
        network = self.networks[network_id]
        allocated = self.allocated[network_id]
        
        # Find next available IP (skip network and broadcast)
        for ip in network.hosts():
            ip_str = str(ip)
            if ip_str not in allocated:
                allocated.append(ip_str)
                logger.debug(f"Allocated IP: {ip_str} from {network_id}")
                return ip_str
        
        raise RuntimeError(f"No available IPs in network {network_id}")
    
    def get_network_cidr(self, network_id: str) -> int:
        """Get CIDR prefix length for a network"""
        if network_id not in self.networks:
            raise ValueError(f"Network '{network_id}' does not exist")
        return self.networks[network_id].prefixlen


class TopologyManager:
    """
    High-level topology management.
    Orchestrates all kernel-level components.
    """
    
    def __init__(self):
        self.namespace_manager = NamespaceManager()
        self.link_manager = LinkManager()
        self.pty_manager = PTYManager()
        self.packet_observer = PacketObserverManager()
        self.ip_allocator = IPAllocator()
        
        self.devices: Dict[str, Device] = {}
        self.links: Dict[str, TopologyLink] = {}
        self.switches: Dict[str, str] = {}  # switch_name -> bridge_name
        self.switch_networks: Dict[str, str] = {}  # switch_name -> network_id
        self.active_failures: Dict[str, List[str]] = {}  # device -> [failure_types]
    
    def _ensure_switch_ip(self, switch_name: str, network_id: str):
        """
        Ensure the switch has an IP address on the specified network.
        Assigns IP to the bridge interface in the root namespace.
        """
        if switch_name not in self.devices:
            return

        device = self.devices[switch_name]
        bridge_name = self.switches.get(switch_name)
        
        if not bridge_name:
            return
            
        # Check if the bridge interface already has an IP in our records
        if "mgmt" in device.ip_addresses:
             return
             
        try:
            # Allocate IP
            ip = self.ip_allocator.allocate_ip(network_id)
            cidr = self.ip_allocator.get_network_cidr(network_id)
            
            # Assign to bridge (Root Namespace)
            # sudo ip addr add 10.0.X.Y/24 dev br-switchX
            cmd = f"sudo ip addr add {ip}/{cidr} dev {bridge_name}"
            subprocess.run(shlex.split(cmd), check=True, capture_output=True)
            
            # Update device records
            device.ip_addresses["mgmt"] = f"{ip}/{cidr}"
            logger.info(f"Assigned management IP {ip}/{cidr} to switch {switch_name}")
            
        except Exception as e:
            logger.warning(f"Failed to assign IP to switch {switch_name} (might already have one): {e}")

    def _auto_configure_routing(self):
        """
        Automatically configure static routes for all devices.
        Implements a simple centralized routing controller (shortest path).
        """
        # 1. Build Graph
        # adjacency: Node -> List[(Neighbor, Subnet, NeighborIP)]
        adjacency = {name: [] for name in self.devices}
        # device_subnets: Node -> Set[IPv4Network] (Directly connected subnets)
        device_subnets = {name: set() for name in self.devices}

        for link in self.links.values():
            d1, d2 = link.device_a, link.device_b
            iface1, iface2 = link.interface_a, link.interface_b
            
            ip1_full = self.devices[d1].ip_addresses.get(iface1)
            ip2_full = self.devices[d2].ip_addresses.get(iface2)
            
            if ip1_full and ip2_full:
                ip1 = ip1_full.split('/')[0]
                ip2 = ip2_full.split('/')[0]
                subnet = ipaddress.ip_network(ip1_full, strict=False)
                
                device_subnets[d1].add(subnet)
                device_subnets[d2].add(subnet)
                
                adjacency[d1].append((d2, subnet, ip2))
                adjacency[d2].append((d1, subnet, ip1))

        # 2. Calculate Routes for each device
        for src_name, src_dev in self.devices.items():
            # Layer 2 devices (Switches) don't need IP routes for forwarding
            if src_dev.device_type == DeviceType.SWITCH:
                continue

            # BFS to find reachable subnets via Gateways
            # Queue: (CurrentNode, NextHopIP)
            # If NextHopIP is None, it means we are at source, next hop is neighbor IP
            queue = [(src_name, None)]
            visited = {src_name}
            
            # Map: DestinationSubnet -> GatewayIP
            # We want the shortest path (first time we see a subnet, that's the best route)
            learned_routes = {}
            
            while queue:
                curr, gateway = queue.pop(0)
                
                # Check subnets attached to current node
                for subnet in device_subnets[curr]:
                    # If this subnet is NOT directly connected to Source
                    if subnet not in device_subnets[src_name]:
                        if subnet not in learned_routes and gateway:
                            learned_routes[subnet] = gateway
                
                # Traverse neighbors
                # Only traverse through Routers (unless it's the first hop, we can always hop to a neighbor)
                # Actually, only ROUTERS forward packets.
                # So if 'curr' is not the Source, 'curr' MUST be a router to forward to neighbors.
                if curr != src_name and self.devices[curr].device_type != DeviceType.ROUTER:
                    continue
                    
                for neighbor, _, neighbor_ip in adjacency[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        # Determine gateway for Source
                        next_gateway = gateway if gateway else neighbor_ip
                        queue.append((neighbor, next_gateway))
            
            # 3. Apply Routes
            # Flush existing routes? No, just replace/add specific ones.
            # We won't delete old routes to be safe, just ensure connectivity.
            for subnet, gateway in learned_routes.items():
                try:
                    # sudo ip netns exec NAME ip route replace SUBNET via GATEWAY
                    cmd = f"sudo ip netns exec {src_name} ip route replace {subnet} via {gateway}"
                    subprocess.run(shlex.split(cmd), check=False, capture_output=True)
                except Exception as e:
                    logger.error(f"Failed to set route on {src_name} to {subnet}: {e}")
    
    def _update_dns_records(self):
        """
        Generates a JSON file with hostname -> IP mappings.
        And configures /etc/netns/<device>/resolv.conf for automatic resolution.
        """
        records = {}
        dns_server_ip = None
        
        # 1. Collect IPs and find DNS Server
        for name, device in self.devices.items():
            ip = None
            if hasattr(device, 'ip_addresses') and device.ip_addresses:
                for addr_cidr in device.ip_addresses.values():
                    if addr_cidr:
                        ip = addr_cidr.split('/')[0]
                        break
            
            if ip:
                records[name] = ip
                records[f"{name}.lan"] = ip
                
                # Identify if this is the DNS server
                if device.device_type == DeviceType.DNS_SERVER:
                    dns_server_ip = ip
        
        # 2. Save Records for Server
        try:
            with open("dns_records.json", "w") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to update DNS records: {e}")

        # 3. Configure Client Resolvers (/etc/netns/<name>/resolv.conf)
        if dns_server_ip:
            for name, device in self.devices.items():
                try:
                    # Skip switches (no namespace usually, or irrelevant)
                    if device.device_type == DeviceType.SWITCH:
                        continue
                        
                    netns_dir = f"/etc/netns/{name}"
                    os.makedirs(netns_dir, exist_ok=True)
                    
                    resolv_conf_path = f"{netns_dir}/resolv.conf"
                    with open(resolv_conf_path, "w") as f:
                        if device.device_type == DeviceType.DNS_SERVER:
                            # DNS server points to itself (localhost)
                            f.write("nameserver 127.0.0.1\n")
                            f.write("search lan\n")
                        else:
                            # Clients point to DNS server IP
                            f.write(f"nameserver {dns_server_ip}\n")
                            f.write("search lan\n")
                            
                    # logger.debug(f"Configured DNS for {name} -> {dns_server_ip}")
                except Exception as e:
                    logger.error(f"Failed to configure resolv.conf for {name}: {e}")
        else:
            # Fallback to Google DNS to avoid systemd-resolved stub issues (127.0.0.53)
            for name, device in self.devices.items():
                try:
                    if device.device_type == DeviceType.SWITCH:
                        continue
                    
                    netns_dir = f"/etc/netns/{name}"
                    os.makedirs(netns_dir, exist_ok=True)
                    
                    with open(f"{netns_dir}/resolv.conf", "w") as f:
                        f.write("nameserver 8.8.8.8\n")
                except Exception as e:
                    logger.error(f"Failed to configure fallback DNS for {name}: {e}")

    def add_device(self, name: str, device_type: str, 
                   ip_address: Optional[str] = None,
                   subnet_mask: Optional[str] = None,
                   x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """
        Add a device to the topology.
        
        Args:
            name: Device name
            device_type: "host", "router", "switch", or "dns_server"
            ip_address: Optional manual IP address
            subnet_mask: Optional subnet mask (default: "255.255.255.0")
        
        Returns:
            Device object
        """
        # Set default random position if not provided
        if x is None:
            x = random.randint(100, 700)
        if y is None:
            y = random.randint(100, 500)
        if name in self.devices:
            raise ValueError(f"Device '{name}' already exists")
        
        # Convert string to DeviceType
        dtype = DeviceType(device_type)
        
        # Create namespace (except for switches - they use bridges)
        if dtype == DeviceType.SWITCH:
            # Create bridge for switch
            bridge_name = f"br-{name}"
            self.link_manager.create_bridge(bridge_name)
            self.switches[name] = bridge_name
            
            # Create dummy namespace for consistency
            namespace = self.namespace_manager.create_namespace(name, dtype)
            
            device = Device(
                name=name,
                device_type=dtype,
                namespace=namespace,
                x=x, y=y
            )
        else:
            # Create namespace
            namespace = self.namespace_manager.create_namespace(name, dtype)
            
            device = Device(
                name=name,
                device_type=dtype,
                namespace=namespace,
                x=x, y=y
            )
            
            # Create PTY session for interactive devices
            if dtype in [DeviceType.HOST, DeviceType.ROUTER, DeviceType.DNS_SERVER]:
                try:
                    session = self.pty_manager.create_session(
                        session_id=f"pty-{name}",
                        namespace=name
                    )
                    device.pty_session_id = session.session_id
                    logger.info(f"Created PTY session for {name}")
                except Exception as e:
                    logger.warning(f"Failed to create PTY session for {name}: {e}")

            # Start services based on type
            import subprocess
            import shlex
            
            try:
                if dtype == DeviceType.DNS_SERVER:
                    # Start Real DNS Server
                    records_file_path = os.path.abspath("dns_records.json")
                    script_path = os.path.abspath("src/simple_dns_server.py")
                    
                    # Ensure records file exists
                    self._update_dns_records()
                    
                    # Run the python script
                    cmd = f"sudo ip netns exec {name} python3 {script_path} --records {records_file_path}"
                    proc = subprocess.Popen(shlex.split(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    device.services.append(proc)
                    logger.info(f"Started Custom DNS service on {name} (reading {records_file_path})")
                    
                elif dtype == DeviceType.SERVER:
                    # Start HTTP server (TCP 80)
                    cmd = f"sudo ip netns exec {name} python3 -m http.server 80"
                    proc = subprocess.Popen(shlex.split(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    device.services.append(proc)
                    logger.info(f"Started HTTP service on {name}")

            except Exception as e:
                logger.error(f"Failed to start services for {name}: {e}")
        
        self.devices[name] = device
        self._update_dns_records() # Update records whenever a device is added
        
        logger.info(f"Added device: {name} (type: {device_type})")
        
        # Return device info as dict for API compatibility
        return {
            "name": name,
            "type": device_type,
            "ip_address": ip_address,
            "subnet_mask": subnet_mask or "255.255.255.0",
            "x": x,
            "y": y,
            "status": "active"
        }
    
    def rename_device(self, old_name: str, new_name: str):
        """Rename a device in the topology"""
        if old_name not in self.devices:
            raise ValueError(f"Device '{old_name}' does not exist")
        if new_name in self.devices:
            raise ValueError(f"Device '{new_name}' already exists")
        
        # Rename namespace
        self.namespace_manager.rename_namespace(old_name, new_name)
        
        # Update devices dict
        device = self.devices.pop(old_name)
        device.name = new_name
        self.devices[new_name] = device
        
        # Update switches dict if applicable
        if old_name in self.switches:
            self.switches[new_name] = self.switches.pop(old_name)
        
        # Update switch_networks if applicable
        if old_name in self.switch_networks:
            self.switch_networks[new_name] = self.switch_networks.pop(old_name)
            
        # Update all links that reference this device
        for link in self.links.values():
            if link.device_a == old_name:
                link.device_a = new_name
            if link.device_b == old_name:
                link.device_b = new_name
        
        logger.info(f"Renamed device {old_name} to {new_name}")
    
    def remove_device(self, name: str):
        """Remove a device from the topology"""
        if name not in self.devices:
            logger.warning(f"Device '{name}' does not exist")
            return
        
        device = self.devices[name]
        
        # Close PTY session
        if device.pty_session_id:
            try:
                self.pty_manager.close_session(device.pty_session_id)
            except Exception as e:
                logger.error(f"Failed to close PTY session: {e}")
        
        # Stop background services
        for proc in device.services:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception as e:
                logger.warning(f"Failed to stop service process for {name}: {e}")
                # Force kill if needed
                try:
                    proc.kill()
                except:
                    pass
        
        # Remove links connected to this device
        links_to_remove = [
            link_id for link_id, link in self.links.items()
            if link.device_a == name or link.device_b == name
        ]
        for link_id in links_to_remove:
            try:
                self.remove_link(link_id)
            except Exception as e:
                logger.error(f"Failed to remove link {link_id} for device {name}: {e}")
        
        # Delete namespace
        try:
            self.namespace_manager.delete_namespace(name)
        except Exception as e:
            logger.error(f"Failed to delete namespace: {e}")
        
        # Delete bridge if switch
        if device.device_type == DeviceType.SWITCH:
            if name in self.switches:
                try:
                    self.link_manager.delete_bridge(self.switches[name])
                    del self.switches[name]
                except Exception as e:
                    logger.error(f"Failed to delete bridge: {e}")
            if name in self.switch_networks:
                del self.switch_networks[name]
        
        del self.devices[name]
        logger.info(f"Removed device: {name}")
    
    def add_link(self, device_a: str, device_b: str,
                 latency_ms: float = 10.0,
                 bandwidth_mbps: Optional[float] = None,
                 packet_loss_percent: float = 0.0) -> TopologyLink:
        """
        Add a link between two devices.
        
        Args:
            device_a: First device name
            device_b: Second device name
            latency_ms: Link latency
            bandwidth_mbps: Bandwidth limit (None = unlimited)
            packet_loss_percent: Packet loss percentage
        
        Returns:
            TopologyLink object
        """
        if device_a not in self.devices:
            raise ValueError(f"Device '{device_a}' does not exist")
        if device_b not in self.devices:
            raise ValueError(f"Device '{device_b}' does not exist")
        
        dev_a = self.devices[device_a]
        dev_b = self.devices[device_b]
        
        # Generate interface names
        iface_a = f"eth{len(dev_a.interfaces)}"
        iface_b = f"eth{len(dev_b.interfaces)}"
        
        # Handle switch connections to ensure same subnet
        network_id = None
        if dev_a.device_type == DeviceType.SWITCH:
            if device_a not in self.switch_networks:
                self.switch_networks[device_a] = self.ip_allocator.create_network()
            network_id = self.switch_networks[device_a]
        elif dev_b.device_type == DeviceType.SWITCH:
            if device_b not in self.switch_networks:
                self.switch_networks[device_b] = self.ip_allocator.create_network()
            network_id = self.switch_networks[device_b]
        else:
            # Point-to-point link gets its own subnet
            network_id = self.ip_allocator.create_network()
            
        cidr = self.ip_allocator.get_network_cidr(network_id)
        
        # Handle switch connections
        # Handle switch connections
        if dev_a.device_type == DeviceType.SWITCH:
            # Connect device_b to switch
            bridge_name = self.switches[device_a]
            
            # Ensure switch has an IP for this network (Management IP)
            self._ensure_switch_ip(device_a, network_id)
            
            link = self.link_manager.create_switched_link(
                namespace=device_b,
                interface=iface_b,
                bridge_name=bridge_name,
                latency_ms=latency_ms,
                bandwidth_mbps=bandwidth_mbps
            )
            
            # Allocate IP for device_b
            ip_b = self.ip_allocator.allocate_ip(network_id)
            self.namespace_manager.add_interface(device_b, iface_b, ip_b, str(cidr))
            
            dev_b.interfaces.append(iface_b)
            dev_b.ip_addresses[iface_b] = f"{ip_b}/{cidr}"
            
            # Start packet observer
            self.packet_observer.start_observer(device_b, iface_b)
            
        elif dev_b.device_type == DeviceType.SWITCH:
            # Connect device_a to switch
            bridge_name = self.switches[device_b]
            
            # Ensure switch has an IP for this network (Management IP)
            self._ensure_switch_ip(device_b, network_id)
            
            link = self.link_manager.create_switched_link(
                namespace=device_a,
                interface=iface_a,
                bridge_name=bridge_name,
                latency_ms=latency_ms,
                bandwidth_mbps=bandwidth_mbps
            )
            
            # Allocate IP for device_a
            ip_a = self.ip_allocator.allocate_ip(network_id)
            self.namespace_manager.add_interface(device_a, iface_a, ip_a, str(cidr))
            
            dev_a.interfaces.append(iface_a)
            dev_a.ip_addresses[iface_a] = f"{ip_a}/{cidr}"
            
            # Start packet observer
            self.packet_observer.start_observer(device_a, iface_a)
            
        else:
            # Point-to-point link
            link = self.link_manager.create_p2p_link(
                namespace_a=device_a,
                interface_a=iface_a,
                namespace_b=device_b,
                interface_b=iface_b,
                latency_ms=latency_ms,
                bandwidth_mbps=bandwidth_mbps,
                packet_loss_percent=packet_loss_percent
            )
            
            # Allocate IPs
            ip_a = self.ip_allocator.allocate_ip(network_id)
            ip_b = self.ip_allocator.allocate_ip(network_id)
            
            # Configure interfaces
            self.namespace_manager.add_interface(device_a, iface_a, ip_a, str(cidr))
            self.namespace_manager.add_interface(device_b, iface_b, ip_b, str(cidr))
            
            dev_a.interfaces.append(iface_a)
            dev_a.ip_addresses[iface_a] = f"{ip_a}/{cidr}"
            dev_b.interfaces.append(iface_b)
            dev_b.ip_addresses[iface_b] = f"{ip_b}/{cidr}"
            
            # Start packet observers
            self.packet_observer.start_observer(device_a, iface_a)
            self.packet_observer.start_observer(device_b, iface_b)
        
        # Create topology link
        topo_link = TopologyLink(
            link_id=link.id,
            device_a=device_a,
            interface_a=iface_a,
            device_b=device_b,
            interface_b=iface_b,
            latency_ms=latency_ms,
            jitter_ms=0.0,
            bandwidth_mbps=bandwidth_mbps,
            packet_loss_percent=packet_loss_percent
        )
        
        self.links[link.id] = topo_link
        logger.info(f"Added link: {device_a}:{iface_a} <-> {device_b}:{iface_b}")
        
        self._update_dns_records() # Update records as IPs might have been allocated
        self._auto_configure_routing() # Recalculate routes

        # Return link info as dict for API compatibility
        return {
            "id": link.id,
            "device_a": device_a,
            "device_b": device_b,
            "latency_ms": latency_ms,
            "bandwidth_mbps": bandwidth_mbps,
            "status": "active"
        }
    
    def update_link(self, link_id: str, 
                    latency_ms: float, 
                    jitter_ms: float = 0.0,
                    bandwidth_mbps: Optional[float] = None, 
                    packet_loss_percent: float = 0.0):
        """Update properties of an existing link"""
        if link_id not in self.links:
            raise ValueError(f"Link '{link_id}' does not exist")
        
        topo_link = self.links[link_id]
        
        # Update kernel-level settings via LinkManager
        self.link_manager.update_link(
            link_id, latency_ms, jitter_ms, bandwidth_mbps, packet_loss_percent
        )
        
        # Update metadata
        topo_link.latency_ms = latency_ms
        topo_link.jitter_ms = jitter_ms
        topo_link.bandwidth_mbps = bandwidth_mbps
        topo_link.packet_loss_percent = packet_loss_percent
        logger.info(f"Updated topology link {link_id}")

    def remove_link(self, link_id: str):
        """Remove a link from the topology"""
        if link_id not in self.links:
            raise ValueError(f"Link '{link_id}' does not exist")
        
        topo_link = self.links[link_id]
        
        # Stop observers
        try:
            self.packet_observer.stop_observer(topo_link.device_a, topo_link.interface_a)
            if topo_link.interface_b:
                self.packet_observer.stop_observer(topo_link.device_b, topo_link.interface_b)
        except Exception as e:
            logger.warning(f"Failed to stop observer for link {link_id}: {e}")
        
        # Remove interfaces from devices
        dev_a = self.devices[topo_link.device_a]
        if topo_link.interface_a in dev_a.interfaces:
            dev_a.interfaces.remove(topo_link.interface_a)
        if topo_link.interface_a in dev_a.ip_addresses:
            del dev_a.ip_addresses[topo_link.interface_a]
            
        dev_b = self.devices[topo_link.device_b]
        if topo_link.interface_b in dev_b.interfaces:
            dev_b.interfaces.remove(topo_link.interface_b)
        if topo_link.interface_b in dev_b.ip_addresses:
            del dev_b.ip_addresses[topo_link.interface_b]
        
        # Delete via LinkManager
        self.link_manager.delete_link(link_id)
        
        del self.links[link_id]
        logger.info(f"Removed topology link: {link_id}")
        self._auto_configure_routing()
    
    def set_default_gateway(self, device_name: str, gateway_ip: str):
        """Set default gateway for a device"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        device = self.devices[device_name]
        device.default_gateway = gateway_ip
        
        # Add default route
        self.namespace_manager.add_route(
            namespace=device_name,
            destination="default",
            gateway=gateway_ip
        )
        
        device.default_gateway = gateway_ip
        logger.info(f"Set default gateway for {device_name}: {gateway_ip}")
    
    def remove_default_gateway(self, device_name: str):
        """Remove default gateway for a device"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        device = self.devices[device_name]
        device.default_gateway = None
        
        self.namespace_manager.remove_route(device_name, "default")
        logger.info(f"Removed default gateway for {device_name}")
    
    def execute_command(self, device_name: str, command: str):
        """Execute a command on a device"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        device = self.devices[device_name]
        
        if not device.pty_session_id:
            raise RuntimeError(f"Device '{device_name}' has no PTY session")
        
        self.pty_manager.execute_command(device.pty_session_id, command)
        logger.info(f"Executed command on {device_name}: {command}")
    
    def get_device_info(self, device_name: str) -> Dict:
        """Get device information"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        device = self.devices[device_name]
        
        # Get routing table or Bridge FDB
        routing_table = []
        if device.device_type == DeviceType.SWITCH and device.name in self.switches:
            fdb = self.link_manager.get_bridge_fdb(self.switches[device.name])
            # Format FDB as routing table for UI
            for entry in fdb:
                routing_table.append({
                    'destination': entry['mac'],
                    'gateway': entry['type'].upper(),
                    'interface': entry['interface']
                })
        else:
            routing_table = self.namespace_manager.get_routing_table(device_name)

        return {
            'name': device.name,
            'type': device.device_type.value,
            'interfaces': device.interfaces,
            'ip_addresses': {k: v.split('/')[0] for k, v in device.ip_addresses.items()},
            'default_gateway': device.default_gateway,
            'routing_table': routing_table,
            'arp_cache': self.namespace_manager.get_arp_cache(device_name),
            'active_sockets': self.namespace_manager.get_active_sockets(device_name),
            'active_failures': self.active_failures.get(device_name, [])
        }
    
    def get_topology_state(self) -> Dict:
        """Get complete topology state"""
        return {
            'devices': [
                {
                    'name': dev.name,
                    'type': dev.device_type.value,
                    'interfaces': dev.interfaces,
                    'ip_addresses': dev.ip_addresses,
                    'default_gateway': dev.default_gateway,
                    'x': dev.x,
                    'y': dev.y
                }
                for dev in self.devices.values()
            ],
            'links': [
                {
                    'id': link.link_id,
                    'device_a': link.device_a,
                    'interface_a': link.interface_a,
                    'device_b': link.device_b,
                    'interface_b': link.interface_b,
                    'latency_ms': link.latency_ms,
                    'bandwidth_mbps': link.bandwidth_mbps,
                    'packet_loss_percent': link.packet_loss_percent
                }
                for link in self.links.values()
            ]
        }
    
    # ========================================================================
    # Failure Injection Methods
    # ========================================================================
    
    def block_icmp(self, device_name: str):
        """Block ICMP packets on a device using iptables"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        # Toggle if already blocked
        if device_name in self.active_failures and "block_icmp" in self.active_failures[device_name]:
            self.unblock_icmp(device_name)
            return

        self.namespace_manager.block_icmp(device_name)
        if device_name not in self.active_failures:
            self.active_failures[device_name] = []
        self.active_failures[device_name].append("block_icmp")
        logger.info(f"Blocked ICMP on {device_name}")
    
    def unblock_icmp(self, device_name: str):
        """Unblock ICMP packets on a device"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        self.namespace_manager.unblock_icmp(device_name)
        if device_name in self.active_failures and "block_icmp" in self.active_failures[device_name]:
            self.active_failures[device_name].remove("block_icmp")
        logger.info(f"Unblocked ICMP on {device_name}")
    
    def enable_silent_router(self, device_name: str):
        """Enable silent router mode (drop all forwarding)"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        device = self.devices[device_name]
        if device.device_type != DeviceType.ROUTER:
            raise ValueError(f"Device '{device_name}' is not a router")
        
        # Toggle if already silent
        if device_name in self.active_failures and "silent_router" in self.active_failures[device_name]:
            self.disable_silent_router(device_name)
            return

        self.namespace_manager.enable_silent_router(device_name)
        if device_name not in self.active_failures:
            self.active_failures[device_name] = []
        self.active_failures[device_name].append("silent_router")
        logger.info(f"Enabled silent router mode on {device_name}")
    
    def disable_silent_router(self, device_name: str):
        """Disable silent router mode"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        self.namespace_manager.disable_silent_router(device_name)
        if device_name in self.active_failures and "silent_router" in self.active_failures[device_name]:
            self.active_failures[device_name].remove("silent_router")
        logger.info(f"Disabled silent router mode on {device_name}")
    
    def set_interface_down(self, device_name: str, interface: str):
        """Bring an interface down"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        device = self.devices[device_name]
        if interface not in device.interfaces:
            raise ValueError(f"Interface '{interface}' not found on {device_name}")
        
        self.namespace_manager.set_interface_down(device_name, interface)
        logger.info(f"Set interface {interface} down on {device_name}")
    
    def set_interface_up(self, device_name: str, interface: str):
        """Bring an interface up"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        self.namespace_manager.set_interface_up(device_name, interface)
        logger.info(f"Set interface {interface} up on {device_name}")
    
    def enable_packet_loss(self, device_name: str, interface: str, percentage: float):
        """Enable packet loss on an interface"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        device = self.devices[device_name]
        if interface not in device.interfaces:
            raise ValueError(f"Interface '{interface}' not found on {device_name}")
        
        self.namespace_manager.enable_packet_loss(device_name, interface, percentage)
        logger.info(f"Enabled {percentage}% packet loss on {device_name}:{interface}")
    
    def get_active_failures(self) -> List[Dict]:
        """Get list of active failures across all devices"""
        failures_list = []
        for device, types in self.active_failures.items():
            for f_type in types:
                failures_list.append({
                    "device": device,
                    "failure_type": f_type
                })
        return failures_list
    
    def auto_configure_routing(self):
        """
        Automatically configure static routing tables on all routers
        to ensure full reachability between all subnets.
        """
        logger.info("Auto-configuring routing tables...")
        # 1. Collect all subnets and the routers connected to them
        subnet_to_routers = {} # Dict[subnet_cidr, List[router_name]]
        router_to_subnets = {} # Dict[router_name, List[subnet_cidr]]
        all_subnets = set()

        # Helper function - defined in shared scope
        def get_router_ip_on_subnet(router_name, subnet_cidr):
            if router_name not in self.devices: return None
            for ip in self.devices[router_name].ip_addresses.values():
                try:
                    if str(ipaddress.IPv4Interface(ip).network) == subnet_cidr:
                        return ip.split('/')[0]
                except:
                    continue
            return None

        # Populate data structures
        for dev_name, device in self.devices.items():
            for iface, ip in device.ip_addresses.items():
                try:
                    if '/' not in ip:
                        continue # Skip interfaces without CIDR
                        
                    interface = ipaddress.IPv4Interface(ip)
                    cidr = str(interface.network)
                    all_subnets.add(cidr)
                    
                    if device.device_type == DeviceType.ROUTER:
                        if cidr not in subnet_to_routers:
                            subnet_to_routers[cidr] = []
                        if dev_name not in subnet_to_routers[cidr]:
                            subnet_to_routers[cidr].append(dev_name)
                            
                        if dev_name not in router_to_subnets:
                            router_to_subnets[dev_name] = []
                        if cidr not in router_to_subnets[dev_name]:
                            router_to_subnets[dev_name].append(cidr)
                except Exception as e:
                    logger.warning(f"Failed to parse IP {ip} on {dev_name}: {e}")
                    continue

        # Block 1: Configure Router-to-Router static routes
        try:
            # 2. For each router, find paths to all other subnets
            routers = [name for name, dev in self.devices.items() if dev.device_type == DeviceType.ROUTER]
            
            # BFS WITH FIRST HOP TRACKING
            for start_router in routers:
                visited = {start_router}
                # (current_router, first_hop_ip)
                queue = []
                
                # Start queue with direct neighbors
                for shared_subnet in router_to_subnets.get(start_router, []):
                    for neighbor in subnet_to_routers.get(shared_subnet, []):
                        if neighbor != start_router:
                            next_hop = get_router_ip_on_subnet(neighbor, shared_subnet)
                            if next_hop:
                                queue.append((neighbor, next_hop))
                                visited.add(neighbor)
                
                direct_subnets = set(router_to_subnets.get(start_router, []))
                found_remote_subnets = set()

                while queue:
                    curr_router, first_hop_ip = queue.pop(0)
                    
                    # All subnets reachable via this neighbor
                    for target_subnet in router_to_subnets.get(curr_router, []):
                        if target_subnet not in direct_subnets and target_subnet not in found_remote_subnets:
                            logger.info(f"Adding auto-route: {start_router} -> {target_subnet} via {first_hop_ip}")
                            try:
                                self.namespace_manager.add_route(start_router, target_subnet, first_hop_ip)
                                found_remote_subnets.add(target_subnet)
                            except Exception as e:
                                logger.error(f"Failed to add route: {e}")

                    # Expand BFS: Find neighbors of curr_router to traverse deeper
                    for next_subnet in router_to_subnets.get(curr_router, []):
                        for next_neighbor in subnet_to_routers.get(next_subnet, []):
                            if next_neighbor not in visited:
                                visited.add(next_neighbor)
                                # IMPORTANT: The first_hop_ip stays the same for the whole branch
                                queue.append((next_neighbor, first_hop_ip))

            logger.info("Router-to-router auto-configuration complete")

        except Exception as e:
            logger.error(f"Router auto-configuration failed: {e}")
            # Do NOT re-raise yet, try to configure hosts first
            
        # Block 2: Configure Host Default Gateways
        try:
            # 3. Configure default gateways for hosts if missing
            # FIX: Also include DNS_SERVER and SERVER which need gateways too
            target_types = [DeviceType.HOST, DeviceType.DNS_SERVER, DeviceType.SERVER]
            hosts = [name for name, dev in self.devices.items() if dev.device_type in target_types]
            for host in hosts:
                device = self.devices[host]
                
                # Assume we want to re-configure/enforce gateway for all hosts on auto-route
                # checking if not device.default_gateway: -> REMOVED to force update
                
                # Look for a router on the same subnet
                gateway_found = False
                for iface, ip in device.ip_addresses.items():
                    try:
                        if '/' not in ip: continue
                        interface = ipaddress.IPv4Interface(ip)
                        cidr = str(interface.network)
                        
                        # Check if we have router info for this subnet
                        if cidr in subnet_to_routers:
                            # Found routers on this subnet
                            routers_on_subnet = subnet_to_routers[cidr]
                            if not routers_on_subnet: continue
                            
                            # Pick the first one (simple logic)
                            router = routers_on_subnet[0]
                            router_ip = get_router_ip_on_subnet(router, cidr)
                            
                            if router_ip:
                                logger.info(f"Auto-configuring gateway for {host}: {router_ip}")
                                self.set_default_gateway(host, router_ip)
                                gateway_found = True
                                break
                    except Exception as e:
                        logger.warning(f"Error checking interface {iface} on {host}: {e}")
                
                if not gateway_found:
                     logger.warning(f"No router found for host {host} on its subnets")

            logger.info("Host gateway auto-configuration complete")
        except Exception as e:
             logger.error(f"Host gateway configuration failed: {e}")
             raise e

    def cleanup(self):
        """Cleanup all resources"""
        logger.info("Cleaning up topology...")
        
        # Stop packet observers
        self.packet_observer.stop_all()
        
        # Close PTY sessions
        self.pty_manager.cleanup_all()
        
        # Delete links
        for link_id in list(self.links.keys()):
            try:
                self.remove_link(link_id)
            except Exception as e:
                logger.error(f"Failed to remove link {link_id}: {e}")
        
        # Delete devices
        for device_name in list(self.devices.keys()):
            try:
                self.remove_device(device_name)
            except Exception as e:
                logger.error(f"Failed to remove device {device_name}: {e}")
        
        # Cleanup managers
        self.link_manager.cleanup_all()
        self.namespace_manager.cleanup_all()
        
        logger.info("Topology cleanup complete")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    topology = TopologyManager()
    
    try:
        # Create devices
        host1 = topology.add_device("host1", "host")
        host2 = topology.add_device("host2", "host")
        router1 = topology.add_device("router1", "router")
        
        # Create links
        link1 = topology.add_link("host1", "router1", latency_ms=5.0)
        link2 = topology.add_link("router1", "host2", latency_ms=10.0)
        
        # Set default gateways
        topology.set_default_gateway("host1", list(topology.devices["router1"].ip_addresses.values())[0])
        topology.set_default_gateway("host2", list(topology.devices["router1"].ip_addresses.values())[1])
        
        # Get topology state
        state = topology.get_topology_state()
        print(f"Topology: {len(state['devices'])} devices, {len(state['links'])} links")
        
    finally:
        # Cleanup
        topology.cleanup()
