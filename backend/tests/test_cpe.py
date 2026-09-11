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