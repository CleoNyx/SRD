# reset_admin.py
import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from backend.models import Base, User   # models.py is in the same folder

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "srd_users.db")
engine   = create_engine(f"sqlite:///{DB_PATH}", future=True)

Base.metadata.create_all(engine)

def reset_or_create_admin():


    with Session(engine) as s:
        u = s.execute(select(User).where(User.email=="admin@srd.local")).scalar_one_or_none()
        if u:
            u.set_password("ChangeMe123!")
            s.commit()
            print("✅ Reset admin password to ChangeMe123!")
        else:
            u = User(email="admin@srd.local", name="Admin", role="admin")
            u.set_password("ChangeMe123!")
            s.add(u)
            s.commit()
            print("✅ Created admin@srd.local with password ChangeMe123!")

if __name__ == "__main__":
    reset_or_create_admin()
