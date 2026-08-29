from app.generation_jobs import state
from app.models.user import User


def _register_and_login(client, email: str = "jane@example.com") -> str:
    from tests._helpers import register_and_login

    return register_and_login(client, email)


def _user_id(db_session, email: str) -> int:
    return db_session.query(User).filter(User.email == email).first().id


def test_get_generation_job_reports_running_then_done_shape(client, db_session):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = _user_id(db_session, "jane@example.com")

    job_id = state.create_job(user_id, total_steps=5)
    running = client.get(f"/generation-jobs/{job_id}", headers=headers)
    assert running.status_code == 200
    body = running.json()
    assert body["status"] == "running"
    assert body["total_steps"] == 5
    assert body["result"] is None

    state.advance(job_id, 2, "Génération du contenu")
    state.complete(job_id, result={"kind": "cv", "needs_review": False})

    done = client.get(f"/generation-jobs/{job_id}", headers=headers).json()
    assert done["status"] == "done"
    assert done["result"] == {"kind": "cv", "needs_review": False}


def test_get_generation_job_reports_error_status():
    job_id = state.create_job(1, total_steps=3)
    state.fail(job_id, "boom")
    job = state.get(job_id, 1)
    assert job is not None
    assert job.status == "error"
    assert job.error == "boom"


def test_get_generation_job_404s_for_another_users_job(client, db_session):
    owner_token = _register_and_login(client, "jane@example.com")
    _register_and_login(client, "mallory@example.com")
    owner_id = _user_id(db_session, "jane@example.com")
    job_id = state.create_job(owner_id, total_steps=3)

    attacker_token = _register_and_login(client, "eve@example.com")
    attacker_headers = {"Authorization": f"Bearer {attacker_token}"}
    response = client.get(f"/generation-jobs/{job_id}", headers=attacker_headers)
    assert response.status_code == 404

    # Sanity check: the owner themself can read it.
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    assert (
        client.get(f"/generation-jobs/{job_id}", headers=owner_headers).status_code
        == 200
    )


def test_get_generation_job_404s_for_unknown_job(client):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/generation-jobs/does-not-exist", headers=headers)
    assert response.status_code == 404
