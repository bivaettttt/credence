from alembic import op

revision = "001"
down_revision = None


def upgrade():
    op.execute("""
CREATE TABLE users (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), username text UNIQUE NOT NULL, name text NOT NULL,
 password text NOT NULL, role text NOT NULL CHECK(role IN ('APPLICANT','CREDIT_ANALYST','RISK_OFFICER','ADMIN')),
 active boolean NOT NULL DEFAULT true
);
CREATE TABLE sessions (digest text PRIMARY KEY, actor uuid NOT NULL REFERENCES users, expires timestamptz NOT NULL);
CREATE TABLE organizations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL, industry text NOT NULL,
 registration text UNIQUE NOT NULL, profile text NOT NULL, kind text NOT NULL DEFAULT 'SYNTHETIC_COMPANY',
 active boolean NOT NULL DEFAULT true
);
CREATE TABLE organization_members (
 organization_id uuid REFERENCES organizations, actor uuid REFERENCES users, PRIMARY KEY(organization_id,actor)
);
CREATE TABLE products (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), code text NOT NULL, version int NOT NULL, name text NOT NULL,
 min_amount bigint NOT NULL CHECK(min_amount>0), max_amount bigint NOT NULL CHECK(max_amount>=min_amount),
 min_months int NOT NULL CHECK(min_months>0), max_months int NOT NULL CHECK(max_months>=min_months),
 rate int NOT NULL CHECK(rate>=0), active boolean NOT NULL, UNIQUE(code,version)
);
CREATE TABLE applications (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), number bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 organization_id uuid NOT NULL REFERENCES organizations, product_id uuid NOT NULL REFERENCES products,
 owner_id uuid NOT NULL REFERENCES users, analyst_id uuid REFERENCES users,
 state text NOT NULL DEFAULT 'DRAFT' CHECK(state IN ('DRAFT','INFO_REQUIRED','SUBMITTED','REVIEW',
 'DECISION_PENDING','OFFERED','REJECTED','ACCEPTED','DECLINED','EXPIRED','WITHDRAWN')),
 revision int NOT NULL DEFAULT 1, data_version int NOT NULL DEFAULT 0,
 data jsonb NOT NULL, current_check uuid, current_risk uuid, current_recommendation uuid,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX application_queue ON applications(state,updated_at DESC);
CREATE INDEX application_org ON applications(organization_id);
CREATE TABLE documents (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), app_id uuid NOT NULL REFERENCES applications,
 kind text NOT NULL CHECK(kind IN ('FINANCIAL','REGISTRATION','SUPPORTING')),
 version int NOT NULL, label text NOT NULL, UNIQUE(app_id,kind,version)
);
CREATE TABLE snapshots (
 app_id uuid REFERENCES applications, version int, payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY(app_id,version)
);
CREATE TABLE evidence (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), app_id uuid NOT NULL,
 version int NOT NULL, kind text NOT NULL CHECK(kind IN ('ELIGIBILITY','RISK','RECOMMENDATION','DECISION')),
 actor uuid NOT NULL REFERENCES users, payload jsonb NOT NULL, created_at timestamptz DEFAULT clock_timestamp() NOT NULL,
 FOREIGN KEY(app_id,version) REFERENCES snapshots
);
CREATE INDEX evidence_app ON evidence(app_id,created_at DESC);
CREATE UNIQUE INDEX single_decision ON evidence(app_id) WHERE kind='DECISION';
ALTER TABLE applications ADD FOREIGN KEY(current_check) REFERENCES evidence;
ALTER TABLE applications ADD FOREIGN KEY(current_risk) REFERENCES evidence;
ALTER TABLE applications ADD FOREIGN KEY(current_recommendation) REFERENCES evidence;
CREATE TABLE offers (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), app_id uuid NOT NULL UNIQUE REFERENCES applications,
 decision_id uuid NOT NULL UNIQUE REFERENCES evidence, terms jsonb NOT NULL,
 expires_at timestamptz NOT NULL, state text NOT NULL DEFAULT 'OPEN' CHECK(state IN ('OPEN','ACCEPTED','DECLINED','EXPIRED'))
);
CREATE TABLE receipts (
 app_id uuid REFERENCES applications, actor uuid REFERENCES users, key text NOT NULL,
 digest text NOT NULL, payload jsonb NOT NULL, PRIMARY KEY(app_id,actor,key)
);
CREATE TABLE events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, app_id uuid REFERENCES applications,
 actor uuid NOT NULL REFERENCES users, action text NOT NULL, previous text, state text, reason text,
 request_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX events_application ON events(app_id,id DESC);
CREATE TABLE notifications (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, actor uuid NOT NULL REFERENCES users,
 app_id uuid NOT NULL REFERENCES applications, message text NOT NULL, read_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE FUNCTION immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Immutable record' USING ERRCODE='23514'; END $$;
CREATE TRIGGER seal_snapshots BEFORE UPDATE OR DELETE ON snapshots FOR EACH ROW EXECUTE FUNCTION immutable();
CREATE TRIGGER seal_evidence BEFORE UPDATE OR DELETE ON evidence FOR EACH ROW EXECUTE FUNCTION immutable();
CREATE TRIGGER seal_products BEFORE UPDATE OR DELETE ON products FOR EACH ROW EXECUTE FUNCTION immutable();
CREATE TRIGGER seal_events BEFORE UPDATE OR DELETE ON events FOR EACH ROW EXECUTE FUNCTION immutable();
CREATE TRIGGER seal_documents BEFORE UPDATE OR DELETE ON documents FOR EACH ROW EXECUTE FUNCTION immutable();
CREATE FUNCTION offer_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR OLD.state<>'OPEN' OR NEW.state='OPEN'
 OR (to_jsonb(NEW)-'state') IS DISTINCT FROM (to_jsonb(OLD)-'state') THEN
 RAISE EXCEPTION 'Immutable offer terms' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER seal_offer BEFORE UPDATE OR DELETE ON offers FOR EACH ROW EXECUTE FUNCTION offer_guard();
""")


def downgrade():
    op.execute(
        "DROP TABLE notifications,events,receipts,offers,evidence,snapshots,documents,applications,products,organization_members,organizations,sessions,users CASCADE"
    )
    op.execute("DROP FUNCTION immutable(), offer_guard()")
