from fastapi import FastAPI 
from app.models.base import Base
from app.database import engine 

# Создаем таблицы (вручную)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="My-Messenger")

@app.get("/")
async def root():
  return {"message": "Backend running"}