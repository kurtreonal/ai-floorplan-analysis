"""Create only additive client-workflow/access tables; preserve existing data."""
import sys
import argparse
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from sqlalchemy import inspect, select, create_engine
from sqlalchemy.engine import make_url
from app.core.config import get_settings
from sqlalchemy.orm import Session
from app.core.database import get_engine
from app.models import Role
from app.models.client_workflow import LocalCredential, LinkedIdentity, ProjectAssignment, ProjectPublication, AccountAccess
from app.models.account_security import AccountEmail, EmailChallenge, TrustedDevice, AdminActivity
from app.models.legend_artwork import LegendArtwork
from app.models.application_defaults import ApplicationDefaults


def provision(engine):
    tables = [x.__table__ for x in (LocalCredential, LinkedIdentity, ProjectAssignment, ProjectPublication, AccountAccess,
        AccountEmail, EmailChallenge, TrustedDevice, AdminActivity, LegendArtwork, ApplicationDefaults)]
    before = set(inspect(engine).get_table_names())
    for table in tables:
        table.create(engine, checkfirst=True)
    with Session(engine) as db:
        if db.scalar(select(Role).where(Role.name == 'CLIENT')) is None:
            db.add(Role(name='CLIENT'))
            db.commit()
    after = set(inspect(engine).get_table_names())
    print({'created_tables': sorted(after - before), 'existing_tables_removed': sorted(before - after),
           'client_role': 'ready', 'accounts_or_projects_modified': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--xampp-config', type=Path)
    args = parser.parse_args()
    engine = get_engine()
    if args.xampp_config:
        # Read only the local, explicitly authorized phpMyAdmin connection.
        # Never print connection strings or change the application's DB account.
        config = args.xampp_config.read_text(encoding='utf-8')
        def setting(key):
            match = re.search(r"\$cfg\['Servers'\]\[\$i\]\['" + key + r"'\]\s*=\s*'([^']*)'", config)
            if match is None:
                raise SystemExit('XAMPP administrator configuration is incomplete.')
            return match[1]
        url = make_url(get_settings().database_url).set(username=setting('user'), password=setting('password'))
        engine = create_engine(url, connect_args={'connect_timeout': 5})
    try:
        provision(engine)
    except Exception as error:
        print({'status': 'failed', 'error_type': type(error).__name__})
        sys.exit(1)
