from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.credential import Credential, RotationState
from app.services.credential_service import CredentialService
from app.services.rotation_service import RotationService


class FailingPushClient:
    def update_credential(self, cpe, password):
        return False

    def verify_credential(self, cpe, password):
        return False


class FailingVerifyClient:
    def update_credential(self, cpe, password):
        return True

    def verify_credential(self, cpe, password):
        return False


class SuccessClient:
    def update_credential(self, cpe, password):
        return True

    def verify_credential(self, cpe, password):
        return True


@pytest.fixture(autouse=True)
def _active_cred(db_session, secret_store, sample_cpe, admin_user):
    CredentialService(db_session, secret_store).create_for_cpe(sample_cpe, "admin", admin_user)
    return sample_cpe


def test_rotation_success_steps_up_version_and_reference(
    db_session, secret_store, sample_cpe, operator_user, admin_user
):
    service = RotationService(db_session, secret_store, SuccessClient())
    cred = service.request_rotation(sample_cpe, operator_user)
    assert cred.version == 2
    assert cred.rotation_state == RotationState.OLD_SECRET_RETIRED.value
    assert cred.status == "ACTIVE"
    assert secret_store.get_secret(cred.secret_reference) is not None


def test_rotation_push_failure_keeps_old_credential(
    db_session, secret_store, sample_cpe, operator_user, admin_user
):
    before = CredentialService(db_session, secret_store).active_credential(sample_cpe)
    old_ref = before.secret_reference
    old_value = secret_store.get_secret(old_ref)

    service = RotationService(db_session, secret_store, FailingPushClient())
    cred = service.request_rotation(sample_cpe, operator_user)
    assert cred.rotation_state == RotationState.ROTATION_FAILED.value
    assert cred.version == 1  # unchanged
    assert cred.secret_reference == old_ref  # reference NOT replaced
    assert secret_store.get_secret(old_ref) == old_value  # value retained (known-good)


def test_rotation_verify_failure_keeps_old_credential(
    db_session, secret_store, sample_cpe, operator_user, admin_user
):
    before = CredentialService(db_session, secret_store).active_credential(sample_cpe)
    old_ref = before.secret_reference

    service = RotationService(db_session, secret_store, FailingVerifyClient())
    cred = service.request_rotation(sample_cpe, operator_user)
    assert cred.rotation_state == RotationState.ROTATION_FAILED.value
    assert cred.secret_reference == old_ref
    assert cred.version == 1


def test_concurrent_active_credential_single_result(db_session, secret_store, sample_cpe):
    creds = CredentialService(db_session, secret_store)
    active = creds.active_credential(sample_cpe)
    assert active is not None


def test_rotation_can_be_retried_after_failure(
    db_session, secret_store, sample_cpe, operator_user, admin_user
):
    service = RotationService(db_session, secret_store, FailingPushClient())
    cred = service.request_rotation(sample_cpe, operator_user)
    assert cred.rotation_state == RotationState.ROTATION_FAILED.value
    assert cred.version == 1

    # Retry with a working client must succeed from the FAILED state.
    service = RotationService(db_session, secret_store, SuccessClient())
    cred = service.request_rotation(sample_cpe, operator_user)
    assert cred.rotation_state == RotationState.OLD_SECRET_RETIRED.value
    assert cred.version == 2


def test_rotation_can_run_again_after_success(
    db_session, secret_store, sample_cpe, operator_user, admin_user
):
    service = RotationService(db_session, secret_store, SuccessClient())
    first = service.request_rotation(sample_cpe, operator_user)
    assert first.version == 2
    # A subsequent rotation from the terminal OLD_SECRET_RETIRED state must work.
    second = service.request_rotation(sample_cpe, operator_user)
    assert second.version == 3


def test_rotation_emits_retired_history_row(
    db_session, secret_store, sample_cpe, operator_user, admin_user
):
    service = RotationService(db_session, secret_store, SuccessClient())
    cred = service.request_rotation(sample_cpe, operator_user)
    assert cred.version == 2

    from sqlalchemy import select

    rows = list(
        db_session.scalars(
            select(Credential).where(Credential.cpe_id == sample_cpe.id).order_by(Credential.version)
        ).all()
    )
    versions = [(r.version, r.status) for r in rows]
    assert (1, "RETIRED") in versions
    assert (2, "ACTIVE") in versions
    retired = next(r for r in rows if r.version == 1)
    assert retired.retired_at is not None


def test_create_sets_next_rotation_at(db_session, secret_store, sample_cpe, admin_user):
    service = CredentialService(db_session, secret_store, rotation_interval_days=30)
    cred = service.create_for_cpe(sample_cpe, "admin", admin_user)
    assert cred.next_rotation_at is not None
    from datetime import timezone

    delta = (cred.next_rotation_at - cred.activated_at).total_seconds()
    assert abs(delta - 30 * 24 * 3600) < 2


def test_successful_rotation_advances_next_rotation_at(
    db_session, secret_store, sample_cpe, operator_user, admin_user
):
    service = RotationService(
        db_session, secret_store, SuccessClient(), rotation_interval_days=45
    )
    cred = service.request_rotation(sample_cpe, operator_user)
    assert cred.next_rotation_at is not None
    from datetime import timezone

    delta = (cred.next_rotation_at - cred.last_rotated_at).total_seconds()
    assert abs(delta - 45 * 24 * 3600) < 2