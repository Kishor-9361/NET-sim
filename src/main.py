"""
FastAPI Backend Server for Network Emulator
Integrates all core components and provides REST API + WebSocket endpoints
"""

import os
import math
import asyncio
import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from dataclasses import asdict
from namespace_manager import NamespaceManager
from link_manager import LinkManager
from pty_manager import PTYManager
from packet_observer import PacketObserverManager
from topology_manager import TopologyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Network Emulator API",
    description="Kernel-level network emulator with real-time visualization",
    version="1.0.0"
)

# Add CORS middleware to handle cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Global managers
topology_manager = TopologyManager()
active_websockets: Dict[str, List[WebSocket]] = {
    'packets': [],
    'terminals': {}
}

# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================

class DeviceCreate(BaseModel):
    name: str
    device_type: str  # 'host', 'router', 'switch', 'dns_server', 'server'
    ip_address: Optional[str] = None
    subnet_mask: Optional[str] = "255.255.255.0"
    x: int = 400
    y: int = 300

class TopologyCreate(BaseModel):
    type: str # 'mesh', 'ring', 'bus', 'star'
    device_count: int

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    default_gateway: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None

class DeviceBatchUpdate(BaseModel):
    updates: Dict[str, DeviceUpdate]

class LinkCreate(BaseModel):
    device_a: str
    device_b: str
    latency_ms: Optional[int] = 0
    bandwidth_mbps: Optional[int] = 1000
    packet_loss_percent: Optional[float] = 0.0

class LinkUpdate(BaseModel):
    latency_ms: Optional[float] = None
    jitter_ms: Optional[float] = None
    packet_loss_percent: Optional[float] = None
    bandwidth_mbps: Optional[float] = None

class RouteCreate(BaseModel):
    device: str
    destination: str
    gateway: str

class FailureInject(BaseModel):
    device: str
    failure_type: str  # 'block_icmp', 'silent_router', 'interface_down', 'packet_loss'
    interface: Optional[str] = None
    percentage: Optional[float] = None

class CommandExecute(BaseModel):
    device: str
    command: str

# ============================================================================
# REST API Endpoints - Topology Management
# ============================================================================

@app.get("/")
async def root():
    """Serve the main HTML page"""
    return FileResponse("static/index.html")

@app.get("/api/status")
async def get_status():
    """Get system status"""
    return {
        "status": "running",
        "devices": len(topology_manager.devices),
        "links": len(topology_manager.links),
        "active_terminals": len(active_websockets['terminals']),
        "active_packet_observers": len(active_websockets['packets'])
    }

@app.post("/api/devices")
async def create_device(device: DeviceCreate):
    """Create a new network device"""
    try:
        logger.info(f"Creating device: {device.name} (type: {device.device_type})")
        
        result = topology_manager.add_device(
            name=device.name,
            device_type=device.device_type,
            ip_address=device.ip_address,
            subnet_mask=device.subnet_mask,
            x=device.x,
            y=device.y
        )
        
        return {
            "success": True,
            "device": result
        }
    except Exception as e:
        logger.error(f"Failed to create device: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/topologies")
async def create_topology(topo: TopologyCreate):
    """Create a specific network topology"""
    try:
        # User Rule Validation
        MAX_DEVICES = 15 # Limit for safety/performance as requested
        if topo.device_count > MAX_DEVICES:
             raise HTTPException(status_code=400, detail=f"Too many devices. Maximum allowed is {MAX_DEVICES}.")
        if topo.device_count < 2:
             raise HTTPException(status_code=400, detail="Device count must be at least 2.")

        logger.info(f"Creating topology: {topo.type} with {topo.device_count} devices")
        
        center_x, center_y = 500, 350
        radius = 200
        device_names = []
        
        # 1. Create Devices
        if topo.type == "star":
            # Star: 1 Switch in center, N Hosts around
            # Create Center Switch
            sw_name = f"sw_star_{len(topology_manager.devices)}"
            topology_manager.add_device(sw_name, "switch", x=center_x, y=center_y)
            device_names.append(sw_name)
            
            for i in range(topo.device_count):
                angle = 2 * math.pi * i / topo.device_count
                x = int(center_x + radius * math.cos(angle))
                y = int(center_y + radius * math.sin(angle))
                
                name = f"h_{i+1}"
                # Ensure unique name
                while name in topology_manager.devices:
                    name = f"h_{i+1}_{len(topology_manager.devices)}"
                
                topology_manager.add_device(name, "host", x=x, y=y)
                device_names.append(name)
                
                # Link to Switch
                topology_manager.add_link(sw_name, name)
                
        elif topo.type == "mesh":
            # Mesh: N Routers fully connected
            routers = []
            for i in range(topo.device_count):
                angle = 2 * math.pi * i / topo.device_count
                x = int(center_x + radius * math.cos(angle))
                y = int(center_y + radius * math.sin(angle))
                
                name = f"r_{i+1}"
                while name in topology_manager.devices:
                    name = f"r_{i+1}_{len(topology_manager.devices)}"
                
                topology_manager.add_device(name, "router", x=x, y=y)
                routers.append(name)
                device_names.append(name)
            
            # Connect every router to every other router
            for i in range(len(routers)):
                for j in range(i + 1, len(routers)):
                    topology_manager.add_link(routers[i], routers[j])
                    
        elif topo.type == "ring":
            # Ring: N Routers in a circle
            routers = []
            for i in range(topo.device_count):
                angle = 2 * math.pi * i / topo.device_count
                x = int(center_x + radius * math.cos(angle))
                y = int(center_y + radius * math.sin(angle))
                
                name = f"r_{i+1}"
                while name in topology_manager.devices:
                    name = f"r_{i+1}_{len(topology_manager.devices)}"
                
                topology_manager.add_device(name, "router", x=x, y=y)
                routers.append(name)
                device_names.append(name)
            
            # Connect in a ring
            for i in range(len(routers)):
                next_i = (i + 1) % len(routers)
                topology_manager.add_link(routers[i], routers[next_i])

        elif topo.type == "bus":
            # Bus: N Routers in a line
            routers = []
            start_x = 100
            spacing = 150
            if topo.device_count > 1:
               spacing = min(150, 800 / (topo.device_count - 1))

            for i in range(topo.device_count):
                x = int(start_x + i * spacing)
                y = center_y
                
                name = f"r_{i+1}"
                while name in topology_manager.devices:
                    name = f"r_{i+1}_{len(topology_manager.devices)}"
                
                topology_manager.add_device(name, "router", x=x, y=y)
                routers.append(name)
                device_names.append(name)
            
            # Connect in a line
            for i in range(len(routers) - 1):
                topology_manager.add_link(routers[i], routers[i+1])
        
        else:
            raise ValueError("Unknown topology type")
            
        return {
            "success": True, 
            "message": f"Created {topo.type} topology with {topo.device_count} devices",
            "devices": device_names
        }

    except Exception as e:
        logger.error(f"Failed to create topology: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/devices")
async def list_devices():
    """List all devices"""
    return {
        "devices": [
            {
                "name": device.name,
                "type": device.device_type.value,
                "ip_address": list(device.ip_addresses.values())[0] if device.ip_addresses else None,
                "status": "active",
                "x": device.x,
                "y": device.y
            }
            for name, device in topology_manager.devices.items()
        ]
    }

@app.get("/api/devices/{device_name}")
async def get_device(device_name: str):
    """Get detailed device information"""
    try:
        return topology_manager.get_device_info(device_name)
    except Exception as e:
        logger.error(f"Failed to get device {device_name}: {e}")
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/api/devices/{device_name}")
async def update_device(device_name: str, update: DeviceUpdate):
    """Update device properties"""
    logger.info(f"Updating device {device_name}: {update}")
    try:
        current_name = device_name
        # Handle rename
        if update.name and update.name != device_name:
            topology_manager.rename_device(device_name, update.name)
            current_name = update.name

        warning = None
        if update.default_gateway is not None:
            try:
                if update.default_gateway.strip():
                    topology_manager.set_default_gateway(current_name, update.default_gateway.strip())
                else:
                    topology_manager.remove_default_gateway(current_name)
            except Exception as e:
                logger.error(f"Failed to set gateway for {current_name}: {e}")
                warning = f"Renamed successfully, but failed to set gateway: {str(e)}"

        if update.x is not None and update.y is not None:
             if current_name in topology_manager.devices:
                 topology_manager.devices[current_name].x = update.x
                 topology_manager.devices[current_name].y = update.y

        response = {
            "success": True, 
            "message": f"Device {current_name} updated", 
            "name": current_name
        }
        if warning:
            response["warning"] = warning
            
        return response
    except Exception as e:
        logger.error(f"Failed to update device {device_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/devices/batch/update")
async def batch_update_devices(batch: DeviceBatchUpdate):
    """Batch update multiple devices (e.g. positions)"""
    try:
        updated_count = 0
        for name, update in batch.updates.items():
            if name in topology_manager.devices:
                # Optimized position update without full object overhead
                dev = topology_manager.devices[name]
                if update.x is not None: dev.x = update.x
                if update.y is not None: dev.y = update.y
                updated_count += 1
        
        return {"success": True, "updated": updated_count}
    except Exception as e:
        logger.error(f"Failed batch update: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/devices/{device_name}")
async def delete_device(device_name: str):
    """Delete a device"""
    try:
        topology_manager.remove_device(device_name)
        return {"success": True, "message": f"Device {device_name} deleted"}
    except Exception as e:
        logger.error(f"Failed to delete device: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/links")
async def create_link(link: LinkCreate):
    """Create a link between two devices"""
    try:
        logger.info(f"Creating link: {link.device_a} <-> {link.device_b}")
        
        result = topology_manager.add_link(
            device_a=link.device_a,
            device_b=link.device_b,
            latency_ms=link.latency_ms,
            bandwidth_mbps=link.bandwidth_mbps,
            packet_loss_percent=link.packet_loss_percent
        )
        
        return {
            "success": True,
            "link": result
        }
    except Exception as e:
        logger.error(f"Failed to create link: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/links")
async def list_links():
    """List all links"""
    return {
        "links": [
            {
                "id": link.link_id,
                "device_a": link.device_a,
                "device_b": link.device_b,
                "latency_ms": link.latency_ms,
                "status": "active"
            }
            for link_id, link in topology_manager.links.items()
        ]
    }

@app.delete("/api/links/{link_id}")
async def delete_link(link_id: str):
    """Delete a link"""
    try:
        topology_manager.remove_link(link_id)
        return {"success": True, "message": f"Link {link_id} deleted"}
    except Exception as e:
        logger.error(f"Failed to delete link: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/routes")
async def add_route(route: RouteCreate):
    """Add a static route to a device"""
    try:
        topology_manager.namespace_manager.add_route(
            namespace=route.device,
            destination=route.destination,
            gateway=route.gateway
        )
        return {"success": True, "message": f"Route to {route.destination} added to {route.device}"}
    except Exception as e:
        logger.error(f"Failed to add route: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-route")
async def auto_route():
    """Auto-configure routing tables"""
    try:
        topology_manager.auto_configure_routing()
        return {"success": True, "message": "Routing tables auto-configured"}
    except Exception as e:
        logger.error(f"Failed to auto-configure routing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/links/{link_id}")
async def update_link(link_id: str, link_update: LinkUpdate):
    """Update link context"""
    try:
        topology_manager.update_link(
            link_id,
            latency_ms=link_update.latency_ms if link_update.latency_ms is not None else 0,
            jitter_ms=link_update.jitter_ms if link_update.jitter_ms is not None else 0,
            packet_loss_percent=link_update.packet_loss_percent if link_update.packet_loss_percent is not None else 0,
            bandwidth_mbps=link_update.bandwidth_mbps
        )
        return {"success": True, "message": f"Link {link_id} updated"}
    except Exception as e:
        logger.error(f"Failed to update link: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/state")
async def get_state():
    """Get complete topology state"""
    return topology_manager.get_topology_state()

# ============================================================================
# REST API Endpoints - Failure Injection
# ============================================================================

@app.post("/api/failures")
async def inject_failure(failure: FailureInject):
    """Inject a network failure"""
    try:
        logger.info(f"Injecting failure: {failure.failure_type} on {failure.device}")
        
        if failure.failure_type == "block_icmp":
            topology_manager.block_icmp(failure.device)
        elif failure.failure_type == "silent_router":
            topology_manager.enable_silent_router(failure.device)
        elif failure.failure_type == "interface_down":
            if not failure.interface:
                raise ValueError("interface required for interface_down failure")
            topology_manager.set_interface_down(failure.device, failure.interface)
        elif failure.failure_type == "packet_loss":
            if failure.percentage is None:
                raise ValueError("percentage required for packet_loss failure")
            topology_manager.enable_packet_loss(
                failure.device, 
                failure.interface or "eth0", 
                failure.percentage
            )
        else:
            raise ValueError(f"Unknown failure type: {failure.failure_type}")
        
        return {
            "success": True,
            "message": f"Failure {failure.failure_type} injected on {failure.device}"
        }
    except Exception as e:
        logger.error(f"Failed to inject failure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/failures")
async def list_failures():
    """List active failures"""
    return {
        "failures": topology_manager.get_active_failures()
    }

@app.delete("/api/failures/{device}/{failure_type}")
async def remove_failure(device: str, failure_type: str):
    """Remove a failure"""
    try:
        if failure_type == "block_icmp":
            topology_manager.unblock_icmp(device)
        elif failure_type == "silent_router":
            topology_manager.disable_silent_router(device)
        elif failure_type == "interface_down":
            topology_manager.set_interface_up(device, "eth0")
        
        return {
            "success": True,
            "message": f"Failure {failure_type} removed from {device}"
        }
    except Exception as e:
        logger.error(f"Failed to remove failure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================


@app.post("/api/failures/icmp/{device}")
async def toggle_icmp(device: str):
    """Toggle ICMP blocking on a device"""
    try:
        topology_manager.block_icmp(device)
        return {"success": True, "message": f"ICMP blocked on {device}"}
    except Exception as e:
        logger.error(f"Failed to toggle ICMP: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/failures/silent/{device}")
async def toggle_silent_mode(device: str):
    """Toggle silent router mode on a device"""
    try:
        topology_manager.enable_silent_router(device)
        return {"success": True, "message": f"Silent mode enabled on {device}"}
    except Exception as e:
        logger.error(f"Failed to toggle silent mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/failures/interface/{device}/{interface}/{state}")
async def set_interface_state(device: str, interface: str, state: str):
    """Set interface up or down"""
    try:
        if state == "down":
            topology_manager.set_interface_down(device, interface)
        elif state == "up":
            topology_manager.set_interface_up(device, interface)
        else:
            raise ValueError(f"Invalid state: {state}")
        
        return {"success": True, "message": f"Interface {interface} set to {state}"}
    except Exception as e:
        logger.error(f"Failed to set interface state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket Endpoint - Terminal
# ============================================================================

@app.websocket("/ws/terminal/{device}")
async def terminal_websocket(websocket: WebSocket, device: str):
    """WebSocket endpoint for terminal I/O"""
    await websocket.accept()
    logger.info(f"Terminal WebSocket connected for device: {device}")
    
    try:
        # Get or create PTY session for device
        session_id = f"pty-{device}"
        
        if not topology_manager.pty_manager.has_session(session_id):
            # Create new PTY session
            topology_manager.pty_manager.create_session(
                session_id=session_id,
                namespace=device
            )
        
        session = topology_manager.pty_manager.get_session(session_id)
        
        # Store websocket
        active_websockets['terminals'][device] = websocket
        
        # Task to send PTY output to browser
        async def send_output():
            while True:
                try:
                    # Use a small timeout to avoid busy-waiting, but don't block too long
                    # Since read_output uses a thread-safe Queue.get(), we can use it with a small timeout.
                    # To avoid blocking the event loop, we run it in a thread.
                    output = await asyncio.to_thread(
                        topology_manager.pty_manager.read_output, 
                        session_id, 
                        timeout=0.2
                    )
                    
                    if output:
                        # Send as text (decoded) because xterm-addon-fit and basic xterm.js 
                        # often prefer string input for simple integrations.
                        await websocket.send_text(output.decode('utf-8', 'replace'))
                except Exception as e:
                    logger.error(f"Error sending output for {device}: {e}")
                    break
        
        # Task to receive input from browser
        async def receive_input():
            while True:
                try:
                    data = await websocket.receive_text()
                    
                    # Try to parse as JSON command (new protocol)
                    try:
                        import json
                        message = json.loads(data)
                        if isinstance(message, dict) and 'type' in message:
                            if message['type'] == 'input':
                                topology_manager.pty_manager.write_input(session_id, message.get('data', ''))
                            elif message['type'] == 'resize':
                                rows = message.get('rows')
                                cols = message.get('cols')
                                if rows and cols:
                                    topology_manager.pty_manager.resize_terminal(session_id, rows, cols)
                            continue
                    except (json.JSONDecodeError, ImportError):
                        # Not JSON or json not available? treat as raw input (backward compatibility)
                        pass
                        
                    # Fallback: treat raw message as input
                    topology_manager.pty_manager.write_input(session_id, data)
                    
                except WebSocketDisconnect:
                    logger.info(f"Terminal WebSocket disconnected for {device}")
                    break
                except Exception as e:
                    logger.error(f"Error receiving input for {device}: {e}")
                    break
        
        # Run both tasks concurrently
        await asyncio.gather(send_output(), receive_input())
        
    except Exception as e:
        logger.error(f"Terminal WebSocket error: {e}")
    finally:
        if device in active_websockets['terminals']:
            del active_websockets['terminals'][device]

# ============================================================================
# WebSocket Endpoint - Packet Events
# ============================================================================

@app.websocket("/ws/packets")
async def packet_websocket(websocket: WebSocket):
    """WebSocket endpoint for packet events"""
    await websocket.accept()
    logger.info("Packet WebSocket connected")
    
    active_websockets['packets'].append(websocket)
    
    # Get the current event loop for this WebSocket connection
    loop = asyncio.get_event_loop()
    
    try:
        # Set callback to broadcast packets to all connected clients
        def packet_callback(packet_event):
            """Called when a packet is observed (from packet observer thread)"""
            # Broadcast to all connected WebSocket clients
            # Convert dataclass to dict for JSON serialization
            data = asdict(packet_event)
            # Add formatted timestamp and readable protocol/type
            data['protocol'] = packet_event.protocol.value
            data['packet_type'] = packet_event.packet_type.value
            
            for ws in active_websockets['packets']:
                try:
                    # Schedule the coroutine on the main event loop from another thread
                    asyncio.run_coroutine_threadsafe(
                        ws.send_json(data),
                        loop
                    )
                except Exception as e:
                    logger.error(f"Error sending packet event: {e}")
        
        # Register callback with packet observer
        topology_manager.packet_observer.set_global_callback(packet_callback)
        
        # Keep connection alive
        while True:
            try:
                # Just receive pings to keep connection alive
                await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info("Packet WebSocket disconnected")
                break
            
    except Exception as e:
        logger.error(f"Packet WebSocket error: {e}")
    finally:
        if websocket in active_websockets['packets']:
            active_websockets['packets'].remove(websocket)

# ============================================================================
# REST API Endpoint - Command Execution (Alternative to WebSocket)
# ============================================================================

@app.post("/api/execute")
async def execute_command(cmd: CommandExecute):
    """Execute a command on a device (alternative to WebSocket)"""
    try:
        session_id = f"pty-{cmd.device}"
        
        if not topology_manager.pty_manager.has_session(session_id):
            topology_manager.pty_manager.create_session(
                session_id=session_id,
                namespace=cmd.device
            )
        
        session = topology_manager.pty_manager.get_session(session_id)
        session.write_input(cmd.command + "\n")
        
        # Wait a bit for output
        await asyncio.sleep(0.5)
        output = session.read_output()
        
        return {
            "success": True,
            "output": output
        }
    except Exception as e:
        logger.error(f"Failed to execute command: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset")
async def reset_topology():
    """Reset the topology completely"""
    try:
        topology_manager.reset()
        return {"success": True, "message": "Topology reset successfully"}
    except Exception as e:
        logger.error(f"Failed to reset topology: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/shutdown")
async def shutdown_server():
    """Shutdown the server"""
    try:
        logger.info("Shutdown requested via API")
        # Use asyncio to schedule shutdown slightly later to allow response to be sent
        loop = asyncio.get_event_loop()
        loop.call_later(1.0, lambda: os.kill(os.getpid(), 2)) # Signal.SIGINT = 2
        return {"success": True, "message": "Server shutting down..."}
    except Exception as e:
        logger.error(f"Failed to shutdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    logger.info("Network Emulator starting up...")
    logger.info("System ready!")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Network Emulator shutting down...")
    topology_manager.cleanup()
    logger.info("Cleanup complete")

# ============================================================================
# Mount Static Files
# ============================================================================

app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Check if running as root (required for network namespaces)
    if sys.platform == "linux" and os.geteuid() != 0:
        logger.error("This application must be run as root (sudo)")
        logger.error("Run: sudo python3 src/main.py")
        sys.exit(1)
    
    logger.info("Starting Network Emulator Server...")
    logger.info("Access the UI at: http://localhost:8000")
    
    uvicorn.run(
        app,
        host="localhost",
        port=8000,
        log_level="info"
    )
