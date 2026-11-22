PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS departments(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
 name TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL,
 department_id INTEGER NOT NULL REFERENCES departments, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
 category TEXT NOT NULL, specifications TEXT NOT NULL DEFAULT '', creator_id INTEGER NOT NULL REFERENCES users);
CREATE TABLE IF NOT EXISTS units(id INTEGER PRIMARY KEY, listing_id INTEGER NOT NULL REFERENCES listings,
 owner_dept_id INTEGER NOT NULL REFERENCES departments, custodian_id INTEGER NOT NULL REFERENCES users,
 location TEXT NOT NULL, condition TEXT NOT NULL, publication TEXT NOT NULL DEFAULT 'Draft',
 serviceability TEXT NOT NULL DEFAULT 'Serviceable', lifecycle TEXT NOT NULL DEFAULT 'Active',
 value_cents INTEGER CHECK(value_cents>=0), purchase_date TEXT, version INTEGER NOT NULL DEFAULT 1,
 parent_unit_id INTEGER REFERENCES units);
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, creator_id INTEGER NOT NULL REFERENCES users,
 listing_id INTEGER REFERENCES listings, purpose TEXT NOT NULL, category TEXT NOT NULL,
 specifications TEXT NOT NULL DEFAULT '', preferred_condition TEXT NOT NULL DEFAULT '',
 quantity INTEGER NOT NULL CHECK(quantity>0), urgency TEXT NOT NULL, needed_date TEXT NOT NULL,
 destination_dept_id INTEGER NOT NULL REFERENCES departments,
 destination_custodian_id INTEGER NOT NULL REFERENCES users, destination_location TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT,
 decision_reason TEXT, version INTEGER NOT NULL DEFAULT 1, request_key TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS holds(id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL REFERENCES requests,
 unit_id INTEGER NOT NULL REFERENCES units, active INTEGER NOT NULL DEFAULT 1, UNIQUE(request_id,unit_id));
CREATE UNIQUE INDEX IF NOT EXISTS one_active_hold ON holds(unit_id) WHERE active=1;
CREATE TABLE IF NOT EXISTS transfers(id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL REFERENCES requests,
 unit_id INTEGER NOT NULL REFERENCES units, source_dept_id INTEGER NOT NULL REFERENCES departments,
 source_custodian_id INTEGER NOT NULL REFERENCES users, source_location TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'Approved', collection_evidence_id INTEGER,
 receipt_evidence_id INTEGER, completed_at TEXT, UNIQUE(request_id,unit_id));
CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, target_id INTEGER NOT NULL,
 actor_id INTEGER NOT NULL REFERENCES users, decision TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, unit_id INTEGER NOT NULL REFERENCES units,
 actor_id INTEGER NOT NULL REFERENCES users, action TEXT NOT NULL, detail TEXT NOT NULL,
 cost_cents INTEGER CHECK(cost_cents>=0), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor_id INTEGER REFERENCES users,
 target_type TEXT NOT NULL, target_id INTEGER NOT NULL, action TEXT NOT NULL,
 detail TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, recipient_id INTEGER NOT NULL REFERENCES users,
 audit_id INTEGER NOT NULL REFERENCES audit, message TEXT NOT NULL, read_at TEXT, UNIQUE(recipient_id,audit_id));
CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY, unit_id INTEGER NOT NULL REFERENCES units,
 uploader_id INTEGER NOT NULL REFERENCES users, filename TEXT NOT NULL, storage_name TEXT NOT NULL UNIQUE,
 mime TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS maintenance(id INTEGER PRIMARY KEY, unit_id INTEGER NOT NULL REFERENCES units,
 assignee_id INTEGER NOT NULL REFERENCES users, status TEXT NOT NULL, description TEXT NOT NULL,
 outcome TEXT, cost_cents INTEGER CHECK(cost_cents>=0), evidence_id INTEGER REFERENCES evidence,
 created_at TEXT NOT NULL, completed_at TEXT);
CREATE TABLE IF NOT EXISTS dispositions(id INTEGER PRIMARY KEY, unit_id INTEGER NOT NULL REFERENCES units,
 proposer_id INTEGER NOT NULL REFERENCES users, action TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending',
 reason TEXT NOT NULL, evidence_id INTEGER REFERENCES evidence, created_at TEXT NOT NULL, completed_at TEXT);
CREATE TABLE IF NOT EXISTS impacts(id INTEGER PRIMARY KEY, unit_id INTEGER NOT NULL UNIQUE REFERENCES units,
 replacement_cents INTEGER CHECK(replacement_cents>=0), transfer_cents INTEGER CHECK(transfer_cents>=0),
 repair_cents INTEGER CHECK(repair_cents>=0), refurbishment_cents INTEGER CHECK(refurbishment_cents>=0),
 replacement_co2 REAL, reuse_co2 REAL, prior_retirement TEXT, revised_retirement TEXT,
 source TEXT NOT NULL DEFAULT '', finance_validated INTEGER NOT NULL DEFAULT 0,
 environment_validated INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS ai_records(id INTEGER PRIMARY KEY, actor_id INTEGER NOT NULL REFERENCES users,
 task TEXT NOT NULL, context TEXT NOT NULL, output TEXT, provider TEXT NOT NULL, model TEXT NOT NULL,
 prompt_version TEXT NOT NULL, validation TEXT NOT NULL, review TEXT, reason TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS narratives(id INTEGER PRIMARY KEY, actor_id INTEGER NOT NULL REFERENCES users,
 ai_id INTEGER NOT NULL REFERENCES ai_records, body TEXT NOT NULL, published_at TEXT NOT NULL);
