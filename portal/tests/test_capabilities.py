from datetime import timedelta

import pytest

from portal_core.capabilities import CapabilitySigner
from portal_core.errors import Expired, Forbidden, Unauthorized, ValidationError


def issue(signer, now):
    return signer.issue(
        now=now, actor_id="actor.test", household_id="household.test", resource_id="upload.test",
        bucket="quarantine", object_key="quarantine/household.test/document.test/random",
        method="PUT", ttl=timedelta(minutes=5), max_bytes=100, part_number=1,
    )


def test_capability_binds_every_authority_dimension(clock):
    signer = CapabilitySigner(b"k" * 32)
    cap = issue(signer, clock.now())
    base = dict(now=clock.now(), actor_id="actor.test", household_id="household.test",
                resource_id="upload.test", bucket="quarantine",
                object_key="quarantine/household.test/document.test/random", method="PUT",
                content_length=100, part_number=1)
    signer.verify(cap.token, **base)
    for field, value in [
        ("actor_id", "other.test"), ("household_id", "other.test"), ("resource_id", "other.test"),
        ("bucket", "clean"), ("object_key", "quarantine/other"), ("method", "GET"),
        ("part_number", 2), ("content_length", 101),
    ]:
        changed = base | {field: value}
        with pytest.raises(Forbidden):
            signer.verify(cap.token, **changed)


def test_capability_signature_expiry_and_max_ttl(clock):
    signer = CapabilitySigner(b"k" * 32)
    cap = issue(signer, clock.now())
    damaged = cap.token[:-1] + ("A" if cap.token[-1] != "A" else "B")
    with pytest.raises(Unauthorized):
        signer.verify(damaged, now=clock.now(), actor_id="actor.test", household_id="household.test",
                      resource_id="upload.test", bucket="quarantine",
                      object_key="quarantine/household.test/document.test/random", method="PUT",
                      content_length=1, part_number=1)
    clock.advance(minutes=5)
    with pytest.raises(Expired):
        signer.verify(cap.token, now=clock.now(), actor_id="actor.test", household_id="household.test",
                      resource_id="upload.test", bucket="quarantine",
                      object_key="quarantine/household.test/document.test/random", method="PUT",
                      content_length=1, part_number=1)
    with pytest.raises(ValidationError):
        signer.issue(now=clock.now(), actor_id="a", household_id="h", resource_id="r", bucket="b",
                     object_key="k", method="GET", ttl=timedelta(minutes=11))
