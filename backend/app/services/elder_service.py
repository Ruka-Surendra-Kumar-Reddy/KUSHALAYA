from sqlalchemy.orm import Session

from app.core.geocoding import apply_coords_to_attributes
from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.vertical_guards import require_any_tenant_feature
from app.models.elder import Elder
from app.models.elder_location import ElderLocation
from app.models.user import User
from app.schemas.elder import ElderCreate, ElderUpdate


from app.core.team_scope import assert_elder_in_team, is_scoped_manager, scope_elder_query

class ElderService:

    @staticmethod
    def _assert_elders_module(db: Session, user: User) -> None:
        # SafeHome uses customer_spine; Elder Care uses elders feature.
        require_any_tenant_feature(db, user, "elders", "customer_spine")

    @staticmethod
    def _assert_can_create_customer_record(db: Session, user: User) -> None:
        require_any_tenant_feature(db, user, "elders", "customer_spine")

    @staticmethod
    def _apply_address_geocode(
        db: Session,
        elder: Elder,
        address: str | None,
        *,
        previous_address: str | None = None,
        custom_attributes: dict | None = None,
    ) -> None:
        attrs = apply_coords_to_attributes(
            custom_attributes if custom_attributes is not None else elder.custom_attributes,
            address,
            previous_address=previous_address,
        )
        elder.custom_attributes = attrs

        lat = (attrs or {}).get("latitude")
        lon = (attrs or {}).get("longitude")
        if lat is None or lon is None:
            return

        row = (
            db.query(ElderLocation)
            .filter(ElderLocation.elder_id == elder.id)
            .first()
        )
        if row:
            row.latitude = float(lat)
            row.longitude = float(lon)

    @staticmethod
    def _tenant_id_for_create(user: User, data: ElderCreate) -> int:
        tid = resolve_tenant_id(user, data.tenant_id)
        if tid is None:
            raise_bad_request("tenant_id is required")
        return tid

    @staticmethod
    def list_elders(db: Session, user: User) -> list[Elder]:
        ElderService._assert_elders_module(db, user)
        query = db.query(Elder)
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(Elder.tenant_id == tid)
        query = scope_elder_query(db, user, query)
        return query.order_by(Elder.id).all()

    @staticmethod
    def get_elder(db: Session, elder_id: int, user: User) -> Elder:
        ElderService._assert_elders_module(db, user)
        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Elder not found")
        assert_tenant_access(user, elder.tenant_id)
        assert_elder_in_team(db, user, elder.id)
        return elder

    @staticmethod
    def create_elder(db: Session, data: ElderCreate, user: User) -> Elder:
        ElderService._assert_can_create_customer_record(db, user)
        tenant_id = ElderService._tenant_id_for_create(user, data)
        custom_attributes = apply_coords_to_attributes(
            data.custom_attributes,
            data.address,
        )
        elder = Elder(
            tenant_id=tenant_id,
            first_name=data.first_name,
            last_name=data.last_name,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            phone=data.phone,
            address=data.address,
            emergency_contact_name=data.emergency_contact_name,
            emergency_contact_phone=data.emergency_contact_phone,
            medical_conditions=data.medical_conditions,
            allergies=data.allergies,
            mobility_status=data.mobility_status,
            care_level=data.care_level,
            custom_attributes=custom_attributes,
            status=data.status,
        )
        if is_scoped_manager(user):
            elder.manager_user_id = user.id
        db.add(elder)
        db.commit()
        db.refresh(elder)
        return elder

    @staticmethod
    def update_elder(
        db: Session,
        elder_id: int,
        data: ElderUpdate,
        user: User,
    ) -> Elder:
        ElderService._assert_elders_module(db, user)
        elder = ElderService.get_elder(db, elder_id, user)
        previous_address = elder.address
        updates = data.model_dump(exclude_unset=True)
        custom_attributes = updates.pop("custom_attributes", None)

        for field, value in updates.items():
            setattr(elder, field, value)

        if custom_attributes is not None or "address" in updates:
            merged = dict(elder.custom_attributes or {})
            if custom_attributes is not None:
                merged.update(custom_attributes)
            ElderService._apply_address_geocode(
                db,
                elder,
                elder.address,
                previous_address=previous_address,
                custom_attributes=merged,
            )

        db.commit()
        db.refresh(elder)
        return elder

    @staticmethod
    def delete_elder(db: Session, elder_id: int, user: User) -> None:
        ElderService._assert_elders_module(db, user)
        elder = ElderService.get_elder(db, elder_id, user)
        elder.status = "INACTIVE"
        db.commit()
