# Backup and recovery

## Recovery objectives to approve

The implementation does not invent contractual objectives. Proposed starting targets for owner approval are database RPO 15 minutes / RTO 4 hours, object RPO governed by bucket versioning or replication / RTO 8 hours, and configuration RPO at every release / RTO 2 hours.

## Backup sets

1. PostgreSQL physical/PITR backups plus encrypted logical schema-only snapshots for rapid inspection.
2. Quarantine and clean bucket versions/replicas according to approved retention; preserve object metadata and checksums.
3. Deployment manifests, digest-pinned image references, migrations, policies, and non-secret configuration in source control.
4. KMS key metadata and recovery procedure. Never export plaintext production encryption keys into this repository.
5. Outbound MAS/Telegram/email envelope directory and delivery-state database rows until reconciliation/retention permits removal.

## Required controls

Use a dedicated backup identity, encryption in transit/at rest, separate account or failure domain, immutable retention where approved, access logging, quarterly restore drills, and documented destruction. A database restore without object reconciliation is not a successful portal restore.

## Restore sequence

1. Provision isolated network, database, buckets, keys, scanner services, and outbound directories.
2. Restore PostgreSQL to the target point; apply any later ordered migration only after compatibility review.
3. Restore object versions without making them publicly readable.
4. Reconcile every non-deleted document: expected bucket/state, key, authoritative size, SHA-256, scan/receipt record, and duplicate linkage.
5. Reconcile upload multipart state; abort orphaned or expired multipart uploads.
6. Keep outbound dispatch disabled while reconciling outbox IDs and delivered timestamps.
7. Run `scripts/restore_drill.sh` and the complete verification suite.
8. Enable authentication, metadata reads, quarantine uploads/scans, clean downloads, then outbound queues.
9. Record achieved RPO/RTO, missing records, test evidence, and owner sign-off.

## Destructive recovery safeguards

Never overwrite the only surviving backup. Never reclassify a quarantined object as clean based solely on its previous database state. Never replay an outbox row without its stable ID/idempotency check. Never treat a treasury envelope as a trade or movement instruction.
