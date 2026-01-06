"""
Network Namespace Manager - Kernel-Level Network Emulator

This module manages Linux network namespaces for device emulation.
Each simulated device (host, router, switch) is represented as a network namespace.

CRITICAL: All network behavior originates from the Linux kernel, not application logic.
"""

import subprocess
import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """Types of network devices"""
    HOST = "host"
    ROUTER = "router"
    SWITCH = "switch"
    DNS_SERVER = "dns_server"


@dataclass
class NetworkInterface:
    """Represents a network interface in a namespace"""
    name: str           # Interface name (e.g., "eth0")
    namespace: str      # Namespace it belongs to
    ip_address: Optional[str] = None
    netmask: Optional[str] = None
    mac_address: Optional[str] = None
    state: str = "down"  # up/down
    mtu: int = 1500


@dataclass
class NetworkNamespace:
    """Represents a Linux network namespace (simulated device)"""
    name: str
    device_type: DeviceType
    interfaces: List[NetworkInterface]
    routing_table: List[Dict]
    arp_cache: List[Dict]
    ip_forward: bool = False


class NamespaceManager:
    """
    Manages Linux network namespaces for device emulation.
    
    Uses kernel-level primitives:
    - ip netns (network namespaces)
    - ip link (veth pairs)
    - ip addr (IP addressing)
    - ip route (routing tables)
    - sysctl (kernel parameters)
    """
    
    def __init__(self):
        self.namespaces: Dict[str, NetworkNamespace] = {}
        self._verify_kernel_support()
    
    def _verify_kernel_support(self):
        """Verify kernel supports required features"""
        try:
            # Check if ip command is available
            subprocess.run(['which', 'ip'], check=True, capture_output=True)
            
            # Check if we can list namespaces (requires CAP_NET_ADMIN)
            subprocess.run(['sudo', 'ip', 'netns', 'list'], check=True, capture_output=True)
            
            logger.info("Kernel network namespace support verified")
        except subprocess.CalledProcessError as e:
            logger.error(f"Kernel support verification failed: {e}")
            raise RuntimeError("Kernel does not support required network features")
    
    def create_namespace(self, name: str, device_type: DeviceType) -> NetworkNamespace:
        """
        Create a new network namespace (simulated device).
        
        Args:
            name: Unique name for the namespace
            device_type: Type of device to emulate
        
        Returns:
            NetworkNamespace object
        
        Raises:
            RuntimeError: If namespace creation fails
        """
        if name in self.namespaces:
            raise ValueError(f"Namespace '{name}' already exists")
        
        try:
            # Create namespace using kernel
            logger.info(f"Creating namespace: {name} (type: {device_type.value})")
            subprocess.run(
                ['sudo', 'ip', 'netns', 'add', name],
                check=True,
                capture_output=True
            )
            
            # Bring up loopback interface in namespace
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', name, 'ip', 'link', 'set', 'lo', 'up'],
                check=True,
                capture_output=True
            )
            
            # Enable IP forwarding for routers
            ip_forward = device_type == DeviceType.ROUTER
            if ip_forward:
                subprocess.run(
                    ['sudo', 'ip', 'netns', 'exec', name, 
                     'sysctl', '-w', 'net.ipv4.ip_forward=1'],
                    check=True,
                    capture_output=True
                )
                logger.info(f"Enabled IP forwarding for router: {name}")
            
            # Create namespace object
            ns = NetworkNamespace(
                name=name,
                device_type=device_type,
                interfaces=[],
                routing_table=[],
                arp_cache=[],
                ip_forward=ip_forward
            )
            
            self.namespaces[name] = ns
            logger.info(f"Namespace created successfully: {name}")
            return ns
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create namespace '{name}': {e.stderr.decode()}")
            raise RuntimeError(f"Namespace creation failed: {e.stderr.decode()}")
    
    def delete_namespace(self, name: str):
        """
        Delete a network namespace and cleanup all resources.
        
        Args:
            name: Name of namespace to delete
        """
        if name not in self.namespaces:
            logger.warning(f"Namespace '{name}' does not exist")
            return
        
        try:
            logger.info(f"Deleting namespace: {name}")
            
            # Delete namespace (kernel automatically cleans up interfaces)
            subprocess.run(
                ['sudo', 'ip', 'netns', 'delete', name],
                check=True,
                capture_output=True
            )
            
            del self.namespaces[name]
            logger.info(f"Namespace deleted successfully: {name}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to delete namespace '{name}': {e.stderr.decode()}")
            raise RuntimeError(f"Namespace deletion failed: {e.stderr.decode()}")
    
    def add_interface(self, namespace: str, interface_name: str, 
                     ip_address: str, netmask: str = "24") -> NetworkInterface:
        """
        Add a network interface to a namespace.
        
        Note: The actual veth pair should be created by LinkManager.
        This method just configures an existing interface.
        
        Args:
            namespace: Namespace name
            interface_name: Interface name (e.g., "eth0")
            ip_address: IP address to assign
            netmask: Network mask (CIDR notation)
        
        Returns:
            NetworkInterface object
        """
        if namespace not in self.namespaces:
            raise ValueError(f"Namespace '{namespace}' does not exist")
        
        try:
            # Assign IP address
            logger.info(f"Configuring interface {interface_name} in {namespace}: {ip_address}/{netmask}")
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace,
                 'ip', 'addr', 'add', f'{ip_address}/{netmask}', 'dev', interface_name],
                check=True,
                capture_output=True
            )
            
            # Bring interface up
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace,
                 'ip', 'link', 'set', interface_name, 'up'],
                check=True,
                capture_output=True
            )
            
            # Get MAC address
            result = subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace,
                 'ip', 'link', 'show', interface_name],
                check=True,
                capture_output=True
            )
            mac_match = re.search(r'link/ether ([0-9a-f:]+)', result.stdout.decode())
            mac_address = mac_match.group(1) if mac_match else None
            
            # Create interface object
            interface = NetworkInterface(
                name=interface_name,
                namespace=namespace,
                ip_address=ip_address,
                netmask=netmask,
                mac_address=mac_address,
                state="up"
            )
            
            self.namespaces[namespace].interfaces.append(interface)
            logger.info(f"Interface configured: {interface_name} ({ip_address}/{netmask})")
            return interface
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add interface: {e.stderr.decode()}")
            raise RuntimeError(f"Interface configuration failed: {e.stderr.decode()}")
    
    def add_route(self, namespace: str, destination: str, gateway: str, 
                  interface: Optional[str] = None):
        """
        Add a route to the namespace's routing table.
        
        Args:
            namespace: Namespace name
            destination: Destination network (e.g., "10.0.2.0/24" or "default")
            gateway: Gateway IP address
            interface: Optional interface name
        """
        if namespace not in self.namespaces:
            raise ValueError(f"Namespace '{namespace}' does not exist")
        
        try:
            cmd = ['sudo', 'ip', 'netns', 'exec', namespace,
                   'ip', 'route', 'add', destination, 'via', gateway]
            
            if interface:
                cmd.extend(['dev', interface])
            
            logger.info(f"Adding route in {namespace}: {destination} via {gateway}")
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Update routing table cache
            self._update_routing_table(namespace)
            
        except subprocess.CalledProcessError as e:
            # Ignore "File exists" error (route already exists)
            if b"File exists" not in e.stderr:
                logger.error(f"Failed to add route: {e.stderr.decode()}")
                raise RuntimeError(f"Route addition failed: {e.stderr.decode()}")
    
    def get_routing_table(self, namespace: str) -> List[Dict]:
        """
        Get the routing table from a namespace.
        
        Args:
            namespace: Namespace name
        
        Returns:
            List of route dictionaries
        """
        if namespace not in self.namespaces:
            raise ValueError(f"Namespace '{namespace}' does not exist")
        
        self._update_routing_table(namespace)
        return self.namespaces[namespace].routing_table
    
    def _update_routing_table(self, namespace: str):
        """Update cached routing table from kernel"""
        try:
            result = subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace, 'ip', 'route', 'show'],
                check=True,
                capture_output=True
            )
            
            routes = []
            for line in result.stdout.decode().strip().split('\n'):
                if line:
                    routes.append({'raw': line})
            
            self.namespaces[namespace].routing_table = routes
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get routing table: {e.stderr.decode()}")
    
    def get_arp_cache(self, namespace: str) -> List[Dict]:
        """
        Get the ARP cache from a namespace.
        
        Args:
            namespace: Namespace name
        
        Returns:
            List of ARP entries
        """
        if namespace not in self.namespaces:
            raise ValueError(f"Namespace '{namespace}' does not exist")
        
        try:
            result = subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace, 'ip', 'neigh', 'show'],
                check=True,
                capture_output=True
            )
            
            arp_entries = []
            for line in result.stdout.decode().strip().split('\n'):
                if line:
                    arp_entries.append({'raw': line})
            
            self.namespaces[namespace].arp_cache = arp_entries
            return arp_entries
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get ARP cache: {e.stderr.decode()}")
            return []
    
    def set_interface_state(self, namespace: str, interface: str, state: str):
        """
        Set interface state (up/down).
        
        Args:
            namespace: Namespace name
            interface: Interface name
            state: "up" or "down"
        """
        if namespace not in self.namespaces:
            raise ValueError(f"Namespace '{namespace}' does not exist")
        
        if state not in ["up", "down"]:
            raise ValueError(f"Invalid state: {state}")
        
        try:
            logger.info(f"Setting interface {interface} in {namespace} to {state}")
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace,
                 'ip', 'link', 'set', interface, state],
                check=True,
                capture_output=True
            )
            
            # Update interface state in cache
            for iface in self.namespaces[namespace].interfaces:
                if iface.name == interface:
                    iface.state = state
                    break
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set interface state: {e.stderr.decode()}")
            raise RuntimeError(f"Interface state change failed: {e.stderr.decode()}")
    
    def list_namespaces(self) -> List[str]:
        """
        List all network namespaces.
        
        Returns:
            List of namespace names
        """
        try:
            result = subprocess.run(
                ['sudo', 'ip', 'netns', 'list'],
                check=True,
                capture_output=True
            )
            
            namespaces = []
            for line in result.stdout.decode().strip().split('\n'):
                if line:
                    # Extract namespace name (first word)
                    ns_name = line.split()[0]
                    namespaces.append(ns_name)
            
            return namespaces
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list namespaces: {e.stderr.decode()}")
            return []
    
    def cleanup_all(self):
        """Delete all managed namespaces"""
        logger.info("Cleaning up all namespaces...")
        for name in list(self.namespaces.keys()):
            try:
                self.delete_namespace(name)
            except Exception as e:
                logger.error(f"Failed to delete namespace {name}: {e}")
        logger.info("Cleanup complete")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    manager = NamespaceManager()
    
    # Create a host
    host1 = manager.create_namespace("host1", DeviceType.HOST)
    print(f"Created namespace: {host1.name}")
    
    # Create a router
    router1 = manager.create_namespace("router1", DeviceType.ROUTER)
    print(f"Created router: {router1.name} (IP forwarding: {router1.ip_forward})")
    
    # List all namespaces
    print(f"All namespaces: {manager.list_namespaces()}")
    
    # Cleanup
    manager.cleanup_all()
