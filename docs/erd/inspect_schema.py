"""Read schema metadata only; never initialize or modify the database."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from sqlalchemy import create_engine, inspect, text
from dotenv import dotenv_values
from app.models import Base

def extract(inspector, name):
    return {
        'name': name,
        'columns': [{k: (str(v) if k == 'type' else v) for k, v in c.items()
                     if k in ('name', 'type', 'nullable', 'default', 'autoincrement')}
                    for c in inspector.get_columns(name)],
        'primary_key': inspector.get_pk_constraint(name)['constrained_columns'],
        'foreign_keys': inspector.get_foreign_keys(name),
        'unique_constraints': inspector.get_unique_constraints(name),
        'checks': inspector.get_check_constraints(name),
    }

import os
database_url = os.environ.get('DATABASE_URL') or dotenv_values(ROOT / '.env').get('DATABASE_URL')
engine = create_engine(database_url, connect_args={'connect_timeout': 5})
try:
    with engine.connect() as conn:
        database, datadir, version = conn.execute(text('SELECT DATABASE(), @@datadir, VERSION()')).one()
        if database != 'ved_electrical':
            raise RuntimeError('Configured database is not the requested ved_electrical database.')
        inspector = inspect(conn)
        tables = [extract(inspector, t) for t in inspector.get_table_names()]
except Exception as exc:
    print('Schema inspection failed: ' + type(exc).__name__)
    raise SystemExit(1) from None

differences = []
live_names = {t['name'] for t in tables}
model_names = set(Base.metadata.tables)
for name in sorted(live_names ^ model_names):
    differences.append({'table': name, 'kind': 'database_only' if name in live_names else 'model_only'})
for table in tables:
    if table['name'] not in model_names:
        continue
    model = Base.metadata.tables[table['name']]
    live_columns = {c['name']: c for c in table['columns']}
    for name in sorted(set(live_columns) ^ set(model.columns.keys())):
        differences.append({'table': table['name'], 'column': name, 'kind': 'column_presence'})
    for column in model.columns:
        if column.name in live_columns and column.nullable != live_columns[column.name]['nullable']:
            differences.append({'table': table['name'], 'column': column.name, 'kind': 'nullability'})
    live_fks = {(tuple(f['constrained_columns']), f['referred_table'], tuple(f['referred_columns'])) for f in table['foreign_keys']}
    model_fks = {(tuple(e.parent.name for e in f.elements), f.elements[0].column.table.name,
                  tuple(e.column.name for e in f.elements)) for f in model.foreign_key_constraints}
    if live_fks != model_fks:
        differences.append({'table': table['name'], 'kind': 'foreign_keys',
                            'database_only': list(live_fks-model_fks), 'model_only': list(model_fks-live_fks)})

result = {'database': database, 'server_version': version, 'data_directory': datadir,
          'captured_at': datetime.now(timezone.utc).isoformat(),
          'source': 'Live database metadata; no application rows read',
          'tables': tables, 'model_comparison': differences}
out = Path(__file__).with_name('schema-metadata.json')
out.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
print(json.dumps({'database': database, 'data_directory': datadir, 'tables': len(tables),
                  'columns': sum(len(t['columns']) for t in tables),
                  'foreign_keys': sum(len(t['foreign_keys']) for t in tables),
                  'model_differences': differences,
                  'sizes': {t['name']: [len(t['columns']),len(t['foreign_keys'])] for t in tables}}, indent=2))
