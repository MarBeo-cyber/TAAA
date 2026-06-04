# Patch Notes — M2 Gated Learning

## Purpose

This patch removes the previous automatic M2 update path from `TAAAAgent` and replaces it with a gated proposal queue.

## Key rule

```text
M2 must never learn automatically from consequential operational events.
```

## Changes

- `SubjectProfile.m2_topology` is now treated as validated operational topology only.
- Added `SubjectProfile.m2_update_queue` for pending review proposals.
- Replaced `_update_m2(...)` with `_propose_m2_update(...)`.
- Added explicit review methods:
  - `approve_m2_proposal(...)`
  - `reject_m2_proposal(...)`
- `PipelineResult` now exposes `m2_update_proposal`.
- Added regression tests for gated behavior.

## Result

Operational daily observations can create reviewable M2 proposals, but cannot mutate `m2_topology` directly.

## Tests

```text
19 passed
```
