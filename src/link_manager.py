"""
Link Manager - Kernel-Level Network Emulator

This module manages network links using veth pairs and Linux bridges.
All link behavior is handled by the Linux kernel.

CRITICAL: Links are real kernel-level virtual ethernet devices, not simulated.
"""

import subprocess
import logging
import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LinkType(Enum):
    """Types of network links"""
    POINT_TO_POINT = "p2p"      # Direct veth pair between two namespaces
    SWITCHED = "switched"         # Connection via bridge (switch)


@dataclass
class Link:
    """Represents a network link"""
    id: str
    link_type: LinkType
    endpoint_a: str  # namespace:interface
    endpoint_b: str  # namespace:interface or bridge name
    latency_ms: float = 0.0
    bandwidth_mbps: Optional[float] = None
    packet_loss_percent: float = 0.0
    jitter_ms: float = 0.0
    state: str = "up"


class LinkManager:
    """
    Manages network links using kernel primitives:
    - veth pairs (virtual ethernet)
    - Linux bridges
    - tc netem (traffic control for latency/loss/jitter)
    - tc tbf (token bucket filter for bandwidth limiting)
    """
    
    def __init__(self):
        self.links: Dict[str, Link] = {}
        self.bridges: Dict[str, List[str]] = {}  # bridge_name -> [interfaces]
        self._verify_kernel_support()
    
    def _verify_kernel_support(self):
        """Verify kernel supports required features"""
        try:
            # Check if tc is available
            subprocess.run(['which', 'tc'], check=True, capture_output=True)
            
            # Check if bridge command is available (part of iproute2)
            subprocess.run(['which', 'bridge'], check=True, capture_output=True)
            
            logger.info("Kernel link management support verified")
        except subprocess.CalledProcessError as e:
            logger.error(f"Kernel support verification failed: {e}")
            raise RuntimeError("Kernel does not support required link features")
    
    def create_veth_pair(self, name_a: str, name_b: str) -> Tuple[str, str]:
        """
        Create a veth (virtual ethernet) pair.
        
        Args:
            name_a: Name for first end of pair
            name_b: Name for second end of pair
        
        Returns:
            Tuple of (name_a, name_b)
        """
        try:
            logger.info(f"Creating veth pair: {name_a} <-> {name_b}")
            subprocess.run(
                ['sudo', 'ip', 'link', 'add', name_a, 'type', 'veth', 'peer', 'name', name_b],
                check=True,
                capture_output=True
            )
            return (name_a, name_b)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create veth pair: {e.stderr.decode()}")
            raise RuntimeError(f"veth pair creation failed: {e.stderr.decode()}")
    
    def attach_to_namespace(self, interface: str, namespace: str):
        """
        Move an interface into a network namespace.
        
        Args:
            interface: Interface name
            namespace: Namespace name
        """
        try:
            logger.info(f"Attaching {interface} to namespace {namespace}")
            subprocess.run(
                ['sudo', 'ip', 'link', 'set', interface, 'netns', namespace],
                check=True,
                capture_output=True
            )
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to attach interface to namespace: {e.stderr.decode()}")
            raise RuntimeError(f"Interface attachment failed: {e.stderr.decode()}")
    
    def create_bridge(self, bridge_name: str) -> str:
        """
        Create a Linux bridge (acts as a switch).
        
        Args:
            bridge_name: Name for the bridge
        
        Returns:
            Bridge name
        """
        if bridge_name in self.bridges:
            logger.warning(f"Bridge '{bridge_name}' already exists")
            return bridge_name
        
        try:
            # Check if bridge already exists in the system (but not in our dictionary)
            res = subprocess.run(['ip', 'link', 'show', bridge_name], capture_output=True)
            if res.returncode == 0:
                logger.info(f"Bridge '{bridge_name}' already exists in system, using it")
                self.bridges[bridge_name] = []
                return bridge_name

            logger.info(f"Creating bridge: {bridge_name}")
            
            # Create bridge
            subprocess.run(
                ['sudo', 'ip', 'link', 'add', bridge_name, 'type', 'bridge'],
                check=True,
                capture_output=True
            )
            
            # Bring bridge up
            subprocess.run(
                ['sudo', 'ip', 'link', 'set', bridge_name, 'up'],
                check=True,
                capture_output=True
            )
            
            self.bridges[bridge_name] = []
            logger.info(f"Bridge created: {bridge_name}")
            return bridge_name
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create bridge: {e.stderr.decode()}")
            raise RuntimeError(f"Bridge creation failed: {e.stderr.decode()}")
    
    def attach_to_bridge(self, interface: str, bridge_name: str):
        """
        Attach an interface to a bridge.
        
        Args:
            interface: Interface name
            bridge_name: Bridge name
        """
        if bridge_name not in self.bridges:
            raise ValueError(f"Bridge '{bridge_name}' does not exist")
        
        try:
            logger.info(f"Attaching {interface} to bridge {bridge_name}")
            
            # Attach to bridge
            subprocess.run(
                ['sudo', 'ip', 'link', 'set', interface, 'master', bridge_name],
                check=True,
                capture_output=True
            )
            
            # Bring interface up
            subprocess.run(
                ['sudo', 'ip', 'link', 'set', interface, 'up'],
                check=True,
                capture_output=True
            )
            
            self.bridges[bridge_name].append(interface)
            logger.info(f"Interface attached to bridge: {interface} -> {bridge_name}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to attach to bridge: {e.stderr.decode()}")
            raise RuntimeError(f"Bridge attachment failed: {e.stderr.decode()}")
    
    def create_p2p_link(self, namespace_a: str, interface_a: str,
                        namespace_b: str, interface_b: str,
                        latency_ms: float = 0.0,
                        bandwidth_mbps: Optional[float] = None,
                        packet_loss_percent: float = 0.0) -> Link:
        """
        Create a point-to-point link between two namespaces.
        
        Args:
            namespace_a: First namespace
            interface_a: Interface name in first namespace
            namespace_b: Second namespace
            interface_b: Interface name in second namespace
            latency_ms: Link latency in milliseconds
            bandwidth_mbps: Bandwidth limit in Mbps (None = unlimited)
            packet_loss_percent: Packet loss percentage (0-100)
        
        Returns:
            Link object
        """
        # Generate unique veth pair names
        veth_a = f"veth-{uuid.uuid4().hex[:8]}"
        veth_b = f"veth-{uuid.uuid4().hex[:8]}"
        
        try:
            # Create veth pair
            self.create_veth_pair(veth_a, veth_b)
            
            # Attach to namespaces
            self.attach_to_namespace(veth_a, namespace_a)
            self.attach_to_namespace(veth_b, namespace_b)
            
            # Rename interfaces inside namespaces
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace_a,
                 'ip', 'link', 'set', veth_a, 'name', interface_a],
                check=True,
                capture_output=True
            )
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace_b,
                 'ip', 'link', 'set', veth_b, 'name', interface_b],
                check=True,
                capture_output=True
            )
            
            # Apply traffic control settings
            if latency_ms > 0 or packet_loss_percent > 0:
                self._apply_netem(namespace_a, interface_a, latency_ms, 0.0, packet_loss_percent)
                self._apply_netem(namespace_b, interface_b, latency_ms, 0.0, packet_loss_percent)
            
            if bandwidth_mbps:
                self._apply_bandwidth_limit(namespace_a, interface_a, bandwidth_mbps)
                self._apply_bandwidth_limit(namespace_b, interface_b, bandwidth_mbps)
            
            # Create link object
            link_id = str(uuid.uuid4())
            link = Link(
                id=link_id,
                link_type=LinkType.POINT_TO_POINT,
                endpoint_a=f"{namespace_a}:{interface_a}",
                endpoint_b=f"{namespace_b}:{interface_b}",
                latency_ms=latency_ms,
                bandwidth_mbps=bandwidth_mbps,
                packet_loss_percent=packet_loss_percent,
                state="up"
            )
            
            self.links[link_id] = link
            logger.info(f"P2P link created: {namespace_a}:{interface_a} <-> {namespace_b}:{interface_b}")
            return link
            
        except Exception as e:
            logger.error(f"Failed to create P2P link: {e}")
            # Cleanup on failure
            try:
                subprocess.run(['sudo', 'ip', 'link', 'delete', veth_a], 
                             capture_output=True)
            except:
                pass
            raise RuntimeError(f"P2P link creation failed: {e}")
    
    def create_switched_link(self, namespace: str, interface: str,
                            bridge_name: str,
                            latency_ms: float = 0.0,
                            bandwidth_mbps: Optional[float] = None) -> Link:
        """
        Create a link from a namespace to a bridge (switch).
        
        Args:
            namespace: Namespace name
            interface: Interface name in namespace
            bridge_name: Bridge name
            latency_ms: Link latency
            bandwidth_mbps: Bandwidth limit
        
        Returns:
            Link object
        """
        # Generate unique veth pair names
        veth_ns = f"veth-{uuid.uuid4().hex[:8]}"
        veth_br = f"veth-{uuid.uuid4().hex[:8]}"
        
        try:
            # Create veth pair
            self.create_veth_pair(veth_ns, veth_br)
            
            # Attach one end to namespace
            self.attach_to_namespace(veth_ns, namespace)
            
            # Rename interface in namespace
            subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace,
                 'ip', 'link', 'set', veth_ns, 'name', interface],
                check=True,
                capture_output=True
            )
            
            # Attach other end to bridge
            self.attach_to_bridge(veth_br, bridge_name)
            
            # Apply traffic control
            if latency_ms > 0:
                self._apply_netem(namespace, interface, latency_ms, 0.0, 0.0)
            
            if bandwidth_mbps:
                self._apply_bandwidth_limit(namespace, interface, bandwidth_mbps)
            
            # Create link object
            link_id = str(uuid.uuid4())
            link = Link(
                id=link_id,
                link_type=LinkType.SWITCHED,
                endpoint_a=f"{namespace}:{interface}",
                endpoint_b=bridge_name,
                latency_ms=latency_ms,
                bandwidth_mbps=bandwidth_mbps,
                state="up"
            )
            
            self.links[link_id] = link
            logger.info(f"Switched link created: {namespace}:{interface} -> {bridge_name}")
            return link
            
        except Exception as e:
            logger.error(f"Failed to create switched link: {e}")
            try:
                subprocess.run(['sudo', 'ip', 'link', 'delete', veth_ns],
                             capture_output=True)
            except:
                pass
            raise RuntimeError(f"Switched link creation failed: {e}")
    
    def _apply_netem(self, namespace: str, interface: str, 
                     latency_ms: float, jitter_ms: float, packet_loss_percent: float):
        """
        Apply network emulation (netem) to an interface.
        
        Uses tc (traffic control) netem qdisc for:
        - Latency
        - Packet loss
        - Jitter
        """
        try:
            cmd = [
                'sudo', 'ip', 'netns', 'exec', namespace,
                'tc', 'qdisc', 'add', 'dev', interface, 'root', 'netem'
            ]
            
            if latency_ms > 0:
                if jitter_ms > 0:
                    cmd.extend(['delay', f'{latency_ms}ms', f'{jitter_ms}ms'])
                else:
                    cmd.extend(['delay', f'{latency_ms}ms'])
            elif jitter_ms > 0: # If only jitter is present without base delay
                cmd.extend(['delay', f'0ms', f'{jitter_ms}ms'])
            
            if packet_loss_percent > 0:
                cmd.extend(['loss', f'{packet_loss_percent}%'])
            
            logger.info(f"Applying netem to {namespace}:{interface}: "
                       f"latency={latency_ms}ms, jitter={jitter_ms}ms, loss={packet_loss_percent}%")
            
            subprocess.run(cmd, check=True, capture_output=True)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply netem: {e.stderr.decode()}")
            raise RuntimeError(f"netem application failed: {e.stderr.decode()}")
    
    def _apply_bandwidth_limit(self, namespace: str, interface: str, 
                               bandwidth_mbps: float):
        """
        Apply bandwidth limit using tc tbf (token bucket filter).
        
        Args:
            namespace: Namespace name
            interface: Interface name
            bandwidth_mbps: Bandwidth in Mbps
        """
        try:
            # Convert Mbps to kbps
            rate_kbps = int(bandwidth_mbps * 1000)
            
            # Calculate burst size (10% of rate)
            burst_kb = max(int(rate_kbps * 0.1), 32)
            
            logger.info(f"Applying bandwidth limit to {namespace}:{interface}: {bandwidth_mbps}Mbps")
            
            subprocess.run([
                'sudo', 'ip', 'netns', 'exec', namespace,
                'tc', 'qdisc', 'add', 'dev', interface, 'root', 'tbf',
                'rate', f'{rate_kbps}kbit',
                'burst', f'{burst_kb}kbit',
                'latency', '400ms'
            ], check=True, capture_output=True)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply bandwidth limit: {e.stderr.decode()}")
            raise RuntimeError(f"Bandwidth limit application failed: {e.stderr.decode()}")
    
    def update_link(self, link_id: str, 
                    latency_ms: float, 
                    jitter_ms: float = 0.0,
                    bandwidth_mbps: Optional[float] = None, 
                    packet_loss_percent: float = 0.0):
        """Update link properties (latency, bandwidth, loss)"""
        if link_id not in self.links:
            raise ValueError(f"Link '{link_id}' does not exist")
        
        link = self.links[link_id]
        
        # Determine endpoints to update (P2P has two, Switched has one)
        endpoints = [link.endpoint_a]
        if link.link_type == LinkType.POINT_TO_POINT:
            endpoints.append(link.endpoint_b)
            
        for endpoint in endpoints:
            if ':' not in endpoint:
                continue
            
            ns, iface = endpoint.split(':')
            
            try:
                # Remove existing qdiscs (ignore errors if none exist)
                subprocess.run([
                    'sudo', 'ip', 'netns', 'exec', ns,
                    'tc', 'qdisc', 'del', 'dev', iface, 'root'
                ], capture_output=True)
                
                # Apply new settings
                if latency_ms > 0 or packet_loss_percent > 0 or jitter_ms > 0:
                    self._apply_netem(ns, iface, latency_ms, jitter_ms, packet_loss_percent)
                
                if bandwidth_mbps:
                    self._apply_bandwidth_limit(ns, iface, bandwidth_mbps)
                
            except Exception as e:
                logger.error(f"Failed to update link endpoint {endpoint}: {e}")
                
        # Update metadata
        link.latency_ms = latency_ms
        link.jitter_ms = jitter_ms
        link.bandwidth_mbps = bandwidth_mbps
        link.packet_loss_percent = packet_loss_percent
        logger.info(f"Updated link {link_id}: {latency_ms}ms +/- {jitter_ms}ms, {bandwidth_mbps}Mbps, {packet_loss_percent}% loss")

    def delete_link(self, link_id: str):
        """Delete a link"""
        if link_id not in self.links:
            logger.warning(f"Link '{link_id}' does not exist")
            return
        
        link = self.links[link_id]
        
        try:
            # Parse endpoint
            ns_a, iface_a = link.endpoint_a.split(':')
            
            # Delete interface (this deletes the veth pair)
            subprocess.run([
                'sudo', 'ip', 'netns', 'exec', ns_a,
                'ip', 'link', 'delete', iface_a
            ], check=True, capture_output=True)
            
            del self.links[link_id]
            logger.info(f"Link deleted: {link_id}")
            
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode()
            if "Cannot find device" in err_msg or "Netns not found" in err_msg:
                logger.warning(f"Interface {iface_a} or namespace {ns_a} not found, assuming deleted")
                del self.links[link_id]
                return
            
            logger.error(f"Failed to delete link: {err_msg}")
            raise RuntimeError(f"Link deletion failed: {err_msg}")
    
    def delete_bridge(self, bridge_name: str):
        """Delete a bridge"""
        if bridge_name not in self.bridges:
            logger.warning(f"Bridge '{bridge_name}' does not exist")
            return
        
        try:
            # Bring bridge down
            subprocess.run([
                'sudo', 'ip', 'link', 'set', bridge_name, 'down'
            ], check=True, capture_output=True)
            
            # Delete bridge
            subprocess.run([
                'sudo', 'ip', 'link', 'delete', bridge_name
            ], check=True, capture_output=True)
            
            del self.bridges[bridge_name]
            logger.info(f"Bridge deleted: {bridge_name}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to delete bridge: {e.stderr.decode()}")
            raise RuntimeError(f"Bridge deletion failed: {e.stderr.decode()}")

    def get_bridge_fdb(self, bridge_name: str) -> List[Dict]:
        """Get the forwarding database (MAC table) for a bridge"""
        try:
            # bridge fdb show br <bridge>
            result = subprocess.run(
                ['sudo', 'bridge', 'fdb', 'show', 'br', bridge_name],
                check=True,
                capture_output=True
            )
            
            entries = []
            # Output format: 00:00:00:00:00:00 dev iface [vlan 1] self [permanent]
            for line in result.stdout.decode().strip().split('\n'):
                parts = line.split()
                if len(parts) >= 3:
                     # Filter out self/permanent entries to show relevant learned MACs
                     is_static = 'permanent' in line or 'static' in line
                     is_self = 'self' in parts
                     
                     # We want to show learned addresses (typically dynamic) or explicitly static ones,
                     # but maybe hide the bridge's own MAC usually marked as 'self permanent'
                     if is_self and is_static:
                         continue
                         
                     entries.append({
                         'mac': parts[0],
                         'interface': parts[2],
                         'type': 'static' if is_static else 'dynamic'
                     })
            return entries
        except Exception as e:
            logger.error(f"Failed to get FDB for {bridge_name}: {e}")
            return []
    
    def cleanup_all(self):
        """Delete all links and bridges"""
        logger.info("Cleaning up all links and bridges...")
        
        for link_id in list(self.links.keys()):
            try:
                self.delete_link(link_id)
            except Exception as e:
                logger.error(f"Failed to delete link {link_id}: {e}")
        
        for bridge_name in list(self.bridges.keys()):
            try:
                self.delete_bridge(bridge_name)
            except Exception as e:
                logger.error(f"Failed to delete bridge {bridge_name}: {e}")
        
        logger.info("Cleanup complete")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    manager = LinkManager()
    
    # Create a bridge (switch)
    bridge = manager.create_bridge("br0")
    print(f"Created bridge: {bridge}")
    
    # Cleanup
    manager.cleanup_all()
