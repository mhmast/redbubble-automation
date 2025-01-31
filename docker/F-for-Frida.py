import os
import subprocess
import sys
import requests
import time
from tqdm import tqdm
import logging
from colorama import Fore, Style, init
from shutil import which

# Initialize colorama
init(autoreset=True)

# Logging configuration
logging.basicConfig(filename='frida_script.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

FRIDA_PORT = 27042

# Check if 'xz' is installed on the system
def check_xz_installed():
    if which("xz") is None:
        print(Fore.RED + "[-] Error: 'xz' command is not installed on your system. Please install it to continue.")
        sys.exit(1)

# Function to run ADB commands with SU privilege
def adb_shell_su(command):
    result = subprocess.run(f"adb shell su -c '{command}'", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode('utf-8').strip(), result.stderr.decode('utf-8').strip()

# Function to check if a device is connected via ADB
def check_device_connected():
    print(Fore.CYAN + "[*] Checking if a device is connected...")
    result = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE)
    devices = result.stdout.decode('utf-8').splitlines()
    
    if len(devices) <= 1:  # No device connected
        print(Fore.RED + "[-] No device connected. Please connect a device and enable USB Debugging.")
        return False

    for device in devices[1:]:
        if "unauthorized" in device:
            print(Fore.RED + "[-] Device connected, but ADB authorization is not granted. Please authorize the device.")
            return False
        elif "device" not in device:
            print(Fore.RED + "[-] Device connected, but USB Debugging is not enabled. Please enable USB Debugging.")
            return False
        else:
            print(Fore.GREEN + "[+] Device connected and authorized.")
            return True

    return False

# Function to check if the device is rooted using ADB
def check_root():
    print(Fore.CYAN + "[*] Checking if the device is rooted...")
    try:
        result = subprocess.run(["adb", "shell", "id"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        stdout = result.stdout.decode('utf-8').strip()
        if "uid=0(root)" in stdout:
            print(Fore.GREEN + "[+] Root access confirmed!")
            return True
        else:
            print(Fore.RED + "[-] The device is not rooted or ADB root is not enabled.")
            return False
    except subprocess.TimeoutExpired:
        print(Fore.RED + "[-] Root check timed out. Ensure that the device is connected and ADB is enabled.")
        return False

# Function to check if Frida is running on the default port and get its PIDs
def check_frida_running_on_port():
    print(Fore.CYAN + "[*] Checking if Frida is running on the default port...")
    try:
        result = subprocess.run(["adb", "shell", f"netstat -tuln | grep {FRIDA_PORT}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = result.stdout.decode('utf-8').strip()

        if output:
            print(Fore.GREEN + f"[+] Frida server is running on port {FRIDA_PORT}.")
            pid_result = subprocess.run(["adb", "shell", f"ps -Af | grep frida-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            pid_output = pid_result.stdout.decode('utf-8').strip()
            
            if pid_output:
                # Extract PIDs from the output
                pids = [line.split()[1] for line in pid_output.splitlines() if "frida-server" in line]
                print(Fore.GREEN + f"[+] Found Frida server PIDs: {', '.join(pids)}")
                return pids
            else:
                print(Fore.RED + "[-] No Frida server processes found.")
                return None
        else:
            print(Fore.RED + f"[-] Frida server is not running on the default port ({FRIDA_PORT}).")
            return None
    except Exception as e:
        print(Fore.RED + f"[-] Error checking Frida server port: {e}")
        return None

# Function to detect device architecture using adb
def get_device_architecture():
    print(Fore.CYAN + "[*] Detecting device architecture...")
    try:
        # Get the architecture from the device's properties
        result = subprocess.run(["adb", "shell", "getprop", "ro.product.cpu.abi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        arch = result.stdout.decode('utf-8').strip()

        # Map the architecture from the device to the format required for Frida
        if arch in ["arm64-v8a", "arm64"]:
            return "arm64"
        elif arch in ["armeabi-v7a", "armeabi"]:
            return "arm"
        elif arch == "x86":
            return "x86"
        elif arch == "x86_64":
            return "x86_64"
        else:
            print(Fore.RED + f"[-] Unknown architecture: {arch}")
            return None
    except subprocess.CalledProcessError as e:
        print(Fore.RED + f"[-] Failed to detect architecture: {e}")
        return None
        
# Function to stop all running Frida server PIDs with a single adb shell and su session
def stop_all_frida_servers(pids):
    print(Fore.CYAN + "[*] Stopping all Frida server processes...")

    try:
        # Step 1: Open ADB shell and gain SU privileges
        print(Fore.CYAN + "[*] Gaining SU privileges in ADB shell...")
        su_session = subprocess.Popen(["adb", "shell", "su"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Check if SU privileges were obtained
        su_session.stdin.write("id\n")
        su_session.stdin.flush()
        output = su_session.stdout.readline().strip()
        if "uid=0(root)" not in output:
            print(Fore.RED + "[-] Failed to get SU privileges. Please ensure the device is rooted.")
            su_session.terminate()
            return

        # Step 2: Execute the kill command for each PID within the same session
        for pid in pids:
            print(Fore.CYAN + f"[*] Stopping Frida server with PID {pid}...")
            su_session.stdin.write(f"kill -9 {pid}\n")
            su_session.stdin.flush()
        
        su_session.stdin.write("exit\n")  # Close the SU session properly
        su_session.stdin.flush()
        su_session.wait()

        print(Fore.GREEN + "[+] All Frida server processes stopped successfully.")

    except Exception as e:
        print(Fore.RED + f"[-] Error stopping Frida servers: {e}")

# Function to download and install the Frida server on the device
def download_and_install_frida_server(version, architecture):
    print(Fore.CYAN + f"[*] Downloading and installing Frida server version {version} for {architecture}...")
    url = f"https://github.com/frida/frida/releases/download/{version}/frida-server-{version}-android-{architecture}.xz"
    local_filename = f"frida-server-{version}-android-{architecture}.xz"

    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            block_size = 1024
            t = tqdm(total=total_size, unit='iB', unit_scale=True)
            with open(local_filename, 'wb') as f:
                for data in r.iter_content(block_size):
                    t.update(len(data))
                    f.write(data)
            t.close()

        print(Fore.CYAN + f"[*] Extracting Frida server {version}...")
        subprocess.run(['xz', '--decompress', '-f', local_filename])
        
        # Push to the device and set permissions
        extracted_file = local_filename.rstrip(".xz")
        subprocess.run(["adb", "push", extracted_file, f"/data/local/tmp/frida-server-{version}-android-{architecture}"])
        subprocess.run(["adb", "shell", "chmod", "755", f"/data/local/tmp/frida-server-{version}-android-{architecture}"])
        print(Fore.GREEN + f"[+] Frida server {version} installed on the device.")
        return f"/data/local/tmp/frida-server-{version}-android-{architecture}"

    except requests.exceptions.HTTPError as err:
        print(Fore.RED + f"[-] Failed to download frida-server: {err}")
        return None

# Function to run Frida server using nohup and check if it's running
def run_frida_server(frida_server_path):
    print(Fore.CYAN + f"[*] Starting Frida server at {frida_server_path}...")

    try:
        # Start Frida server in the background using nohup
        start_command = f"adb shell '{frida_server_path}' >/dev/null 2>&1 &"
        result = subprocess.run(start_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Capture any stdout or stderr messages for diagnostics
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if stdout:
            print(Fore.CYAN + f"[*] Frida server stdout: {stdout}")
        if stderr:
            print(Fore.RED + f"[-] Frida server stderr: {stderr}")

        # Wait for a few seconds to check if Frida starts successfully
        time.sleep(3)

        # Check if Frida server is running by looking for its process
        print(Fore.CYAN + "[*] Checking if Frida server is running...")
        check_command = "adb shell ps | grep frida-server"
        check_result = subprocess.run(check_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if check_result.returncode == 0 and "frida-server" in check_result.stdout:
            # Extract the PID
            pid_line = check_result.stdout.strip().splitlines()[0]
            pid = pid_line.split()[1]  # Assuming the PID is the second column
            print(Fore.GREEN + f"[+] Frida server started successfully with PID: {pid}.")
        else:
            print(Fore.RED + "[-] Failed to start Frida server. No running process detected.")
            # Check device logs for Frida-related issues
            log_result = subprocess.run("adb logcat | grep frida", shell=True, stdout=subprocess.PIPE, text=True)
            print(Fore.RED + "[-] Frida log output:")
            print(log_result.stdout)

    except Exception as e:
        print(Fore.RED + f"[-] Error starting Frida server: {e}")

# Function to check if a Frida server is installed on the device
def check_frida_server_installed(version, architecture):
    frida_server_path = f"/data/local/tmp/frida-server-{version}-android-{architecture}"
    print(Fore.CYAN + f"[*] Checking if Frida server is installed at {frida_server_path}...")
    
    result = subprocess.run(["adb", "shell", "ls", frida_server_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = result.stdout.decode('utf-8').strip()
    stderr = result.stderr.decode('utf-8').strip()
    
    if "No such file" in stderr:
        print(Fore.RED + f"[-] Frida server binary not found at {frida_server_path}.")
        return False
    else:
        print(Fore.GREEN + f"[+] Frida server binary found at {frida_server_path}.")
        return frida_server_path

# Main script logic
def main():
    if not check_device_connected():
        return

    if not check_root():
        return

    # Check if Frida server is running on the default port and get its PIDs
    frida_pids = check_frida_running_on_port()
    
    # Detect architecture
    architecture = get_device_architecture()
    if not architecture:
        print(Fore.RED + "[-] Could not detect device architecture. Exiting.")
        return

    print(Fore.GREEN + f"[+] Device architecture detected: {architecture}")
    
    # If Frida is running, ask the user if they want to stop all processes
    if frida_pids:
        stop_option = input(Fore.CYAN + f"[*] Do you want to stop all running Frida server processes? (y/n): ").strip().lower()
        if stop_option == 'y':
            stop_all_frida_servers(frida_pids)
        elif stop_option == 'n':
            print(Fore.GREEN + "[+] Keeping Frida server processes running.")
            return
        else:
            print(Fore.YELLOW + "[!] Invalid input. Exiting.")
            return

    # Prompt for Frida version and check if the server is installed on the device
    desired_version = "16.6.6" #input(Fore.CYAN + "\nEnter the Frida version you want to use or install (e.g., 16.1.17): ")
    frida_server_path = check_frida_server_installed(desired_version, architecture)

    if not frida_server_path:
        # Download and install the Frida server if not found
        frida_server_path = download_and_install_frida_server(desired_version, architecture)

    # If Frida server is found or installed, ask the user if they want to run it
    run_frida_server(frida_server_path)


if __name__ == "__main__":
    main()
