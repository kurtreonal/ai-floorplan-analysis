"""Reset regression: preserve authority and every referenced account identity."""
import importlib.util
from pathlib import Path
import unittest

from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, create_engine, event, select


spec = importlib.util.spec_from_file_location("reset_local_accounts", Path(__file__).with_name("reset_local_accounts.py"))
reset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset)


class AccountResetTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")
        metadata = MetaData()
        self.roles = Table("roles", metadata, Column("id", Integer, primary_key=True), Column("name", String))
        self.users = Table("users", metadata, Column("id", Integer, primary_key=True),
                           Column("oauth_provider", String), Column("oauth_subject", String),
                           Column("email", String), Column("display_name", String), Column("avatar_url", String),
                           Column("role_id", ForeignKey("roles.id"), nullable=False))
        self.projects = Table("projects", metadata, Column("id", Integer, primary_key=True),
                              Column("owner_id", ForeignKey("users.id")), Column("name", String))
        # A reference absent from the application ORM must also prevent removal.
        self.extra = Table("historical_external_review", metadata, Column("id", Integer, primary_key=True),
                           Column("actor_id", ForeignKey("users.id")), Column("authority_id", ForeignKey("roles.id")))
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(self.roles.insert(), [{"id": 1, "name": "ADMIN"}, {"id": 2, "name": "DESIGNER"},
                {"id": 3, "name": "F2_TEST_AAAAAAAA"}, {"id": 4, "name": "F3_TEST_BBBBBBBB"}])
            connection.execute(self.users.insert(), [dict(id=index, oauth_provider=provider,
                oauth_subject=f"identity-{index}", email=f"user{index}@example.test", display_name="Cached name",
                avatar_url="https://example.test/avatar", role_id=role) for index, provider, role in [
                    (1, "google", 1), (2, "google", 2), (3, "f2-test", 3), (4, "h3-test", 2),
                    (5, "u9-" + "a" * 31, 2), (6, "another-real-provider", 2)]])
            connection.execute(self.projects.insert(), [{"id": 1, "owner_id": 1, "name": "Original project"}])
            connection.execute(self.extra.insert(), [{"id": 1, "actor_id": 4, "authority_id": 3}])

    def tearDown(self):
        self.engine.dispose()

    def test_dry_run_changes_no_data(self):
        with self.engine.begin() as connection:
            before = [dict(row) for row in connection.execute(select(self.users)).mappings()]
            summary = reset.reset_accounts(connection, provider="google")
            self.assertEqual(summary["unused_test_accounts_removed"], 2)
            self.assertEqual(before, [dict(row) for row in connection.execute(select(self.users)).mappings()])

    def test_reset_preserves_identities_roles_projects_and_unknown_references(self):
        with self.engine.begin() as connection:
            before = reset.non_account_fingerprints(connection)
            summary = reset.reset_accounts(connection, provider="google", apply=True)
            self.assertEqual(before, reset.non_account_fingerprints(connection))
            self.assertEqual(summary["retained_referenced_test_accounts"], 1)
            self.assertEqual(summary["unused_test_roles_removed"], 1)
            rows = list(connection.execute(select(self.users).order_by(self.users.c.id)).mappings())
            self.assertEqual([row["id"] for row in rows], [1, 2, 4, 6])
            self.assertEqual([row["role_id"] for row in rows], [1, 2, 2, 2])
            self.assertTrue(all(row["oauth_subject"] == f"identity-{row['id']}" for row in rows))
            self.assertTrue(all(row[key] is None for row in rows for key in ["email", "display_name", "avatar_url"]))
            self.assertEqual(set(connection.scalars(select(self.roles.c.id))), {1, 2, 3})
            again = reset.reset_accounts(connection, provider="google", apply=True)
            self.assertEqual(again["unused_test_accounts_removed"], 0)

    def test_transaction_failure_rolls_back_all_account_changes(self):
        with self.assertRaises(RuntimeError):
            with self.engine.begin() as connection:
                reset.reset_accounts(connection, provider="google", apply=True)
                raise RuntimeError("Injected failure")
        with self.engine.connect() as connection:
            self.assertEqual(len(list(connection.scalars(select(self.users.c.id)))), 6)
            self.assertTrue(all(connection.scalars(select(self.users.c.email))))

    def test_configured_provider_never_removed_even_if_named_like_test_provider(self):
        with self.engine.begin() as connection:
            reset.reset_accounts(connection, provider="f2-test", apply=True)
            self.assertIsNotNone(connection.scalar(select(self.users.c.id).where(self.users.c.id == 3)))

    def _project_children(self):
        metadata = MetaData()
        Table("projects", metadata, autoload_with=self.engine)
        floors = Table("project_floors", metadata, Column("id", Integer, primary_key=True),
                       Column("project_id", ForeignKey("projects.id")))
        plans = Table("floor_plans", metadata, Column("id", Integer, primary_key=True),
                      Column("project_floor_id", ForeignKey("project_floors.id")))
        jobs = Table("processing_jobs", metadata, Column("id", Integer, primary_key=True),
                     Column("floor_plan_id", ForeignKey("floor_plans.id")))
        artifacts = Table("processing_artifacts", metadata, Column("id", Integer, primary_key=True),
                          Column("processing_job_id", ForeignKey("processing_jobs.id")))
        catalog = Table("symbol_legends", metadata, Column("id", Integer, primary_key=True), Column("name", String))
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            for table, parent in [(floors, "project_id"), (plans, "project_floor_id"),
                                  (jobs, "floor_plan_id"), (artifacts, "processing_job_id")]:
                connection.execute(table.insert(), {"id": 1, parent: 1})
            connection.execute(catalog.insert(), {"id": 1, "name": "Approved legend"})
        return [self.projects, floors, plans, jobs, artifacts]

    def test_project_only_reset_preserves_accounts_catalog_and_foreign_key_checks(self):
        tables = self._project_children()
        with self.engine.begin() as connection:
            before = reset.non_account_fingerprints(connection, skip_tables=reset.PROJECT_DATA_TABLES)
            summary = reset.reset_project_data(connection, apply=True)
            self.assertEqual(summary["total_rows_removed"], 5)
            self.assertEqual(summary["projects_after"], 0)
            self.assertEqual(before, reset.non_account_fingerprints(connection, skip_tables=reset.PROJECT_DATA_TABLES))
            self.assertTrue(all(not list(connection.execute(select(table))) for table in tables))
            self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_keys").scalar(), 1)
            self.assertEqual(reset.reset_project_data(connection, apply=True)["total_rows_removed"], 0)

    def test_project_dry_run_preserves_data(self):
        tables = self._project_children()
        with self.engine.begin() as connection:
            reset.reset_project_data(connection)
            self.assertTrue(all(list(connection.execute(select(table))) for table in tables))

    def test_project_reset_refuses_unreviewed_dependency_before_deletion(self):
        metadata = MetaData()
        Table("projects", metadata, autoload_with=self.engine)
        unknown = Table("unreviewed_project_data", metadata, Column("id", Integer, primary_key=True),
                        Column("project_id", ForeignKey("projects.id")))
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            with self.assertRaises(RuntimeError):
                reset.reset_project_data(connection, apply=True)
            self.assertEqual(list(connection.scalars(select(self.projects.c.id))), [1])

    def test_project_deletion_rolls_back_on_failure(self):
        tables = self._project_children()
        with self.assertRaises(RuntimeError):
            with self.engine.begin() as connection:
                reset.reset_project_data(connection, apply=True)
                raise RuntimeError("Injected failure")
        with self.engine.connect() as connection:
            self.assertTrue(all(list(connection.execute(select(table))) for table in tables))


if __name__ == "__main__":
    unittest.main()
