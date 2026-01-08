
import logging
from topology_manager import TopologyManager
from namespace_manager import DeviceType
import time
import subprocess
import shlex

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='test_run.log',
    filemode='w'
)
logger = logging.getLogger(__name__)

# Add a handler to print only the report or critical errors to stdout? 
# No, let's just keep stdout clean for print() calls.

# Initialize TM
tm = TopologyManager()

# Results
results = {
    "connectivity": [],
    "routing": [],
    "analysis": [],
    "dns": []
}

def run_cmd(device, cmd):
    try:
        full_cmd = f"sudo ip netns exec {device} {cmd}"
        result = subprocess.run(shlex.split(full_cmd), capture_output=True, timeout=5)
        return result.returncode == 0, result.stdout.decode(), result.stderr.decode()
    except Exception as e:
        return False, "", str(e)

def setup_topology():
    logger.info("Setting up complex topology...")
    tm.cleanup() # Clean start (Fixed method name from cleanup_all to cleanup)
    
    # Create 3 Routers (Mesh)
    # r1 <-> r2 <-> r3 <-> r1
    tm.add_device("r1", "router", x=300, y=100)
    tm.add_device("r2", "router", x=500, y=100)
    tm.add_device("r3", "router", x=400, y=300)
    
    tm.add_link("r1", "r2")
    tm.add_link("r2", "r3")
    tm.add_link("r3", "r1")

    # Connect Switch to r1
    tm.add_device("sw1", "switch", x=200, y=100)
    tm.add_link("r1", "sw1")
    
    # Hosts on Switch
    # h1 -> sw1
    # h2 -> sw1
    tm.add_device("h1", "host", x=100, y=50)
    tm.add_link("h1", "sw1")
    tm.add_device("h2", "host", x=100, y=150)
    tm.add_link("h2", "sw1")
    
    # Host on r3 (different subnet)
    tm.add_device("h3", "host", x=400, y=400)
    tm.add_link("h3", "r3")

    # Server on r2
    tm.add_device("srv1", "server", x=600, y=100)
    tm.add_link("srv1", "r2")

    # DNS on r2
    tm.add_device("dns1", "dns_server", x=600, y=200)
    tm.add_link("dns1", "r2")

    logger.info("Topology Created.")
    time.sleep(2) # Let interfaces come up

    # Enable Forwarding on Routers
    logger.info("Enabling Forwarding on Routers...")
    for r in ["r1", "r2", "r3"]:
        run_cmd(r, "sysctl -w net.ipv4.ip_forward=1")

    # Configure Routing & DNS
    logger.info("Configuring Routing & DNS...")
    tm._auto_configure_routing()
    tm._update_dns_records()
    time.sleep(5) # Let routes settle

def test_connectivity():
    logger.info("Testing Connectivity...")
    # Ping h1 -> h2 (Same subnet)
    success, out, _ = run_cmd("h1", "ping -c 3 h2.lan") # Using DNS name via records json update?
    # Might need direct IP if DNS not ready, but let's try hostname since TM does auto-dns
    
    # If hostname fails, fallback to IP logic or trust TM's auto-config
    # TM updates dns_records.json. 
    # Let's get IPs to be safe for rigorous testing
    
    h2_ip = list(tm.devices["h2"].ip_addresses.values())[0].split('/')[0]
    h3_ip = list(tm.devices["h3"].ip_addresses.values())[0].split('/')[0]
    srv1_ip = list(tm.devices["srv1"].ip_addresses.values())[0].split('/')[0]

    # 1. Local Ping
    success, _, _ = run_cmd("h1", f"ping -c 1 {h2_ip}")
    results["connectivity"].append(("Ping Local (h1->h2)", success))

    # 2. Routed Ping (h1 -> h3)
    # This requires routing. TM has _auto_configure_routing but it needs gateways.
    # Our new update adds auto gateway for Hosts.
    # h1 -> sw1 -> r1. Gateway of h1 should be r1's IP on that link.
    success, _, _ = run_cmd("h1", f"ping -c 1 {h3_ip}")
    results["connectivity"].append(("Ping Routed (h1->h3)", success))
    
    # 3. Server Ping
    success, _, _ = run_cmd("h1", f"ping -c 1 {srv1_ip}")
    results["connectivity"].append(("Ping Server (h1->srv1)", success))

def test_commands():
    logger.info("Testing Commands...")
    h2_ip = list(tm.devices["h2"].ip_addresses.values())[0].split('/')[0]

    # Traceroute
    success, out, _ = run_cmd("h1", f"traceroute -n {h2_ip}")
    results["connectivity"].append(("traceroute", success))

    # ip addr
    success, out, _ = run_cmd("h1", "ip addr")
    results["routing"].append(("ip addr", success and "eth0" in out))

    # ip route
    success, out, _ = run_cmd("h1", "ip route")
    results["routing"].append(("ip route", success and "default" in out)) # Should have default gateway

    # tcpdump (just check if binary runs)
    success, _, _ = run_cmd("h1", "timeout 1 tcpdump -h") # timeout to ensure it doesn't hang
    results["analysis"].append(("tcpdump", success)) # check return code or valid help output

    # netstat
    success, out, _ = run_cmd("h1", "netstat -rn")
    results["analysis"].append(("netstat", success))

    # nmap (scan localhost or neighbor)
    success, _, _ = run_cmd("h1", f"nmap -sn -n {h2_ip}")
    results["analysis"].append(("nmap", success))
    
    # nc (netcat) - check if installed
    success, _, _ = run_cmd("h1", "nc -h")
    results["analysis"].append(("netcat", success))
    
    # DNS: nslookup
    # We set up a DNS server.
    # Host h1 should resolve 'h2.lan'.
    success, out, err = run_cmd("h1", "nslookup h2.lan")
    results["dns"].append(("nslookup", success))
    
    # dig
    success, out, err = run_cmd("h1", "dig h2.lan")
    results["dns"].append(("dig", success))

def main():
    try:
        setup_topology()
        test_connectivity()
        test_commands()
        
        # Print Grid
        print("\n\n=== TEST REPORT ===")
        print(f"{'CATEGORY':<15} | {'TEST':<25} | {'STATUS':<10}")
        print("-" * 55)
        for category, items in results.items():
            for test_name, status in items:
                mark = "✅" if status else "❌"
                print(f"{category:<15} | {test_name:<25} | {mark}")
                
    finally:
        tm.cleanup()

if __name__ == "__main__":
    main()
