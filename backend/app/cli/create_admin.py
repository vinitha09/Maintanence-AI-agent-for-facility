from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.db.connection import create_db_and_tables, engine
from backend.app.models.maintenance import User, UserRole
from backend.app.services.auth_security import hash_password


def main() -> None:
    create_db_and_tables()
    name = input("Administrator name: ").strip()
    if not name or len(name) > 150:
        raise SystemExit("Name must contain 1 to 150 characters.")
    try:
        email = TypeAdapter(EmailStr).validate_python(
            input("Administrator email: ").strip().lower()
        )
    except ValidationError as error:
        raise SystemExit("Enter a valid email address.") from error

    password = getpass("Password (8-128 characters): ")
    confirmation = getpass("Confirm password: ")
    if not 8 <= len(password) <= 128:
        raise SystemExit("Password must contain 8 to 128 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    with Session(engine) as session:
        existing = session.exec(select(User.id).where(User.email == email)).first()
        if existing is not None:
            raise SystemExit("An account already exists for this email.")
        admin = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            is_verified=True,
            is_approved=True,
            is_active=True,
        )
        session.add(admin)
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise SystemExit(
                "The administrator account could not be created because the "
                "database schema is not up to date or this email is already in use. "
                "Rerun the command after the database migration succeeds."
            ) from error
    print(f"Administrator account created for {email}.")


if __name__ == "__main__":
    main()
