#!/usr/bin/env bash
# Mount an OCI block volume on Oracle Linux 9 for WorkforceOS data.
# Run as root after attaching the volume in OCI Console.
#
# Usage:
#   sudo bash mount-block-volume-ol9.sh
#   sudo bash mount-block-volume-ol9.sh /dev/sdb
#   sudo DEVICE=/dev/sdb MOUNT=/data/eldercareops sudo -E bash mount-block-volume-ol9.sh
#
# Recommended mount points (pick one):
#   /data/eldercareops     — app, uploads, backups (this script default)
#   /var/lib/eldercareops  — match UPLOAD_DIR in backend .env

set -euo pipefail

MOUNT="${MOUNT:-/data/eldercareops}"
DEVICE="${DEVICE:-}"

echo "==> Block devices:"
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL

if [[ -z "$DEVICE" ]]; then
  echo ""
  echo "Set DEVICE to the data disk (not the boot disk), e.g.:"
  echo "  export DEVICE=/dev/sdb"
  echo "  sudo -E bash $0"
  exit 1
fi

if [[ ! -b "$DEVICE" ]]; then
  echo "ERROR: $DEVICE is not a block device. Attach volume in OCI or run iSCSI connect first."
  exit 1
fi

mkdir -p "$MOUNT"

if ! blkid "$DEVICE" &>/dev/null; then
  echo "==> Formatting $DEVICE with xfs (first use only)..."
  mkfs.xfs -f "$DEVICE"
fi

UUID=$(blkid -s UUID -o value "$DEVICE")
echo "==> UUID=$UUID"

if ! grep -q "$UUID" /etc/fstab; then
  echo "UUID=$UUID $MOUNT xfs defaults,nofail 0 2" >> /etc/fstab
  echo "Added fstab entry."
fi

mount -a
echo "==> Mounted:"
df -h "$MOUNT"

mkdir -p "$MOUNT"/{app,uploads,backups,pgsql}
chown -R eldercareops:eldercareops "$MOUNT" 2>/dev/null || true
chown -R postgres:postgres "$MOUNT/pgsql" 2>/dev/null || true
chmod 700 "$MOUNT"

echo ""
echo "Done. Suggested .env paths:"
echo "  UPLOAD_DIR=$MOUNT/uploads"
echo "  Clone app to $MOUNT/app or symlink /opt/eldercareops -> $MOUNT/app"
