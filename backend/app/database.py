from sqlalchemy import create_engine 
from sqlalchemy.orm import sessionmaker 
from app.core.config import settings 


# Подключение к БД через настройки
engine = create_engine(
  settings.DATABASE_URL,
  pool_pre_ping=True,
  pool_size=5,
  max_overflow=10,
  echo=settings.DEBUG,      # Вывод SQL-запросов в консоль
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency 
def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()