---
slug: l6-zip-export
version: v0.1.0
materials_status: stale
test_source: acceptance_criteria
env: container-http
---

# Tests: l6-zip-export

主执行方式是 curl：每个用例都给出可直接粘贴的命令与 `jq -e` 断言。`STAGE_STORE=local` 时走 l3 的本地 mock（`cloud://local/`），不需要真实 COS；真实 COS 与真机分享另行标 BLOCKED。执行结果按本轮复跑起始时间建目录落盘，例如 `evidence/run-20261109-0600/case-*.json`；同一用例多次观测加 `a`、`b` 后缀。

## 前置条件

```bash
export PARSE_BASE="http://127.0.0.1:18099"
PORT_MAIN="${PARSE_BASE##*:}"
export STAGE_STORE=local
export STAGE_LOCAL_DIR=/tmp/renlink-stage-store
export STAGE_TASK_TTL_S=600
export ZIP_MAX_IMAGES=50
export ZIP_MAX_BYTES=209715200
export ZIP_TIMEOUT_S=60
export ZIP_CACHE_TTL_S=600
export XHS_NOTE_1="小红书图文真实分享链接（≥2 张）"
export XHS_NOTE_2="小红书图文真实分享链接，与 XHS_NOTE_1 不同（用于未转存 task）"
```

共同步骤：同一进程起服务（/parse 的清单在进程内缓存，必须与 /stage、/zip 同进程）。

```bash
cd /Users/apple/Developer/Personal/renlink/container
STAGE_STORE=local STAGE_LOCAL_DIR=/tmp/renlink-stage-store \
  PARSE_RATE_LIMIT_PER_MIN=0 uvicorn app.main:app --port 18099
```

准备清单、task_id 与前两张图：

```bash
curl -sS -X POST $PARSE_BASE/parse -H 'content-type: application/json' \
  -d '{"url":"'$XHS_NOTE_1'"}' > /tmp/parse.json
jq -e '.ok == true and (.items | length) >= 2' /tmp/parse.json

TASK_ID=$(cd /Users/apple/Developer/Personal/renlink/container && python3 -c \
  'import json; from app.stage_cache import task_id_for; print(task_id_for(json.load(open("/tmp/parse.json"))))')
echo $TASK_ID

python3 /Users/apple/Developer/Personal/renlink/ops/stage_smoke.py \
  --parse-json /tmp/parse.json --index 0 --out /tmp > /tmp/stage-0.json
python3 /Users/apple/Developer/Personal/renlink/ops/stage_smoke.py \
  --parse-json /tmp/parse.json --index 1 --out /tmp > /tmp/stage-1.json
jq -e '.ok == true and (.fileID | startswith("cloud://"))' /tmp/stage-0.json /tmp/stage-1.json
```

读回工具（local 模式）：

```bash
zip_path() { python3 -c 'import sys, os; root = os.environ.get("STAGE_LOCAL_DIR", "/tmp/renlink-stage-store"); print(sys.argv[1].replace("cloud://local/", root.rstrip("/") + "/", 1))' "$1"; }
tmp_zip_count() { ls /tmp/renlink-zip-* 2>/dev/null | wc -l | tr -d ' '; }
task_of() { (cd /Users/apple/Developer/Personal/renlink/container && python3 -c \
  'import json,sys; from app.stage_cache import task_id_for; print(task_id_for(json.load(open(sys.argv[1]))))' "$1"); }

# 在指定端口的实例上 /parse 并逐个 /stage，最后打印该实例的 task_id
setup_task() {
  local port=$1; shift
  curl -sS -X POST "http://127.0.0.1:$port/parse" -H 'content-type: application/json' \
    -d '{"url":"'"$XHS_NOTE_1"'"}' > /tmp/parse-$port.json
  jq -e '.ok == true' /tmp/parse-$port.json >/dev/null
  for i in "$@"; do
    PARSE_BASE="http://127.0.0.1:$port" python3 /Users/apple/Developer/Personal/renlink/ops/stage_smoke.py \
      --parse-json /tmp/parse-$port.json --index "$i" --out /tmp > /dev/null
  done
  task_of /tmp/parse-$port.json
}

store_snapshot() { find "${STAGE_LOCAL_DIR:-/tmp/renlink-stage-store}" -type f \
  -exec stat -f '%N %z %m' {} + 2>/dev/null | sort; }
l3_snapshot() { find "${STAGE_LOCAL_DIR:-/tmp/renlink-stage-store}/l3" -type f \
  -exec stat -f '%N %z %m' {} + 2>/dev/null | sort; }
zip_obj_count() { find "${STAGE_LOCAL_DIR:-/tmp/renlink-stage-store}/l6" -name '*.zip' 2>/dev/null | wc -l | tr -d ' '; }
elapsed_s() { python3 -c 'import sys; print("%.3f" % (float(sys.argv[2]) - float(sys.argv[1])))' "$1" "$2"; }
```

## 覆盖矩阵

| AC ID | TC ID | Layer | Command | Assertion |
|-------|-------|-------|---------|-----------|
| AC-001 | TC-001 | e2e | `curl /zip -d '{"task_id":"'$TASK_ID'"}'` | 200、四字段、count==已转存图数、zip 可打开且条目数==count、读回字节==bytes |
| AC-002 | TC-002 | behavior | `curl /zip -d '{"task_id":...,"indexes":[7,1,7]}'`，前置样本 ≥8 张 | 200、count=2、条目为 `001.<ext>`、`007.<ext>`；样本不足 8 张时记 BLOCKED |
| AC-003 | TC-003 | behavior | 同参数连打两次（`ZIP_FAKE_DELAY_MS=1500`） | 两次 fileID/bytes/count 相同、第二次耗时 <0.3s、对象存储快照不变 |
| AC-004 | TC-004 | negative | 未知 task_id / TTL=1 后调用 | 410、STAGE_EXPIRED、retryable=false、无 fileID |
| AC-005 | TC-005 | negative | 无 bucket、无凭证、本地目录不可写三种实例 | 三种均 503、ZIP_NOT_READY、retryable=true、无 cloud://、无残留 |
| AC-006 | TC-006 | negative | `ZIP_MAX_IMAGES=1` 后请求两张 | 413、TOO_LARGE、无 zip 对象 |
| AC-007 | TC-007 | negative | `ZIP_MAX_BYTES=1` 后请求一张 | 413、TOO_LARGE、无 zip 对象 |
| AC-008 | TC-008 | negative | `ZIP_FAULT_INJECT=read`、`=write`、`=upload` | 三种均 502、ZIP_FAILED、retryable=true、无 fileID |
| AC-009 | TC-009 | negative | 8 类非法输入 | 400、INVALID_REQUEST、retryable=false |
| AC-010 | TC-010 | contract | 成功响应字节数与键集合 | ≤1024000 且键恰为 ok/fileID/bytes/count，无路径与 base64 |
| AC-011 | TC-011 | behavior | 混合已转存/未转存 index；全未转存 index | 只打包已转存且 count 正确、对象存储快照不增（未触发 /stage）；全未转存 400 且无 zip 对象 |
| AC-012 | TC-012 | behavior | 成功与各失败路径后查 /tmp | `renlink-zip-*` 数为 0 |
| AC-013 | TC-013 | negative | `ZIP_TIMEOUT_S=1` + `ZIP_FAKE_DELAY_MS=3000` | 504、TIMEOUT、retryable=true、无 fileID、无残留 |
| AC-014 | TC-014 | behavior | `ZIP_CACHE_TTL_S=0` 连打两次并下载 | 条目名/顺序固定、时间戳 1980-01-01、ZIP_STORED、无目录条目、两次 sha256 相同 |
| AC-015 | TC-015 | device | 体验版点「打包导出 ZIP」 | 手机 shareFileMessage、PC saveFileToDisk、取消/失败文案正确 |
| AC-016 | TC-016 | governance | `git diff --stat` + cookie 请求体 | l1/l3/l5 四件套 diff 为空；cookie 字段 400 INVALID_REQUEST |

## 用例明细

### TC-001 全部已转存图片打包

```bash
curl -sS -X POST $PARSE_BASE/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID'"}' -o /tmp/zip-001.json -w '%{http_code}\n'
jq -e '.ok == true and (.fileID | startswith("cloud://")) and (.bytes > 0)' /tmp/zip-001.json
jq -e --argjson n "$(jq -s '[.[] | select(.ok)] | length' /tmp/stage-0.json /tmp/stage-1.json)" \
  '.count == $n' /tmp/zip-001.json
Z=$(zip_path "$(jq -r .fileID /tmp/zip-001.json)")
[ -f "$Z" ] && [ "$(stat -f%z "$Z")" = "$(jq -r .bytes /tmp/zip-001.json)" ]
[ "$(unzip -l "$Z" | awk 'NR>3 && $1 ~ /^[0-9]+$/ {n++} END {print n+0}')" = "$(jq -r .count /tmp/zip-001.json)" ]
```

判据：HTTP 200；`count` 等于已转存图片数；zip 实际字节等于 `bytes`；`unzip -l` 条目数等于 `count`。

### TC-002 indexes 子集、去重与升序

```bash
# 前置条件：样本清单至少 8 项（index 0..7 可取）。样本不足 8 项时本用例记 BLOCKED，
# 原因写“样本项数 N < 8”，不得改 index 凑过。
N=$(jq '.items | length' /tmp/parse.json)
[ "$N" -ge 8 ]
TASK_ID_002=$(setup_task "$PORT_MAIN" 1 7)
curl -sS -X POST $PARSE_BASE/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_002'","indexes":[7,1,7]}' -o /tmp/zip-002.json -w '%{http_code}\n'
jq -e '.ok == true and .count == 2' /tmp/zip-002.json
Z=$(zip_path "$(jq -r .fileID /tmp/zip-002.json)")
unzip -Z1 "$Z"
unzip -Z1 "$Z" | tr '\n' ' ' | grep -Eq '^001\.[a-z0-9]+ 007\.[a-z0-9]+ $'
[ "$(unzip -Z1 "$Z" | wc -l | tr -d ' ')" = "2" ]
```

判据：HTTP 200；`count=2`；条目按升序为 `001.<ext>`、`007.<ext>`；重复的 7 只出现一次，共 2 个条目。

### TC-003 幂等

```bash
# 18091 实例：ZIP_FAKE_DELAY_MS=1500，缓存 TTL 默认 600，缓存命中时延迟不生效
cd /Users/apple/Developer/Personal/renlink/container
ZIP_FAKE_DELAY_MS=1500 STAGE_STORE=local PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18091

TASK_ID_18091=$(setup_task 18091 0 1)
ZIP_BEFORE=$(zip_obj_count)
T0=$(python3 -c 'import time; print(time.time())')
curl -sS -X POST http://127.0.0.1:18091/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_18091'","indexes":[0,1]}' -o /tmp/zip-003a.json
T1=$(python3 -c 'import time; print(time.time())')
SNAP_BEFORE=$(store_snapshot)
sleep 1
T2=$(python3 -c 'import time; print(time.time())')
curl -sS -X POST http://127.0.0.1:18091/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_18091'","indexes":[1,0]}' -o /tmp/zip-003b.json
T3=$(python3 -c 'import time; print(time.time())')
jq -e '.ok == true' /tmp/zip-003a.json /tmp/zip-003b.json
[ "$(jq -r .fileID /tmp/zip-003a.json)" = "$(jq -r .fileID /tmp/zip-003b.json)" ]
[ "$(jq -r .bytes /tmp/zip-003a.json)" = "$(jq -r .bytes /tmp/zip-003b.json)" ]
[ "$(jq -r .count /tmp/zip-003a.json)" = "$(jq -r .count /tmp/zip-003b.json)" ]
python3 -c 'import sys; assert float(sys.argv[2]) - float(sys.argv[1]) >= 1.5' "$T0" "$T1"
python3 -c 'import sys; assert float(sys.argv[2]) - float(sys.argv[1]) < 0.3' "$T2" "$T3"
SNAP_AFTER=$(store_snapshot)
[ "$SNAP_BEFORE" = "$SNAP_AFTER" ]
[ "$(zip_obj_count)" = "$ZIP_BEFORE" ]
```

判据：两次 `fileID`、`bytes`、`count` 完全相同；第一次带 1500ms 注入延迟，第二次 <0.3s（缓存命中不重打包、不重读源对象）；对象存储快照（路径、大小、mtime）前后一致，`l6/` 下 zip 对象数不增加（无第二次上传、无覆盖写入）。

### TC-004 task 过期

```bash
curl -sS -X POST $PARSE_BASE/zip -H 'content-type: application/json' \
  -d '{"task_id":"st_000000000000000000000000"}' -o /tmp/zip-004a.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "STAGE_EXPIRED" and .error.retryable == false and (has("fileID") | not)' /tmp/zip-004a.json
```

TTL 过期路径：`STAGE_TASK_TTL_S=1` 起 18092 实例，转存 index 0 后等 2 秒再调用：

```bash
STAGE_TASK_TTL_S=1 STAGE_STORE=local PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18092
TASK_ID_TTL=$(setup_task 18092 0)
sleep 2
curl -sS -X POST http://127.0.0.1:18092/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_TTL'"}' -o /tmp/zip-004b.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "STAGE_EXPIRED"' /tmp/zip-004b.json
```

判据与未知 task_id 相同。

### TC-005 存储未就绪

```bash
# (a) 18098：cos 模式且未配置 COS_BUCKET
cd /Users/apple/Developer/Personal/renlink/container
STAGE_STORE=cos COS_BUCKET= COS_SECRET_ID= COS_SECRET_KEY= PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18098

# 清单在进程内，必须在 18098 上重新 /parse 并用同一算法算 task_id
TASK_ID_18098=$(setup_task 18098)
curl -sS -X POST http://127.0.0.1:18098/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_18098'"}' -o /tmp/zip-005a.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "ZIP_NOT_READY" and .error.retryable == true' /tmp/zip-005a.json
! grep -q 'cloud://' /tmp/zip-005a.json
[ "$(tmp_zip_count)" = "0" ]

# (b) 18089：cos 模式有 bucket、凭证为空
STAGE_STORE=cos COS_BUCKET=renlink-test-bucket COS_SECRET_ID= COS_SECRET_KEY= PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18089
TASK_ID_18089=$(setup_task 18089)
curl -sS -X POST http://127.0.0.1:18089/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_18089'"}' -o /tmp/zip-005b.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "ZIP_NOT_READY" and .error.retryable == true' /tmp/zip-005b.json
! grep -q 'cloud://' /tmp/zip-005b.json
[ "$(tmp_zip_count)" = "0" ]

# (c) 18088：local 模式但存储目录不可写（macOS 只读卷下的路径，mkdir 返回 EROFS）
STAGE_STORE=local STAGE_LOCAL_DIR=/System/renlink-no-write PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18088
TASK_ID_18088=$(setup_task 18088)
curl -sS -X POST http://127.0.0.1:18088/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_18088'"}' -o /tmp/zip-005c.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "ZIP_NOT_READY" and .error.retryable == true' /tmp/zip-005c.json
! grep -q 'cloud://' /tmp/zip-005c.json
[ "$(tmp_zip_count)" = "0" ]
```

判据：(a)(b)(c) 三种情形均 HTTP 503、`ZIP_NOT_READY`、`retryable=true`；响应不含 `cloud://`；`/tmp` 无新增 `renlink-zip-*`。存储就绪检查先于选图，未转存的清单也返回 503 而不是 400。

### TC-006 图片数量上限

```bash
# 18097 实例：ZIP_MAX_IMAGES=1，先转存 index 0 与 1
cd /Users/apple/Developer/Personal/renlink/container
ZIP_MAX_IMAGES=1 STAGE_STORE=local PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18097

TASK_ID_18097=$(setup_task 18097 0 1)
curl -sS -X POST http://127.0.0.1:18097/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_18097'"}' -o /tmp/zip-006.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "TOO_LARGE" and .error.retryable == false' /tmp/zip-006.json
[ "$(find /tmp/renlink-stage-store/l6 -name '*.zip' 2>/dev/null | wc -l | tr -d ' ')" = "0" ]
```

判据：HTTP 413；`TOO_LARGE`；不产生 zip 对象。真实 51 张样本走默认 50 的验证见 BLOCKED 清单。

### TC-007 zip 总量上限

```bash
# 18096 实例：ZIP_MAX_BYTES=1，先转存 index 0
cd /Users/apple/Developer/Personal/renlink/container
ZIP_MAX_BYTES=1 STAGE_STORE=local PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18096

TASK_ID_18096=$(setup_task 18096 0)
curl -sS -X POST http://127.0.0.1:18096/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_18096'","indexes":[0]}' -o /tmp/zip-007.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "TOO_LARGE"' /tmp/zip-007.json
[ "$(find /tmp/renlink-stage-store/l6 -name '*.zip' 2>/dev/null | wc -l | tr -d ' ')" = "0" ]
```

判据：HTTP 413；`TOO_LARGE`；不产生 zip 对象。默认 200MB 的真实样本验证见 BLOCKED 清单。

### TC-008 打包/上传失败

```bash
# 18095 实例：ZIP_FAULT_INJECT=read
ZIP_FAULT_INJECT=read STAGE_STORE=local PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18095

TASK_ID_18095=$(setup_task 18095 0 1)
curl -sS -X POST http://127.0.0.1:18095/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_18095'"}' -o /tmp/zip-008-read.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "ZIP_FAILED" and .error.retryable == true and (has("fileID") | not)' /tmp/zip-008-read.json
[ "$(tmp_zip_count)" = "0" ]

# 18085 实例：ZIP_FAULT_INJECT=write（打包落盘阶段失败）
ZIP_FAULT_INJECT=write STAGE_STORE=local PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18085
TASK_ID_18085=$(setup_task 18085 0 1)
curl -sS -X POST http://127.0.0.1:18085/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_18085'"}' -o /tmp/zip-008-write.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "ZIP_FAILED" and .error.retryable == true and (has("fileID") | not)' /tmp/zip-008-write.json
[ "$(tmp_zip_count)" = "0" ]

# 18075 实例：ZIP_FAULT_INJECT=upload（zip 已生成、上传失败）
ZIP_FAULT_INJECT=upload STAGE_STORE=local PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18075
TASK_ID_18075=$(setup_task 18075 0 1)
curl -sS -X POST http://127.0.0.1:18075/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_18075'"}' -o /tmp/zip-008-upload.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "ZIP_FAILED" and .error.retryable == true and (has("fileID") | not)' /tmp/zip-008-upload.json
[ "$(zip_obj_count)" = "0" ]
[ "$(tmp_zip_count)" = "0" ]
```

判据：`read`、`write`、`upload` 三种注入均 HTTP 502、`ZIP_FAILED`、`retryable=true`、响应无 fileID；三种路径均无残留 `renlink-zip-*`，`upload` 失败不产生 zip 对象。

### TC-009 非法请求（8 类）

```bash
for body in \
  '{}' \
  '{"task_id":"bad"}' \
  '{"task_id":"'$TASK_ID'","indexes":1}' \
  '{"task_id":"'$TASK_ID'","indexes":[0,"1"]}' \
  '{"task_id":"'$TASK_ID'","indexes":[-1]}' \
  '{"task_id":"'$TASK_ID'","indexes":[99999]}' \
  '{"task_id":"'$TASK_ID'","indexes":[]}' \
  'not-json'; do
  code=$(curl -sS -X POST $PARSE_BASE/zip -H 'content-type: application/json' -d "$body" \
    -o /tmp/zip-009.json -w '%{http_code}')
  [ "$code" = "400" ] && jq -e '.ok == false and .error.code == "INVALID_REQUEST" and .error.retryable == false' /tmp/zip-009.json
 done
```

显式视频 index 另加一条：从清单取 `select(.type=="video") | .index` 作为 `indexes`，同样判 400 INVALID_REQUEST。清单内但未转存的 index 不在此列（见 TC-011）。

### TC-010 响应形状与体积

```bash
curl -sS -X POST $PARSE_BASE/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID'"}' -o /tmp/zip-010.json
[ "$(wc -c < /tmp/zip-010.json | tr -d ' ')" -le 1024000 ]
jq -e 'keys_unsorted == ["ok","fileID","bytes","count"] or (keys | sort) == ["bytes","count","fileID","ok"]' /tmp/zip-010.json
! grep -Eq 'base64|/tmp/|file://|data:' /tmp/zip-010.json
```

判据：≤1024000 字节；键集合恰为四个；无 base64、`/tmp/`、绝对路径或 data URI。

### TC-011 只打已转存，不重跑 /stage

```bash
# 只转存 index 0；清单里 index 1 未转存
# 前置条件里主实例已转存 0、1，本用例另起 18087 与独立存储目录，保证 index 1 确实未转存
export STAGE_LOCAL_DIR=/tmp/renlink-stage-store-011
cd /Users/apple/Developer/Personal/renlink/container
STAGE_STORE=local STAGE_LOCAL_DIR=$STAGE_LOCAL_DIR PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18087

TASK_ID_011=$(setup_task 18087 0)
L3_BEFORE=$(l3_snapshot)
curl -sS -X POST http://127.0.0.1:18087/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_011'","indexes":[0,1]}' -o /tmp/zip-011.json -w '%{http_code}\n'
jq -e '.ok == true and .count == 1' /tmp/zip-011.json
unzip -Z1 "$(zip_path "$(jq -r .fileID /tmp/zip-011.json)")" | grep -q '^000\.'
! unzip -Z1 "$(zip_path "$(jq -r .fileID /tmp/zip-011.json)")" | grep -q '^001\.'
L3_AFTER=$(l3_snapshot)
[ "$L3_BEFORE" = "$L3_AFTER" ]

# 全未转存：新 parse 一个 task（不 stage），只传未转存 index
curl -sS -X POST http://127.0.0.1:18087/parse -H 'content-type: application/json' \
  -d '{"url":"'$XHS_NOTE_2'"}' > /tmp/parse-fresh.json
jq -e '.ok == true' /tmp/parse-fresh.json
TASK_ID_FRESH=$(task_of /tmp/parse-fresh.json)
[ "$TASK_ID_FRESH" != "$TASK_ID_011" ]
ZIP_BEFORE=$(zip_obj_count)
curl -sS -X POST http://127.0.0.1:18087/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_FRESH'","indexes":[0]}' -o /tmp/zip-011b.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "INVALID_REQUEST"' /tmp/zip-011b.json
[ "$(zip_obj_count)" = "$ZIP_BEFORE" ]
export STAGE_LOCAL_DIR=/tmp/renlink-stage-store
```

判据：混合请求 `count=1` 且只有已转存条目；打包前后 l3 对象快照（路径、大小、mtime）完全一致，即未对未转存 index 触发 `/stage`（触发会新增 `l3/<content_id>/1.<ext>`）；全未转存 400 且 zip 对象数不变。

### TC-012 临时文件清理

```bash
[ "$(tmp_zip_count)" = "0" ]
# 依次执行 TC-001、TC-006、TC-008、TC-013 后再断言一次
[ "$(tmp_zip_count)" = "0" ]
```

判据：成功与失败路径结束后 `ls /tmp/renlink-zip-*` 均为空。

### TC-013 60s 硬上限

```bash
# 18094 实例：ZIP_TIMEOUT_S=1、ZIP_FAKE_DELAY_MS=3000
ZIP_TIMEOUT_S=1 ZIP_FAKE_DELAY_MS=3000 STAGE_STORE=local PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18094

TASK_ID_18094=$(setup_task 18094 0 1)
curl -sS -X POST http://127.0.0.1:18094/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID_18094'"}' -o /tmp/zip-013.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "TIMEOUT" and .error.retryable == true and (has("fileID") | not)' /tmp/zip-013.json
[ "$(tmp_zip_count)" = "0" ]
```

判据：HTTP 504；`TIMEOUT`；无 fileID；临时文件已清。

### TC-014 zip 内容与字节稳定

```bash
# 18093 实例：ZIP_CACHE_TTL_S=0（禁用缓存，强制重打）
ZIP_CACHE_TTL_S=0 STAGE_STORE=local PARSE_RATE_LIMIT_PER_MIN=0 \
  uvicorn app.main:app --port 18093

TASK_ID_18093=$(setup_task 18093 0 1)
for i in 1 2; do
  curl -sS -X POST http://127.0.0.1:18093/zip -H 'content-type: application/json' \
    -d '{"task_id":"'$TASK_ID_18093'","indexes":[0,1]}' -o /tmp/zip-014-$i.json
  cp "$(zip_path "$(jq -r .fileID /tmp/zip-014-$i.json)")" /tmp/zip-014-$i.zip
done
shasum -a 256 /tmp/zip-014-1.zip /tmp/zip-014-2.zip
[ "$(shasum -a 256 /tmp/zip-014-1.zip | cut -d' ' -f1)" = "$(shasum -a 256 /tmp/zip-014-2.zip | cut -d' ' -f1)" ]
python3 - /tmp/zip-014-1.zip <<'PY'
import re, sys, zipfile

infos = zipfile.ZipFile(sys.argv[1]).infolist()
names = [i.filename for i in infos]
assert len(infos) == 2, names
assert names == sorted(names), names
assert all(re.fullmatch(r"\d{3}\.[a-z0-9]+", n) for n in names), names
assert [n[:3] for n in names] == ["000", "001"], names
assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in infos), [i.date_time for i in infos]
assert all(i.compress_type == zipfile.ZIP_STORED for i in infos), [i.compress_type for i in infos]
assert all(not i.is_dir() and not n.endswith("/") for i, n in zip(infos, names)), names
print("OK", names, infos[0].date_time, infos[0].compress_type)
PY
# 同一文件再用 zipinfo 复核时间戳与目录条目（DOS 时间粒度为 2 秒，这里要求整点 0 秒）
Z=$(zip_path "$(jq -r .fileID /tmp/zip-014-1.json)")
[ "$(zipinfo -v "$Z" | grep -Ec 'DOS date/time\): +1980 Jan 1 00:00:00')" = "2" ]
! zipinfo -1 "$Z" | grep -q '/$'
```

判据：两次 sha256 相同；条目名 `000.<ext>`、`001.<ext>` 升序；每个条目的 DOS 时间坐标恰为 `(1980, 1, 1, 0, 0, 0)`；压缩方式 ZIP_STORED；无目录条目。

### TC-015 端侧转发（体验版真机）

1. 图文解析 → 逐张保存（或直接点「打包导出 ZIP」）→ 走 `/zip` 拿 fileID。
2. 手机：`wx.cloud.downloadFile({fileID})` 后 `wx.shareFileMessage({filePath, fileName})`，会话选择面板出现，转发到文件传输助手成功。
3. PC 微信开发者工具/Windows：降级 `wx.saveFileToDisk`，保存对话框出现且文件落盘。
4. 取消分享：提示「已取消分享」；下载失败：提示「ZIP 下载失败，请重试」；`ZIP_NOT_READY`：提示「打包服务暂不可用，请稍后再试」；`TOO_LARGE`：提示「图片太多或太大，请分批保存」；`STAGE_EXPIRED`：提示「链接信息已过期，请重新解析」；`ZIP_FAILED`：提示「打包失败，请重试」；`INVALID_REQUEST`：提示「还没有可打包的图片」。

判据：三条路径（手机转发、电脑存盘、失败文案）均有人工截图或录屏，登记 evidence。

### TC-016 依赖边界

```bash
cd /Users/apple/Developer/Personal/renlink
git diff --stat -- docs/beacon/v0.1.0/features/l1-parser-core \
  docs/beacon/v0.1.0/features/l3-media-delivery \
  docs/beacon/v0.1.0/features/l5-miniprogram-pages
# 期望：无输出（本湖冻结时不得改已冻结正文）

curl -sS -X POST $PARSE_BASE/zip -H 'content-type: application/json' \
  -d '{"task_id":"'$TASK_ID'","cookie":"x"}' -o /tmp/zip-016.json -w '%{http_code}\n'
jq -e '.ok == false and .error.code == "INVALID_REQUEST"' /tmp/zip-016.json
```

判据：三湖四件套无 diff；cookie 字段 400 INVALID_REQUEST；`/parse`、`/stage` 响应字段与 l1/l3 冻结契约一致（复跑 l3 的 case-response-shape 与 l1 schema 校验）。

## BLOCKED：需要真实环境才能完成的项

| 项 | 关联 | 阻塞原因 | 解除条件 |
|----|------|----------|----------|
| 真实 COS 上传与回读（`STAGE_STORE=cos`） | TC-001、TC-003、TC-005 | 本机无生产 COS 桶与临时密钥 | 注入 `COS_BUCKET`/`COS_REGION` 与凭证后复跑，evidence 写明 store 模式 |
| 默认 50 张上限的真实 51 张图文样本 | TC-006 | 现有真实样本不足 51 张 | 找到 ≥51 张图文笔记，用默认 `ZIP_MAX_IMAGES=50` 复跑 |
| 默认 200MB 上限的真实样本 | TC-007 | 本机没有可打包到 200MB 的已转存图片集 | 造出 >200MB 已转存图集后用默认 `ZIP_MAX_BYTES` 复跑 |
| 真机 `wx.shareFileMessage` / PC `wx.saveFileToDisk` | TC-015 | 需要体验版微信与真机/Windows 客户端 | 体验版发布后按 TC-015 手工验收 |
| 真实 COS 下的 60s 超时 | TC-013 | local 注入只能证明超时分支 | 生产桶下用大包或注入延迟复跑 |
