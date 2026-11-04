"""Lightweight SQLite migrations for dev. Run: python -m app.db_migrate"""

from sqlalchemy import inspect, text

from app.core.database import engine


def _is_sqlite() -> bool:
    return engine.dialect.name == "sqlite"


def _ensure_tables(table_names: list[str]) -> None:
    import app.models  # noqa: F401

    from app.core.database import Base

    insp = inspect(engine)
    missing = [name for name in table_names if not insp.has_table(name)]
    if not missing:
        return
    tables = [
        Base.metadata.tables[name]
        for name in missing
        if name in Base.metadata.tables
    ]
    if tables:
        Base.metadata.create_all(bind=engine, tables=tables)


def migrate_team_reporting() -> None:
    """Admin / Manager / Caregiver team: who each caregiver and client reports to."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in ("caregivers", "elders"):
            if not insp.has_table(table):
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if "manager_user_id" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN manager_user_id INTEGER"))
        if insp.has_table("products"):
            cols = {c["name"] for c in insp.get_columns("products")}
            if "image_key" not in cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN image_key VARCHAR(500)"))
            if "image_version" not in cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN image_version INTEGER DEFAULT 0 NOT NULL"))
            if "product_code" not in cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN product_code VARCHAR(20)"))
        if insp.has_table("orders"):
            cols = {c["name"] for c in insp.get_columns("orders")}
            ts = "DATETIME" if _is_sqlite() else "TIMESTAMP WITH TIME ZONE"
            for name, ddl in (
                ("quoted_at", ts),
                ("family_note", "VARCHAR(300) DEFAULT '' NOT NULL"),
                ("paid_paise", "INTEGER DEFAULT 0 NOT NULL"),
                ("paid_at", ts),
                ("wallet_transaction_id", "VARCHAR(32)"),
            ):
                if name not in cols:
                    conn.execute(text(f"ALTER TABLE orders ADD COLUMN {name} {ddl}"))
        if insp.has_table("care_jobs"):
            cols = {c["name"] for c in insp.get_columns("care_jobs")}
            if "report" not in cols:
                kind = "TEXT" if _is_sqlite() else "JSON"
                conn.execute(text(f"ALTER TABLE care_jobs ADD COLUMN report {kind}"))
            # Visit location capture: check-in accuracy and the check-out point.
            for name in ("checkin_accuracy_m", "checkout_lat", "checkout_lng", "checkout_accuracy_m"):
                if name not in cols:
                    conn.execute(text(f"ALTER TABLE care_jobs ADD COLUMN {name} FLOAT"))


def migrate_caregiver_portal() -> None:
    """Tables behind the caregiver field app (/api/v1/caregiver-portal/*):
    check-in devices and events, attendance, home geofences, visits and pay runs."""
    import app.models.assignment  # noqa: F401
    import app.models.attendance_alert  # noqa: F401
    import app.models.attendance_record  # noqa: F401
    import app.models.caregiver_device  # noqa: F401
    import app.models.caregiver_location_event  # noqa: F401
    import app.models.elder_location  # noqa: F401
    import app.models.payroll_deduction  # noqa: F401
    import app.models.payroll_run  # noqa: F401
    import app.models.visit  # noqa: F401
    import app.models.care_job  # noqa: F401
    import app.models.commerce  # noqa: F401

    _ensure_tables(
        [
            "care_jobs",
            "products",
            "coupons",
            "orders",
            "assignments",
            "attendance_records",
            "attendance_alerts",
            "caregiver_devices",
            "caregiver_location_events",
            "elder_locations",
            "visits",
            "payroll_runs",
            "payroll_lines",
            "payroll_deductions",
        ]
    )


def migrate_app_global_settings() -> None:
    """Platform key/value store (global catalog). Must exist before catalog APIs run."""
    import app.models.app_global_setting  # noqa: F401

    _ensure_tables(["app_global_settings"])


def migrate_auth_attempts() -> None:
    """Brute-force throttle for sign-in and password-reset requests."""
    import app.models.auth_attempt  # noqa: F401

    _ensure_tables(["auth_attempts"])


def migrate_documents():
    if not _is_sqlite():
        insp = inspect(engine)
        if insp.has_table("documents"):
            with engine.begin() as conn:
                try:
                    conn.execute(
                        text("ALTER TABLE documents ALTER COLUMN tenant_id DROP NOT NULL")
                    )
                except Exception:
                    pass
        return
    insp = inspect(engine)
    if not insp.has_table("documents"):
        return

    cols = {c["name"] for c in insp.get_columns("documents")}
    alters = []

    if "storage_key" not in cols:
        alters.append("ALTER TABLE documents ADD COLUMN storage_key VARCHAR(1000)")
    if "mime_type" not in cols:
        alters.append("ALTER TABLE documents ADD COLUMN mime_type VARCHAR(100)")
    if "file_size_bytes" not in cols:
        alters.append("ALTER TABLE documents ADD COLUMN file_size_bytes INTEGER")
    if "rejection_reason" not in cols:
        alters.append("ALTER TABLE documents ADD COLUMN rejection_reason TEXT")
    if "verified_at" not in cols:
        alters.append("ALTER TABLE documents ADD COLUMN verified_at DATETIME")
    if "verified_by_user_id" not in cols:
        alters.append(
            "ALTER TABLE documents ADD COLUMN verified_by_user_id INTEGER"
        )
    if "uploaded_by_user_id" not in cols:
        alters.append(
            "ALTER TABLE documents ADD COLUMN uploaded_by_user_id INTEGER"
        )
    if "document_name" not in cols:
        alters.append("ALTER TABLE documents ADD COLUMN document_name VARCHAR(255)")
    if "ocr_extracted_json" not in cols:
        alters.append("ALTER TABLE documents ADD COLUMN ocr_extracted_json TEXT")
    if "qr_extracted_json" not in cols:
        alters.append("ALTER TABLE documents ADD COLUMN qr_extracted_json TEXT")
    if "qr_validation_status" not in cols:
        alters.append(
            "ALTER TABLE documents ADD COLUMN qr_validation_status VARCHAR(50)"
        )
    if "extraction_timestamp" not in cols:
        alters.append("ALTER TABLE documents ADD COLUMN extraction_timestamp DATETIME")

    with engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
        if "storage_key" not in cols:
            conn.execute(
                text(
                    "UPDATE documents SET storage_key = storage_url "
                    "WHERE storage_key IS NULL OR storage_key = ''"
                )
            )


def migrate_tenants():
    if not _is_sqlite():
        return
    insp = inspect(engine)
    if not insp.has_table("tenants"):
        return

    cols = {c["name"] for c in insp.get_columns("tenants")}
    alters = []

    if "theme" not in cols:
        alters.append(
            "ALTER TABLE tenants ADD COLUMN theme VARCHAR(50) DEFAULT 'classic'"
        )
    if "logo_url" not in cols:
        alters.append("ALTER TABLE tenants ADD COLUMN logo_url VARCHAR(1000)")
    if "portal_title" not in cols:
        alters.append("ALTER TABLE tenants ADD COLUMN portal_title VARCHAR(255)")
    if "bench_cost_per_caregiver_month_inr" not in cols:
        alters.append(
            "ALTER TABLE tenants ADD COLUMN bench_cost_per_caregiver_month_inr "
            "FLOAT DEFAULT 15000.0"
        )
    if "elder_field_schema" not in cols:
        alters.append("ALTER TABLE tenants ADD COLUMN elder_field_schema TEXT")
    if "caregiver_field_schema" not in cols:
        alters.append("ALTER TABLE tenants ADD COLUMN caregiver_field_schema TEXT")
    if "vertical" not in cols:
        alters.append(
            "ALTER TABLE tenants ADD COLUMN vertical VARCHAR(50) DEFAULT 'LIVEWELL360'"
        )

    if not alters:
        return

    with engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
        if "vertical" not in cols:
            conn.execute(
                text(
                    "UPDATE tenants SET vertical = 'LIVEWELL360' "
                    "WHERE vertical IS NULL OR vertical = ''"
                )
            )


def migrate_safehome_deploy_vertical():
    """Force tenant.vertical to DEPLOY_VERTICAL on SafeHomeOps (fixes Elder Care nav)."""
    from app.core.deploy import deploy_vertical

    target = deploy_vertical()
    if target != "LIVEWELL360":
        return
    insp = inspect(engine)
    if not insp.has_table("tenants"):
        return
    cols = {c["name"] for c in insp.get_columns("tenants")}
    if "vertical" not in cols:
        return
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE tenants SET vertical = :v "
                "WHERE vertical IS NULL OR vertical = '' OR vertical != :v"
            ),
            {"v": target},
        )
        if result.rowcount:
            print(f"migrate_safehome_deploy_vertical: set {result.rowcount} tenant(s) -> {target}")


def migrate_elder_portal():
    insp = inspect(engine)

    if insp.has_table("users"):
        cols = {c["name"] for c in insp.get_columns("users")}
        alters = []
        if "elder_id" not in cols:
            alters.append("ALTER TABLE users ADD COLUMN elder_id INTEGER")
        if "portal_relationship" not in cols:
            alters.append(
                "ALTER TABLE users ADD COLUMN portal_relationship VARCHAR(100)"
            )
        if "caregiver_id" not in cols:
            alters.append("ALTER TABLE users ADD COLUMN caregiver_id INTEGER")
        if alters and _is_sqlite():
            with engine.begin() as conn:
                for sql in alters:
                    conn.execute(text(sql))

    if not _is_sqlite():
        _ensure_tables(["elder_notifications", "elder_messages"])
        return

    if not insp.has_table("elder_notifications"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE elder_notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER NOT NULL,
                        elder_id INTEGER NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        body TEXT NOT NULL,
                        sent_by_user_id INTEGER,
                        read_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(tenant_id) REFERENCES tenants(id),
                        FOREIGN KEY(elder_id) REFERENCES elders(id),
                        FOREIGN KEY(sent_by_user_id) REFERENCES users(id)
                    )
                    """
                )
            )

    if not insp.has_table("elder_messages"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE elder_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER NOT NULL,
                        elder_id INTEGER NOT NULL,
                        direction VARCHAR(50) NOT NULL,
                        body TEXT NOT NULL,
                        sender_user_id INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(tenant_id) REFERENCES tenants(id),
                        FOREIGN KEY(elder_id) REFERENCES elders(id),
                        FOREIGN KEY(sender_user_id) REFERENCES users(id)
                    )
                    """
                )
            )


def migrate_workflows():
    _ensure_tables(["workflow_events", "workflow_tasks"])

    insp = inspect(engine)
    if insp.has_table("tenants"):
        cols = {c["name"] for c in insp.get_columns("tenants")}
        if "workflow_config" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN workflow_config TEXT"))

    if insp.has_table("workflow_tasks"):
        cols = {c["name"] for c in insp.get_columns("workflow_tasks")}
        if "metadata_json" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE workflow_tasks ADD COLUMN metadata_json TEXT")
                )


def migrate_monitoring():
    if not _is_sqlite():
        _ensure_tables(["monitoring_consents", "monitoring_alerts"])
        return
    insp = inspect(engine)

    if insp.has_table("tenants"):
        cols = {c["name"] for c in insp.get_columns("tenants")}
        if "monitoring_config" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE tenants ADD COLUMN monitoring_config TEXT"))

    if insp.has_table("incidents"):
        cols = {c["name"] for c in insp.get_columns("incidents")}
        if "source_event_id" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE incidents ADD COLUMN source_event_id INTEGER"
                    )
                )

    if not insp.has_table("monitoring_consents"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE monitoring_consents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER NOT NULL,
                        elder_id INTEGER NOT NULL UNIQUE,
                        video_monitoring_consent BOOLEAN DEFAULT 0,
                        family_notifications_consent BOOLEAN DEFAULT 0,
                        consented_by_name VARCHAR(200),
                        consented_at DATETIME,
                        notes VARCHAR(500),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(tenant_id) REFERENCES tenants(id),
                        FOREIGN KEY(elder_id) REFERENCES elders(id)
                    )
                    """
                )
            )

    if not insp.has_table("monitoring_alerts"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE monitoring_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER NOT NULL,
                        elder_id INTEGER NOT NULL,
                        camera_event_id INTEGER,
                        incident_id INTEGER,
                        channel VARCHAR(50) NOT NULL,
                        recipient_role VARCHAR(50) NOT NULL,
                        recipient VARCHAR(255) NOT NULL,
                        status VARCHAR(50) DEFAULT 'LOGGED',
                        message TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(tenant_id) REFERENCES tenants(id),
                        FOREIGN KEY(elder_id) REFERENCES elders(id),
                        FOREIGN KEY(camera_event_id) REFERENCES camera_events(id),
                        FOREIGN KEY(incident_id) REFERENCES incidents(id)
                    )
                    """
                )
            )


def migrate_caregiver_verification():
    if not _is_sqlite():
        _ensure_tables(["caregiver_identities"])
        return

    insp = inspect(engine)

    if not insp.has_table("caregiver_identities"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE caregiver_identities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER NOT NULL,
                        caregiver_id INTEGER NOT NULL UNIQUE,
                        full_name VARCHAR(200),
                        gender VARCHAR(50),
                        date_of_birth DATE,
                        mobile_number VARCHAR(50),
                        email VARCHAR(255),
                        address_line1 VARCHAR(500),
                        address_line2 VARCHAR(500),
                        city VARCHAR(100),
                        district VARCHAR(100),
                        state VARCHAR(100),
                        postal_code VARCHAR(20),
                        aadhaar_last4 VARCHAR(4),
                        aadhaar_vid VARCHAR(50),
                        photo_url VARCHAR(1000),
                        verification_status VARCHAR(50) DEFAULT 'PENDING',
                        qr_validation_status VARCHAR(50),
                        qr_payload TEXT,
                        primary_aadhaar_document_id INTEGER,
                        user_confirmed_at DATETIME,
                        verified_at DATETIME,
                        identity_consent_at DATETIME,
                        notes TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(tenant_id) REFERENCES tenants(id),
                        FOREIGN KEY(caregiver_id) REFERENCES caregivers(id),
                        FOREIGN KEY(primary_aadhaar_document_id) REFERENCES documents(id)
                    )
                    """
                )
            )


def migrate_geofence():
    # Only create tables registered for this DEPLOY_VERTICAL (SafeHome skips devices/attendance).
    _ensure_tables(
        [
            "elder_locations",
            "caregiver_devices",
            "caregiver_location_events",
            "attendance_records",
            "attendance_alerts",
        ]
    )


def migrate_tier1_operations():
    _ensure_tables(
        [
            "caregiver_pay_rates",
            "payroll_runs",
            "payroll_lines",
            "elder_billing_rates",
            "invoices",
            "invoice_lines",
            "visits",
        ]
    )

    insp = inspect(engine)
    if not insp.has_table("visits"):
        return

    cols = {c["name"] for c in insp.get_columns("visits")}
    alters = []
    if "tenant_id" not in cols:
        alters.append("ALTER TABLE visits ADD COLUMN tenant_id INTEGER")
    if "elder_id" not in cols:
        alters.append("ALTER TABLE visits ADD COLUMN elder_id INTEGER")
    if "caregiver_id" not in cols:
        alters.append("ALTER TABLE visits ADD COLUMN caregiver_id INTEGER")
    if "scheduled_start" not in cols:
        alters.append("ALTER TABLE visits ADD COLUMN scheduled_start DATETIME")
    if "scheduled_end" not in cols:
        alters.append("ALTER TABLE visits ADD COLUMN scheduled_end DATETIME")
    if "attendance_record_id" not in cols:
        alters.append("ALTER TABLE visits ADD COLUMN attendance_record_id INTEGER")
    if "created_at" not in cols:
        alters.append(
            "ALTER TABLE visits ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        )
    if "updated_at" not in cols:
        alters.append(
            "ALTER TABLE visits ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        )
    if alters:
        with engine.begin() as conn:
            for sql in alters:
                conn.execute(text(sql))


def migrate_academy():
    _ensure_tables(
        [
            "qualification_packs",
            "caregiver_certifications",
            "training_programs",
            "caregiver_program_enrollments",
        ]
    )


def migrate_shift_swap():
    _ensure_tables(["shift_swap_requests"])


def migrate_statutory_payroll():
    _ensure_tables(["payroll_deductions"])

    insp = inspect(engine)

    if insp.has_table("payroll_runs"):
        cols = {c["name"] for c in insp.get_columns("payroll_runs")}
        alters = []
        if "total_deductions" not in cols:
            alters.append(
                "ALTER TABLE payroll_runs ADD COLUMN total_deductions REAL DEFAULT 0"
            )
        if "total_net" not in cols:
            alters.append(
                "ALTER TABLE payroll_runs ADD COLUMN total_net REAL DEFAULT 0"
            )
        if alters:
            with engine.begin() as conn:
                for sql in alters:
                    conn.execute(text(sql))

    if insp.has_table("tenants"):
        cols = {c["name"] for c in insp.get_columns("tenants")}
        if "payroll_config" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE tenants ADD COLUMN payroll_config TEXT")
                )


def migrate_markets():
    insp = inspect(engine)

    if insp.has_table("tenants"):
        cols = {c["name"] for c in insp.get_columns("tenants")}
        if "market" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE tenants ADD COLUMN market VARCHAR(10) DEFAULT 'IN'")
                )
                conn.execute(
                    text(
                        "UPDATE tenants SET market = 'US' "
                        "WHERE LOWER(country) IN ('us', 'usa', 'united states', "
                        "'united states of america')"
                    )
                )

    if insp.has_table("subscription_plans"):
        cols = {c["name"] for c in insp.get_columns("subscription_plans")}
        if "market" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE subscription_plans ADD COLUMN market VARCHAR(10) "
                        "DEFAULT 'IN'"
                    )
                )


def migrate_subscriptions():
    _ensure_tables(
        [
            "subscription_plans",
            "tenant_subscriptions",
            "subscription_invoices",
        ]
    )

    from app.services.subscription_service import SubscriptionService

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        SubscriptionService.ensure_default_plans(db)
    finally:
        db.close()


def migrate_leave_requests():
    _ensure_tables(["leave_requests"])


def migrate_finance_outputs():
    insp = inspect(engine)
    if not insp.has_table("invoices"):
        return

    cols = {c["name"] for c in insp.get_columns("invoices")}
    alters = []
    column_defs = {
        "invoice_number": "VARCHAR(50)",
        "subtotal": "REAL DEFAULT 0",
        "tax_rate": "REAL DEFAULT 0",
        "tax_amount": "REAL DEFAULT 0",
        "amount_paid": "REAL DEFAULT 0",
        "due_date": "DATE",
        "paid_at": "DATETIME",
    }
    for name, col_type in column_defs.items():
        if name not in cols:
            alters.append(f"ALTER TABLE invoices ADD COLUMN {name} {col_type}")
    if not alters:
        return
    with engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))


def migrate_resume_parsing():
    insp = inspect(engine)
    if not insp.has_table("caregiver_prospects"):
        return

    cols = {c["name"] for c in insp.get_columns("caregiver_prospects")}
    alters = []
    if "resume_parsed_json" not in cols:
        alters.append("ALTER TABLE caregiver_prospects ADD COLUMN resume_parsed_json TEXT")
    if "resume_score" not in cols:
        alters.append("ALTER TABLE caregiver_prospects ADD COLUMN resume_score REAL")
    if "resume_document_id" not in cols:
        alters.append(
            "ALTER TABLE caregiver_prospects ADD COLUMN resume_document_id INTEGER"
        )
    if not alters:
        return
    with engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))


def migrate_prospects():
    _ensure_tables(["elder_prospects", "caregiver_prospects", "pipeline_activities"])

    insp = inspect(engine)
    if not insp.has_table("elder_prospects"):
        return
    cols = {c["name"] for c in insp.get_columns("elder_prospects")}
    if "source_ip" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE elder_prospects ADD COLUMN source_ip VARCHAR(64)")
            )


def migrate_tenant_register_slug():
    insp = inspect(engine)

    if insp.has_table("tenants"):
        cols = {c["name"] for c in insp.get_columns("tenants")}
        if "register_slug" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE tenants ADD COLUMN register_slug VARCHAR(100)"
                    )
                )

    import app.models  # noqa: F401

    from app.core.database import SessionLocal
    from app.core.slug import ensure_tenant_register_slug
    from app.models.tenant import Tenant

    db = SessionLocal()
    try:
        for tenant in db.query(Tenant).all():
            ensure_tenant_register_slug(db, tenant)
        db.commit()
    finally:
        db.close()


def migrate_family_portal():
    _ensure_tables(["family_service_requests", "family_elder_links"])
    _backfill_family_elder_links()


def _backfill_family_elder_links() -> None:
    """Legacy family users only had users.elder_id — copy into join table."""
    insp = inspect(engine)
    if not insp.has_table("family_elder_links") or not insp.has_table("users"):
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO family_elder_links (user_id, elder_id, created_at, updated_at)
                SELECT u.id, u.elder_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM users u
                WHERE u.elder_id IS NOT NULL
                  AND u.role = 'ELDER_PORTAL'
                  AND NOT EXISTS (
                    SELECT 1 FROM family_elder_links l
                    WHERE l.user_id = u.id AND l.elder_id = u.elder_id
                  )
                """
            )
        )


def migrate_care_plans():
    _ensure_tables(["care_plans", "care_plan_activities", "care_plan_activity_logs"])


def migrate_home_safety_ai_jobs():
    _ensure_tables(["home_safety_ai_jobs"])
    insp = inspect(engine)
    if not insp.has_table("home_safety_ai_jobs"):
        return
    cols = {c["name"] for c in insp.get_columns("home_safety_ai_jobs")}
    if "origin_session_id" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE home_safety_ai_jobs "
                    "ADD COLUMN origin_session_id VARCHAR(36)"
                )
            )
    # AI room preview: background progress + room-unchanged score + regeneration link.
    dt = "DATETIME" if _is_sqlite() else "TIMESTAMP"
    fl = "REAL" if _is_sqlite() else "DOUBLE PRECISION"
    for name, ddl in (
        ("progress_stage", "VARCHAR(32)"),
        ("started_at", dt),
        ("finished_at", dt),
        ("similarity_score", fl),
        ("render_attempts", "INTEGER"),
        ("regenerated_from", "VARCHAR(32)"),
    ):
        if name not in cols:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE home_safety_ai_jobs ADD COLUMN {name} {ddl}"))


def migrate_home_safety_vision_analyses():
    _ensure_tables(["home_safety_vision_analyses"])


def migrate_ai_hazard_checks() -> None:
    """AI room hazard check + shared AI usage counter. New tables only."""
    import app.models.ai_hazard_check  # noqa: F401
    import app.models.ai_usage  # noqa: F401

    _ensure_tables(["ai_usage_events", "ai_hazard_checks", "ai_hazard_feedback"])


def migrate_home_safety_assessments():
    _ensure_tables(["home_safety_assessments"])
    insp = inspect(engine)
    if not insp.has_table("home_safety_assessments"):
        return
    cols = {c["name"] for c in insp.get_columns("home_safety_assessments")}
    alters: list[str] = []
    if "prospect_id" not in cols:
        alters.append(
            "ALTER TABLE home_safety_assessments ADD COLUMN prospect_id INTEGER"
        )
    if "elder_id" not in cols:
        alters.append("ALTER TABLE home_safety_assessments ADD COLUMN elder_id INTEGER")
    if "configuration_version_id" not in cols:
        alters.append(
            "ALTER TABLE home_safety_assessments "
            "ADD COLUMN configuration_version_id VARCHAR(64)"
        )
    if "server_score" not in cols:
        alters.append("ALTER TABLE home_safety_assessments ADD COLUMN server_score INTEGER")
    if "client_reported_score" not in cols:
        alters.append(
            "ALTER TABLE home_safety_assessments ADD COLUMN client_reported_score INTEGER"
        )
    if "versions" not in cols:
        alters.append("ALTER TABLE home_safety_assessments ADD COLUMN versions TEXT")
    if "history" not in cols:
        alters.append("ALTER TABLE home_safety_assessments ADD COLUMN history TEXT")
    if not alters:
        return
    with engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))


def migrate_background_jobs():
    _ensure_tables(["background_jobs"])


def migrate_visit_execution():
    _ensure_tables(["visit_care_notes", "visit_checklist_logs"])


def migrate_user_sessions():
    """Session activity tracking tables (assessor / family / system)."""
    import app.models.user_session  # noqa: F401

    _ensure_tables(["user_sessions", "user_session_events"])
    insp = inspect(engine)
    if not insp.has_table("user_sessions"):
        # Fallback when metadata create_all did not bind (older pack registration).
        with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS user_sessions (
                            id VARCHAR(36) PRIMARY KEY,
                            tenant_id INTEGER REFERENCES tenants(id),
                            user_id INTEGER NOT NULL REFERENCES users(id),
                            actor_type VARCHAR(20) NOT NULL,
                            user_email VARCHAR(255) NOT NULL,
                            user_name VARCHAR(255) NOT NULL DEFAULT '',
                            user_role VARCHAR(40) NOT NULL,
                            started_at TIMESTAMPTZ NOT NULL,
                            last_seen_at TIMESTAMPTZ NOT NULL,
                            ended_at TIMESTAMPTZ,
                            user_agent VARCHAR(512),
                            ip_address VARCHAR(64),
                            event_count INTEGER NOT NULL DEFAULT 0
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_user_sessions_tenant_started "
                        "ON user_sessions (tenant_id, started_at)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_user_sessions_user_started "
                        "ON user_sessions (user_id, started_at)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_user_sessions_actor_started "
                        "ON user_sessions (actor_type, started_at)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_user_sessions_tenant_id "
                        "ON user_sessions (tenant_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id "
                        "ON user_sessions (user_id)"
                    )
                )
            else:
                _ensure_tables(["user_sessions", "user_session_events"])
                return

    if not insp.has_table("user_session_events"):
        with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS user_session_events (
                            id SERIAL PRIMARY KEY,
                            session_id VARCHAR(36) NOT NULL
                                REFERENCES user_sessions(id),
                            tenant_id INTEGER REFERENCES tenants(id),
                            occurred_at TIMESTAMPTZ NOT NULL,
                            event_kind VARCHAR(20) NOT NULL DEFAULT 'api_call',
                            action VARCHAR(120) NOT NULL,
                            method VARCHAR(10),
                            path VARCHAR(512),
                            status_code INTEGER,
                            duration_ms FLOAT,
                            request_id VARCHAR(40),
                            entity_type VARCHAR(50),
                            entity_id VARCHAR(80),
                            summary TEXT,
                            meta JSON
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_user_session_events_session_occurred "
                        "ON user_session_events (session_id, occurred_at)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_user_session_events_tenant_occurred "
                        "ON user_session_events (tenant_id, occurred_at)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_user_session_events_session_id "
                        "ON user_session_events (session_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_user_session_events_tenant_id "
                        "ON user_session_events (tenant_id)"
                    )
                )

    # AI jobs: origin session link for return-event attribution
    if insp.has_table("home_safety_ai_jobs"):
        cols = {c["name"] for c in insp.get_columns("home_safety_ai_jobs")}
        if "origin_session_id" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE home_safety_ai_jobs "
                        "ADD COLUMN origin_session_id VARCHAR(36)"
                    )
                )


def migrate_user_session_root() -> None:
    """Additive: user_sessions.root_session_id — links server-opened continuation
    sessions (idle split / daily system rollover) to the id the client sends."""
    insp = inspect(engine)
    if not insp.has_table("user_sessions"):
        return
    cols = {c["name"] for c in insp.get_columns("user_sessions")}
    if "root_session_id" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE user_sessions ADD COLUMN root_session_id VARCHAR(36)"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_user_sessions_root_session_id "
                "ON user_sessions (root_session_id)"
            )
        )


def migrate_recommendation_chat():
    """Assessor recommendation chat (assessment-grounded Azure OpenAI)."""
    import app.models.recommendation_chat  # noqa: F401

    _ensure_tables(["recommendation_conversations", "recommendation_messages"])
    insp = inspect(engine)
    if not insp.has_table("recommendation_conversations") and engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS recommendation_conversations (
                        id VARCHAR(36) PRIMARY KEY,
                        tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        assessment_id VARCHAR(64) NOT NULL,
                        elder_id INTEGER,
                        prospect_id INTEGER,
                        title VARCHAR(255) NOT NULL DEFAULT '',
                        status VARCHAR(20) NOT NULL DEFAULT 'open',
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        message_count INTEGER NOT NULL DEFAULT 0,
                        origin_session_id VARCHAR(36)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_rec_chat_tenant_assessment "
                    "ON recommendation_conversations (tenant_id, assessment_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_rec_chat_tenant_user "
                    "ON recommendation_conversations (tenant_id, user_id)"
                )
            )
    insp = inspect(engine)
    if not insp.has_table("recommendation_messages") and engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS recommendation_messages (
                        id SERIAL PRIMARY KEY,
                        conversation_id VARCHAR(36) NOT NULL
                            REFERENCES recommendation_conversations(id),
                        tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                        role VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        structured JSON,
                        model_deployment VARCHAR(120),
                        latency_ms FLOAT,
                        validation_status VARCHAR(40),
                        requires_human_review BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_rec_msg_conversation_created "
                    "ON recommendation_messages (conversation_id, created_at)"
                )
            )


def migrate_iot_devices() -> None:
    """MG7 hubs + B7 bands registry."""
    import app.models.iot_device  # noqa: F401

    _ensure_tables(["iot_hubs", "iot_devices"])


def migrate_family_elder_link_columns() -> None:
    """Additive: circle primary flag + inviter on family_elder_links."""
    insp = inspect(engine)
    if not insp.has_table("family_elder_links"):
        return
    cols = {c["name"] for c in insp.get_columns("family_elder_links")}
    alters = []
    if "is_primary" not in cols:
        alters.append(
            "ALTER TABLE family_elder_links ADD COLUMN is_primary BOOLEAN NOT NULL DEFAULT FALSE"
        )
    if "invited_by_user_id" not in cols:
        alters.append("ALTER TABLE family_elder_links ADD COLUMN invited_by_user_id INTEGER")
    if not alters:
        return
    with engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))


def migrate_family_wallet() -> None:
    """Prepaid family wallet + append-only transaction ledger."""
    import app.models.family_wallet  # noqa: F401

    _ensure_tables(["family_wallets", "wallet_transactions"])


def migrate_care_incidents() -> None:
    """Staff-side SOS / incident operations (additive: new tables only)."""
    import app.models.incident  # noqa: F401

    _ensure_tables(["care_incidents", "care_incident_events", "care_incident_partner_links"])
    # Staff-raised emergency (Phase 3D): owner + details on the incident row.
    insp = inspect(engine)
    if insp.has_table("care_incidents"):
        cols = {c["name"] for c in insp.get_columns("care_incidents")}
        with engine.begin() as conn:
            if "owner_user_id" not in cols:
                conn.execute(text("ALTER TABLE care_incidents ADD COLUMN owner_user_id INTEGER"))
            if "details" not in cols:
                kind = "TEXT" if _is_sqlite() else "JSON"
                conn.execute(text(f"ALTER TABLE care_incidents ADD COLUMN details {kind}"))


def migrate_family_contacts() -> None:
    """K2: family contact preferences (phone, channel, timezone, level) + family questions."""
    import app.models.family_contact  # noqa: F401

    _ensure_tables(["family_contacts", "family_questions"])
    # Uniqueness (one row per login / per email-only contact per client). Drop any
    # duplicates first, keeping the oldest row (the one the app reads and edits).
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM family_contacts WHERE user_id IS NOT NULL AND id NOT IN ("
            "SELECT MIN(id) FROM family_contacts WHERE user_id IS NOT NULL GROUP BY elder_id, user_id)"
        ))
        conn.execute(text(
            "DELETE FROM family_contacts WHERE user_id IS NULL AND id NOT IN ("
            "SELECT MIN(id) FROM family_contacts WHERE user_id IS NULL GROUP BY elder_id, email)"
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_family_contacts_elder_user "
            "ON family_contacts (elder_id, user_id) WHERE user_id IS NOT NULL"
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_family_contacts_elder_email "
            "ON family_contacts (elder_id, email) WHERE user_id IS NULL"
        ))


def migrate_kushlife_weekly() -> None:
    """KushLife K2: weekly summaries (draft → manager approves → family). New table only;
    the "Normal for" baseline override lives in elder.custom_attributes (no column)."""
    import app.models.kushlife_weekly  # noqa: F401

    _ensure_tables(["kushlife_weekly_summaries"])


def migrate_kushlife_quality() -> None:
    """K3 + Phase 5 (#100 #106): monthly letters, visit voice notes, visit ratings, NPS. New tables only."""
    import app.models.kushlife_quality  # noqa: F401

    _ensure_tables(["kushlife_monthly_letters", "visit_voice_notes", "visit_ratings", "nps_responses"])


def migrate_client_care() -> None:
    """Phase 4B (#94 #95 #98): client sheet, care plan goals, risk register, handovers. New tables only."""
    import app.models.client_care  # noqa: F401

    _ensure_tables(["client_sheets", "care_goals", "client_risks", "handover_notes"])


def migrate_incident_reports() -> None:
    """Phase 4C (#97): after-the-fact incident reports. New table only; the per-client
    visit checklist (#99) lives in elder.custom_attributes and job.report (no column)."""
    import app.models.incident_report  # noqa: F401

    _ensure_tables(["care_incident_reports"])


def migrate_staff_alerts() -> None:
    """Per-user ops alerts with a close button (visit logged away from home). New table only."""
    import app.models.staff_alert  # noqa: F401

    _ensure_tables(["staff_alerts"])


def migrate_sos_siren() -> None:
    """C1 SOS siren: one row per person who must hear an SOS. New table only."""
    import app.models.incident  # noqa: F401
    import app.models.sos_siren  # noqa: F401

    _ensure_tables(["sos_siren_alerts"])


def migrate_care_job_assignee() -> None:
    """Assessments are assigned to a care manager: care_jobs.assignee_user_id."""
    insp = inspect(engine)
    if not insp.has_table("care_jobs"):
        return
    if "assignee_user_id" not in {c["name"] for c in insp.get_columns("care_jobs")}:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE care_jobs ADD COLUMN assignee_user_id INTEGER"))


def migrate_push_devices() -> None:
    """Android app SOS alarm: one row per phone (FCM token). New table only."""
    import app.models.push_device  # noqa: F401

    _ensure_tables(["push_devices"])


def migrate_live_location() -> None:
    """Phase 4D (#115): latest caregiver position per on-the-way job. New table only."""
    import app.models.care_job_live_location  # noqa: F401

    _ensure_tables(["care_job_live_locations"])


def run_migrations():
    migrate_app_global_settings()
    migrate_auth_attempts()
    migrate_caregiver_portal()
    migrate_team_reporting()
    migrate_documents()
    migrate_tenants()
    migrate_safehome_deploy_vertical()
    migrate_elder_portal()
    migrate_workflows()
    migrate_monitoring()
    migrate_caregiver_verification()
    migrate_geofence()
    migrate_tier1_operations()
    migrate_academy()
    migrate_prospects()
    migrate_resume_parsing()
    migrate_finance_outputs()
    migrate_shift_swap()
    migrate_leave_requests()
    migrate_statutory_payroll()
    migrate_markets()
    migrate_subscriptions()
    migrate_tenant_register_slug()
    migrate_family_portal()
    migrate_family_elder_link_columns()
    migrate_care_plans()
    migrate_visit_execution()
    migrate_home_safety_ai_jobs()
    migrate_home_safety_vision_analyses()
    migrate_ai_hazard_checks()
    migrate_home_safety_assessments()
    migrate_background_jobs()
    migrate_user_sessions()
    migrate_user_session_root()
    migrate_recommendation_chat()
    migrate_iot_devices()
    migrate_family_wallet()
    migrate_care_incidents()
    migrate_kushlife_weekly()
    migrate_kushlife_quality()
    migrate_family_contacts()
    migrate_client_care()
    migrate_incident_reports()
    migrate_live_location()
    migrate_staff_alerts()
    migrate_sos_siren()
    migrate_push_devices()
    migrate_care_job_assignee()
    migrate_care_series()
    migrate_tax_invoices()
    migrate_lead_tracking()
    migrate_privacy()
    migrate_blog()
    migrate_customer_plans()
    migrate_vendors()
    migrate_user_phone()
    migrate_live_share_by()
    migrate_iot_gateway_http()
    migrate_plan_purchases()
    migrate_contracts()


def migrate_contracts() -> None:
    """Contracts signed in the app (vendor agreements, client contracts). New tables only."""
    import app.models.vendor  # noqa: F401
    import app.models.contract  # noqa: F401

    _ensure_tables(["contract_templates", "contract_signatories", "contracts"])


def migrate_live_share_by() -> None:
    """Who shared a live location from the ops web page (care manager on the way)."""
    insp = inspect(engine)
    if not insp.has_table("care_job_live_locations"):
        return
    if "shared_by_user_id" not in {c["name"] for c in insp.get_columns("care_job_live_locations")}:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE care_job_live_locations ADD COLUMN shared_by_user_id INTEGER"))


def migrate_user_phone() -> None:
    """Work phone on staff accounts (Team page)."""
    insp = inspect(engine)
    if not insp.has_table("users"):
        return
    if "phone" not in {c["name"] for c in insp.get_columns("users")}:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(30)"))


def migrate_vendors() -> None:
    """Sales -> Vendors: vendors table, plus the uploaded paper agreement."""
    import app.models.vendor  # noqa: F401

    _ensure_tables(["vendors"])
    have = {c["name"] for c in inspect(engine).get_columns("vendors")}
    stamp = "TIMESTAMP WITH TIME ZONE" if engine.dialect.name == "postgresql" else "DATETIME"
    with engine.begin() as conn:
        for name, ddl in (
            ("signed_agreement_key", "VARCHAR(500)"),
            ("signed_agreement_name", "VARCHAR(200)"),
            ("signed_agreement_mime", "VARCHAR(40)"),
            ("signed_agreement_at", stamp),
            ("signed_agreement_by", "VARCHAR(200)"),
        ):
            if name not in have:
                conn.execute(text(f"ALTER TABLE vendors ADD COLUMN {name} {ddl}"))


def migrate_customer_plans() -> None:
    """Sales board + customer plans: customer_plans table only. Lead stages and their
    history reuse elder_prospects.stage and pipeline_activities (no new columns)."""
    import app.models.customer_plan  # noqa: F401

    _ensure_tables(["customer_plans"])


def migrate_blog() -> None:
    """Blog (www /blog): blog_posts + blog_images, then the sample post if its slug is missing."""
    import app.models.blog  # noqa: F401

    _ensure_tables(["blog_posts", "blog_images"])
    from app.core.database import SessionLocal
    from app.livewell.blog_seed import seed_marketing_posts, seed_sample_post

    db = SessionLocal()
    try:
        seed_sample_post(db)
        seed_marketing_posts(db)
    finally:
        db.close()


def migrate_lead_tracking() -> None:
    """FIX 107/108: UTM / referrer / referral / pincode / assessment slot on elder_prospects."""
    _ensure_tables(["elder_prospects"])
    insp = inspect(engine)
    if not insp.has_table("elder_prospects"):
        return
    cols = {c["name"] for c in insp.get_columns("elder_prospects")}
    wanted = {
        "utm_source": "VARCHAR(100)",
        "utm_medium": "VARCHAR(100)",
        "utm_campaign": "VARCHAR(150)",
        "referrer_url": "VARCHAR(500)",
        "landing_page": "VARCHAR(500)",
        "referral_code": "VARCHAR(32)",
        "pincode": "VARCHAR(10)",
        "area_served": "BOOLEAN",
        "assessment_slot": "VARCHAR(40)",
        "assessment_fee_paise": "INTEGER",
        "assessment_order_id": "VARCHAR(64)",
        "assessment_paid_at": "TIMESTAMP",
    }
    with engine.begin() as conn:
        for name, sql_type in wanted.items():
            if name not in cols:
                conn.execute(text(f"ALTER TABLE elder_prospects ADD COLUMN {name} {sql_type}"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_elder_prospects_assessment_order ON elder_prospects (assessment_order_id)"
        ))


def migrate_tax_invoices() -> None:
    """Phase 5B (#102): GST invoices / credit notes and their gapless counters. New tables only;
    business details live in tenant.workflow_config["business"] (no column)."""
    import app.models.tax_invoice  # noqa: F401

    _ensure_tables(["invoice_counters", "tax_invoices"])


def migrate_privacy() -> None:
    """Phase 5C (#104 DPDP): consent history and delete-my-account requests. New tables only."""
    import app.models.privacy  # noqa: F401

    _ensure_tables(["privacy_consents", "privacy_data_requests"])


def migrate_care_series() -> None:
    """Phase 4A: repeating visits — care_series table, care_jobs.series_id/series_date
    and a unique (series_id, series_date) index so generation is idempotent."""
    import app.models.care_series  # noqa: F401

    _ensure_tables(["care_series", "leave_requests"])
    insp = inspect(engine)
    if not insp.has_table("care_jobs"):
        return
    cols = {c["name"] for c in insp.get_columns("care_jobs")}
    with engine.begin() as conn:
        if "series_id" not in cols:
            conn.execute(text("ALTER TABLE care_jobs ADD COLUMN series_id INTEGER REFERENCES care_series(id) ON DELETE SET NULL"))
        if "series_date" not in cols:
            conn.execute(text("ALTER TABLE care_jobs ADD COLUMN series_date DATE"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_care_jobs_series_id ON care_jobs (series_id)"))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_care_jobs_series_date ON care_jobs (series_id, series_date)"
        ))


if __name__ == "__main__":
    run_migrations()
    print("Migrations applied.")


def migrate_iot_gateway_http() -> None:
    """Device handling (Oct 2026): HTTP gateway token + MAC + client on hubs, watch
    state on devices, and devices that are not assigned to a client yet."""
    insp = inspect(engine)
    dt = "DATETIME" if _is_sqlite() else "TIMESTAMP WITH TIME ZONE"
    if insp.has_table("iot_hubs"):
        cols = {c["name"] for c in insp.get_columns("iot_hubs")}
        with engine.begin() as conn:
            for name, sql_type in (("mac_address", "VARCHAR(32)"), ("http_token", "VARCHAR(80)"), ("elder_id", "INTEGER")):
                if name not in cols:
                    conn.execute(text(f"ALTER TABLE iot_hubs ADD COLUMN {name} {sql_type}"))
            if "http_token" not in cols:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_iot_hubs_http_token ON iot_hubs (http_token)"))
    if not insp.has_table("iot_devices"):
        return
    cols = {c["name"]: c for c in insp.get_columns("iot_devices")}
    with engine.begin() as conn:
        for name, sql_type in (
            ("last_rssi", "INTEGER"),
            ("last_motion_at", dt),
            ("motion_xyz", "VARCHAR(40)"),
            ("sos_active_at", dt),
            ("immobility_alerted_at", dt),
        ):
            if name not in cols:
                conn.execute(text(f"ALTER TABLE iot_devices ADD COLUMN {name} {sql_type}"))
    if cols.get("elder_id", {}).get("nullable", True):
        return
    if not _is_sqlite():
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE iot_devices ALTER COLUMN elder_id DROP NOT NULL"))
        return
    # SQLite cannot drop NOT NULL: rebuild the table from its own CREATE statement.
    with engine.begin() as conn:
        create_sql = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='iot_devices'")
        ).scalar()
        index_sql = [
            r[0]
            for r in conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='iot_devices' AND sql IS NOT NULL")
            ).fetchall()
        ]
        new_sql = create_sql.replace("elder_id INTEGER NOT NULL", "elder_id INTEGER", 1)
        if new_sql == create_sql:
            return
        col_list = ", ".join(c["name"] for c in insp.get_columns("iot_devices"))
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("ALTER TABLE iot_devices RENAME TO iot_devices_old"))
        conn.execute(text(new_sql))
        conn.execute(text(f"INSERT INTO iot_devices ({col_list}) SELECT {col_list} FROM iot_devices_old"))
        conn.execute(text("DROP TABLE iot_devices_old"))
        for sql in index_sql:
            conn.execute(text(sql))
        conn.execute(text("PRAGMA foreign_keys=ON"))


def migrate_plan_purchases() -> None:
    """Website "Buy now" (30 Oct 2026): plan_purchases table, and the coupon given on
    a customer plan (customer_plans.coupon_code / discount_paise)."""
    import app.models.plan_purchase  # noqa: F401

    _ensure_tables(["plan_purchases"])
    insp = inspect(engine)
    # Pay-as-you-go visit bought online (31 Oct 2026).
    pp_cols = {c["name"] for c in insp.get_columns("plan_purchases")}
    with engine.begin() as conn:
        if "details" not in pp_cols:
            conn.execute(text("ALTER TABLE plan_purchases ADD COLUMN details JSON"))
        if "service_request_id" not in pp_cols:
            conn.execute(text("ALTER TABLE plan_purchases ADD COLUMN service_request_id VARCHAR(40)"))
    if not insp.has_table("customer_plans"):
        return
    cols = {c["name"] for c in insp.get_columns("customer_plans")}
    with engine.begin() as conn:
        if "coupon_code" not in cols:
            conn.execute(text("ALTER TABLE customer_plans ADD COLUMN coupon_code VARCHAR(40)"))
        if "discount_paise" not in cols:
            conn.execute(text("ALTER TABLE customer_plans ADD COLUMN discount_paise INTEGER NOT NULL DEFAULT 0"))
