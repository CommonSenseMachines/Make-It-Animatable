import subprocess
import time
import sys
import argparse
import os # Import os module

# --- Configuration ---
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

# GPU IDs remain constant regardless of the environment.
GPU_IDS = [5, 6, 7]

def launch_all_servers(config, environment_name):
    """
    Launches multiple worker servers and a corresponding router server
    in the background.
    """
    worker_ports = config["worker_ports"]
    router_port = config["router_port"]
    
    # --- 1. Launch Worker Servers ---
    if len(worker_ports) != len(GPU_IDS):
        print(f"❌ Error: The number of ports ({len(worker_ports)}) must match GPU IDs ({len(GPU_IDS)}).")
        sys.exit(1)

    print(f"🚀 Launching worker servers for '{environment_name.upper()}' environment...")
    
    # Get a copy of the current environment variables to pass to subprocesses
    current_env = os.environ.copy()

    for port, gpu_id in zip(worker_ports, GPU_IDS):
        # Set CUDA_VISIBLE_DEVICES in the environment for this specific subprocess
        worker_env = current_env.copy()
        worker_env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        
        # Command as a list of arguments for security (no shell=True)
        command = ["python", "server.py", "--port", str(port)]
        
        print(f"   - Executing worker command: {' '.join(command)} with CUDA_VISIBLE_DEVICES={gpu_id}")
        try:
            # Use Popen without shell=True, pass env and redirect stdout/stderr
            subprocess.Popen(command, env=worker_env, stdout=sys.stdout, stderr=sys.stderr)
        except FileNotFoundError:
            print("❌ Error: 'python' command not found. Make sure Python is in your system's PATH.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ An unexpected error occurred while launching worker on port {port}: {e}")
            sys.exit(1)

    print("\n✅ Worker servers launched.")
    # Give workers a moment to start up before launching the router
    time.sleep(3)

    # --- 2. Launch Router Server ---
    print(f"\n🚀 Launching router for '{environment_name.upper()}' environment...")
    
    # Command as a list of arguments for security (no shell=True)
    router_command = ["python", "router.py", "--port", str(router_port), "--env", environment_name]
    
    print(f"   - Executing router command: {' '.join(router_command)}")
    try:
        # Use Popen without shell=True, redirect stdout/stderr
        subprocess.Popen(router_command, stdout=sys.stdout, stderr=sys.stderr)
    except FileNotFoundError:
        print("❌ Error: 'python' command not found.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ An unexpected error occurred while launching router: {e}")
        sys.exit(1)

    print("\n✅ All server instances have been launched in the background.")
    print(f"   - Workers on ports: {worker_ports}")
    print(f"   - Router on port: {router_port}")
    print("\nℹ️  To stop the servers, you will need to terminate their processes manually.")
    print("   On Linux/macOS, you can use: pkill -f 'python server.py' && pkill -f 'python router.py'")
    print("   Alternatively, use the 'kill_servers.py' script you created previously.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Launch worker servers and a router for development or production."
    )
    parser.add_argument(
        "env",
        type=str,
        choices=["dev", "prod"],
        default="dev",
        nargs="?",
        help="The environment to launch: 'dev' or 'prod'. Defaults to 'dev'."
    )
    args = parser.parse_args()
    
    # Select the configuration based on the chosen environment.
    config_to_use = CONFIG_MAPPING[args.env]
    
    # Call the main function with the correct config and environment name.
    launch_all_servers(config_to_use, args.env)