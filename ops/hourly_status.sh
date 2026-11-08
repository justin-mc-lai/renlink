#!/usr/bin/env bash
# Hourly progress check for the renlink delivery.
# Writes a log line set every run; messages the room only when something needs a human.
set -uo pipefail

ROOT="$HOME/Developer/Personal/renlink"
BG="$HOME/Developer/Personal/products/beacon-go"
OM="$HOME/.agents/skills/qi-dev/qi-dev-openmausbot/scripts/om.sh"
LOG_DIR="$ROOT/logs/hourly"
STATE="$LOG_DIR/.last-alert"
mkdir -p "$LOG_DIR"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin"

TS="$(date '+%Y-%m-%d %H:%M')"
STAMP="$(date '+%Y%m%d-%H%M')"
OUT="$LOG_DIR/$STAMP.log"
ATTENTION=()

# ---- renlink ----
cd "$ROOT" || exit 1
DIRTY="$(git status --porcelain --untracked-files=all | wc -l | tr -d ' ')"
AHEAD="$(git log --oneline origin/main..HEAD 2>/dev/null | wc -l | tr -d ' ')"
TRUTH="$($HOME/.local/bin/beacon-go truth list --project . 2>/dev/null | head -9)"
L3="$(printf '%s\n' "$TRUTH" | awk '$1=="l3-media-delivery"{print $3}')"
L4="$(printf '%s\n' "$TRUTH" | awk '$1=="l4-session-egress"{print $3}')"
FE_BUILD="missing"; [ -f "$ROOT/frontend/dist/build/mp-weixin/app.json" ] && FE_BUILD="present"

# ---- openmausbot (server + dispatch hygiene) ----
OMB_HEALTH="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:8799/health 2>/dev/null || echo 000)"
STALE_DISPATCH="$(/usr/bin/python3 "$ROOT/ops/stale_dispatches.py" 2 2>/dev/null || echo 0)"

# ---- beacon-go ----
cd "$BG" 2>/dev/null && {
  BGL="$(git log --oneline -1)"
  BGAHEAD="$(git rev-list --count origin/main..main 2>/dev/null || echo 0)"
} || { BGL="n/a"; BGAHEAD=0; }

{
  echo "== $TS =="
  echo "renlink: dirty=$DIRTY ahead=$AHEAD l3=$L3 l4=$L4 frontend_build=$FE_BUILD"
  echo "beacon-go: $BGL ahead=$BGAHEAD"
  echo "openmausbot: health=$OMB_HEALTH stale_dispatch=$STALE_DISPATCH"
  echo "-- truth --"
  printf '%s\n' "$TRUTH"
  echo "-- recent commits --"
  cd "$ROOT" && git log --oneline -3
} > "$OUT" 2>&1

# ---- attention rules ----
[ "$DIRTY" -gt 0 ] && ATTENTION+=("renlink 有 $DIRTY 个未提交改动")
[ "$AHEAD" -gt 0 ] && ATTENTION+=("renlink 有 $AHEAD 个提交未推送")
[ "$FE_BUILD" = "missing" ] && ATTENTION+=("前端 mp-weixin 构建产物缺失")
[ "$L3" != "frozen/Freeze" ] && ATTENTION+=("l3 truth 未冻结($L3)")
[ "$L4" != "frozen/Freeze" ] && ATTENTION+=("l4 truth 未冻结($L4)")
[ "$BGAHEAD" -gt 0 ] && ATTENTION+=("beacon-go 有 $BGAHEAD 个提交未推送")
[ "$OMB_HEALTH" = "200" ] || ATTENTION+=("OpenMausBot server 不可达($OMB_HEALTH)")
[ "${STALE_DISPATCH:-0}" -gt 0 ] && ATTENTION+=("有 $STALE_DISPATCH 个派活超 2h 未验收")

printf '%s | dirty=%s ahead=%s l3=%s l4=%s fe=%s bg_ahead=%s | %s\n' \
  "$TS" "$DIRTY" "$AHEAD" "$L3" "$L4" "$FE_BUILD" "$BGAHEAD" \
  "${ATTENTION[*]:-ok}" >> "$LOG_DIR/hourly-status.log"

# keep 72 hourly files
ls -1t "$LOG_DIR"/[0-9]*.log 2>/dev/null | tail -n +73 | xargs -r rm -f

# ---- alert the room (dedup: same alert text within 3h) ----
if [ "${HOURLY_NO_SEND:-0}" = "1" ]; then
  :
elif [ ${#ATTENTION[@]} -gt 0 ]; then
  CUR="${ATTENTION[*]}"
  LAST="$(cat "$STATE" 2>/dev/null || true)"
  AGE=99999
  [ -f "$STATE" ] && AGE=$(( $(date +%s) - $(stat -f %m "$STATE" 2>/dev/null || echo 0) ))
  if [ "$CUR" != "$LAST" ] || [ "$AGE" -ge 10800 ]; then
    printf '%s' "$CUR" > "$STATE"
    TEXT="[hourly] ${TS} 进度检查发现：$(printf '%s；' "${ATTENTION[@]}")请核对。日志：$LOG_DIR/hourly-status.log"
    OPENMAUSBOT_TOKEN="$(cat "$HOME/.openmausbot/cli.token" 2>/dev/null)" \
    OPENMAUSBOT_URL="http://127.0.0.1:8799" \
      "$OM" send "Renlink · 任链接开发群" --text "$TEXT" >/dev/null 2>&1 || true
  fi
else
  : > "$STATE"
fi

# ---- daily digest: one message per day, after 09:00 ----
TODAY="$(date +%Y%m%d)"
DAILY_STATE="$LOG_DIR/.daily-sent"
HOUR="$(date +%H)"; HOUR="${HOUR#0}"; HOUR="${HOUR:-0}"
if { [ "${HOURLY_FORCE_DIGEST:-0}" = "1" ] || [ "$HOUR" -ge 9 ]; } && [ "$(cat "$DAILY_STATE" 2>/dev/null || true)" != "$TODAY" ]; then
  COMMITS="$(git -C "$ROOT" log --since='24 hours ago' --oneline 2>/dev/null | wc -l | tr -d ' ')"
  FROZEN="$(printf '%s\n' "$TRUTH" | grep -c 'frozen/Freeze' || true)"
  SUMMARY="[daily] ${TS} 任链接进度
提交(24h)=${COMMITS} | 未提交=${DIRTY} | 未推送=${AHEAD}
truth 冻结=${FROZEN}/9 | l3=${L3} | l4=${L4} | 前端构建=${FE_BUILD}
beacon-go=${BGL} | 未推送=${BGAHEAD}
关注：${ATTENTION[*]:-无}
日志：$LOG_DIR/hourly-status.log"
  OPENMAUSBOT_TOKEN="$(cat "$HOME/.openmausbot/cli.token" 2>/dev/null)" \
  OPENMAUSBOT_URL="http://127.0.0.1:8799" \
    "$OM" send "Renlink · 任链接开发群" --text "$SUMMARY" >/dev/null 2>&1 \
    && printf '%s' "$TODAY" > "$DAILY_STATE"
fi

exit 0
