# Implementation Roadmap — Intake → Quote → Booking Workflow

Tracks the sequential builds that wrap the existing single-image volume-estimation pipeline (`moveai_prototype/`) in the full customer workflow specified in `DESIGN.md`. Each build gets its own plan-mode session: read this file, confirm scope for that build only, execute, verify, update status here, stop. Don't start a build whose dependencies aren't marked complete. Each build's session ends with a commit containing both the code changes and this file's updated status/notes — the status table is only trustworthy if it stays synchronized with git history, so a build isn't real until it's committed.

## How to resume

1. Read `DESIGN.md` first — the product vision and the contracts (especially §5a inter-stage schemas and §5c volume→quote contract) that every build must satisfy.
2. Read this file's status table and build notes below.
3. **Cross-check the status table against `git log`/`git status` before trusting it.** If a build is marked complete but its files aren't in git history, the table is stale — treat git as the source of truth over the table.
4. Pick the next "Not started" build whose dependencies are complete, and scope that build only.

## Known environment constraints

The Hugging Face model cache is not populated in this dev environment, and `moveai_prototype/models.py` sets `local_files_only=True`, so the full 4-stage pipeline cannot run end-to-end here (Grounding DINO download is blocked). This affected Build 1's verification and will affect any later build that needs a live pipeline run (Builds 4–7 in particular). Fallback verification method: exercise the real code path with synthetic/hand-built data (see Build 1's note below) rather than a full pipeline run, and flag in the build notes when this substitution was used.

| # | Build | Depends on | Status |
|---|---|---|---|
| 1 | Axis-semantics fix (`geometry.py`) | — | Complete |
| 2 | SQLite persistence layer (`db.py`) | 1 | Complete |
| 3 | Pricing engine + boxed-goods estimator (`pricing.py`, `boxed_goods.py`, `priors.py` stub) | 1, 2 | Not started |
| 4 | Intake page + job-spine integration into `app.py` | 2 | Not started |
| 5 | Inventory Review page | 2, 3, 4 | Not started |
| 6 | Quote page | 3, 5 | Not started |
| 7 | Booking Confirmation + Company Console pages | 6 | Not started |

## Build notes

**Build 1 — axis-semantics fix.** `ObjectMeasurement.dimensions_m` (`geometry.py`) discarded which fitted-box extent was width/height/depth. Fixed by classifying each local box axis via the box's rotation `box.R` against camera-frame axes (depth ≈ camera-forward, height ≈ up, remainder is width), replacing `dimensions_m: np.ndarray` with named `width_m`/`height_m`/`depth_m` fields and adding `used_axis_aligned_fallback: bool`. Call sites updated: `app.py` (two unpacking sites + UI column labels), `smoke_test.py` (JSON export field names), and `generate_presentation_assets.py` (missed by the original plan — found by grep, consumed `smoke_test.py`'s old `obb_edges_m` JSON key in two places).

Verification note: the full pipeline couldn't run end-to-end in this environment (Grounding DINO isn't cached locally and `local_files_only=True` blocks the download — pre-existing, unrelated to this change). Verified instead with a synthetic-scene unit check that exercises the real `measure_detection`/`_named_dimensions` code path via Open3D: a frontal-shell object correctly resolves `depth_m` as the smallest axis, plus direct checks of `_named_dimensions` against identity and rotated rotation matrices. All four edited files pass `py_compile`.

**Build 2 — SQLite persistence layer.** New `db.py`: tables for `job`, `intake`, `inventory_item` (unifies measured/prior_assisted/declared items and boxed-goods lines via `measurement_basis` + `is_boxed_goods`), `pricing_config` (company-configurable, seeded with a default row, currency HKD), `quote`/`quote_line` (versioned — new quotes are inserted, never mutated, prior version flagged superseded), `booking`. See `DESIGN.md` §5a/§5c for the contracts this schema must satisfy. Stdlib `sqlite3` only, no ORM; module stays free of Streamlit/pipeline imports so it can run without the model stack. `config.py` gained `DB_PATH` (overridable via `MOVEAI_DB_PATH`).

Contracts from §5a/§5c are enforced as schema `CHECK` constraints rather than left as convention: boxed-goods lines can't carry dimensions, `measured` items can't carry `prior_assisted_axes`, `quote_line.surcharge_eligible` is forced to agree with `measurement_basis` (the surcharge contract), and a partial unique index caps `pricing_config` at one active row. `customer_confirmed` is a column separate from `review_state` so confirming an item structurally cannot clear a staff escalation. Quotes are versioned by inserting a new row and flagging the previous one superseded within `create_quote()`, never mutating in place.

Verification: `db_smoke_test.py` (committed) exercises the full job → intake → inventory → quote-v1 → quote-v2 → booking lifecycle against a throwaway SQLite file, including an intake re-submit (upsert, not duplicate), all four inventory line types, the customer-confirm/staff-escalate independence rule, and four negative cases each asserting `sqlite3.IntegrityError` on a `CHECK`/unique-index violation. 24/24 checks pass; `db.py`, `db_smoke_test.py`, and `config.py` pass `py_compile`. No substitution needed — this module needs no model weights, so it was verified for real rather than synthetically.

**Build 3 — pricing engine + boxed-goods estimator.** Pure functions, no I/O, mirroring `pipeline.py`/`geometry.py` staying Streamlit-agnostic. `upper_bound_volume_m3()` is the single place the margin is applied. `access_multiplier()` from intake floor/lift/parking data. Boxed-goods gets its own labour weight on top. `recommend_truck()` stays a separate function from pricing per `DESIGN.md` §5c. `priors.py` is a stub (`flag_implausible_dimension()` always no-flag) — no fabricated class-priors table this milestone.

**Build 4 — Intake page + job spine.** `pages/1_Intake.py` (`st.form` for contact/addresses/floor/lift/parking), `job_id` stored in `st.session_state` and mirrored to `st.query_params` for refresh recovery. `app.py` gets soft `job_id` integration (persists to `db.inventory_item` when a job exists; standalone usage without an intake still works unchanged).

**Build 5 — Inventory Review page.** Implements the `DESIGN.md` §5b interrupt rule: auto-accept unless a concrete signal fires (low detection score, low point count, axis-aligned fallback used, mask touching image border). One proposed number to confirm per flagged item, never a re-capture request. Boxed-goods seeded number is customer-adjustable. `staff_escalate` items are read-only to the customer.

**Build 6 — Quote page.** Loads confirmed inventory + intake access factors + active `pricing_config`, calls `pricing.build_quote()`, displays line items labelled by `measurement_basis`, shows recommended truck, persists as a new quote version on each generation.

**Build 7 — Booking Confirmation + Company Console.** Booking Confirmation creates a `pending_staff_review` booking row. Company Console is a separate, unauthenticated staff view (explicitly flagged as prototype-only, not production-ready) listing bookings with status transitions.

## Explicit scope exclusions (apply across all builds)

No auth, no payments, no real notifications, no video/multi-frame capture, no populated class-priors table, no multi-room logic beyond a `room_count` passthrough parameter, no inventory versioning (only quotes are versioned).
