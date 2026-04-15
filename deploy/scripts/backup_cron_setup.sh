#!/usr/bin/env bash
set -euo pipefail

# 安装每日凌晨 3 点的数据库备份 cron job
# 用法: bash deploy/scripts/backup_cron_setup.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/pg_backup.sh"
LOG_DIR="$SCRIPT_DIR/../data/logs"
mkdir -p "$LOG_DIR"

CRON_LINE="0 3 * * * $BACKUP_SCRIPT >> $LOG_DIR/backup.log 2>&1"

# 避免重复添加
if crontab -l 2>/dev/null | grep -qF "$BACKUP_SCRIPT"; then
    echo "backup cron already installed"
else
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "backup cron installed: $CRON_LINE"
fi
