"""
FastAPI Backend Server for Network Emulator
Integrates all core components and provides REST API + WebSocket endpoints
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

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
    type: str  # 'host', 'router', 'switch', 'dns_server'
    ip_address: Optional[str] = None
    subnet_mask: Optional[str] = "255.255.255.0"

class LinkCreate(BaseModel):
    device_a: str
    device_b: str
    latency_ms: Optional[int] = 0
    bandwidth_mbps: Optional[int] = 1000

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
        logger.info(f"Creating device: {device.name} (type: {device.type})")
        
        result = topology_manager.add_device(
            name=device.name,
            device_type=device.type,
            ip_address=device.ip_address,
            subnet_mask=device.subnet_mask
        )
        
        return {
            "success": True,
            "device": result
        }
    except Exception as e:
        logger.error(f"Failed to create device: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/devices")
async def list_devices():
    """List all devices"""
    return {
        "devices": [
            {
                "name": name,
                "type": info["type"],
                "ip_address": info.get("ip_address"),
                "status": info.get("status", "active")
            }
            for name, info in topology_manager.devices.items()
        ]
    }

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
            bandwidth_mbps=link.bandwidth_mbps
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
                "id": link_id,
                "device_a": info["device_a"],
                "device_b": info["device_b"],
                "latency_ms": info.get("latency_ms", 0),
                "status": info.get("status", "active")
            }
            for link_id, info in topology_manager.links.items()
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
                    output = session.read_output()
                    if output:
                        await websocket.send_text(output)
                    await asyncio.sleep(0.01)  # 10ms polling
                except Exception as e:
                    logger.error(f"Error sending output: {e}")
                    break
        
        # Task to receive input from browser
        async def receive_input():
            while True:
                try:
                    data = await websocket.receive_text()
                    session.write_input(data)
                except WebSocketDisconnect:
                    logger.info(f"Terminal WebSocket disconnected for {device}")
                    break
                except Exception as e:
                    logger.error(f"Error receiving input: {e}")
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
    
    try:
        # Set callback to broadcast packets to all connected clients
        def packet_callback(packet_event):
            """Called when a packet is observed"""
            # Broadcast to all connected WebSocket clients
            for ws in active_websockets['packets']:
                try:
                    asyncio.create_task(
                        ws.send_json(packet_event)
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
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
