#!/usr/bin/env bash
# 快速发送：整批在【单个 Python 进程】内完成（不再每条重开进程），
# 每 N 条用 --pin-every 轻量重钉窗口（已去掉 SW_RESTORE，不会漂移）。
# 切片写到 $PWD/_send_slice.tmp（用 PWD，不依赖 dirname，规避 Git Bash 垫片 bug）。
#
# 用法: send_onebyone.sh <词表文件> [起始行=1] [结束行=0(全部)] [每条间隔ms=300] [pin_every=5]
set -u

export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:/usr/bin:/bin:$PATH"
VENV_PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
# 用 pwd -W 取 Windows 风格绝对路径（C:/...），否则 POSIX 的 /c/... 路径
# 传给 Windows 原生 Python 会 FileNotFoundError。
HERE="$(pwd -W)"

LIST="${1:?need payload file}"
FROM="${2:-1}"
TO="${3:-0}"
DELAY="${4:-300}"
PIN="${5:-5}"
LOG="$HERE/_onebyone.log"
TMP="$HERE/_send_slice.tmp"

: > "$LOG"
: > "$TMP"

# 抽取 [FROM, TO] 行到临时切片（剥 CRLF 的 \r，跳过注释行与空行）
n=0
while IFS= read -r line; do
  line="${line%$'\r'}"
  n=$((n + 1))
  [ -z "$line" ] && continue
  case "$line" in \#*) continue ;; esac
  if [ "$n" -lt "$FROM" ]; then continue; fi
  if [ "$TO" -gt 0 ] && [ "$n" -gt "$TO" ]; then break; fi
  printf '%s\n' "$line" >> "$TMP"
done < "$LIST"

cnt=$(wc -l < "$TMP" | tr -d ' ')
echo "slice lines=$cnt from=$FROM to=$TO delay=${DELAY}ms pin_every=$PIN" >> "$LOG"
echo "slice lines=$cnt from=$FROM to=$TO delay=${DELAY}ms pin_every=$PIN"

if [ "$cnt" -gt 0 ]; then
  "$VENV_PY" -u qq_gui.py send --file "$TMP" --enter --delay "$DELAY" --pin-every "$PIN" \
      --click-x 600 --click-y 500 >> "$LOG" 2>&1
  rc=$?
else
  rc=0
  echo "nothing to send (slice empty)" >> "$LOG"
fi
echo "rc=$rc" >> "$LOG"
echo "DONE rc=$rc"
rm -f "$TMP"