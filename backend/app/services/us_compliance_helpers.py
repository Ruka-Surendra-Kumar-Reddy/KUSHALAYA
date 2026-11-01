"""US workforce classification helpers."""

from sqlalchemy.orm import Session

from app.models.us_workforce_compliance import USWorkforceCompliance

CLASSIFICATION_1099 = "1099_CONTRACTOR"
CLASSIFICATION_W2 = "W2_EMPLOYEE"


def get_classification(
    db: Session,
    caregiver_id: int,
    tenant_id: int,
) -> str:
    row = (
        db.query(USWorkforceCompliance)
        .filter(
            USWorkforceCompliance.caregiver_id == caregiver_id,
            USWorkforceCompliance.tenant_id == tenant_id,
        )
        .first()
    )
    if row and row.classification:
        return row.classification.upper()
    return CLASSIFICATION_W2


def is_1099_contractor(db: Session, caregiver_id: int, tenant_id: int) -> bool:
    return get_classification(db, caregiver_id, tenant_id) == CLASSIFICATION_1099
