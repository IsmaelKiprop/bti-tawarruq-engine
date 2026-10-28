from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from tawarruq.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from tawarruq import models  # noqa: F401
    from tawarruq.services.shariah_ledger_service import register_append_only_guards

    Base.metadata.create_all(bind=engine)
    _ensure_api_key_role_column()
    _ensure_ops_user_dealer_column()
    _ensure_ops_user_hr_columns()
    _ensure_audit_ops_columns()
    _ensure_application_desk_columns()
    _ensure_certificate_ecert_columns()
    _ensure_trade_evidence_columns()
    _ensure_customer_email_column()
    _ensure_api_key_hmac_column()
    _ensure_mobile_account_reset_columns()
    _ensure_mobile_approval_columns()
    _ensure_customer_kyc_columns()
    _ensure_mobile_push_token_column()
    _ensure_control_schema()
    _ensure_sedania_financing_columns()
    _ensure_institution_kyc_columns()
    _ensure_api_key_reveal_column()
    _ensure_platform_settings_table()
    register_append_only_guards()


def _ensure_api_key_role_column() -> None:
    """SQLite dev databases created before RBAC may lack api_keys.role."""
    if not settings.is_sqlite:
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "api_keys" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("api_keys")}
    if "role" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE api_keys ADD COLUMN role VARCHAR(32) DEFAULT 'institution_ops' NOT NULL"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_keys_role ON api_keys (role)"))


def _ensure_ops_user_dealer_column() -> None:
    """SQLite: bind an ops user to one Agent Dealer desk."""
    if not settings.is_sqlite:
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "ops_users" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("ops_users")}
    if "agent_dealer_id" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE ops_users ADD COLUMN agent_dealer_id VARCHAR(36)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ops_users_agent_dealer_id ON ops_users (agent_dealer_id)"))


def _ensure_ops_user_hr_columns() -> None:
    """Add optional HR / profile fields on ops_users (SQLite and Postgres)."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "ops_users" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("ops_users")}
    additions = {
        "job_title": "ALTER TABLE ops_users ADD COLUMN job_title VARCHAR(128)",
        "department": "ALTER TABLE ops_users ADD COLUMN department VARCHAR(128)",
        "employee_number": "ALTER TABLE ops_users ADD COLUMN employee_number VARCHAR(64)",
        "phone": "ALTER TABLE ops_users ADD COLUMN phone VARCHAR(64)",
        "office": "ALTER TABLE ops_users ADD COLUMN office VARCHAR(128)",
    }
    with engine.begin() as conn:
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(text(ddl))


def _ensure_audit_ops_columns() -> None:
    """Institution / request grouping columns for ops audit middleware."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "audit_events" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("audit_events")}
    additions = {
        "institution_id": "ALTER TABLE audit_events ADD COLUMN institution_id VARCHAR(36)",
        "actor_user_id": "ALTER TABLE audit_events ADD COLUMN actor_user_id VARCHAR(36)",
        "group_id": "ALTER TABLE audit_events ADD COLUMN group_id VARCHAR(36)",
        "action_group": "ALTER TABLE audit_events ADD COLUMN action_group VARCHAR(64)",
        "http_method": "ALTER TABLE audit_events ADD COLUMN http_method VARCHAR(16)",
        "http_path": "ALTER TABLE audit_events ADD COLUMN http_path VARCHAR(512)",
        "http_status": "ALTER TABLE audit_events ADD COLUMN http_status INTEGER",
    }
    with engine.begin() as conn:
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(text(ddl))
        if "institution_id" not in columns:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_events_institution_id ON audit_events (institution_id)"))
        if "group_id" not in columns:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_events_group_id ON audit_events (group_id)"))
        if "action_group" not in columns:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_events_action_group ON audit_events (action_group)"))


def _ensure_application_desk_columns() -> None:
    """SQLite: add customer_name / currency for Bursa desk packets."""
    if not settings.is_sqlite:
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "financing_applications" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("financing_applications")}
    with engine.begin() as conn:
        if "customer_name" not in columns:
            conn.execute(text("ALTER TABLE financing_applications ADD COLUMN customer_name VARCHAR(256)"))
        if "currency" not in columns:
            conn.execute(text("ALTER TABLE financing_applications ADD COLUMN currency VARCHAR(8) DEFAULT 'KES' NOT NULL"))
        if "wad_text" not in columns:
            conn.execute(text("ALTER TABLE financing_applications ADD COLUMN wad_text TEXT"))
        if "wad_accepted_at" not in columns:
            conn.execute(text("ALTER TABLE financing_applications ADD COLUMN wad_accepted_at DATETIME"))


def _ensure_certificate_ecert_columns() -> None:
    """SQLite: add Bursa e-certificate metadata columns."""
    if not settings.is_sqlite:
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "certificates" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("certificates")}
    additions = {
        "seller": "ALTER TABLE certificates ADD COLUMN seller VARCHAR(255)",
        "buyer": "ALTER TABLE certificates ADD COLUMN buyer VARCHAR(255)",
        "bid_no": "ALTER TABLE certificates ADD COLUMN bid_no VARCHAR(32)",
        "selling_time": "ALTER TABLE certificates ADD COLUMN selling_time VARCHAR(64)",
        "selling_date": "ALTER TABLE certificates ADD COLUMN selling_date VARCHAR(64)",
        "value_date": "ALTER TABLE certificates ADD COLUMN value_date VARCHAR(64)",
        "product_code": "ALTER TABLE certificates ADD COLUMN product_code VARCHAR(64)",
        "product_description": "ALTER TABLE certificates ADD COLUMN product_description VARCHAR(255)",
        "unit": "ALTER TABLE certificates ADD COLUMN unit VARCHAR(64)",
        "volume": "ALTER TABLE certificates ADD COLUMN volume VARCHAR(64)",
        "currency": "ALTER TABLE certificates ADD COLUMN currency VARCHAR(8)",
        "price": "ALTER TABLE certificates ADD COLUMN price VARCHAR(64)",
        "price_myr_equivalent": "ALTER TABLE certificates ADD COLUMN price_myr_equivalent VARCHAR(64)",
        "value_amount": "ALTER TABLE certificates ADD COLUMN value_amount VARCHAR(64)",
        "transaction_type": "ALTER TABLE certificates ADD COLUMN transaction_type VARCHAR(64)",
        "pdf_path": "ALTER TABLE certificates ADD COLUMN pdf_path VARCHAR(512)",
        "pdf_filename": "ALTER TABLE certificates ADD COLUMN pdf_filename VARCHAR(255)",
        "details_json": "ALTER TABLE certificates ADD COLUMN details_json TEXT",
    }
    with engine.begin() as conn:
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(text(ddl))


def _ensure_trade_evidence_columns() -> None:
    """SQLite: add e-PO / DO refs on asset batches."""
    if not settings.is_sqlite:
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "asset_batches" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("asset_batches")}
    additions = {
        "purchase_order_ref": "ALTER TABLE asset_batches ADD COLUMN purchase_order_ref VARCHAR(64)",
        "delivery_order_ref": "ALTER TABLE asset_batches ADD COLUMN delivery_order_ref VARCHAR(128)",
        "supplier_invoice_ref": "ALTER TABLE asset_batches ADD COLUMN supplier_invoice_ref VARCHAR(64)",
        "source_dealer_code": "ALTER TABLE asset_batches ADD COLUMN source_dealer_code VARCHAR(32)",
    }
    with engine.begin() as conn:
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(text(ddl))


def _ensure_customer_email_column() -> None:
    """SQLite: add customer email for Murabaha accept notices."""
    if not settings.is_sqlite:
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "customers" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("customers")}
    if "email" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE customers ADD COLUMN email VARCHAR(255)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_customers_email ON customers (email)"))


def _ensure_api_key_hmac_column() -> None:
    """SQLite: HMAC secret for inbound SACCO execute requests."""
    if not settings.is_sqlite:
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "api_keys" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("api_keys")}
    if "hmac_secret" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE api_keys ADD COLUMN hmac_secret VARCHAR(64)"))


def _ensure_api_key_reveal_column() -> None:
    """Keep the issued API client key so FI Admin can copy it from FI profile."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "api_keys" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("api_keys")}
    if "reveal_key" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE api_keys ADD COLUMN reveal_key VARCHAR(128)"))


def _ensure_mobile_account_reset_columns() -> None:
    """SQLite: password-reset fields for mobile accounts created before reset support."""
    if not settings.is_sqlite:
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "mobile_accounts" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("mobile_accounts")}
    with engine.begin() as conn:
        if "password_reset_hash" not in columns:
            conn.execute(text("ALTER TABLE mobile_accounts ADD COLUMN password_reset_hash VARCHAR(128)"))
        if "password_reset_expires_at" not in columns:
            conn.execute(text("ALTER TABLE mobile_accounts ADD COLUMN password_reset_expires_at DATETIME"))


def _ensure_mobile_approval_columns() -> None:
    """SQLite: hybrid onboarding — approval status, limit, invites."""
    if not settings.is_sqlite:
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "mobile_invites" not in tables:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE mobile_invites (
                        id VARCHAR(36) PRIMARY KEY,
                        institution_id VARCHAR(36) NOT NULL,
                        email VARCHAR(255) NOT NULL,
                        phone VARCHAR(32),
                        full_name VARCHAR(255),
                        code VARCHAR(32) NOT NULL UNIQUE,
                        credit_limit NUMERIC(18, 2) NOT NULL DEFAULT 0,
                        activate_on_claim BOOLEAN NOT NULL DEFAULT 0,
                        status VARCHAR(32) NOT NULL DEFAULT 'pending',
                        expires_at DATETIME,
                        claimed_account_id VARCHAR(36),
                        created_by_ops_user_id VARCHAR(36),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_invites_email ON mobile_invites (email)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_invites_code ON mobile_invites (code)"))
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_mobile_invites_institution_id ON mobile_invites (institution_id)")
            )

    if "mobile_accounts" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("mobile_accounts")}
    additions = {
        "approval_status": "ALTER TABLE mobile_accounts ADD COLUMN approval_status VARCHAR(32) DEFAULT 'pending' NOT NULL",
        "phone": "ALTER TABLE mobile_accounts ADD COLUMN phone VARCHAR(32)",
        "credit_limit": "ALTER TABLE mobile_accounts ADD COLUMN credit_limit NUMERIC(18, 2)",
        "rejection_reason": "ALTER TABLE mobile_accounts ADD COLUMN rejection_reason VARCHAR(512)",
        "approved_at": "ALTER TABLE mobile_accounts ADD COLUMN approved_at DATETIME",
        "approved_by_ops_user_id": "ALTER TABLE mobile_accounts ADD COLUMN approved_by_ops_user_id VARCHAR(36)",
        "invite_id": "ALTER TABLE mobile_accounts ADD COLUMN invite_id VARCHAR(36)",
    }
    with engine.begin() as conn:
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(text(ddl))
        if "approval_status" not in columns or True:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_accounts_approval_status ON mobile_accounts (approval_status)"))


def _ensure_customer_kyc_columns() -> None:
    if not settings.is_sqlite:
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "customers" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("customers")}
    additions = {
        "id_document_path": "ALTER TABLE customers ADD COLUMN id_document_path VARCHAR(512)",
        "selfie_path": "ALTER TABLE customers ADD COLUMN selfie_path VARCHAR(512)",
        "kyc_submitted_at": "ALTER TABLE customers ADD COLUMN kyc_submitted_at DATETIME",
    }
    with engine.begin() as conn:
        for name, ddl in additions.items():
            if name not in columns:
                conn.execute(text(ddl))


def _ensure_mobile_push_token_column() -> None:
    if not settings.is_sqlite:
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "mobile_accounts" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("mobile_accounts")}
    if "push_token" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE mobile_accounts ADD COLUMN push_token VARCHAR(512)"))


def _ensure_control_schema() -> None:
    """Add maker-checker / billing / MFA columns on existing SQLite and Postgres databases."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    bool_true = "1" if settings.is_sqlite else "TRUE"

    def add_missing(table: str, additions: dict[str, str]) -> None:
        if table not in tables:
            return
        existing = {col["name"] for col in inspector.get_columns(table)}
        with engine.begin() as conn:
            for name, ddl in additions.items():
                if name not in existing:
                    conn.execute(text(ddl))

    add_missing(
        "institutions",
        {
            "active": f"ALTER TABLE institutions ADD COLUMN active BOOLEAN DEFAULT {bool_true} NOT NULL",
            "approval_steps": (
                "ALTER TABLE institutions ADD COLUMN approval_steps VARCHAR(256) "
                "DEFAULT 'murabaha,liquidation,disbursement' NOT NULL"
            ),
            "approval_limit_amount": "ALTER TABLE institutions ADD COLUMN approval_limit_amount NUMERIC(18, 2)",
            "billing_fee_bps": "ALTER TABLE institutions ADD COLUMN billing_fee_bps INTEGER DEFAULT 25 NOT NULL",
            "bti_charge_pct": "ALTER TABLE institutions ADD COLUMN bti_charge_pct NUMERIC(10, 6) DEFAULT 0.004 NOT NULL",
        },
    )
    add_missing(
        "ops_users",
        {
            "approval_limit_amount": "ALTER TABLE ops_users ADD COLUMN approval_limit_amount NUMERIC(18, 2)",
            "mfa_secret": "ALTER TABLE ops_users ADD COLUMN mfa_secret VARCHAR(64)",
            "mfa_method": "ALTER TABLE ops_users ADD COLUMN mfa_method VARCHAR(16)",
            "mfa_enabled": f"ALTER TABLE ops_users ADD COLUMN mfa_enabled BOOLEAN DEFAULT {0 if settings.is_sqlite else 'FALSE'} NOT NULL",
        },
    )


def _ensure_sedania_financing_columns() -> None:
    """Add bank CMP / muqassah / CASA / physical-delivery columns on existing DBs."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "tawarruq_executions" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("tawarruq_executions")}
    bool_true = "1" if settings.is_sqlite else "TRUE"
    bool_false = "0" if settings.is_sqlite else "FALSE"
    dt = "DATETIME" if settings.is_sqlite else "TIMESTAMP"
    additions = {
        "path": "ALTER TABLE tawarruq_executions ADD COLUMN path VARCHAR(32) DEFAULT 'sacco' NOT NULL",
        "flow_variant": (
            "ALTER TABLE tawarruq_executions ADD COLUMN flow_variant VARCHAR(32) "
            "DEFAULT 'approved_wakeel' NOT NULL"
        ),
        "delivery_mode": (
            "ALTER TABLE tawarruq_executions ADD COLUMN delivery_mode VARCHAR(32) "
            "DEFAULT 'constructive' NOT NULL"
        ),
        "agency_role": "ALTER TABLE tawarruq_executions ADD COLUMN agency_role VARCHAR(16) DEFAULT 'wakeel' NOT NULL",
        "agency_party": (
            "ALTER TABLE tawarruq_executions ADD COLUMN agency_party VARCHAR(64) "
            "DEFAULT 'SEDANIA_AS_SALAM_CAPITAL' NOT NULL"
        ),
        "appoint_sasc": (
            f"ALTER TABLE tawarruq_executions ADD COLUMN appoint_sasc BOOLEAN DEFAULT {bool_true} NOT NULL"
        ),
        "purchase_order_ref": "ALTER TABLE tawarruq_executions ADD COLUMN purchase_order_ref VARCHAR(64)",
        "commodity_invoice_ref": "ALTER TABLE tawarruq_executions ADD COLUMN commodity_invoice_ref VARCHAR(64)",
        "delivery_order_ref": "ALTER TABLE tawarruq_executions ADD COLUMN delivery_order_ref VARCHAR(128)",
        "trading_ecert_ref": "ALTER TABLE tawarruq_executions ADD COLUMN trading_ecert_ref VARCHAR(128)",
        "supplier_ref": "ALTER TABLE tawarruq_executions ADD COLUMN supplier_ref VARCHAR(128)",
        "purchaser_ref": "ALTER TABLE tawarruq_executions ADD COLUMN purchaser_ref VARCHAR(128)",
        "muqassah_ref": "ALTER TABLE tawarruq_executions ADD COLUMN muqassah_ref VARCHAR(64)",
        "muqassah_at": f"ALTER TABLE tawarruq_executions ADD COLUMN muqassah_at {dt}",
        "casa_account": "ALTER TABLE tawarruq_executions ADD COLUMN casa_account VARCHAR(64)",
        "casa_ref": "ALTER TABLE tawarruq_executions ADD COLUMN casa_ref VARCHAR(64)",
        "casa_credited_at": f"ALTER TABLE tawarruq_executions ADD COLUMN casa_credited_at {dt}",
        "cash_disbursement": (
            "ALTER TABLE tawarruq_executions ADD COLUMN cash_disbursement VARCHAR(32) "
            "DEFAULT 'sacco_cbs' NOT NULL"
        ),
        "physical_delivery_requested": (
            "ALTER TABLE tawarruq_executions ADD COLUMN physical_delivery_requested "
            f"BOOLEAN DEFAULT {bool_false} NOT NULL"
        ),
        "physical_delivery_status": "ALTER TABLE tawarruq_executions ADD COLUMN physical_delivery_status VARCHAR(32)",
        "physical_delivery_notified_at": (
            f"ALTER TABLE tawarruq_executions ADD COLUMN physical_delivery_notified_at {dt}"
        ),
        "repayment_settled_at": f"ALTER TABLE tawarruq_executions ADD COLUMN repayment_settled_at {dt}",
    }
    with engine.begin() as conn:
        for name, ddl in additions.items():
            if name not in existing:
                conn.execute(text(ddl))
        if "path" not in existing:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tawarruq_executions_path ON tawarruq_executions (path)"))


def _ensure_institution_kyc_columns() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "institutions" not in tables:
        return
    existing = {col["name"] for col in inspector.get_columns("institutions")}
    with engine.begin() as conn:
        if "lifecycle_status" not in existing:
            conn.execute(
                text("ALTER TABLE institutions ADD COLUMN lifecycle_status VARCHAR(32) DEFAULT 'active' NOT NULL")
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_institutions_lifecycle_status ON institutions (lifecycle_status)")
            )


def _ensure_platform_settings_table() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "platform_settings" in inspector.get_table_names():
        existing = {col["name"] for col in inspector.get_columns("platform_settings")}
        if "sedania_charge_pct" not in existing:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE platform_settings ADD COLUMN sedania_charge_pct "
                        "NUMERIC(10, 6) DEFAULT 0.0035 NOT NULL"
                    )
                )
        return
    dt = "DATETIME" if settings.is_sqlite else "TIMESTAMP"
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE platform_settings (
                    id VARCHAR(32) NOT NULL PRIMARY KEY,
                    sedania_charge_pct NUMERIC(10, 6) NOT NULL DEFAULT 0.0035,
                    updated_at {dt},
                    updated_by_id VARCHAR(36),
                    FOREIGN KEY(updated_by_id) REFERENCES ops_users (id)
                )
                """
            )
        )
