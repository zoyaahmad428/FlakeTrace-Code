# Members and ownership

*Ownership follows [[07-Defense/ownership-map]] (the version defended at the proposal). The
post-defence action plan's two-student split is superseded by the three-member split in
[[07-Defense/decisions/three-member-split]].*

> Member 1 (Zoya) and Member 3 (Zarpash) confirmed their rows on 2026-10-09.

| # | Name | Reg. no. | GitHub | Owns | Folder |
| --- | --- | --- | --- | --- | --- |
| 1 | Zoya Ahmad | 23i-0805 | `zoyaahmad428` | Resource evidence and explanation | `evidence/` |
| 2 | Abdul Raffay | 23i-0587 | `abdulraffay-m` | Bounded search and verification · CLI · CI · integration | `runner/`, `.github/` |
| 3 | Zarpash Nasim | 23i-0027 | `ZarpashNasim` | Evaluation infrastructure · fixtures · statistics · gated repair | `eval/`, `fixtures/` |

**Joint:** contracts, architecture, the Mid report, the evidence worksheet, the deck.

## Current work — update this whenever your task changes

| Member | Current task | Branch | State | Blocked by |
| --- | --- | --- | --- | --- |
| 1 | Static-field + system-property extraction for F1/F2 | `m1/adr006-deepen` | W8 complete: Phases 2–6 and ADR-006 (depth 1–5, pair-mode auto-deepening; fastjson FJ-01/FJ-02 at `depth_used` 4/5); report chapters next | M2 and M3 switch their calls to `analyse_pair` |
| 2 | ADR-008: NOT_REPRODUCED reports, `--order`, valid shuffled orders (design) | `m2/adr-008-not-reproduced` | W6-W10 and panel actions A1/A3/A4/A7 merged (#26-#41); ADR-008 proposed, needs M3 (schema, fixtures F4/N3) | M3 agreement |
| 3 | ADR-008 implemented (NOT_REPRODUCED handling, new fixture cases F4/N3); report ch. 4 and 7–8 per `08-MidEval/README`'s Form 3 table next | `main` | Phases 0–5 done; real `VERIFIED`/`UNRESOLVED` reports produced for F1, F2, F3 (via M2's W10), N1, N2; N3 confirmed `NOT_REPRODUCED` pending M2's `diagnose()` change; F4 confirmed by hand pending M2's order search (see `docs/evidence-m3.md`) | Report chapters need a refresh against current state; worksheet and tag (W12) not started |

## Evidence files per member

| Member | Evidence log | GenAI log |
| --- | --- | --- |
| 1 | `docs/evidence-m1.md` *(create on first run)* | `docs/genai-log-m1.md` *(create)* |
| 2 | `docs/evidence-m2.md` | `docs/genai-log-m2.md` |
| 3 | [[evidence-m3]] | [[genai-log-m3]] |

## Integration owner

**Member 2** merges the final Mid Eval PR, creates the `mid-eval-v1` tag, and keeps CI green —
this sits inside the CLI/CI ownership already defended.
