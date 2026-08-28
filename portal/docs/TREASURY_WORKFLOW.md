# Treasury workflow: policy amendment versus cash operation

## Treasury policy version

A policy version changes the rules under which future cash-operation requests may be admitted. It includes currency, minimum operating reserve, per-operation limit, allowed operation types, designated signer IDs, approval threshold, base version, and future effective time.

An initial policy or amendment begins `pending_approval`. Every signer must have an active membership in the household and at least one designated signer must be an advisor. Final approval requires the threshold of distinct designated signers and at least one advisor approval. An amendment also requires the approved base to remain the latest version; only one pending amendment may derive from a base. Approval does not make a future version effective early.

## Cash operation

A cash operation is a bounded request evaluated against one approved policy version. It contains an allowed operation type, positive amount under the policy limit, matching currency, target entity in actor scope, future/effective date, rationale, conflict key, governing policy, designated signers, threshold, and expected revision.

The resulting terminal state is `approved_for_intake`, not executed. Final approval requires distinct designated signers and an advisor. A successful approval creates:

- one outbound-only MAS intake envelope with `execution`, `trade`, and `money_movement` equal to `none`;
- one Telegram notification envelope with no bank coordinates;
- one recalculation job.

## Conflict and replay controls

Idempotency returns the original workflow for the same household/key. Active cash operations cannot share a conflict key. Expected revisions reject stale approvals/cancellations. Policy finalization rechecks the base version. Outbox consumers preserve stable IDs and atomically write envelopes before marking delivered.
