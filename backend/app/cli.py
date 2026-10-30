"""
Commandes d'exploitation.

    python -m app.cli create-admin --email admin@exemple.com --first-name Clovis --role super_admin

Le mot de passe est demandé de façon masquée (jamais en argument : il resterait dans
l'historique du terminal). Le compte devra activer la double authentification avant
d'accéder à l'administration. Dans Docker :

    docker exec -it safetradev2-backend python -m app.cli create-admin --email ... --role ...
"""

import argparse
import getpass
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app import audit
from app.auth import security
from app.authz import ADMIN_ROLES
from app.db.models import User, UserRole
from app.db.session import get_engine


def create_admin(
    db: DbSession, *, email: str, first_name: str, role: UserRole, password: str, promote: bool
) -> User:
    if role not in ADMIN_ROLES:
        raise ValueError(f"rôle non administrateur : {role}")
    existing = db.scalars(
        select(User).where(func.lower(User.email) == email.strip().lower())
    ).first()
    if existing is not None:
        if not promote:
            raise ValueError("ce compte existe déjà (utiliser --promote pour lui donner le rôle)")
        existing.role = role
        user = existing
    else:
        problem = security.password_problem(password, email)
        if problem:
            raise ValueError(problem)
        user = User(
            email=email.strip(),
            first_name=first_name.strip(),
            password_hash=security.hash_password(password),
            role=role,
            email_verified_at=datetime.now(UTC),
        )
        db.add(user)
        db.flush()
    audit.record(
        db,
        "admin.grant_role",
        "success",
        target_type="user",
        target_id=str(user.id),
        details={"role": role.value, "via": "cli", "promoted": existing is not None},
    )
    db.commit()
    return user


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="créer ou promouvoir un administrateur")
    admin.add_argument("--email", required=True)
    admin.add_argument("--first-name", default="Admin")
    admin.add_argument("--role", required=True, choices=sorted(r.value for r in ADMIN_ROLES))
    admin.add_argument("--promote", action="store_true", help="promouvoir un compte existant")
    args = parser.parse_args(argv)

    password = ""
    if not args.promote:
        password = getpass.getpass("Mot de passe : ")
        if password != getpass.getpass("Confirmer : "):
            print("Les mots de passe ne correspondent pas.", file=sys.stderr)
            return 1
    with DbSession(get_engine()) as db:
        try:
            user = create_admin(
                db,
                email=args.email,
                first_name=args.first_name,
                role=UserRole(args.role),
                password=password,
                promote=args.promote,
            )
        except ValueError as exc:
            print(f"Refusé : {exc}", file=sys.stderr)
            return 1
    print(
        f"Administrateur prêt : {user.email} ({args.role}). Activer la double authentification "
        "dans Sécurité avant d'accéder à l'administration."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
