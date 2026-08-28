# AWS deployment boundary

The Terraform creates private, versioned, KMS-encrypted buckets with public access blocked and short quarantine cleanup. Attach the example IAM policies only after substituting account, region, bucket and KMS identifiers. Keep the API and worker roles separate. The API can initiate quarantine writes and issue clean reads; the worker alone can read quarantine and promote verified content to clean storage.

Enable CloudTrail data events for both buckets and KMS, RDS PostgreSQL encrypted backups and point-in-time recovery, GuardDuty malware findings as a supplemental signal, VPC endpoints for S3/KMS, and alerting on policy changes, public-access changes, KMS denial spikes, scan retries and RLS authorization failures. Supplemental cloud malware detection never replaces the fail-closed libmagic, executable/PDF, ClamAV and qpdf gate in the worker.
