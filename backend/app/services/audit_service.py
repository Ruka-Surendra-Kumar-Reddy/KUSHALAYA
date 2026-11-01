from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditService:

    @staticmethod
    def log(
        db: Session,
        *,
        tenant_id: int,
        user_id: int | None,
        entity_type: str,
        entity_id: int,
        action: str,
        old_value: dict | None = None,
        new_value: dict | None = None,
    ) -> AuditLog:
        row = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(row)
        return row
