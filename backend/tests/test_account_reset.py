"""Isolated MySQL proof that reset accounts refresh without losing role/ownership."""
import importlib.util
from pathlib import Path
import unittest
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models import FloorPlan, ProcessingJob, Project, ProjectFloor, Role, User
from app.services.authentication import ExternalOIDCIdentity, resolve_external_user


spec = importlib.util.spec_from_file_location("reset_local_accounts", Path(__file__).resolve().parents[2] / "scripts/reset_local_accounts.py")
reset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset)


class AccountResetMySQLTests(unittest.TestCase):
    def test_project_only_reset_clears_children_and_allows_new_project_without_changing_accounts(self):
        connection = get_engine().connect()
        transaction = connection.begin()
        session = Session(bind=connection, expire_on_commit=False)
        try:
            designer = session.scalar(select(Role).where(Role.name == "DESIGNER"))
            user = User(oauth_provider="google", oauth_subject=uuid4().hex, role_id=designer.id)
            session.add(user)
            session.flush()
            project = Project(owner_id=user.id, name="Project to reset")
            session.add(project)
            session.flush()
            floor = ProjectFloor(project_id=project.id, name="Ground floor")
            session.add(floor)
            session.flush()
            plan = FloorPlan(project_floor_id=floor.id, original_filename="synthetic.png",
                             storage_path="originals/synthetic.png", mime_type="image/png", file_size=1)
            session.add(plan)
            session.flush()
            session.add(ProcessingJob(floor_plan_id=plan.id, job_type="floor_plan_analysis"))
            session.flush()
            before = reset.non_account_fingerprints(connection, skip_tables=reset.PROJECT_DATA_TABLES)
            result = reset.reset_project_data(connection, apply=True)
            self.assertEqual(result["total_rows_removed"], 4)
            self.assertEqual(before, reset.non_account_fingerprints(connection, skip_tables=reset.PROJECT_DATA_TABLES))
            self.assertEqual(connection.exec_driver_sql("SELECT @@FOREIGN_KEY_CHECKS").scalar(), 1)
            self.assertEqual(list(connection.scalars(select(Project.id))), [])
            session.expunge_all()
            fresh = Project(owner_id=user.id, name="Fresh project after reset")
            session.add(fresh)
            session.flush()
            self.assertIsNotNone(fresh.id)
            self.assertEqual(session.get(User, user.id).role.name, "DESIGNER")
        finally:
            session.close()
            transaction.rollback()
            connection.close()

    def test_profile_refresh_preserves_admin_id_ownership_and_exact_oidc_subject(self):
        connection = get_engine().connect()
        transaction = connection.begin()
        session = Session(bind=connection, expire_on_commit=False)
        try:
            admin = session.scalar(select(Role).where(Role.name == "ADMIN"))
            marker = uuid4().hex
            user = User(oauth_provider="google", oauth_subject=marker, email="old@example.test",
                        display_name="Old cache", avatar_url="https://example.test/old", role_id=admin.id)
            session.add(user)
            session.flush()
            project = Project(owner_id=user.id, name="Reset preservation " + marker)
            session.add(project)
            session.flush()
            original_id = user.id
            before = reset.non_account_fingerprints(connection)
            reset.reset_accounts(connection, provider="google", apply=True)
            session.expire_all()
            self.assertIsNone(user.email)
            self.assertIsNone(user.display_name)
            self.assertIsNone(user.avatar_url)
            self.assertEqual(before, reset.non_account_fingerprints(connection))
            refreshed, created = resolve_external_user(session, ExternalOIDCIdentity(
                provider="google", subject=marker, email="new@example.test", display_name="Refreshed cache",
                avatar_url="https://example.test/new"))
            self.assertFalse(created)
            self.assertEqual(refreshed.id, original_id)
            self.assertEqual(refreshed.role.name, "ADMIN")
            self.assertEqual(project.owner_id, original_id)
            self.assertEqual(refreshed.email, "new@example.test")
            other, created = resolve_external_user(session, ExternalOIDCIdentity(provider="google", subject=uuid4().hex))
            self.assertTrue(created)
            self.assertNotEqual(other.id, original_id)
            self.assertEqual(other.role.name, "DESIGNER")
        finally:
            session.close()
            transaction.rollback()
            connection.close()
