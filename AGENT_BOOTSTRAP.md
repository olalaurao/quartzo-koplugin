# Quartzo KOReader Plugin — Agent Bootstrap

This repository is intentionally plan-first. Before implementing anything:

1. Read `STATUS.md` completely.
2. Read `IMPLEMENTATION_SPEC.md` completely. It is the canonical execution specification.
3. Read `PLAN.md` completely. It is the canonical product scope and roadmap.
4. Re-read the current upstream Quartzo architecture before coding:
   - `olalaurao/aplicativo/AGENT_BOOTSTRAP.md`
   - `olalaurao/aplicativo/agents.md`
   - applicable active specs under `olalaurao/aplicativo/docs/specs/`
   - current Resource model and persistence contract.
5. Re-read the current Quartzo Obsidian Companion architecture/contracts before changing any vault or cross-client behavior.
6. Re-read the current `olalaurao/reader` implementation and status before adding optional Readwise Reader integration.
7. Re-verify the target KOReader version and the exact `statistics.sqlite3` schema on the pinned target version.
8. Do not implement later phases while an earlier gate is open.
9. Do not create a parallel source of truth in Quartzo. Reading Activity must have an explicitly documented canonical persistence owner upstream before production sync is implemented.
10. Never write to KOReader's `statistics.sqlite3`; it is owned by KOReader Reading Statistics.
11. Never infer document identity from title alone.
12. Update `STATUS.md` after every meaningful implementation session, including branch/commit, tests, device evidence, open blockers and the exact next step.
13. Run all automated and physical-device gates required by `IMPLEMENTATION_SPEC.md` before declaring a phase complete.

## Dependency rule

Implementation is intentionally deferred until the current `olalaurao/reader` Readwise Reader plugin reaches a stable V1/tag, unless the user explicitly changes that sequencing decision.

## Authority order

1. Current user request.
2. `IMPLEMENTATION_SPEC.md`.
3. `PLAN.md`.
4. Current upstream Quartzo canonical architecture/contracts.
5. Current KOReader behavior on the pinned target version.
6. Existing code.

If implementation evidence invalidates an assumption in the spec, update the spec deliberately in the same change and explain the reason in `STATUS.md`.
