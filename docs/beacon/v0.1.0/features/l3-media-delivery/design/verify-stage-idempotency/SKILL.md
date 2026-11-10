---
name: verify-stage-idempotency
description: "Verify the /stage idempotency and expiry invariants with TLC. Use when changing stage_cache, routes_stage, store upload, or retry logic."
---

# Verify /stage idempotency

Run the TLA+ model before and after any change to staging, caching or retry code.

## Run

```bash
cd docs/beacon/v0.1.0/features/l3-media-delivery/design
java -cp ~/.local/opt/tla/tla2tools.jar tlc2.TLC -config statechart.cfg statechart.tla
```

Pass: `No error has been found`. Any violation prints the shortest counterexample.

## Prove the check can fail

```bash
java -cp ~/.local/opt/tla/tla2tools.jar tlc2.TLC -config statechart_buggy.cfg statechart_buggy.tla
```

Must report `Invariant NoDoubleUpload is violated`. If it passes, the model is
too weak — fix the model, not the bug.

## Covered code

- `container/app/stage_cache.py` — task cache + idempotent object key
- `container/app/routes_stage.py` — request dedupe, expiry, response shape
- `container/app/stage_store.py` — upload path

## Sync commit

Last confirmed against `acaa7a6` / renlink `b7a6563`. After changing covered
files, re-run and move this commit forward only when the model still describes
the code.
