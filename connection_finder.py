import socket
import requests
import json
from urllib.parse import urlparse
import subprocess
import sys
import time

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

def scan_ports(host="localhost", port_range=(3000, 6000)):
    """Scan for open ports in the given range"""
    print(f"🔍 Scanning ports {port_range[0]}-{port_range[1]} on {host}...")
    open_ports = []
    
    for port in range(port_range[0], port_range[1] + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((host, port))
            if result == 0:
                open_ports.append(port)
                print(f"   ✅ Port {port} is open")
            sock.close()
        except Exception:
            pass
    
    return open_ports

def test_http_on_port(port):
    """Test HTTP/HTTPS connections on a specific port"""
    results = []
    
    urls_to_test = [
        f"https://localhost:{port}",
        f"http://localhost:{port}",
        f"https://127.0.0.1:{port}",
        f"http://127.0.0.1:{port}"
    ]
    
    for url in urls_to_test:
        try:
            print(f"   Testing {url}...")
            response = requests.get(url, verify=False, timeout=3)
            content_length = len(response.content)
            results.append({
                'url': url,
                'status': response.status_code,
                'content_length': content_length,
                'content_preview': response.text[:100].replace('\n', ' ') if response.text else ""
            })
            print(f"      ✅ Status: {response.status_code}, Size: {content_length} bytes")
            
        except requests.exceptions.SSLError:
            print(f"      ⚠️ SSL Error")
        except requests.exceptions.ConnectionError:
            print(f"      ❌ Connection Error")
        except requests.exceptions.Timeout:
            print(f"      ⏰ Timeout")
        except Exception as e:
            print(f"      ❌ Error: {str(e)[:50]}")
    
    return results

def check_gateway_endpoints(base_url):
    """Test common IBKR Gateway API endpoints"""
    print(f"\n🔍 Testing IBKR API endpoints on {base_url}...")
    
    # Common IBKR Gateway endpoints
    endpoints_to_test = [
        "",  # Root
        "/",
        "/sso/Login",
        "/v1/api/iserver/auth/status",
        "/v1/portal/iserver/auth/status",
        "/iserver/auth/status", 
        "/portal/iserver/auth/status",
        "/v1/api/one/user",
        "/api/v1/portal/iserver/auth/status",
        "/clientportal.gw/api/v1/portal/iserver/auth/status"
    ]
    
    working_endpoints = []
    
    for endpoint in endpoints_to_test:
        full_url = f"{base_url}{endpoint}"
        
        # Try both GET and POST
        for method in ['GET', 'POST']:
            try:
                print(f"   {method} {endpoint}...", end="")
                
                if method == 'GET':
                    response = requests.get(full_url, verify=False, timeout=5)
                else:
                    response = requests.post(full_url, verify=False, timeout=5)
                
                print(f" Status: {response.status_code}")
                
                if response.status_code in [200, 401, 403, 500]:
                    working_endpoints.append({
                        'method': method,
                        'endpoint': endpoint,
                        'url': full_url,
                        'status': response.status_code,
                        'content': response.text[:200] if response.text else ""
                    })
                    
                    # If it's a successful response, show more details
                    if response.status_code == 200 and response.text:
                        print(f"      Content preview: {response.text[:100].replace(chr(10), ' ')}")
                    elif response.status_code in [401, 403]:
                        print(f"      🔐 Authentication required (good sign!)")
                
            except Exception as e:
                print(f" Error: {str(e)[:30]}")
    
    return working_endpoints

def find_netstat_info():
    """Find what's actually listening on ports"""
    print("\n🔍 Checking what's listening on ports...")
    
    try:
        if sys.platform == "win32":
            result = subprocess.run(["netstat", "-an"], capture_output=True, text=True, timeout=10)
            lines = result.stdout.split('\n')
            listening_lines = [line for line in lines if 'LISTENING' in line and ('5000' in line or '4000' in line or '3000' in line)]
        else:
            result = subprocess.run(["netstat", "-tuln"], capture_output=True, text=True, timeout=10)
            lines = result.stdout.split('\n')
            listening_lines = [line for line in lines if 'LISTEN' in line and ('5000' in line or '4000' in line or '3000' in line)]
        
        if listening_lines:
            print("   Found services listening on relevant ports:")
            for line in listening_lines:
                print(f"   {line.strip()}")
        else:
            print("   No services found listening on ports 3000-5000")
            
    except Exception as e:
        print(f"   Error running netstat: {e}")

def check_java_processes():
    """Find Java processes that might be IBKR Gateway"""
    print("\n🔍 Looking for Java processes...")
    
    try:
        if sys.platform == "win32":
            result = subprocess.run(["wmic", "process", "where", "name='java.exe'", "get", "processid,commandline"], 
                                  capture_output=True, text=True, timeout=10)
        else:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=10)
        
        lines = result.stdout.split('\n')
        java_processes = [line for line in lines if 'java' in line.lower()]
        
        if java_processes:
            print("   Found Java processes:")
            for process in java_processes:
                if 'ibkr' in process.lower() or 'interactive' in process.lower() or 'clientportal' in process.lower():
                    print(f"   🎯 IBKR-related: {process.strip()}")
                elif len(process.strip()) > 0:
                    print(f"   ⚪ Other Java: {process.strip()[:100]}...")
        else:
            print("   No Java processes found")
            
    except Exception as e:
        print(f"   Error checking processes: {e}")

def main():
    print("🚀 IBKR Gateway Connection Finder")
    print("=" * 60)
    
    # Step 1: Check what's actually listening
    find_netstat_info()
    check_java_processes()
    
    # Step 2: Scan for open ports
    print(f"\n" + "=" * 60)
    open_ports = scan_ports()
    
    if not open_ports:
        print("\n❌ No open ports found in range 3000-6000")
        print("💡 IBKR Gateway might not be running or using a different port")
        return
    
    print(f"\n✅ Found {len(open_ports)} open ports: {open_ports}")
    
    # Step 3: Test HTTP connections on open ports
    print(f"\n" + "=" * 60)
    print("🌐 Testing HTTP/HTTPS connections on open ports...")
    
    all_working_urls = []
    
    for port in open_ports:
        print(f"\n📡 Testing port {port}:")
        results = test_http_on_port(port)
        
        # Filter to working URLs
        working_urls = [r for r in results if r['status'] in [200, 401, 403, 500]]
        if working_urls:
            all_working_urls.extend(working_urls)
            print(f"   ✅ Found {len(working_urls)} working URLs on port {port}")
    
    # Step 4: Test IBKR API endpoints on working URLs
    if all_working_urls:
        print(f"\n" + "=" * 60)
        print(f"🔍 Testing IBKR API endpoints on {len(all_working_urls)} working URLs...")
        
        all_api_endpoints = []
        
        for url_info in all_working_urls:
            base_url = url_info['url']
            print(f"\n🌐 Testing {base_url}:")
            
            api_endpoints = check_gateway_endpoints(base_url)
            if api_endpoints:
                all_api_endpoints.extend(api_endpoints)
        
        # Step 5: Summary
        print(f"\n" + "=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        
        if all_working_urls:
            print(f"✅ Working HTTP endpoints:")
            for url_info in all_working_urls:
                print(f"   {url_info['url']} -> Status {url_info['status']}")
        
        if all_api_endpoints:
            print(f"\n✅ Working API endpoints:")
            for api_info in all_api_endpoints:
                print(f"   {api_info['method']} {api_info['url']} -> Status {api_info['status']}")
        
        if all_api_endpoints:
            # Give specific instructions for using the working endpoints
            best_endpoint = all_api_endpoints[0]
            base_url = best_endpoint['url'].replace(best_endpoint['endpoint'], '')
            
            print(f"\n🎯 RECOMMENDED CONFIGURATION:")
            print(f"   Base URL: {base_url}")
            print(f"   Test this URL in your browser first: {base_url}")
            print(f"   Then update your Python script to use: {base_url}")
        else:
            print(f"\n⚠️ No IBKR API endpoints found")
            print(f"💡 Try opening these URLs in your browser:")
            for url_info in all_working_urls:
                print(f"   {url_info['url']}")
    
    else:
        print(f"\n❌ No working HTTP endpoints found")
        print(f"💡 IBKR Gateway might be:")
        print(f"   1. Not fully started yet")
        print(f"   2. Running on a different port")
        print(f"   3. Requiring specific authentication")

if __name__ == "__main__":
    main()