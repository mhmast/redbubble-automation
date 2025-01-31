#!/bin/bash

 if [ -z "$PROXY_HOST" ] || [ -z "$PROXY_PORT" ]; then
  export EMULATOR_ADDITIONAL_ARGS="$EMULATOR_ADDITIONAL_ARGS -http-proxy $PROXY_HOST:$PROXY_PORT"
  echo "added proxy to env"
fi

env

function shuwdown(){
  echo "SIGTERM is received! Clean-up will be executed if needed!"
  process_id=$(pgrep -f "start device")
  kill ${process_id}
  sleep 10
  if [[ ${DEVICE_TYPE} == "geny_aws" ]]; then
    # Give time to execute tear_down method
    sleep 180
  fi
}

trap shuwdown SIGTERM

function installApks(){

# Directory containing the APK files
APK_DIR="/tmp/local/apk"
FRIDA_SCRIPT="/tmp/local/frida-android-repinning_sa-1.js"

# Check if the APK directory exists
if [ ! -d "$APK_DIR" ]; then
  echo "Directory $APK_DIR does not exist."
  exit 1
fi

# Ensure adb is available
if ! command -v adb &>/dev/null; then
  echo "adb is not installed. Please install it before running this script."
  exit 1
fi

# Ensure frida is available
if ! command -v frida &>/dev/null; then
  echo "frida is not installed. Please install it before running this script."
  exit 1
fi

waitForDevice
# Iterate through each APK file in the directory
for apk in "$APK_DIR"/*.apk; do
  # Skip if no APK files are found
  if [ ! -f "$apk" ]; then
    echo "No APK files found in $APK_DIR."
    continue
  fi

  echo "Processing $apk..."
  
  # Install the APK
  INSTALLED=$(adb install $apk | grep "Success")
  if [ -z "$INSTALLED" ]; then
    echo "Failed to install $apk."
    continue
  fi

  # Extract the package name of the installed APK
  PACKAGE_NAME=$(/home/androidusr/android-11/aapt dump badging "$apk" | grep "package: name=" | awk -F"'" '{print $2}')
  if [ -z "$PACKAGE_NAME" ]; then
    echo "Failed to fetch the package name for $apk."
    continue
  fi

  echo "Package installed: $PACKAGE_NAME"

  # Run Frida command
  frida -U -f "$PACKAGE_NAME" -l "$FRIDA_SCRIPT" &
done

}


# # URL of the certificate to download
# CERT_NAME="FiddlerRoot.cer"            # Name for the certificate file
# CERT_URL="http://$PROXY_HOST:$PROXY_PORT/$CERT_NAME" # Replace with the actual URL
# CERT_ALIAS="FiddlerRoot"                # Alias for the certificate

# # Temporary paths
CERT_LOCAL_PATH="/data/local/tmp/cert-der.crt"
CERT_DEVICE_PATH="/data/local/tmp/cert-der.crt"

# Function to check if adb is available
check_adb() {
  if ! command -v adb &>/dev/null; then
    echo "adb is not installed. Please install it before running this script."
    exit 1
  fi
}

# # Function to download the certificate
# download_certificate() {
#   echo "Downloading certificate from $CERT_URL..."
#   curl -o "$CERT_LOCAL_PATH" "$CERT_URL"
#   if [ $? -ne 0 ]; then
#     echo "Failed to download the certificate."
#     exit 1
#   fi
#   echo "Certificate downloaded to $CERT_LOCAL_PATH."
# }

# Function to push the certificate to the device
push_certificate_to_device() {
  echo "Pushing certificate to the device..."
  adb push "$CERT_LOCAL_PATH" "$CERT_DEVICE_PATH"
  if [ $? -ne 0 ]; then
    echo "Failed to push the certificate to the device."
    exit 1
  fi
  echo "Certificate pushed to $CERT_DEVICE_PATH."
}

# # Function to install and trust the certificate
# install_and_trust_certificate() {
#   echo "Installing and trusting the certificate..."

 
#   # Push the certificate to the device's trusted store
#   adb push "$CERT_LOCAL_PATH" "/system/etc/security/cacerts/$CERT_NAME"
#   if [ $? -ne 0 ]; then
#     echo "Failed to install the certificate on the device."
#     exit 1
#   fi

#   # Set proper permissions
#   adb shell chmod 644 "/system/etc/security/cacerts/$CERT_NAME"
#   adb shell chown root:root "/system/etc/security/cacerts/$CERT_NAME"

#   echo "Certificate installed and trusted on the device."
# }




# function set_wifi_proxy() {

#   if [ -z "$PROXY_HOST" ] || [ -z "$PROXY_PORT" ]; then
#   return
#   fi

#   echo "Configuring Wi-Fi proxy on the device..."

#   adb shell settings put global http_proxy "$PROXY_HOST:$PROXY_PORT"
#   if [ $? -eq 0 ]; then
#     echo "Wi-Fi proxy configured: $PROXY_HOST:$PROXY_PORT"
#       download_certificate
#       push_certificate_to_device
#       #install_and_trust_certificate
#   else
#     echo "Failed to configure Wi-Fi proxy."
#   fi
# }

function waitForDevice(){
  timeout 60 adb wait-for-device

# Wait until the device is fully booted
while [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" != "1" ]; do
    sleep 2
done

# Ensure the device is responsive
while ! adb shell echo "Device is ready"; do
    sleep 2
done

echo "Device is fully started and ready for further tasks..."
}

function installFrida(){
waitForDevice
adb root
# adb shell "setenforce 0 && mkdir -p /mnt/tmp_system /mnt/tmp_upper /mnt/tmp_work && mount -t tmpfs tmpfs /mnt/tmp_system && cp -r /system/* /mnt/tmp_system/ && mount -t overlay overlay -o lowerdir=/system,upperdir=/mnt/tmp_system,workdir=/mnt/tmp_work /system"
# waitForDevice
# adb push /tmp/local/frida-server /data/local/tmp/frida-server
# adb push /tmp/local/cert-der.crt /data/local/tmp/cert-der.crt
# adb shell "chmod 755 /data/local/tmp/frida-server"
# adb shell "./data/local/tmp/frida-server" &
python3 /tmp/local/F-for-Frida.py
push_certificate_to_device
installApks

}

SUPERVISORD_CONFIG_PATH="${APP_PATH}/mixins/configs/process"
if [[ ${DEVICE_TYPE} == "geny_"* ]]; then
  /usr/bin/supervisord --configuration ${SUPERVISORD_CONFIG_PATH}/supervisord-base.conf & \
  installFrida & \
  wait
elif [[ ${EMULATOR_HEADLESS} == true ]]; then
  /usr/bin/supervisord --configuration ${SUPERVISORD_CONFIG_PATH}/supervisord-port.conf & \
  /usr/bin/supervisord --configuration ${SUPERVISORD_CONFIG_PATH}/supervisord-base.conf & \
  installFrida &\
  wait
else
  /usr/bin/supervisord --configuration ${SUPERVISORD_CONFIG_PATH}/supervisord-screen.conf & \
  /usr/bin/supervisord --configuration ${SUPERVISORD_CONFIG_PATH}/supervisord-port.conf & \
  /usr/bin/supervisord --configuration ${SUPERVISORD_CONFIG_PATH}/supervisord-base.conf & \
  installFrida & \
  wait
fi

