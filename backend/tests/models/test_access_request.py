from app.models.access_request import AccessRequest


def test_access_request_row_roundtrips(db_session):
    row = AccessRequest(
        email="a@b.com", note="je cherche un poste de dev", source_ip="1.2.3.4"
    )
    db_session.add(row)
    db_session.commit()

    fetched = db_session.query(AccessRequest).one()
    assert fetched.email == "a@b.com"
    assert fetched.note == "je cherche un poste de dev"
    assert fetched.source_ip == "1.2.3.4"
    assert fetched.handled_at is None
    assert fetched.created_at is not None


def test_access_request_note_defaults_empty(db_session):
    row = AccessRequest(email="c@d.com")
    db_session.add(row)
    db_session.commit()
    assert db_session.query(AccessRequest).one().note == ""
