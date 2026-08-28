# Operations runbook

## Daily

Check API readiness, PostgreSQL pool errors, scanner readiness/definition age, scan/delete/outbox/recalculation queue age, retry/dead-letter counts, quarantine growth, bucket access-denied anomalies, login/rate-limit anomalies, and outbound-directory disk capacity. Investigate age, not merely count.

## Weekly

Reconcile document database state against bucket presence/size/hash samples; abort expired multipart uploads; review advisor/operations membership changes; verify outbox atomic-write and replay behavior; review rejected files and scanner causes; confirm no portal object is publicly accessible.

## Monthly

Patch base images and scanners, rotate non-production keys, test user/session revocation, review IAM/database grants, verify backup completion, and execute one sample restore/reconciliation. Production key rotation follows the approved key schedule and incident requirements.

## Queue handling

Worker claims are idempotent and use `SKIP LOCKED`. A worker must complete or retry through RPC; it must not update queue tables directly. When an external outbound destination is unavailable, retain the stable envelope ID and payload, increment attempts, apply bounded backoff, and do not synthesize a new workflow.

## Reconciliation invariants

- `quarantined/scanning` document: quarantine key exists; clean key absent.
- `ready_for_review/accepted`: clean key exists and matches authoritative hash/size; quarantine absent.
- `duplicate`: points to an existing same-household document; redundant object is absent after delete job.
- `deleted`: object bytes absent after job; immutable deletion receipt remains.
- `approved_for_intake`: no execution state other than `not_executable`; outbound/recalculation side effects have stable aggregate ID.
