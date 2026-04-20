from sqlmodel import SQLModel, Session, create_engine
from app.config import DATABASE_URL


def _engine_kwargs():
    if DATABASE_URL.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}


engine = create_engine(DATABASE_URL, echo=False, **_engine_kwargs())


def init_db():
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _seed_admin()


def _seed_admin():
    """Seed the single admin user on first boot."""
    from app.config import ADMIN_DEFAULT_USERNAME, ADMIN_DEFAULT_PASSWORD
    from app.auth import hash_password
    from app.models import User
    from sqlmodel import select

    with Session(engine) as s:
        existing = s.exec(select(User).where(User.username == ADMIN_DEFAULT_USERNAME)).first()
        if existing:
            return
        s.add(
            User(
                username=ADMIN_DEFAULT_USERNAME,
                password_hash=hash_password(ADMIN_DEFAULT_PASSWORD),
                role="admin",
            )
        )
        s.commit()


def get_session():
    with Session(engine) as session:
        yield session
