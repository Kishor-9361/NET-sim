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
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import ipaddress

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


@dataclass
class TopologyLink:
    """High-level link representation"""
    link_id: str
    device_a: str
    interface_a: str
    device_b: str
    interface_b: str
    latency_ms: float
    bandwidth_mbps: Optional[float]
    packet_loss_percent: float


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
    
    def add_device(self, name: str, device_type: str) -> Device:
        """
        Add a device to the topology.
        
        Args:
            name: Device name
            device_type: "host", "router", "switch", or "dns_server"
        
        Returns:
            Device object
        """
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
                namespace=namespace
            )
        else:
            # Create namespace
            namespace = self.namespace_manager.create_namespace(name, dtype)
            
            device = Device(
                name=name,
                device_type=dtype,
                namespace=namespace
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
        
        self.devices[name] = device
        logger.info(f"Added device: {name} (type: {device_type})")
        return device
    
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
        
        # Remove links connected to this device
        links_to_remove = [
            link_id for link_id, link in self.links.items()
            if link.device_a == name or link.device_b == name
        ]
        for link_id in links_to_remove:
            self.remove_link(link_id)
        
        # Delete namespace
        try:
            self.namespace_manager.delete_namespace(name)
        except Exception as e:
            logger.error(f"Failed to delete namespace: {e}")
        
        # Delete bridge if switch
        if device.device_type == DeviceType.SWITCH and name in self.switches:
            try:
                self.link_manager.delete_bridge(self.switches[name])
                del self.switches[name]
            except Exception as e:
                logger.error(f"Failed to delete bridge: {e}")
        
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
        
        # Create network for this link
        network_id = self.ip_allocator.create_network()
        cidr = self.ip_allocator.get_network_cidr(network_id)
        
        # Handle switch connections
        if dev_a.device_type == DeviceType.SWITCH:
            # Connect device_b to switch
            bridge_name = self.switches[device_a]
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
            dev_b.ip_addresses[iface_b] = ip_b
            
            # Start packet observer
            self.packet_observer.start_observer(device_b, iface_b)
            
        elif dev_b.device_type == DeviceType.SWITCH:
            # Connect device_a to switch
            bridge_name = self.switches[device_b]
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
            dev_a.ip_addresses[iface_a] = ip_a
            
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
            dev_a.ip_addresses[iface_a] = ip_a
            dev_b.interfaces.append(iface_b)
            dev_b.ip_addresses[iface_b] = ip_b
            
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
            bandwidth_mbps=bandwidth_mbps,
            packet_loss_percent=packet_loss_percent
        )
        
        self.links[link.id] = topo_link
        logger.info(f"Added link: {device_a}:{iface_a} <-> {device_b}:{iface_b}")
        return topo_link
    
    def remove_link(self, link_id: str):
        """Remove a link"""
        if link_id not in self.links:
            logger.warning(f"Link '{link_id}' does not exist")
            return
        
        link = self.links[link_id]
        
        # Stop packet observers
        try:
            self.packet_observer.stop_observer(f"{link.device_a}:{link.interface_a}")
        except:
            pass
        try:
            self.packet_observer.stop_observer(f"{link.device_b}:{link.interface_b}")
        except:
            pass
        
        # Delete link
        try:
            self.link_manager.delete_link(link_id)
        except Exception as e:
            logger.error(f"Failed to delete link: {e}")
        
        del self.links[link_id]
        logger.info(f"Removed link: {link_id}")
    
    def set_default_gateway(self, device_name: str, gateway_ip: str):
        """Set default gateway for a device"""
        if device_name not in self.devices:
            raise ValueError(f"Device '{device_name}' does not exist")
        
        device = self.devices[device_name]
        
        # Add default route
        self.namespace_manager.add_route(
            namespace=device_name,
            destination="default",
            gateway=gateway_ip
        )
        
        device.default_gateway = gateway_ip
        logger.info(f"Set default gateway for {device_name}: {gateway_ip}")
    
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
        
        return {
            'name': device.name,
            'type': device.device_type.value,
            'interfaces': device.interfaces,
            'ip_addresses': device.ip_addresses,
            'default_gateway': device.default_gateway,
            'routing_table': self.namespace_manager.get_routing_table(device_name),
            'arp_cache': self.namespace_manager.get_arp_cache(device_name)
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
                    'default_gateway': dev.default_gateway
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
