#!/bin/bash

# Get the device name from the udev rule
DEVICE="/dev/$1"
USER=$(logname)  # Get the username of the current user
MOUNT_POINT="/media/$USER/$(basename $DEVICE)"

# Create the mount point directory if it doesn't exist
mkdir -p "$MOUNT_POINT"

# Mount the partition with exFAT support
mount "$DEVICE" "$MOUNT_POINT"

# Set permissions so that the user can access the mount point
chown "$USER:$USER" "$MOUNT_POINT"
chmod 755 "$MOUNT_POINT"