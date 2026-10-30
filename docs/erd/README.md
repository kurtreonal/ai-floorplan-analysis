# VED Electrical Services — four compact ERD parts

Open **ved-electrical-erd.drawio** in diagrams.net using **File → Open From → Device**. The current document has four tabs:

- **Part A: Accounts and projects** — 10 tables.
- **Part B: Processing and AI** — 8 tables.
- **Part C: Symbols and layouts** — 9 tables.
- **Part D: Routing and estimates** — 6 tables.

This grouping follows the supplied reference: full table definitions connect within each part, while short, labeled continuation connectors connect the parts. Each table appears once. The diagrams include all 33 tables, 303 columns, and 60 foreign keys from the schema snapshot.

## How to follow a connector

A code in a table header is its diagram address. For example, **A2** identifies the users table in Part A. A foreign-key row pointing to an oval marked **A2** continues to that same users table. The small directory at the bottom of each part identifies its referenced tables.

Direct lines start at the exact child FK row and end at the parent table boundary. These are entity relationships; the position on the parent boundary does not identify a different parent field. All parent references in this schema point to the id primary key.

**PK** means primary key, **FK** means foreign key, **UQ** means a single-column unique constraint, and **?** means nullable. Crow's foot with a circle means zero or many; double bars mean exactly one; a circle with a bar means zero or one. Composite unique constraints and full SQL details remain in schema-metadata.json.

## Files

- **ved-electrical-erd.drawio**: current editable four-part document.
- **ved-electrical-erd-preview.html**: local preview of all four parts with fit and readable-size controls.
- **part-a.png** through **part-d.png**, and matching SVGs: individual diagrams.
- **four-parts-overview.png**, **ved-electrical-erd.png**, and **ved-electrical-erd.svg**: overview of the four parts.
- **verification.json**: coverage and layout checks.
- **parts-layout.json**: drawing geometry and relationship mapping.
- **build_parts_erd.py**: current generator. Earlier generators and preview/ files belong to superseded drafts.

## Source and verification

The source is the live XAMPP ved_electrical schema captured on 7 October 2026, previously compared with the SQLAlchemy models. This revision uses that metadata snapshot and changes the diagram layout only. No application rows, credentials, database structures, original uploads, or reference images were changed.

- **PASS:** four main parts, all 33 full tables represented exactly once.
- **PASS:** all 303 columns and 60 foreign keys preserved.
- **PASS:** 32 direct relationships within parts and 28 continuation relationships between parts.
- **PASS:** zero crossed or overlapping connectors, zero connector intersections with tables or other continuation symbols.
- **PASS:** text fits; XML parses; all native edge endpoints resolve; previews visually inspected.
- **PASS:** total canvas area is 52.7% smaller than the previous single-canvas version.
- **NOT TESTED:** importing into the diagrams.net editor; the earlier browser attempt remained on its loading screen.

Interpretation releases have no declared foreign keys and are displayed without invented connections. Document-based geometry and route storage are preserved as actual fields; no roadmap-only tables are added.
