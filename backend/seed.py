from datetime import date, timedelta
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import *

CATEGORIES = [("Electronics","electronics","laptop"),("Water Bottles","water-bottles","bottle"),("Bags","bags","briefcase"),("ID Cards","id-cards","badge"),("Books","books","book"),("Keys","keys","key"),("Clothing","clothing","shirt"),("Accessories","accessories","watch"),("Other","other","package")]
def run():
    with SessionLocal() as db:
        if db.scalar(select(Institution)): print("Seed data already exists"); return
        inst = Institution(name="Findora Demo University", email_domain="findora.edu"); db.add(inst); db.flush()
        users = [User(institution_id=inst.id,name=n,email=e,password_hash=hash_password("Findora123!"),role=r,is_platform_admin=(e=="admin@findora.edu")) for n,e,r in [
            ("Asha Admin","admin@findora.edu",Role.ADMIN),("Omar Officer","officer@findora.edu",Role.OFFICER),("Maya Student","student@findora.edu",Role.USER),("Ravi Student","ravi@findora.edu",Role.USER)]]
        db.add_all(users); db.flush()
        db.add_all([InstitutionMembership(institution_id=inst.id,user_id=u.id,role=u.role) for u in users])
        db.add(InstitutionSettings(institution_id=inst.id)); db.add(RetentionPolicy(institution_id=inst.id))
        categories = [Category(institution_id=inst.id,name=n,slug=s,icon=i) for n,s,i in CATEGORIES]; db.add_all(categories); db.flush()
        db.add_all([Location(institution_id=inst.id,name=n) for n in ["Central Library","Science Block","Student Centre","Main Auditorium","Sports Complex"]])
        cat = {c.slug:c for c in categories}; student, ravi = users[2], users[3]
        found = [
            FoundItem(reference="FOUND-DEMO01",institution_id=inst.id,reporter_id=ravi.id,category_id=cat["water-bottles"].id,name="Insulated water bottle",description="Tall matte bottle with a small mountain sticker",color="Blue",brand="Milton",location="Central Library",date_found=date.today()-timedelta(days=1),custody="Security desk, Central Library"),
            FoundItem(reference="FOUND-DEMO02",institution_id=inst.id,reporter_id=ravi.id,category_id=cat["electronics"].id,name="Wireless earphones",description="Black earbuds in charging case",color="Black",brand="boAt",location="Student Centre",date_found=date.today()-timedelta(days=3),custody="Lost & Found office"),
            FoundItem(reference="FOUND-DEMO03",institution_id=inst.id,reporter_id=ravi.id,category_id=cat["bags"].id,name="Laptop backpack",description="Grey backpack with two front pockets",color="Grey",brand="Wildcraft",location="Science Block",date_found=date.today()-timedelta(days=2),custody="Science Block reception")]
        lost = LostReport(reference="LOST-DEMO01",institution_id=inst.id,user_id=student.id,category_id=cat["water-bottles"].id,name="Insulated bottle",description="Has a mountain sticker",color="Blue",brand="Milton",location="Central Library",date_lost=date.today()-timedelta(days=2),private_details="Name initials scratched underneath")
        db.add_all(found+[lost]); db.flush()
        claim = Claim(institution_id=inst.id,claimant_id=student.id,found_item_id=found[0].id,ownership_details="My initials are engraved underneath and the lid has a small dent.")
        db.add(claim); db.add(Notification(institution_id=inst.id,user_id=student.id,title="Welcome to Findora",message="Your campus lost and found is now in one place.")); db.commit(); print("Seeded Findora demo data")
if __name__ == "__main__": run()
