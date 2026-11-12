import os
import re
import unittest
from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from backend.app.api.routes import auth as auth_routes
from backend.app.api.routes import admin as admin_routes
from backend.app.api.routes import rag as rag_routes
from backend.app.api.routes import maintenance_logs as maintenance_log_routes
from backend.app.api.routes.facility import router as application_router
from backend.app.db.connection import _ensure_existing_schema, get_session
from backend.app.models.maintenance import (
    AdminInvitation,
    Facility,
    FunctionalSystem,
    Machine,
    MaintenanceLog,
    Organization,
    PhysicalLocation,
    PasswordResetToken,
    PendingRegistration,
    UserInvitation,
    User,
    UserRole,
)
from backend.app.services.auth_security import (
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    token_expiration,
)


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["JWT_SECRET_KEY"] = "test-secret-" + ("x" * 40)

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(
            self.engine,
            tables=[
                User.__table__,
                Organization.__table__,
                Facility.__table__,
                FunctionalSystem.__table__,
                PhysicalLocation.__table__,
                Machine.__table__,
                MaintenanceLog.__table__,
                PendingRegistration.__table__,
                PasswordResetToken.__table__,
                AdminInvitation.__table__,
                UserInvitation.__table__,
            ],
        )

        def override_session():
            with Session(self.engine) as session:
                yield session

        self.app = FastAPI()
        self.app.include_router(application_router)
        self.app.dependency_overrides[get_session] = override_session
        self.sent_emails = []
        self.original_send_email = auth_routes.send_email
        self.admin_sent_emails = []
        self.original_admin_send_email = admin_routes.send_email
        self.original_index_maintenance_log = (
            maintenance_log_routes.index_maintenance_log
        )
        self.original_get_context_matches = rag_routes._get_context_matches
        auth_routes.send_email = (
            lambda recipient, subject, body: self.sent_emails.append(body)
        )
        admin_routes.send_email = (
            lambda recipient, subject, body: self.admin_sent_emails.append(body)
        )
        maintenance_log_routes.index_maintenance_log = lambda _: None
        rag_routes._get_context_matches = lambda *_: []
        self.client = TestClient(self.app)
        with Session(self.engine) as session:
            session.add(
                User(
                    name="Site Admin",
                    email="admin@example.com",
                    password_hash=hash_password("admin-password"),
                    role=UserRole.ADMIN.value,
                    is_verified=True,
                    is_approved=True,
                    is_active=True,
                )
            )
            organization = Organization(name="Test organization")
            session.add(organization)
            session.flush()
            session.add(
                Facility(
                    organization_id=organization.id,
                    name="Test facility",
                )
            )
            session.commit()

    def tearDown(self):
        self.client.close()
        auth_routes.send_email = self.original_send_email
        admin_routes.send_email = self.original_admin_send_email
        maintenance_log_routes.index_maintenance_log = (
            self.original_index_maintenance_log
        )
        rag_routes._get_context_matches = self.original_get_context_matches
        self.engine.dispose()

    def test_registration_creates_user_only_after_verification_and_forces_user_role(self):
        escalation_attempt = self.client.post(
            "/auth/register",
            json={
                "name": "New User",
                "email": "new@example.com",
                "password": "user-password",
                "role": "ADMIN",
            },
        )
        self.assertEqual(escalation_attempt.status_code, 422)
        response = self.client.post(
            "/auth/register",
            json={
                "name": "New User",
                "email": "new@example.com",
                "password": "user-password",
            },
        )
        self.assertEqual(response.status_code, 202)
        with Session(self.engine) as session:
            self.assertIsNone(
                session.exec(
                    select(User).where(User.email == "new@example.com")
                ).first()
            )

        token = re.search(
            r"token=([A-Za-z0-9_-]+)",
            self.sent_emails[0],
        ).group(1)
        response = self.client.post("/auth/verify-email", json={"token": token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], UserRole.USER.value)
        self.assertFalse(response.json()["is_approved"])

    def test_schema_initialization_adds_columns_without_deleting_existing_rows(self):
        schema_engine = create_engine("sqlite://")
        with schema_engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE app_user (id INTEGER PRIMARY KEY, name TEXT)")
            )
            connection.execute(
                text("INSERT INTO app_user (id, name) VALUES (7, 'Existing user')")
            )
            connection.execute(
                text("CREATE TABLE machine (id INTEGER PRIMARY KEY, machine_name TEXT)")
            )
            connection.execute(
                text("INSERT INTO machine (id, machine_name) VALUES (9, 'Existing pump')")
            )
            connection.execute(
                text("CREATE TABLE maintenance_log (id INTEGER PRIMARY KEY)")
            )
            connection.execute(
                text(
                    "CREATE TABLE user_invitation "
                    "(id INTEGER PRIMARY KEY, email TEXT NOT NULL)"
                )
            )
            _ensure_existing_schema(connection)

            user = connection.execute(
                text("SELECT name, auth_version, is_invited FROM app_user WHERE id = 7")
            ).one()
            machine = connection.execute(
                text("SELECT machine_name, is_deleted FROM machine WHERE id = 9")
            ).one()
            self.assertEqual(user, ("Existing user", 0, 0))
            self.assertEqual(machine, ("Existing pump", 0))
            self.assertIn(
                "user_id",
                {
                    column["name"]
                    for column in inspect(connection).get_columns("maintenance_log")
                },
            )
            self.assertIn(
                "failed_attempts",
                {
                    column["name"]
                    for column in inspect(connection).get_columns("user_invitation")
                },
            )
        schema_engine.dispose()

    def test_approval_and_role_authorization(self):
        with Session(self.engine) as session:
            user = User(
                name="Regular User",
                email="user@example.com",
                password_hash=hash_password("user-password"),
                role=UserRole.USER.value,
                is_verified=True,
                is_approved=True,
                is_active=True,
            )
            session.add(user)
            session.commit()
        user_login = self.client.post(
            "/auth/user/login",
            json={"email": "user@example.com", "password": "user-password"},
        )
        self.assertEqual(user_login.status_code, 200)
        self.assertEqual(self.client.get("/organizations").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/organizations",
                json={"name": "Unauthorized organization"},
            ).status_code,
            403,
        )
        self.assertEqual(self.client.delete("/machines/1").status_code, 403)
        self.assertEqual(self.client.get("/admin/users").status_code, 403)

        self.client.post("/auth/logout")
        admin_login = self.client.post(
            "/auth/admin/login",
            json={"email": "admin@example.com", "password": "admin-password"},
        )
        self.assertEqual(admin_login.status_code, 200)
        self.assertEqual(self.client.get("/admin/users").status_code, 200)

    def test_unapproved_user_cannot_use_ai_or_register_but_can_edit(self):
        with Session(self.engine) as session:
            facility = session.exec(
                select(Facility).where(Facility.name == "Test facility")
            ).first()
            facility_id = facility.id

        with Session(self.engine) as session:
            session.add(
                User(
                    name="Pending User",
                    email="pending@example.com",
                    password_hash=hash_password("user-password"),
                    role=UserRole.USER.value,
                    is_verified=True,
                    is_approved=False,
                    is_active=True,
                )
            )
            session.commit()
        response = self.client.post(
            "/auth/user/login",
            json={"email": "pending@example.com", "password": "user-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["user"]["is_approved"])
        self.assertEqual(self.client.get("/auth/me").status_code, 200)
        self.assertEqual(self.client.get("/machines").status_code, 200)
        self.assertEqual(self.client.get("/maintenance-logs").status_code, 200)

        create_before_approval = self.client.post(
            "/machines",
            json={
                "facility_id": facility_id,
                "machine_name": "User-created pump",
                "machine_code": "USER-PUMP-1",
                "description": "Created before administrator approval.",
            },
        )
        self.assertEqual(create_before_approval.status_code, 403)
        ai_response = self.client.post(
            "/manuals/search/stream",
            json={
                "scope_type": "facility",
                "scope_id": facility_id,
                "question": "Summarize the facility maintenance history.",
                "top_k": 3,
            },
        )
        self.assertEqual(ai_response.status_code, 403)

        self.client.post("/auth/logout")
        self.client.post(
            "/auth/admin/login",
            json={"email": "admin@example.com", "password": "admin-password"},
        )
        created = self.client.post(
            "/machines",
            json={
                "facility_id": facility_id,
                "machine_name": "Existing pump",
                "machine_code": "USER-PUMP-1",
                "description": "Existing machine.",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.client.post("/auth/logout")
        response = self.client.post(
            "/auth/user/login",
            json={"email": "pending@example.com", "password": "user-password"},
        )
        self.assertEqual(response.status_code, 200)

        updated = self.client.patch(
            f"/machines/{created.json()['id']}",
            json={"description": "Edited before administrator approval."},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(
            updated.json()["description"],
            "Edited before administrator approval.",
        )
        log = self.client.post(
            "/maintenance-logs",
            json={
                "machine_id": created.json()["id"],
                "record_type": "daily",
                "recorded_on": "2026-11-12",
                "description": "Initial inspection.",
            },
        )
        self.assertEqual(log.status_code, 201, log.text)
        edited_log = self.client.patch(
            f"/maintenance-logs/{log.json()['id']}",
            json={"description": "Updated inspection."},
        )
        self.assertEqual(edited_log.status_code, 200, edited_log.text)
        self.assertEqual(edited_log.json()["description"], "Updated inspection.")
        self.assertEqual(
            self.client.post(
                "/organizations",
                json={"name": "User cannot manage organizations"},
            ).status_code,
            403,
        )

    def test_only_an_administrator_can_invite_another_administrator(self):
        self.assertEqual(
            self.client.post(
                "/admin/invitations",
                json={"email": "new-admin@example.com"},
            ).status_code,
            401,
        )
        self.client.post(
            "/auth/admin/login",
            json={"email": "admin@example.com", "password": "admin-password"},
        )
        invitation = self.client.post(
            "/admin/invitations",
            json={"email": "new-admin@example.com"},
        )
        self.assertEqual(invitation.status_code, 202)
        token = re.search(
            r"token=([A-Za-z0-9_-]+)",
            self.admin_sent_emails[0],
        ).group(1)
        accepted = self.client.post(
            "/auth/admin-invitations/accept",
            json={
                "token": token,
                "name": "Invited Admin",
                "password": "new-admin-password",
            },
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["user"]["role"], UserRole.ADMIN.value)

    def test_admin_user_invitation_grants_access_without_approval(self):
        self.assertEqual(
            self.client.post(
                "/admin/user-invitations",
                json={"email": "invited-user@example.com"},
            ).status_code,
            401,
        )
        self.client.post(
            "/auth/admin/login",
            json={"email": "admin@example.com", "password": "admin-password"},
        )
        invitation = self.client.post(
            "/admin/user-invitations",
            json={"email": "invited-user@example.com"},
        )
        self.assertEqual(invitation.status_code, 202)
        token = re.search(
            r"Invitation code: ([A-Z]{4}[2-9]{3})",
            self.admin_sent_emails[0],
        ).group(1)
        accepted = self.client.post(
            "/auth/user-invitations/accept",
            json={
                "token": token,
                "email": "invited-user@example.com",
                "name": "Invited User",
                "password": "invited-user-password",
            },
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        invited_user = accepted.json()["user"]
        self.assertEqual(invited_user["role"], UserRole.USER.value)
        self.assertFalse(invited_user["is_approved"])
        self.assertTrue(invited_user["is_invited"])
        self.assertEqual(self.client.get("/auth/me").status_code, 200)

        with Session(self.engine) as session:
            facility = session.exec(
                select(Facility).where(Facility.name == "Test facility")
            ).first()
            facility_id = facility.id

        created = self.client.post(
            "/machines",
            json={
                "facility_id": facility_id,
                "machine_name": "Invited user's pump",
                "machine_code": "INVITED-PUMP-1",
                "description": "Created with invitation access.",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        ai_response = self.client.post(
            "/manuals/search/stream",
            json={
                "scope_type": "facility",
                "scope_id": facility_id,
                "question": "Summarize the facility maintenance history.",
                "top_k": 3,
            },
        )
        self.assertNotEqual(ai_response.status_code, 403, ai_response.text)

    def test_user_invitation_can_grant_access_to_existing_pending_account(self):
        with Session(self.engine) as session:
            user = User(
                name="Existing Pending User",
                email="existing-pending@example.com",
                password_hash=hash_password("existing-password"),
                role=UserRole.USER.value,
                is_verified=True,
                is_approved=False,
                is_active=True,
            )
            session.add(user)
            session.commit()

        self.client.post(
            "/auth/admin/login",
            json={"email": "admin@example.com", "password": "admin-password"},
        )
        invitation = self.client.post(
            "/admin/user-invitations",
            json={"email": "existing-pending@example.com"},
        )
        self.assertEqual(invitation.status_code, 202, invitation.text)
        token = re.search(
            r"Invitation code: ([A-Z]{4}[2-9]{3})",
            self.admin_sent_emails[0],
        ).group(1)
        accepted = self.client.post(
            "/auth/user-invitations/accept",
            json={
                "token": token,
                "email": "existing-pending@example.com",
                "name": "Existing Pending User",
                "password": "existing-password",
            },
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["user"]["name"], "Existing Pending User")
        self.assertFalse(accepted.json()["user"]["is_approved"])
        self.assertTrue(accepted.json()["user"]["is_invited"])
        self.assertEqual(self.client.get("/auth/me").status_code, 200)

    def test_shared_invitation_code_is_reusable_without_admin_approval(self):
        self.client.post(
            "/auth/admin/login",
            json={"email": "admin@example.com", "password": "admin-password"},
        )
        invitation = self.client.post(
            "/admin/user-invitations",
            json={},
        )
        self.assertEqual(invitation.status_code, 202, invitation.text)
        code = invitation.json()["code"]
        self.assertRegex(code, r"^[A-Z]{4}[2-9]{3}$")

        for number in (1, 2):
            accepted = self.client.post(
                "/auth/user-invitations/accept",
                json={
                    "token": code,
                    "email": f"recruiter{number}@example.com",
                    "name": f"Recruiter {number}",
                    "password": f"recruiter-{number}-password",
                },
            )
            self.assertEqual(accepted.status_code, 200, accepted.text)
            self.assertEqual(accepted.json()["user"]["role"], UserRole.USER.value)
            self.assertFalse(accepted.json()["user"]["is_approved"])
            self.assertTrue(accepted.json()["user"]["is_invited"])

        with Session(self.engine) as session:
            facility = session.exec(
                select(Facility).where(Facility.name == "Test facility")
            ).first()
            facility_id = facility.id
        created = self.client.post(
            "/machines",
            json={
                "facility_id": facility_id,
                "machine_name": "Recruiter-created pump",
                "machine_code": "RECRUITER-PUMP",
                "description": "Created using the shared recruiter code.",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)

    def test_password_reset_invalidates_existing_sessions(self):
        with Session(self.engine) as session:
            user = User(
                name="Regular User",
                email="user@example.com",
                password_hash=hash_password("user-password"),
                role=UserRole.USER.value,
                is_verified=True,
                is_approved=True,
                is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            token = generate_opaque_token()
            session.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=hash_opaque_token(token),
                    expires_at=token_expiration(timedelta(minutes=30)),
                )
            )
            session.commit()

        self.client.post(
            "/auth/user/login",
            json={"email": "user@example.com", "password": "user-password"},
        )
        response = self.client.post(
            "/auth/reset-password",
            json={"token": token, "password": "new-user-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.assertEqual(
            self.client.post(
                "/auth/user/login",
                json={"email": "user@example.com", "password": "user-password"},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                "/auth/user/login",
                json={"email": "user@example.com", "password": "new-user-password"},
            ).status_code,
            200,
        )
