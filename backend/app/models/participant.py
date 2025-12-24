from sqlalchemy import Column, Integer, ForeignKey, Table 
from app.models.base import Base 


participants = Table(
  "participants",
  Base.metadata,
  Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
  Column("chat_id", Integer, ForeignKey("chat_rooms.id"), primary_key=True),
)