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