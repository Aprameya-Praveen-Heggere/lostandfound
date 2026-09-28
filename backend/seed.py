"""Idempotent Findora demo data seed.

Development startup may call this without flags. Production requires an explicit
command-line confirmation so demo credentials can never appear merely because
the service restarted.
"""
import argparse
from datetime import date, timedelta

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.models import (
    Category, Claim, FoundItem, Institution, InstitutionMembership,
    InstitutionSettings, Location, LostReport, Notification, RetentionPolicy,
    Role, User,
)


DEMO_INSTITUTION_NAME = "Findora Demo University"
DEMO_EMAIL_DOMAIN = "findora.edu"
DEMO_PASSWORD = "Findora123!"
DEMO_USERS = [
    ("Asha Admin", "admin@findora.edu", Role.ADMIN, True),
    ("Omar Officer", "officer@findora.edu", Role.OFFICER, False),
    ("Maya Student", "student@findora.edu", Role.USER, False),
    ("Ravi Student", "ravi@findora.edu", Role.USER, False),
]
CATEGORIES = [
    ("Electronics", "electronics", "laptop"),
    ("Water Bottles", "water-bottles", "bottle"),
    ("Bags", "bags", "briefcase"),
    ("ID Cards", "id-cards", "badge"),
    ("Books", "books", "book"),
    ("Keys", "keys", "key"),
    ("Clothing", "clothing", "shirt"),
    ("Accessories", "accessories", "watch"),
    ("Other", "other", "package"),
]
LOCATIONS = ["Central Library", "Science Block", "Student Centre", "Main Auditorium", "Sports Complex"]


def run(*, session_factory=SessionLocal, allow_production: bool = False) -> dict[str, int]:
    if settings.environment.lower() == "production" and not allow_production:
        raise RuntimeError(
            "Production demo seeding is disabled. Run with "
            "--confirm-production-demo-seed only after reviewing the public demo credentials."
        )

    created = {"institutions": 0, "users": 0, "memberships": 0, "settings": 0,
               "categories": 0, "locations": 0, "items": 0, "claims": 0, "notifications": 0}
    with session_factory() as db:
        by_domain = db.scalar(select(Institution).where(func.lower(Institution.email_domain) == DEMO_EMAIL_DOMAIN))
        by_name = db.scalar(select(Institution).where(func.lower(Institution.name) == DEMO_INSTITUTION_NAME.lower()))
        if by_domain and by_name and by_domain.id != by_name.id:
            raise RuntimeError("Demo institution name and domain belong to different existing institutions; no changes were made")
        institution = by_domain or by_name
        if institution and institution.email_domain.lower() != DEMO_EMAIL_DOMAIN:
            raise RuntimeError("Demo institution name already exists with another domain; no changes were made")
        if institution and not institution.is_active:
            raise RuntimeError("Demo institution exists but is inactive; no changes were made")
        if not institution:
            institution = Institution(name=DEMO_INSTITUTION_NAME, email_domain=DEMO_EMAIL_DOMAIN)
            db.add(institution); db.flush(); created["institutions"] += 1

        users: dict[str, User] = {}
        for name, email, role, is_platform_admin in DEMO_USERS:
            user = db.scalar(select(User).where(func.lower(User.email) == email))
            if user:
                if user.institution_id != institution.id:
                    raise RuntimeError(f"Existing demo email {email} belongs to another institution; no changes were made")
                try:
                    password_matches = verify_password(DEMO_PASSWORD, user.password_hash)
                except Exception:
                    password_matches = False
                if not password_matches:
                    raise RuntimeError(f"Existing demo user {email} has a different password; refusing to overwrite it")
                if user.role != role or user.is_platform_admin != is_platform_admin or not user.is_active:
                    raise RuntimeError(f"Existing demo user {email} has different access settings; refusing to overwrite them")
            else:
                user = User(institution_id=institution.id, name=name, email=email,
                            password_hash=hash_password(DEMO_PASSWORD), role=role,
                            is_platform_admin=is_platform_admin)
                db.add(user); db.flush(); created["users"] += 1
            users[email] = user

            membership = db.scalar(select(InstitutionMembership).where(
                InstitutionMembership.institution_id == institution.id,
                InstitutionMembership.user_id == user.id,
            ))
            if membership and (membership.role != role or not membership.is_active):
                raise RuntimeError(f"Existing membership for {email} has different access settings; refusing to overwrite it")
            if not membership:
                db.add(InstitutionMembership(institution_id=institution.id, user_id=user.id, role=role))
                created["memberships"] += 1

        if not db.scalar(select(InstitutionSettings).where(InstitutionSettings.institution_id == institution.id)):
            db.add(InstitutionSettings(institution_id=institution.id)); created["settings"] += 1
        if not db.scalar(select(RetentionPolicy).where(RetentionPolicy.institution_id == institution.id)):
            db.add(RetentionPolicy(institution_id=institution.id)); created["settings"] += 1

        categories: dict[str, Category] = {}
        for name, slug, icon in CATEGORIES:
            category = db.scalar(select(Category).where(Category.institution_id == institution.id, Category.slug == slug))
            if not category:
                category = Category(institution_id=institution.id, name=name, slug=slug, icon=icon)
                db.add(category); db.flush(); created["categories"] += 1
            categories[slug] = category

        for name in LOCATIONS:
            location = db.scalar(select(Location).where(
                Location.institution_id == institution.id, func.lower(Location.name) == name.lower()))
            if not location:
                db.add(Location(institution_id=institution.id, name=name)); created["locations"] += 1

        ravi = users["ravi@findora.edu"]
        student = users["student@findora.edu"]
        found_specs = [
            ("FOUND-DEMO01", "water-bottles", "Insulated water bottle", "Tall matte bottle with a small mountain sticker", "Blue", "Milton", "Central Library", 1, "Security desk, Central Library"),
            ("FOUND-DEMO02", "electronics", "Wireless earphones", "Black earbuds in charging case", "Black", "boAt", "Student Centre", 3, "Lost & Found office"),
            ("FOUND-DEMO03", "bags", "Laptop backpack", "Grey backpack with two front pockets", "Grey", "Wildcraft", "Science Block", 2, "Science Block reception"),
        ]
        found: dict[str, FoundItem] = {}
        for reference, category_slug, name, description, color, brand, location, days_ago, custody in found_specs:
            item = db.scalar(select(FoundItem).where(FoundItem.reference == reference))
            if item and item.institution_id != institution.id:
                raise RuntimeError(f"Demo reference {reference} belongs to another institution; no changes were made")
            if not item:
                item = FoundItem(reference=reference, institution_id=institution.id, reporter_id=ravi.id,
                    category_id=categories[category_slug].id, name=name, description=description, color=color,
                    brand=brand, location=location, date_found=date.today()-timedelta(days=days_ago), custody=custody)
                db.add(item); db.flush(); created["items"] += 1
            found[reference] = item

        lost = db.scalar(select(LostReport).where(LostReport.reference == "LOST-DEMO01"))
        if lost and lost.institution_id != institution.id:
            raise RuntimeError("Demo reference LOST-DEMO01 belongs to another institution; no changes were made")
        if not lost:
            lost = LostReport(reference="LOST-DEMO01", institution_id=institution.id, user_id=student.id,
                category_id=categories["water-bottles"].id, name="Insulated bottle", description="Has a mountain sticker",
                color="Blue", brand="Milton", location="Central Library", date_lost=date.today()-timedelta(days=2),
                private_details="Name initials scratched underneath")
            db.add(lost); created["items"] += 1

        claim = db.scalar(select(Claim).where(
            Claim.claimant_id == student.id,
            Claim.found_item_id == found["FOUND-DEMO01"].id,
        ))
        if not claim:
            db.add(Claim(institution_id=institution.id, claimant_id=student.id,
                found_item_id=found["FOUND-DEMO01"].id,
                ownership_details="My initials are engraved underneath and the lid has a small dent."))
            created["claims"] += 1

        welcome = db.scalar(select(Notification).where(
            Notification.user_id == student.id,
            Notification.title == "Welcome to Findora",
        ))
        if not welcome:
            db.add(Notification(institution_id=institution.id, user_id=student.id,
                title="Welcome to Findora", message="Your campus lost and found is now in one place."))
            created["notifications"] += 1

        db.commit()

    total = sum(created.values())
    print(f"Findora demo seed complete: {total} records created; existing matching records were preserved")
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the idempotent Findora demo institution and accounts")
    parser.add_argument("--confirm-production-demo-seed", action="store_true",
                        help="explicitly allow public demo credentials to be created in production")
    args = parser.parse_args()
    try:
        run(allow_production=args.confirm_production_demo_seed)
    except RuntimeError as exc:
        raise SystemExit(f"Demo seed aborted: {exc}") from exc


if __name__ == "__main__":
    main()
