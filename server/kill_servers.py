# kill_servers.py
import subprocess
import sys
import argparse
import platform

# --- Configuration (Copied from your launch script) ---
# Map environment names to their respective port configurations.
CONFIG_MAPPING = {
    "dev": {
        "worker_ports": [8001, 8002, 8003],
        "router_port": 8000
    },
    "prod": {
        "worker_ports": [9001, 9002, 9003],
        "router_port": 9000
    },
}

def get_pids_on_port(port):
    """
    Finds the Process ID (PID) of the process listening on the given port.
    Supports both Unix-like systems (Linux/macOS) and Windows.
    Returns a list of PIDs found on the port.
    """
    system = platform.system()
    pids = []

    try:
        if system == "Linux" or system == "Darwin":  # Linux or macOS
            # Use lsof to find the process ID listening on the port
            # -t: output PIDs only
            command = ["lsof", "-t", "-i", f":{port}"]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            if result.stdout:
                # Split by newline and filter out empty strings to get a list of PIDs
                pids = [pid.strip() for pid in result.stdout.strip().split('\n') if pid.strip()]
        elif system == "Windows":
            # Use netstat to find the PID
            command = ["netstat", "-ano"]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            
            # Parse netstat output for the specific port
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    # Example line: TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       12345
                    parts = line.strip().split()
                    if len(parts) > 4:
                        # The PID is usually the last part of the line for LISTENING connections
                        pid = parts[-1]
                        if pid.isdigit() and pid not in pids: # Ensure unique PIDs
                            pids.append(pid)
        else:
            print(f"⚠️ Warning: Unsupported operating system '{system}'. Cannot reliably find processes by port.")
    except subprocess.CalledProcessError as e:
        # lsof or netstat might not be installed, or no process found
        # For lsof, it often exits with 1 if nothing is found, so we check stdout first
        if "lsof" in e.cmd[0] and "no process" in e.stderr.lower():
            pass # No process found, which is fine
        else:
            print(f"❌ Error executing command to find PID for port {port}: {e}")
            print(f"   Stderr: {e.stderr}")
    except FileNotFoundError:
        if system == "Linux" or system == "Darwin":
            print(f"❌ Error: 'lsof' command not found. Please install it (e.g., 'sudo apt-get install lsof' or 'brew install lsof').")
        elif system == "Windows":
            print(f"❌ Error: 'netstat' command not found. This is unusual for Windows.")
        sys.exit(1)
    
    return pids

def kill_process(pid, port):
    """
    Kills the process with the given PID.
    Supports both Unix-like systems (Linux/macOS) and Windows.
    """
    system = platform.system()
    try:
        if system == "Linux" or system == "Darwin":  # Linux or macOS
            command = ["kill", str(pid)]
            subprocess.run(command, check=True)
            print(f"   ✅ Successfully killed process {pid} on port {port}.")
        elif system == "Windows":
            # /F forcefully terminates the process
            command = ["taskkill", "/PID", str(pid), "/F"]
            subprocess.run(command, check=True)
            print(f"   ✅ Successfully killed process {pid} on port {port}.")
        else:
            print(f"⚠️ Warning: Unsupported operating system '{system}'. Cannot reliably kill process {pid}.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to kill process {pid} on port {port}: {e}")
        print(f"   Stderr: {e.stderr}")
    except FileNotFoundError:
        if system == "Linux" or system == "Darwin":
            print(f"❌ Error: 'kill' command not found. This is unusual.")
        elif system == "Windows":
            print(f"❌ Error: 'taskkill' command not found. This is unusual.")
        sys.exit(1)

def kill_all_servers_by_port(config, environment_name):
    """
    Kills processes associated with worker and router servers
    by finding and terminating processes on their respective ports.
    """
    worker_ports = config["worker_ports"]
    router_port = config["router_port"]
    
    all_ports = worker_ports + [router_port]
    
    print(f"🛑 Attempting to kill server processes for '{environment_name.upper()}' environment...")

    processes_killed_count = 0
    for port in all_ports:
        print(f"\nSearching for processes on port {port}...")
        pids = get_pids_on_port(port)
        
        if pids:
            print(f"   Found process(es) with PID(s) {', '.join(pids)} on port {port}. Attempting to kill...")
            for pid in pids:
                kill_process(pid, port)
                processes_killed_count += 1
        else:
            print(f"   No process found listening on port {port}.")

    if processes_killed_count > 0:
        print(f"\n✅ Finished. Total {processes_killed_count} processes killed.")
    else:
        print("\nℹ️ No server processes found running on the configured ports.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Kill worker and router server processes by port for development or production."
    )
    parser.add_argument(
        "env",
        type=str,
        choices=["dev", "prod"],
        default="dev",
        nargs="?",
        help="The environment for which to kill processes: 'dev' or 'prod'. Defaults to 'dev'."
    )
    args = parser.parse_args()
    
    # Select the configuration based on the chosen environment.
    config_to_use = CONFIG_MAPPING[args.env]
    
    # Call the main function to kill processes.
    kill_all_servers_by_port(config_to_use, args.env)
