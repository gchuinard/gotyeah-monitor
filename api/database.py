import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

load_dotenv()


class Base(DeclarativeBase):
    pass


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "")

DATABASE_URL = (
    f"mysql+asyncmy://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    # MySQL ferme les connexions inactives (wait_timeout, 8h par défaut) : on les
    # recycle avant pour éviter les "MySQL server has gone away" sur un Pi peu sollicité.
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    # Import ici pour éviter les imports circulaires
    import models  # noqa: F401

    # En prod, le schéma est géré EXCLUSIVEMENT par Alembic (entrypoint.sh) pour
    # éviter une double autorité. create_all ne sert qu'en dev, où aucune
    # migration n'est lancée (le Dockerfile dev démarre uvicorn directement).
    # ⚠️ create_all ne fait que CRÉER les tables manquantes : il n'ajoute pas une
    # colonne à une table existante. Après l'ajout d'une colonne au modèle,
    # recréer le volume dev : `docker compose -f docker-compose.dev.yml down -v`.
    if os.getenv("DEBUG", "false").lower() != "true":
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
