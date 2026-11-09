# l2-xhs-images 独立验收（AC-004 / AC-005）

| 字段 | 值 |
|---|---|
| mode_id | beacon-go |
| run_id | run_0b9f727bd66d0ca3f5b1f8b4 |
| stage | qa |
| feature | l2-xhs-images |
| worktree | /tmp/l2-qa-20261110 |
| HEAD | 5818c1f（5818c1fe962ad1741185b3551566e8b7ac76d564，detached） |
| 被验改动 | 882320e |
| baseline | 24a661e |
| maker | 任链接 后端（他人） |
| checker | 验收员（独立） |

## 判定

| AC | 判据 | 结论 | 关键证据 |
|---|---|---|---|
| AC-004 | 两种页面结构都能定位 note 与 imageList；都取不到时报 PARSE_FAILED | PASS | 构造双结构 items 签名完全一致；真实页 5818c1f 成功取到 imageList=1；双缺失抛 PARSE_FAILED |
| AC-005 | 无 state / 坏 JSON / 空列表 / 双结构都取不到，均 502 PARSE_FAILED、items 为空、无调用栈与异常类型 | PASS | 四场景端到端全部 502，ok=false，retryable=true，items=[]，响应无 Traceback/ApiError/Exception |

未做 release 判定，未改代码、truth、tests，未 push，未碰 l7 的 19 项未提交改动。

## 1. 提交审计（882320e）

命令：

```
git -C /tmp/l2-qa-20261110 show --numstat --format='' 882320e
```

原始输出：

```
15	11	container/app/parsers/xhs.py
11	0	docs/beacon/v0.1.0/features/l2-xhs-images/evidence.md
37	0	docs/beacon/v0.1.0/features/l2-xhs-images/evidence/run-20261110-note-fallback/note_from_state.diff
30	0	docs/beacon/v0.1.0/features/l2-xhs-images/evidence/run-20261110-note-fallback/pytest-test_parse-test_stage.txt
6	0	docs/beacon/v0.1.0/features/l2-xhs-images/evidence/run-20261110-note-fallback/pytest-test_xhs.txt
48	0	docs/beacon/v0.1.0/features/l2-xhs-images/evidence/run-20261110-note-fallback/summary.json
92	0	tests/test_xhs.py
```

结论：恰好 7 个文件，与派单清单一致。`tests/test_xhs.py` 新增 92 行、删除 0 行；diff 只在文件末尾追加 4 个用例，既有断言未被触碰或放宽。未夹带 l3/l5/l7 或 truth 正文改动。`git merge-base --is-ancestor 882320e HEAD` 通过，882320e 在 5818c1f 历史内。

## 2. 测试（隔离 venv，jsonschema 4.23.0）

环境：Python 3.9.6；`.venv` 安装 jsonschema 4.23.0、pytest 8.4.2、httpx 0.27.2、pydantic 2.9.2、fastapi 0.115.6、uvicorn 0.34.0、Pillow 11.3.0。`container/requirements.txt` 的 `f2==0.0.1.7` 在 PyPI 已不可解析（最高 0.0.1.6），故按测试实际导入面安装，未安装 f2；该包不参与本组测试导入链。

```
$ ./.venv/bin/python -m pytest tests/test_xhs.py -q
...............                                                          [100%]
15 passed in 1.55s
```

```
$ ./.venv/bin/python -m pytest tests/test_parse.py tests/test_stage.py -q
............                                                             [100%]
12 passed, 2 warnings in 8.67s
```

两组均 exit 0。与 882320e 证据目录登记的 15 passed / 12 passed 一致。

## 3. 真实页面回放

样本：`/private/tmp/xhs_note.html`，71791 字节，note id `6a93b57b0000000007007deb`。结构检查：文件中 `noteDetailMap` 出现 0 次，`noteData` 出现 5 次；`noteData.data.noteData.noteId` 与 URL id 一致。未用构造 HTML 冒充。

脚本只调用 `_extract_state` 与 `_note_from_state`（`/tmp/l2qa-replay/replay.py`），分别在两个 worktree 执行。

5818c1f 原始输出：

```
state keys: ['UseAbExpStore', 'expFlags', 'fakeModal', 'global', 'noteData', 'profile']
note keys: <class 'NoneType'>
noteData present: True
noteData.data keys: ['commentData', 'noteData', 'widgets']
noteData.data.noteData noteId: 6a93b57b0000000007007deb
imageList len: 1
RESULT: OK noteId='6a93b57b0000000007007deb' title='天啊！加拿大水狗弄到宝了' imageList=1
```

1166d3e（反证 worktree /tmp/l2-qa-old-1166d3e）原始输出：

```
state keys: ['UseAbExpStore', 'expFlags', 'fakeModal', 'global', 'noteData', 'profile']
note keys: <class 'NoneType'>
noteData present: True
noteData.data keys: ['commentData', 'noteData', 'widgets']
noteData.data.noteData noteId: 6a93b57b0000000007007deb
imageList len: 1
RESULT: ApiError code='PARSE_FAILED' retryable=True message='页面缺少 noteDetailMap'
```

结论：同一真实页，5818c1f 成功且 imageList 非空（1 张），1166d3e 抛 PARSE_FAILED「页面缺少 noteDetailMap」。与派单预期完全一致。

## 4. AC-004 双结构等价（构造页交叉验证）

脚本 `/tmp/l2qa-replay/ac004_probe.py`，同一 note 分别注入 `note.noteDetailMap[note_id].note` 与 `noteData.data.noteData`，走 `parse_note`：

```
map: note_id=6a0000000000000000000011 title='双结构' items=2 sig=[(0, 'image', 'https://sns-img-qc.xhscdn.com/aa.webp', 'webp'), (1, 'image', 'https://sns-img-qc.xhscdn.com/bb.jpg', 'jpeg')]
noteData: note_id=6a0000000000000000000011 title='双结构' items=2 sig=[(0, 'image', 'https://sns-img-qc.xhscdn.com/aa.webp', 'webp'), (1, 'image', 'https://sns-img-qc.xhscdn.com/bb.jpg', 'jpeg')]
identical: True
both_missing: ApiError code='PARSE_FAILED' retryable=True msg='两种结构都取不到目标笔记'
```

## 5. AC-005 错误口径（端到端 /parse）

脚本 `/tmp/l2qa-replay/ac005_matrix.py` 与 `ac005_empty.py`，TestClient 直打 `POST /parse`，xhs 桩页覆盖四种失败结构：

```
no_state      status=502 ok=False code=PARSE_FAILED retryable=True items=[] no_stack_or_type=True msg=页面没有 window.__INITIAL_STATE__
broken_json   status=502 ok=False code=PARSE_FAILED retryable=True items=[] no_stack_or_type=True msg=初始状态 JSON 解析失败
empty_list    status=502 ok=False code=PARSE_FAILED retryable=True items=[] no_stack_or_type=True msg=imageList 为空或不是数组
both_missing  status=502 ok=False code=PARSE_FAILED retryable=True items=[] no_stack_or_type=True msg=两种结构都取不到目标笔记
```

单个失败响应的完整信封（both_missing）：

```
HTTP status: 502
content-type: application/json
body: {"elapsed_ms": 1, "error": {"code": "PARSE_FAILED", "message": "两种结构都取不到目标笔记", "retryable": true}, "items": [], "ok": false, "resolved_url": ""}
contains 'Traceback': False
contains 'ApiError': False
contains 'Exception': False
contains 'File "': False
contains 'site-packages': False
```

逐条核对：502 是；ok=false 是；error.code=PARSE_FAILED 是；retryable=true 是；items=[] 是；无调用栈、无异常类型 是。

## 观察（不阻塞）

1. 882320e 把旧实现中「noteDetailMap 里没有这个笔记」「条目不是对象」「页面缺少 note 正文」三种消息统一收敛为「两种结构都取不到目标笔记」。错误码与 HTTP 状态未变，AC-005 只约束 code/status/信封，故不影响判定；但对排障可读性有影响，可作为后续优化项。
2. 真实样本只有 1 张图，且只验证了 noteData 结构；map 结构在真实页上的多图顺序未由本样本覆盖，仅由构造用例与单测覆盖。
3. 本次仅判 AC-004/AC-005，未对 AC-001/002/003/006–012 作任何结论，也未作 release 判定。

## 边界

- 未 push、未 commit、未改代码/truth/tests，未 tick goal。
- 主工作区 l7 的 19 项未提交改动未被读取或修改；全部验收在 5818c1f 的独立 worktree 内完成。
- 报告本身是本 worktree 内唯一新增未跟踪文件。

## 工作区状态

```
$ git -C /tmp/l2-qa-20261110 status --short -uall
?? docs/qa/l2-xhs-note-fallback-qa-20261110.md
```

