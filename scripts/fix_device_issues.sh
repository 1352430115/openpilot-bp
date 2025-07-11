#!/usr/bin/env bash
#
# Fix Device Issues - Run this on the Comma device via SSH
#
# Usage:
#   ssh comma@10.0.1.125 'bash -s' < scripts/fix_device_issues.sh
#   OR
#   scp scripts/fix_device_issues.sh comma@10.0.1.125:/tmp/
#   ssh comma@10.0.1.125 "bash /tmp/fix_device_issues.sh"

set -e

echo "================================================"
echo "BluePilot Device Issue Fixer"
echo "================================================"
echo ""

# Fix 1: Kill duplicate manager instances (not forkpty parent/child pairs)
echo "[1/3] Checking for multiple manager instances..."
# manager.py uses forkpty in unblock_stdout(): expect 2 PIDs per instance (parent + child).
count_manager_instances() {
  local n=0
  for pid in $(pgrep -f 'python3 ./manager.py' 2>/dev/null || true); do
    ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    if [ -z "$ppid" ]; then
      continue
    fi
    if ! ps -p "$ppid" -o args= 2>/dev/null | grep -q 'python3 ./manager.py'; then
      n=$((n + 1))
    fi
  done
  echo "$n"
}
MANAGER_INSTANCES=$(count_manager_instances)
MANAGER_PIDS=$(pgrep -f 'python3 ./manager.py' 2>/dev/null || true)

if [ "$MANAGER_INSTANCES" -gt 1 ]; then
    echo "  Found $MANAGER_INSTANCES manager instances ($MANAGER_PIDS raw PIDs)"
    echo "  Keeping the oldest root manager, stopping other instances..."

    ROOT_PID=$(pgrep -f 'python3 ./manager.py' 2>/dev/null | head -1)
    for pid in $MANAGER_PIDS; do
        ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        if ! ps -p "$ppid" -o args= 2>/dev/null | grep -q 'python3 ./manager.py' && [ "$pid" != "$ROOT_PID" ]; then
            echo "  Stopping extra manager instance PID: $pid"
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    sleep 2
    echo "  ✓ Extra manager instances stopped"
else
    echo "  ✓ Single manager instance (forkpty shows ${MANAGER_INSTANCES:-0} root + child PIDs: $MANAGER_PIDS)"
fi

echo ""

# Fix 2: Clean up stale overlay locks (if any exist besides .overlay_init)
echo "[2/3] Cleaning up stale overlay locks..."
cd /data/openpilot
LOCK_FILES=$(find . -maxdepth 1 -name '.overlay*' ! -name '.overlay_init' 2>/dev/null)

if [ -n "$LOCK_FILES" ]; then
    echo "  Found stale lock files:"
    echo "$LOCK_FILES"
    rm -f .overlay_consistent .overlay_lock 2>/dev/null || true
    echo "  ✓ Stale locks removed"
else
    echo "  ✓ No stale locks found"
fi

echo ""

# Fix 3: Verify critical files exist
echo "[3/3] Verifying critical files..."
FILES_TO_CHECK=(
    "/data/openpilot/CHANGELOG.md"
    "/data/openpilot/sunnypilot/common/version.h"
)

ALL_OK=true
for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file exists"
    else
        echo "  ✗ MISSING: $file"
        ALL_OK=false
    fi
done

if [ "$ALL_OK" = true ]; then
    echo "  ✓ All critical files present"
fi

echo ""
echo "================================================"
echo "Fix Complete!"
echo "================================================"
echo ""
echo "Summary:"
echo "  - Manager processes: Fixed (if multiple were running)"
echo "  - Overlay locks: Cleaned"
echo "  - Critical files: Verified"
echo ""
echo "Next steps:"
echo "  1. Check Sentry for new errors: ./scripts/sentry_issues_agent.py stats"
echo "  2. Monitor the device for a few minutes"
echo "  3. If issues persist, check journalctl: journalctl -u comma -f"
echo ""









