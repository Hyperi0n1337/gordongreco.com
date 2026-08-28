# Ordered PostgreSQL migrations

Apply `0001` through `0009` exactly once, in lexical order, as a migration owner
that is not used by the API or worker. Each file is transactional. The runtime
roles are `NOINHERIT NOBYPASSRLS`, receive no table mutation grants, and can
mutate only through fixed-search-path `SECURITY DEFINER` RPCs.

Production gate:

```bash
python scripts/check_migrations.py
psql "$DATABASE_URL_MIGRATOR" -v ON_ERROR_STOP=1 -f migrations/0001_bootstrap.sql
# repeat in order, or use scripts/apply_migrations.sh
```

Do not set `app.user_id`, `app.household_ids`, `app.entity_ids`, or
`app.actor_role` from request input. `PortalDatabase.actor_transaction()` sets
those transaction-local values only after `authenticate_session()` derives them
from active memberships.
