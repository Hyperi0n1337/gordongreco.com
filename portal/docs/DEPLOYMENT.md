# Deployment guide

## Required services

PostgreSQL 16+, two private S3-compatible buckets, KMS or equivalent envelope encryption, ClamAV daemon, libmagic, qpdf, TLS ingress/WAF, secret manager, immutable audit/log sink, and a private filesystem or queue for outbound MAS/Telegram/email envelopes.

## Separation

Deploy `apps/public-site` independently on the public marketing origin. Deploy `portal-web`, API, and worker in the private portal environment. The public site must never proxy database, object, or portal API traffic. `client.html` remains only the orientation shell.

## Database

Apply `migrations/0001...0009` with an administrative migration identity. Runtime roles are `NOINHERIT NOBYPASSRLS`; enable LOGIN only through deployment-time secrets. API and worker use separate connection strings. Never connect runtime processes as schema owner or superuser.

## Containers

`deploy/docker/compose.yaml` is a local integration template. Set every `*_IMAGE` variable to an immutable digest-pinned reference. The Dockerfiles intentionally require an explicit Python base image argument. Do not promote the local vault or fictional fixtures to production.

## Kubernetes

Templates set a read-only root filesystem, non-root UID, dropped Linux capabilities, seccomp runtime default, resource limits, no service-account token automount, API/worker network policies, PodDisruptionBudget, and TLS ingress. Replace placeholder secrets through an external secret manager; do not commit Secret objects.

## AWS

Terraform templates create private/versioned/encrypted buckets with public-access blocks and lifecycle rules. IAM examples separate API capability signing/object metadata access from worker quarantine/clean copy/delete access. Tighten ARNs, KMS conditions, VPC endpoints, object-lock decision, logging destination, and cross-account backup before apply.

## Release gate

1. Build from a clean checkout and hash-locked dependencies/wheelhouse.
2. Run unit/security tests, ephemeral PostgreSQL/RLS tests, scanner integration tests, dependency/SBOM/vulnerability checks, and container policy tests.
3. Apply migrations to staging and run backup/restore plus object reconciliation.
4. Perform authorization abuse tests with two households and repeated entity IDs.
5. Confirm outbound connectors point to non-production sinks until owner approval.
6. Deploy canary API/worker, verify health and scanner definitions, then enable portal ingress.
