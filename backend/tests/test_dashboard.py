from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api.v1.dashboard import dashboard_stats
from app.config import get_settings
from app.models.credential import Credential, RotationState


def _add_cpe(db_session, cpe_id="CPE-DASH-1"):
    from app.models.cpe import CPE

    cpe = CPE(cpe_id=cpe_id, device_name=f"dev-{cpe_id}", site="Lab", status="online")
    db_session.add(cpe)
    db_session.commit()
    return cpe


def _add_credential(db_session, cpe, *, rotation_state=RotationState.ACTIVE.value, **kw):
    cred = Credential(
        cpe_id=cpe.id,
        username="admin",
        secret_reference=f"cred:{cpe.cpe_id}-{rotation_state}",
        version=1,
        status="ACTIVE",
        rotation_state=rotation_state,
        **kw,
    )
    db_session.add(cred)
    db_session.commit()
    return cred


def _stats(db_session, operator_user):
    return dashboard_stats(db_session, operator_user, get_settings())


def test_fresh_active_credentials_need_no_rotation(db_session, operator_user):
    cpe = _add_cpe(db_session)
    _add_credential(db_session, cpe, activated_at=datetime.now(timezone.utc))
    assert _stats(db_session, operator_user).credentials_needing_rotation == 0


def test_rotation_failed_counts_as_needing_rotation(db_session, operator_user):
    cpe = _add_cpe(db_session)
    _add_credential(
        db_session, cpe,
        rotation_state=RotationState.ROTATION_FAILED.value,
        activated_at=datetime.now(timezone.utc),
    )
    assert _stats(db_session, operator_user).credentials_needing_rotation == 1


def test_stale_last_rotation_counts_as_needing_rotation(db_session, operator_user):
    cpe = _add_cpe(db_session)
    _add_credential(
        db_session, cpe,
        activated_at=datetime.now(timezone.utc) - timedelta(days=100),
        last_rotated_at=datetime.now(timezone.utc) - timedelta(days=100),
    )
    assert _stats(db_session, operator_user).credentials_needing_rotation == 1


def test_fresh_last_rotation_not_due(db_session, operator_user):
    cpe = _add_cpe(db_session)
    _add_credential(
        db_session, cpe,
        activated_at=datetime.now(timezone.utc) - timedelta(days=100),
        last_rotated_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    assert _stats(db_session, operator_user).credentials_needing_rotation == 0


def test_past_next_rotation_counts(db_session, operator_user):
    cpe = _add_cpe(db_session)
    _add_credential(
        db_session, cpe,
        activated_at=datetime.now(timezone.utc),
        next_rotation_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    assert _stats(db_session, operator_user).credentials_needing_rotation == 1


def test_future_next_rotation_not_due(db_session, operator_user):
    cpe = _add_cpe(db_session)
    _add_credential(
        db_session, cpe,
        activated_at=datetime.now(timezone.utc),
        next_rotation_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    assert _stats(db_session, operator_user).credentials_needing_rotation == 0


def test_retired_history_rows_not_counted(db_session, operator_user):
    cpe = _add_cpe(db_session)
    active = _add_credential(db_session, cpe, activated_at=datetime.now(timezone.utc))
    # A retired history row with old rotation metadata must not count.
    db_session.add(
        Credential(
            cpe_id=cpe.id,
            username="admin",
            secret_reference="cred:history-v1",
            version=1,
            status="RETIRED",
            rotation_state=RotationState.OLD_SECRET_RETIRED.value,
            activated_at=datetime.now(timezone.utc) - timedelta(days=400),
            retired_at=datetime.now(timezone.utc) - timedelta(days=400),
            last_rotated_at=datetime.now(timezone.utc) - timedelta(days=400),
        )
    )
    db_session.commit()
    assert active.status == "ACTIVE"
    assert _stats(db_session, operator_user).credentials_needing_rotation == 0