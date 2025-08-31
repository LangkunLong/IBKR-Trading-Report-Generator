import requests
import socket
import subprocess
import sys
from urllib.parse import urlparse

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

def check_port_open(host, port):
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"Error checking port: {e}")
        return False

def test_different_protocols_and_ports():
    """Test different combinations of protocols and ports"""
    test_configs = [
        ("https://localhost:5000", "HTTPS on 5000 (most common)"),
        ("http://localhost:5000", "HTTP on 5000"),
        ("https://127.0.0.1:5000", "HTTPS on 127.0.0.1:5000"),
        ("http://127.0.0.1:5000", "HTTP on 127.0.0.1:5000"),
        ("https://localhost:5001", "HTTPS on 5001"),
        ("http://localhost:5001", "HTTP on 5001"),
        ("https://localhost:4000", "HTTPS on 4000"),
        ("http://localhost:4000", "HTTP on 4000"),
    ]
    
    working_endpoints = []
    
    print("🔍 Testing different IBKR Gateway configurations...")
    print("=" * 60)
    
    for url, description in test_configs:
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port
            
            print(f"\n📍 Testing {description}")
            print(f"   URL: {url}")
            
            # First check if port is open
            if not check_port_open(host, port):
                print(f"   ❌ Port {port} is not open on {host}")
                continue
            
            print(f"   ✅ Port {port} is open")
            
            # Try to connect
            response = requests.get(url, verify=False, timeout=5)
            print(f"   ✅ HTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                content_length = len(response.content)
                print(f"   ✅ Response received ({content_length} bytes)")
                working_endpoints.append((url, description, response.status_code))
                
                # Check if it looks like IBKR content
                if "interactive" in response.text.lower() or "ibkr" in response.text.lower():
                    print(f"   🎯 Looks like IBKR Gateway!")
                elif content_length < 100:
                    print(f"   ⚠️  Very small response - might be empty")
                else:
                    print(f"   ℹ️  Got response but doesn't look like IBKR")
                    
            else:
                print(f"   ⚠️  Got HTTP {response.status_code} - not OK but server is responding")
                working_endpoints.append((url, description, response.status_code))
                
        except requests.exceptions.SSLError as e:
            print(f"   ❌ SSL Error: {e}")
            print(f"      💡 Try the HTTP version instead")
        except requests.exceptions.ConnectionError as e:
            print(f"   ❌ Connection Error: {e}")
        except requests.exceptions.Timeout as e:
            print(f"   ❌ Timeout: {e}")
        except Exception as e:
            print(f"   ❌ Unexpected Error: {e}")
    
    return working_endpoints

def check_running_processes():
    """Check for IBKR-related processes"""
    print("\n🔍 Checking for IBKR-related processes...")
    try:
        if sys.platform == "win32":
            result = subprocess.run(["tasklist"], capture_output=True, text=True)
            processes = result.stdout
            ibkr_processes = [line for line in processes.split('\n') if 'ibkr' in line.lower() or 'interactive' in line.lower()]
        else:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            processes = result.stdout
            ibkr_processes = [line for line in processes.split('\n') if 'ibkr' in line.lower() or 'interactive' in line.lower()]
        
        if ibkr_processes:
            print("✅ Found IBKR-related processes:")
            for process in ibkr_processes:
                print(f"   {process.strip()}")
        else:
            print("❌ No IBKR-related processes found")
            print("💡 Make sure IBKR Client Portal Gateway is actually running")
            
    except Exception as e:
        print(f"❌ Could not check processes: {e}")

def test_api_endpoints(base_url):
    """Test specific IBKR API endpoints"""
    print(f"\n🔍 Testing IBKR API endpoints on {base_url}...")
    
    endpoints = [
        "/v1/api/iserver/auth/status",
        "/v1/portal/iserver/auth/status", 
        "/iserver/auth/status",
        "/portal/iserver/auth/status",
        "/v1/api/one/user",
        "/sso/Login",
        "/"
    ]
    
    working_endpoints = []
    
    for endpoint in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            print(f"\n   Testing: {url}")
            
            # Try both GET and POST
            for method in ["GET", "POST"]:
                try:
                    if method == "GET":
                        response = requests.get(url, verify=False, timeout=5)
                    else:
                        response = requests.post(url, verify=False, timeout=5)
                    
                    print(f"      {method}: Status {response.status_code}")
                    
                    if response.status_code in [200, 401, 403]:  # These indicate server is responding
                        working_endpoints.append(f"{method} {url} -> {response.status_code}")
                        
                        if response.content:
                            content_preview = response.text[:200].replace('\n', ' ')
                            print(f"      Content preview: {content_preview}...")
                            
                except Exception as e:
                    print(f"      {method}: Error - {str(e)[:50]}")
                    
        except Exception as e:
            print(f"   Error testing {endpoint}: {e}")
    
    return working_endpoints

def main():
    print("🚀 IBKR Gateway Connection Debugger")
    print("=" * 50)
    
    # Check for running processes first
    check_running_processes()
    
    # Test different configurations
    working_endpoints = test_different_protocols_and_ports()
    
    # If we found working endpoints, test their API endpoints
    if working_endpoints:
        print(f"\n🎉 Found {len(working_endpoints)} working endpoints!")
        print("=" * 50)
        
        for url, description, status_code in working_endpoints:
            print(f"✅ {description}: {url} (Status: {status_code})")
            
            # Test API endpoints on the first working URL
            if working_endpoints.index((url, description, status_code)) == 0:
                test_api_endpoints(url)
                
    else:
        print("\n❌ No working endpoints found!")
        print("\n🛠️  Troubleshooting steps:")
        print("1. Check if IBKR Client Portal Gateway is actually running")
        print("2. Look for any IBKR Gateway configuration files that specify port/host")
        print("3. Check if Windows Firewall or antivirus is blocking the connection")
        print("4. Try running the gateway as administrator")
        print("5. Check IBKR Gateway logs for any error messages")
        print("6. Make sure you're not running multiple instances")

if __name__ == "__main__":
    main()