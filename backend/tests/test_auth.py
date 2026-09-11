from __future__ import annotations

from app.auth.keycloak import TokenUser, _extract_claims


class _FakeSettings:
    keycloak_client_id = "versa-cpe-manager"


def test_extract_roles_from_claims():
    payload = {
        "sub": "u-1",
        "preferred_username": "bob",
        "email": "bob@example.com",
        "realm_access": {"roles": ["field_engineer", "offline_access"]},
        "resource_access": {
            "versa-cpe-manager": {"roles": ["field_engineer"]},
            "other-client": {"roles": ["admin"]},
        },
    }
    user = _extract_claims(payload, _FakeSettings())
    assert user.subject == "u-1"
    assert user.username == "bob"
    assert "field_engineer" in user.roles
    assert "admin" not in user.roles  # other client's roles must NOT leak in
    assert user.has_role("field_engineer")


def test_roles_deduplicated():
    payload = {
        "sub": "u-2",
        "preferred_username": "alice",
        "realm_access": {"roles": ["admin"]},
        "resource_access": {"versa-cpe-manager": {"roles": ["admin"]}},
    }
    user = _extract_claims(payload, _FakeSettings())
    assert user.roles == ["admin"]


def test_password_generation_meets_policy():
    from app.utils.crypto import PasswordPolicy, generate_password, _validate_password

    policy = PasswordPolicy(length=24)
    for _ in range(20):
        password = generate_password(policy)
        assert _validate_password(password, policy)


def test_password_generation_has_no_positional_pattern():
    from app.utils.crypto import PasswordPolicy, generate_password

    policy = PasswordPolicy(length=32)
    seen = {generate_password(policy) for _ in range(20)}
    assert len(seen) == 20  # all distinct, no trivially repeated output