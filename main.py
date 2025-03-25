from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import os
import logging

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Створення бази даних
SQLALCHEMY_DATABASE_URL = "sqlite:///./clients.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модель бази даних
class ClientDB(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    address = Column(String)
    birth_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    total_spent = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

# Pydantic модель для валідації даних
class ClientBase(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    birth_date: Optional[datetime] = None
    notes: Optional[str] = None
    total_spent: Optional[float] = 0.0

class ClientCreate(ClientBase):
    pass

class Client(ClientBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Створення таблиць
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Система управління клієнтами")

# Налаштування CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Підключення статичних файлів
app.mount("/static", StaticFiles(directory="static"), name="static")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def read_root():
    try:
        return FileResponse("templates/index.html")
    except Exception as e:
        logger.error(f"Помилка при завантаженні index.html: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# API endpoints
@app.post("/clients/", response_model=Client)
def create_client(client: ClientCreate):
    logger.info(f"Створення нового клієнта: {client}")
    db = SessionLocal()
    try:
        db_client = ClientDB(**client.dict())
        db.add(db_client)
        db.commit()
        db.refresh(db_client)
        return db_client
    except Exception as e:
        logger.error(f"Помилка при створенні клієнта: {e}")
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@app.get("/clients/", response_model=List[Client])
def read_clients(
    sort_by: Optional[str] = Query(None, description="Поле для сортування (name, created_at, total_spent)"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортування (asc або desc)")
):
    logger.info(f"Отримання списку клієнтів. Сортування: {sort_by}, порядок: {sort_order}")
    db = SessionLocal()
    try:
        query = db.query(ClientDB)
        
        if sort_by:
            if sort_by == "name":
                query = query.order_by(ClientDB.name.asc() if sort_order == "asc" else ClientDB.name.desc())
            elif sort_by == "created_at":
                query = query.order_by(ClientDB.created_at.asc() if sort_order == "asc" else ClientDB.created_at.desc())
            elif sort_by == "total_spent":
                query = query.order_by(ClientDB.total_spent.asc() if sort_order == "asc" else ClientDB.total_spent.desc())
        
        clients = query.all()
        logger.info(f"Знайдено {len(clients)} клієнтів")
        return clients
    except Exception as e:
        logger.error(f"Помилка при отриманні списку клієнтів: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/clients/{client_id}", response_model=Client)
def read_client(client_id: int):
    logger.info(f"Отримання клієнта з ID: {client_id}")
    db = SessionLocal()
    try:
        client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
        if client is None:
            logger.warning(f"Клієнт з ID {client_id} не знайдений")
            raise HTTPException(status_code=404, detail="Клієнт не знайдено")
        return client
    except Exception as e:
        logger.error(f"Помилка при отриманні клієнта: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.put("/clients/{client_id}", response_model=Client)
def update_client(client_id: int, client: ClientCreate):
    logger.info(f"Оновлення клієнта з ID {client_id}: {client}")
    db = SessionLocal()
    try:
        db_client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
        if db_client is None:
            logger.warning(f"Клієнт з ID {client_id} не знайдений")
            raise HTTPException(status_code=404, detail="Клієнт не знайдено")
        
        for key, value in client.dict().items():
            setattr(db_client, key, value)
        
        db.commit()
        db.refresh(db_client)
        return db_client
    except Exception as e:
        logger.error(f"Помилка при оновленні клієнта: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.delete("/clients/{client_id}")
def delete_client(client_id: int):
    logger.info(f"Видалення клієнта з ID: {client_id}")
    db = SessionLocal()
    try:
        db_client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
        if db_client is None:
            logger.warning(f"Клієнт з ID {client_id} не знайдений")
            raise HTTPException(status_code=404, detail="Клієнт не знайдено")
        
        db.delete(db_client)
        db.commit()
        return {"message": "Клієнт успішно видалено"}
    except Exception as e:
        logger.error(f"Помилка при видаленні клієнта: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    logger.info("Запуск сервера...")
    uvicorn.run(app, host="0.0.0.0", port=8002) 