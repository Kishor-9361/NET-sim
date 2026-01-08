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
    SERVER = "server"


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
    
    def rename_namespace(self, old_name: str, new_name: str):
        """Rename a network namespace"""
        if old_name not in self.namespaces:
            raise ValueError(f"Namespace '{old_name}' does not exist")
        
        try:
            logger.info(f"Renaming namespace {old_name} to {new_name}")
            
            import os
            # Determine correct path
            base_path = "/var/run/netns"
            if not os.path.exists(base_path) and os.path.exists("/run/netns"):
                base_path = "/run/netns"
                
            old_path = f"{base_path}/{old_name}"
            new_path = f"{base_path}/{new_name}"
            
            if not os.path.exists(old_path):
                raise RuntimeError(f"Namespace mount point {old_path} not found")
            
            # Strategy 1: Attempt atomic move (rename)
            # This often fails for bind mounts with "Device or resource busy"
            try:
                subprocess.run(['sudo', 'mv', old_path, new_path], check=True, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError:
                logger.info("mv failed, attempting bind mount strategy")
                
                # Strategy 2: Bind mount new -> Unmount old
                # 1. Create empty file for new mount point
                subprocess.run(['sudo', 'touch', new_path], check=True)
                
                # 2. Bind mount old to new (preserves the namespace)
                # The critical part: we bind the *file* old_path to new_path. 
                # Since old_path is a bind mount to the netns, new_path becomes one too.
                subprocess.run(['sudo', 'mount', '--bind', old_path, new_path], check=True)
                
                # 3. Unmount old - using lazy unmount to avoid busy errors
                subprocess.run(['sudo', 'umount', '-l', old_path], check=True)
                
                # 4. Remove old file
                subprocess.run(['sudo', 'rm', old_path], check=True)
                 
            ns = self.namespaces.pop(old_name)
            ns.name = new_name
            self.namespaces[new_name] = ns
            
        except Exception as e:
            logger.error(f"Failed to rename namespace: {e}")
            raise RuntimeError(f"Namespace rename failed: {e}")
    
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
            err_msg = e.stderr.decode()
            if "No such file or directory" in err_msg:
                logger.warning(f"Namespace '{name}' file missing during deletion (ignoring): {err_msg.strip()}")
                if name in self.namespaces:
                    del self.namespaces[name]
                return

            logger.error(f"Failed to delete namespace '{name}': {err_msg}")
            raise RuntimeError(f"Namespace deletion failed: {err_msg}")
    
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
                   'ip', 'route', 'replace', destination, 'via', gateway]
            
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
    
    def remove_route(self, namespace: str, destination: str):
        """Remove a route from a namespace"""
        if namespace not in self.namespaces:
            raise ValueError(f"Namespace '{namespace}' does not exist")
        
        try:
            logger.info(f"Removing route in {namespace}: {destination}")
            subprocess.run([
                'sudo', 'ip', 'netns', 'exec', namespace,
                'ip', 'route', 'delete', destination
            ], capture_output=True)
            
            # Update routing table cache
            self._update_routing_table(namespace)
            
        except Exception as e:
            logger.error(f"Failed to remove route: {e}")
            # We don't raise here because the route might already be gone
    
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
                if not line: continue
                parts = line.split()
                route = {'raw': line}
                if 'default' in line:
                    route['destination'] = '0.0.0.0/0'
                    if 'via' in parts:
                        route['gateway'] = parts[parts.index('via') + 1]
                else:
                    route['destination'] = parts[0]
                
                if 'dev' in parts:
                    route['interface'] = parts[parts.index('dev') + 1]
                
                routes.append(route)
            
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
                if not line: continue
                parts = line.split()
                # 10.0.1.2 dev eth0 lladdr 52:54:00:12:34:56 REACHABLE
                entry = {'raw': line}
                if len(parts) >= 1:
                    entry['ip'] = parts[0]
                if 'lladdr' in parts:
                    entry['mac'] = parts[parts.index('lladdr') + 1]
                if 'REACHABLE' in parts or 'STALE' in parts or 'DELAY' in parts:
                    entry['state'] = parts[-1]
                
                arp_entries.append(entry)
            
            self.namespaces[namespace].arp_cache = arp_entries
            return arp_entries
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get ARP cache: {e.stderr.decode()}")
            return []
    
    def get_active_sockets(self, namespace: str) -> List[Dict]:
        """Get active TCP/UDP sockets from namespace using ss"""
        if namespace not in self.namespaces:
            return []
            
        try:
            result = subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace, 'ss', '-tun'],
                check=True,
                capture_output=True
            )
            
            sockets = []
            output = result.stdout.decode().strip()
            if not output:
                return []
                
            lines = output.split('\n')
            # Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 5:
                    sockets.append({
                        'protocol': parts[0],
                        'state': parts[1],
                        'local': parts[4],
                        'remote': parts[5] if len(parts) > 5 else '*:*'
                    })
            return sockets
        except Exception as e:
            logger.error(f"Failed to get sockets: {e}")
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

    def set_interface_up(self, namespace: str, interface: str):
        """Alias for set_interface_state(..., 'up')"""
        self.set_interface_state(namespace, interface, "up")

    def set_interface_down(self, namespace: str, interface: str):
        """Alias for set_interface_state(..., 'down')"""
        self.set_interface_state(namespace, interface, "down")

    def block_icmp(self, namespace: str):
        """
        Block ICMP Echo Requests (Ping) destined for this device.
        Allows forwarding and outgoing pings.
        """
        try:
            # Block incoming echo requests only (Stealth Mode)
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace,
                 'iptables', '-A', 'INPUT', '-p', 'icmp', '--icmp-type', 'echo-request', '-j', 'DROP'],
                check=True,
                capture_output=True
            )
            logger.info(f"Blocked ICMP Echo Requests (INPUT) in {namespace}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to block ICMP: {e.stderr.decode()}")
            raise RuntimeError(f"Failed to apply ICMP block: {e.stderr.decode()}")

    def unblock_icmp(self, namespace: str):
        """Unblock ICMP packets"""
        try:
            # 1. Cleanup aggressive rules from previous version (All chains, all types)
            for chain in ['INPUT', 'OUTPUT', 'FORWARD']:
                subprocess.run(
                    ['sudo', 'ip', 'netns', 'exec', namespace,
                     'iptables', '-D', chain, '-p', 'icmp', '-j', 'DROP'],
                    check=False,
                    capture_output=True
                )
            
            # 2. Cleanup specific rule (Standard)
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace,
                 'iptables', '-D', 'INPUT', '-p', 'icmp', '--icmp-type', 'echo-request', '-j', 'DROP'],
                check=False,
                capture_output=True
            )
            
            logger.info(f"Unblocked ICMP in {namespace}")
        except Exception as e:
            logger.error(f"Failed to unblock ICMP: {e}")

    def enable_silent_router(self, namespace: str):
        """Enable silent router mode (disable IP forwarding)"""
        try:
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace,
                 'sysctl', '-w', 'net.ipv4.ip_forward=0'],
                check=True,
                capture_output=True
            )
            logger.info(f"Enabled silent router in {namespace}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to enable silent router: {e.stderr.decode()}")

    def disable_silent_router(self, namespace: str):
        """Disable silent router mode (enable IP forwarding)"""
        try:
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace,
                 'sysctl', '-w', 'net.ipv4.ip_forward=1'],
                check=True,
                capture_output=True
            )
            logger.info(f"Disabled silent router in {namespace}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to disable silent router: {e.stderr.decode()}")

    def enable_packet_loss(self, namespace: str, interface: str, percentage: float):
        """Enable packet loss using tc netem"""
        try:
            # Try to add rule, if exists replace it
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace,
                 'tc', 'qdisc', 'add', 'dev', interface, 'root', 'netem', 'loss', f'{percentage}%'],
                check=False,
                capture_output=True
            )
            # If add failed, try replace
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace,
                 'tc', 'qdisc', 'replace', 'dev', interface, 'root', 'netem', 'loss', f'{percentage}%'],
                check=True,
                capture_output=True
            )
            logger.info(f"Enabled {percentage}% packet loss on {namespace}:{interface}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to enable packet loss: {e.stderr.decode()}")
    
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
