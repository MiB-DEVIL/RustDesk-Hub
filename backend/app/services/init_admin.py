from app.auth.security import hash_password
from app.models.group import Group
from app.models.user import User


def create_default_admin(db):
    admin = db.query(User).filter(User.username == "admin").first()

    if not admin:
        admin = User(
            username="admin",
            password_hash=hash_password("admin"),
            is_admin=True
        )
        db.add(admin)
        db.commit()

    default_group = db.query(Group).filter(Group.name == "Clients").first()

    if not default_group:
        db.add(Group(name="Clients"))
        db.commit()
