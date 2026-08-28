# Kubernetes release template

These manifests are intentionally non-deploying templates. Replace the `.test` host, create `portal-secrets` through the platform secret manager, bind the two service accounts to separate cloud IAM roles, and replace each image marker with a verified digest. Do not apply `portal-secrets-example-do-not-apply`.

The portal UI and public site should be published as separate immutable static artifacts. Route `/api/*` only to `portal-api`; do not place private objects behind the static origin. The worker requires database, KMS, object-storage, ClamAV, qpdf, and outbound intake access, but no inbound Service.
