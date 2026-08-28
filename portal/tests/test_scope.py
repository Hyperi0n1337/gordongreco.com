import pytest

from conftest import ENTITY_A, ENTITY_B, ENTITY_SHARED, HH_A, HH_B
from portal_core.errors import Forbidden
from portal_core.models import Role
from portal_core.scope import require_entity, require_role


def test_household_entity_pairs_do_not_collapse_to_global_entity_ids(actor_factory):
    actor = actor_factory("advisor-a")
    require_entity(actor, HH_A, ENTITY_SHARED)
    with pytest.raises(Forbidden):
        require_entity(actor, HH_B, ENTITY_SHARED)
    with pytest.raises(Forbidden):
        require_entity(actor, HH_A, ENTITY_B)


def test_role_is_derived_per_household_not_from_highest_global_role(actor_factory):
    mixed = actor_factory("mixed-user")
    assert mixed.role is Role.ADVISOR
    require_role(mixed, Role.ADVISOR, household_id=HH_A)
    require_role(mixed, Role.CLIENT, household_id=HH_B)
    with pytest.raises(Forbidden):
        require_role(mixed, Role.ADVISOR, household_id=HH_B)


def test_scope_is_server_derived_from_active_memberships(actor_factory):
    actor = actor_factory("client-a")
    assert actor.household_ids == frozenset({HH_A})
    assert actor.entity_scope == frozenset({(HH_A, ENTITY_SHARED), (HH_A, ENTITY_A)})
    assert (HH_A, Role.CLIENT) in actor.role_scope
