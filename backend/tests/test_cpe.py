from __future__ import annotations

from app.services.cpe_service import CPEService


def test_create_and_get_cpe(db_session, admin_user):
    service = CPEService(db_session)
    cpe = service.create(
        {"cpe_id": "CPE-A-1", "device_name": "BR-1", "site": "Site A"}, None, admin_user
    )
    assert cpe.cpe_id == "CPE-A-1"
    fetched = service.get("CPE-A-1")
    assert fetched.id == cpe.id


def test_list_pagination_and_unknown_status_normalisation(db_session, admin_user):
    service = CPEService(db_session)
    for i in range(15):
        service.create(
            {"cpe_id": f"CPE-{i:03d}", "site": "Site B", "status": "weird"}, None, admin_user
        )
    rows, total = service.list(page=1, page_size=10)
    assert total == 15
    assert len(rows) == 10
    assert rows[0].status == "unknown"


def test_csv_import(db_session, admin_user):
    csv_content = "cpe_id,device_name,serial_number,site,management_ip\n" \
                  "IM-1,BR-IM-1,SN1,SiteC,10.0.0.1\n" \
                  "IM-2,BR-IM-2,SN2,SiteD,10.0.0.2\n"
    result = CPEService(db_session).import_csv(csv_content, admin_user)
    assert result == {"created": 2, "updated": 0}
    assert CPEService(db_session).get("IM-1").serial_number == "SN1"


def _add_cpe_with_credential(db_session, cpe_id, *, rotation_state="ACTIVE"):
    from datetime import datetime, timedelta, timezone

    from app.models.cpe import CPE
    from app.models.credential import Credential

    cpe = CPE(cpe_id=cpe_id, device_name=f"dev {cpe_id}", site="Lab", status="online")
    db_session.add(cpe)
    db_session.flush()
    db_session.add(
        Credential(
            cpe_id=cpe.id,
            username="admin",
            secret_reference=f"cred:{cpe_id}-{rotation_state}",
            version=1,
            status="ACTIVE",
            rotation_state=rotation_state,
            activated_at=datetime.now(timezone.utc) - timedelta(days=400),
            last_rotated_at=datetime.now(timezone.utc) - timedelta(days=400),
        )
    )
    db_session.commit()
    return cpe


def test_list_needs_rotation_only_returns_due_cpes(db_session, admin_user):
    from datetime import datetime, timedelta, timezone

    from app.models.credential import Credential

    service = CPEService(db_session)
    _add_cpe_with_credential(db_session, "CPE-DUE-1")
    _add_cpe_with_credential(db_session, "CPE-DUE-2")
    fresh_cpe = _add_cpe_with_credential(db_session, "CPE-FRESH-1")
    # Reset its rotation metadata to "just rotated" (not due).
    cred = db_session.query(Credential).filter(Credential.cpe_id == fresh_cpe.id).one()
    cred.last_rotated_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    rows, total = service.list(needs_rotation=True, page_size=100)
    ids = {c.cpe_id for c in rows}
    assert "CPE-DUE-1" in ids and "CPE-DUE-2" in ids
    assert "CPE-FRESH-1" not in ids
    assert total == 2


def test_list_needs_rotation_counts_rotation_failed(db_session, admin_user):
    from app.models.credential import RotationState

    service = CPEService(db_session)
    _add_cpe_with_credential(db_session, "CPE-FAIL-1", rotation_state=RotationState.ROTATION_FAILED.value)
    rows, total = service.list(needs_rotation=True, page_size=100)
    assert {c.cpe_id for c in rows} == {"CPE-FAIL-1"}
    assert total == 1