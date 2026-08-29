"""Manage beta invite codes. Run inside the container:

    docker compose -f docker-compose.prod.yml exec backend \\
        python -m scripts.invites generate --count 15 --note "vague 1"
    ... python -m scripts.invites list
    ... python -m scripts.invites revoke <code>
"""

import argparse
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.invite_code import InviteCode
from app.utils.time import utcnow


def generate_codes(
    db: Session, count: int, note: str | None, ttl_days: int = 30
) -> list[str]:
    codes: list[str] = []
    for _ in range(count):
        value = secrets.token_urlsafe(9)
        db.add(
            InviteCode(
                code=value,
                note=note,
                expires_at=utcnow() + timedelta(days=ttl_days),
            )
        )
        codes.append(value)
    db.commit()
    return codes


def list_codes(db: Session) -> list[InviteCode]:
    return db.query(InviteCode).order_by(InviteCode.created_at).all()


def revoke_code(db: Session, code: str) -> bool:
    row = db.query(InviteCode).filter_by(code=code).one_or_none()
    if row is None or row.used_at is not None:
        return False
    db.delete(row)
    db.commit()
    return True


def _main() -> None:
    parser = argparse.ArgumentParser(prog="scripts.invites")
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--count", type=int, required=True)
    g.add_argument("--note", default=None)
    sub.add_parser("list")
    r = sub.add_parser("revoke")
    r.add_argument("code")

    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.cmd == "generate":
            for code in generate_codes(db, args.count, args.note):
                print(code)
        elif args.cmd == "list":
            for row in list_codes(db):
                status = (
                    f"used by user {row.used_by_user_id}" if row.used_at else "unused"
                )
                print(f"{row.code}\t{status}\t{row.note or ''}")
        elif args.cmd == "revoke":
            print(
                "revoked"
                if revoke_code(db, args.code)
                else "not revocable (unknown or already used)"
            )
    finally:
        db.close()


if __name__ == "__main__":
    _main()
