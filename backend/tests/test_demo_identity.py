"""Demo identity contract: `seed.py` assignments must reference the deterministic
Keycloak subjects declared in keycloak/realm-config/versa-telecom-realm.json.

If these drift, the demo field engineer can log in but every credential reveal
is denied with 403 because `is_assigned()` compares the token `sub` against the
assignment subject. The test guards that regression at the source of truth.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

_JSON_ABSPATH = Path(__file__).resolve().parents[2] / "keycloak" / "realm-config" / "versa-telecom-realm.json"


def _field_user_id() -> str:
    realm = json.loads(_JSON_ABSPATH.read_text(encoding="utf-8"))
    for user in realm["users"]:
        if user.get("username") == "field":
            return str(user["id"])
    raise AssertionError("field user not found in realm JSON")


def test_field_demo_subject_is_a_valid_uuid():
    from app.seed import FIELD_DEMO_SUBJECT

    uuid.UUID(FIELD_DEMO_SUBJECT)


def test_seed_subject_matches_realm_json_field_user_id():
    from app.seed import FIELD_DEMO_SUBJECT

    assert FIELD_DEMO_SUBJECT == _field_user_id()


def test_demo_assignments_only_reference_the_field_subject():
    from app.seed import DEMO_ASSIGNMENTS, FIELD_DEMO_SUBJECT

    assert DEMO_ASSIGNMENTS
    assert {subject for subject, _ in DEMO_ASSIGNMENTS} == {FIELD_DEMO_SUBJECT}


def test_seed_writes_assignments_for_the_deterministic_subject(db_session):
    from app.models.access import CPEAssignment
    from app.seed import DEMO_ASSIGNMENTS, FIELD_DEMO_SUBJECT, _seed_assignments

    _seed_assignments(db_session)
    rows = db_session.query(CPEAssignment).all()
    assert {r.user_subject for r in rows} == {FIELD_DEMO_SUBJECT}
    assert {r.cpe_id for r in rows} == {cpe_id for _, cpe_id in DEMO_ASSIGNMENTS}