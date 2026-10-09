# NEXT

Updated 2026-10-09. No runs since 2026-10-04.

## Open work

1. **Measure a Tier-2 noise band.** Run one harness twice at the same version and model
   (A/A), then any head-to-head (for example opencode against omp on current releases)
   with at least 2 repeats per harness. Until then every verdict stays SNAPSHOT and no
   ranking is a stats-backed WINNER (METHOD.md section 6).
2. **Re-run omp and opencode on current releases.** Tier-2 used omp 18.2.0 and opencode
   1.18.30 while Tier-1 audited 18.2.4 and 1.18.31.
3. **Write down per-criterion Tier-1 scores** for the first eight harnesses (only category
   means survive; nanocodex has them), so every total recomputes exactly.
4. **crush raw evidence**: on the next crush run, commit the `crush session show --json`
   capture next to RESULT.md (the 2026-09-17 capture was not kept).
5. **eve golden trace**: re-run the golden task and capture `eve traces --json` from the
   same session (the committed trace is from an earlier golden session).
6. **Emit the standard from the runners.** The per-harness runner scripts under `t2/`
   write raw evidence only. `scripts/backfill_standard.py` builds the run manifests from
   hand-entered scores plus golden numbers recomputed from that evidence. A new run should
   add its scores there (or a runner should write `runs/<id>/samples.jsonl` directly),
   then `bench-kit stats && bench-kit render`.
7. **Turn bench-lint into a hard check**: drop `--warn-only` in
   `.github/workflows/validate.yml` once the standard has settled here.

## Track (carried from the 2026-10-04 write-up and BENCHMARK.md)

- **dsh**: best-architected of the CLIs and top live score (20/21). Re-evaluate once it
  leaves alpha, emits USD cost in the stream, adds an env-token subscription OAuth path,
  and the published `latest` accepts `--json` again.
- **fx**: re-run on qwen/qwen3.7-flash once a release ships the custom-provider support
  that today exists only in source, so its T8 becomes comparable.
- **nanocodex**: track as the reference driver output contract. Running it on qwen needs a
  way to turn Code Mode off (or a provider that accepts its custom tool).
- **flue**: track for its default env scrub. **eve**: treat as gateway-first.
- Manual check: pi's ~106k GitHub star count looked suspicious at audit time.

## Operator housekeeping noted during the 2026-09-17 run

Status not tracked in this repo (see BENCHMARK.md "Security items surfaced during the
run"): move the plaintext provider key out of the global crush config, and purge stale
bench task logs under the session tmp dir that captured a provider key.
