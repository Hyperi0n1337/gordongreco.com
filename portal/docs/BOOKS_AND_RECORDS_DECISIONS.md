# Books-and-records decision list

These items require the firm's designated owner and, where applicable, qualified legal/compliance review before production. The implementation supplies controls and evidence fields; it does not invent the firm's retention schedule.

| Decision | Options / evidence needed | Code impact |
|---|---|---|
| Are invitation, login, step-up, recovery, revocation, download, review, and deletion events records? | Record class, retention, legal hold, export format, supervisory review. | Audit/receipt retention and export jobs. |
| Are uploaded client documents official records at quarantine, acceptance, or MAS intake? | Define point of record, duplicate treatment, rejected-file retention, client copy rights. | Bucket lifecycle and document-state retention. |
| Are immutable receipts themselves books and records? | Retention, hash verification cadence, correction procedure without mutation. | Receipt export and verification report. |
| Treasury policy versions | Approval evidence, effective/superseded version retention, signer identity evidence. | Policy/approval retention and report. |
| Cash-operation requests | Clarify that `approved_for_intake` is not execution; retain conflicts, cancellations, rationales, signer evidence. | Workflow export and MAS reconciliation. |
| Telegram notifications | Determine whether notification text/metadata is retained as a communication record and where. | Outbox payload minimization and archive connector. |
| Email invitations/magic links | Decide whether template/delivery metadata is retained; never retain plaintext secret token. | Provider delivery receipt mapping. |
| Deletion | Retention expiry, client request, legal hold override, dual approval, storage-version deletion, tombstone duration. | Delete RPC/job and lifecycle policy. |
| Backup copies | Retention extension, legal holds, purge verification, restore access. | Backup policy and deletion evidence. |
| Scanner findings | Retention of signatures/control versions/results; handling of rejected malware. | Findings schema/export. |
| MAS intake | Canonical owner after acceptance, acknowledgement record, duplicate/replay handling, reconciliation cadence. | Outbox delivery adapter and acknowledgement table. |
| Access reviews | Cadence and evidence for advisor/operations memberships and worker/service identities. | Review report and revocation workflow. |
| Client notices/consent | Portal terms, electronic delivery, privacy notice, upload prohibitions, support route. | UI content/version evidence. |

Do not enable automatic permanent deletion, legal-hold behavior, or external communications until these decisions are approved and reflected in migration/configuration changes.
