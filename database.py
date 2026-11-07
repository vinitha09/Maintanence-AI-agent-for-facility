from pathlib import Path
from sqlmodel import SQLModel, create_engine

from models.maintanence import (
    Machine,
    MachineManual,
    MaintenanceLog,
)

Path("data").mkdir(exist_ok=True)

DATABASE_URL = "sqlite:///./data/maintenance.db"

engine = create_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False},
)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)