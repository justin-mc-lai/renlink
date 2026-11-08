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

# ---- beacon-go ----
cd "$BG" 2>/dev/null && {
  BGL="$(git log --oneline -1)"
  BGAHEAD="$(git log --oneline origin/main..HEAD 2>/dev/null | wc -l | tr -d ' ')"
} || { BGL="n/a"; BGAHEAD=0; }

{
  echo "== $TS =="
  echo "renlink: dirty=$DIRTY ahead=$AHEAD l3=$L3 l4=$L4 frontend_build=$FE_BUILD"
  echo "beacon-go: $BGL ahead=$BGAHEAD"
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

printf '%s | dirty=%s ahead=%s l3=%s l4=%s fe=%s bg_ahead=%s | %s\n' \
  "$TS" "$DIRTY" "$AHEAD" "$L3" "$L4" "$FE_BUILD" "$BGAHEAD" \
  "${ATTENTION[*]:-ok}" >> "$LOG_DIR/hourly-status.log"

# keep 72 hourly files
ls -1t "$LOG_DIR"/[0-9]*.log 2>/dev/null | tail -n +73 | xargs -r rm -f

# ---- alert the room (dedup: same alert text within 3h) ----
if [ ${#ATTENTION[@]} -gt 0 ]; then
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

exit 0
