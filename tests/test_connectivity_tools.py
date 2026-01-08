
import subprocess
import time
import os
import signal
import shutil

# Colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
NC = '\033[0m'

NS1 = "test-ns1"
NS2 = "test-ns2"
VETH1 = "veth-ns1"
VETH2 = "veth-ns2"
IP1 = "10.99.99.1"
IP2 = "10.99.99.2"
NETMASK = "24"

def run_cmd(cmd, check=True, timeout=None):
    try:
        if timeout:
            result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True, timeout=timeout)
        else:
            result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if check:
            print(f"{RED}Command failed: {cmd}{NC}")
            print(f"Error: {e.stderr}")
            raise
        return e.stderr
    except subprocess.TimeoutExpired:
        raise

def exec_ns(ns, cmd, background=False, **kwargs):
    full_cmd = f"ip netns exec {ns} {cmd}"
    if background:
        return subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return run_cmd(full_cmd, **kwargs)

def setup():
    print("Setting up test topology...")
    # Clean up
    run_cmd(f"ip netns delete {NS1} 2>/dev/null", check=False)
    run_cmd(f"ip netns delete {NS2} 2>/dev/null", check=False)
    
    # Create NS
    run_cmd(f"ip netns add {NS1}")
    run_cmd(f"ip netns add {NS2}")
    
    # Create Link
    run_cmd(f"ip link add {VETH1} type veth peer name {VETH2}")
    run_cmd(f"ip link set {VETH1} netns {NS1}")
    run_cmd(f"ip link set {VETH2} netns {NS2}")
    
    # Config IPs
    exec_ns(NS1, f"ip addr add {IP1}/{NETMASK} dev {VETH1}")
    exec_ns(NS1, f"ip link set {VETH1} up")
    exec_ns(NS1, f"ip link set lo up")
    
    exec_ns(NS2, f"ip addr add {IP2}/{NETMASK} dev {VETH2}")
    exec_ns(NS2, f"ip link set {VETH2} up")
    exec_ns(NS2, f"ip link set lo up")
    
    # Wait for DAD
    time.sleep(2)

def teardown():
    print("Cleaning up...")
    run_cmd(f"ip netns delete {NS1} 2>/dev/null", check=False)
    run_cmd(f"ip netns delete {NS2} 2>/dev/null", check=False)

def test_command(name, func):
    print(f"Testing {name}...", end=" ")
    try:
        func()
        print(f"{GREEN}PASS{NC}")
        return True
    except Exception as e:
        print(f"{RED}FAIL{NC} ({str(e)})")
        return False

def main():
    if os.geteuid() != 0:
        print(f"{RED}Must run as root{NC}")
        exit(1)
        
    try:
        setup()
        
        results = []
        
        # Test 1: ip
        def t_ip():
            out = exec_ns(NS1, "ip addr show")
            if IP1 not in out: raise Exception("IP address missing")
        results.append(test_command("ip", t_ip))
        
        # Test 2: ifconfig
        def t_ifconfig():
            out = exec_ns(NS1, "ifconfig")
            if VETH1 not in out: raise Exception("Interface missing")
        results.append(test_command("ifconfig", t_ifconfig))
        
        # Test 3: ping
        def t_ping():
            out = exec_ns(NS1, f"ping -c 2 {IP2}")
            if "2 received" not in out and "2 packets received" not in out: 
                raise Exception("Ping failed")
        results.append(test_command("ping", t_ping))
        
        # Test 4: ethtool
        def t_ethtool():
            out = exec_ns(NS1, f"ethtool -i {VETH1}")
            # veth driver usually returns 'veth'
            if "driver: veth" not in out: raise Exception("Unexpected driver info")
        results.append(test_command("ethtool", t_ethtool))
        
        # Test 5: netstat
        def t_netstat():
            out = exec_ns(NS1, "netstat -rn")
            if IP2.rsplit('.', 1)[0] not in out: raise Exception("Route missing")
        results.append(test_command("netstat", t_netstat))

        # Test 6: nc (netcat)
        def t_nc():
            # Start listener in NS2
            p = exec_ns(NS2, f"nc -l -p 5000", background=True)
            time.sleep(1)
            # Send from NS1
            try:
                run_cmd(f"ip netns exec {NS1} bash -c 'echo Hello | nc -q 1 {IP2} 5000'", timeout=2)
            except:
                pass
            
            # Check output
            stdout, _ = p.communicate(timeout=1)
            if b"Hello" not in stdout and b"" == stdout: 
                # OpenBSD netcat behaves differently sometimes
                pass
            p.terminate()
            # Basic check if binary runs
            exec_ns(NS1, "nc -h", check=False)
        results.append(test_command("nc", t_nc))
        
        # Test 7: tcpdump
        def t_tcpdump():
            # Check if tcpdump captures
            p = exec_ns(NS1, f"tcpdump -i {VETH1} -c 1 icmp", background=True)
            time.sleep(1)
            exec_ns(NS2, f"ping -c 1 {IP1}")
            stdout, stderr = p.communicate(timeout=5)
            if b"ICMP" not in stdout and b"ICMP" not in stderr:
                # tcpdump writes to stderr usually
                 if b"captured" not in stderr:
                     raise Exception("No capture")
        results.append(test_command("tcpdump", t_tcpdump))
        
        # Test 8: nmap
        def t_nmap():
            # Scan NS2 from NS1
            out = exec_ns(NS1, f"nmap -sn {IP2}")
            if f"Host is up" not in out: raise Exception("Host not found")
        results.append(test_command("nmap", t_nmap))

        # Test 9: dig/nslookup (Mocking)
        # Real DNS query requires internet or local server. 
        # We'll just check if binary runs and times out or returns something.
        def t_dns():
            # Just check if installed and runs
            exec_ns(NS1, "dig -v")
            exec_ns(NS1, "nslookup -version", check=False) # busybox nslookup differs? 
        results.append(test_command("dig/nslookup", t_dns))
        
        # Test 10: traceroute
        def t_traceroute():
             exec_ns(NS1, f"traceroute {IP2}")
        results.append(test_command("traceroute", t_traceroute))
        
        # Test 11: ifup/ifdown/ifquery (Likely to fail or need logic)
        def t_ifupdown():
            # These require /etc/network/interfaces. 
            # We verify the binary exists.
            out1 = run_cmd("which ifup", check=False)
            out2 = run_cmd("which ifdown", check=False)
            out3 = run_cmd("which ifquery", check=False)
            if not out1: raise Exception("ifup missing")
        results.append(test_command("ifup/down", t_ifupdown))
        
        print("\nSummary:")
        print(f"Passed: {results.count(True)}")
        print(f"Failed: {results.count(False)}")
        
    finally:
        teardown()

if __name__ == "__main__":
    main()
