from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.database import get_db 
from app.schemas.chat import ChatRoomCreate, ChatRoomResponse
from app.models.chat import ChatRoom
from app.models.participant import participants 
from app.dependencies.auth import get_current_user
from app.models.user import User 


router = APIRouter(prefix="/chats", tags=["chats"])

@router.post("/", response_model=ChatRoomResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
  chat_data: ChatRoomCreate,
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """
  Создание чата (личного)
  """

  # 1. Проверка, что второй пользователь не текущий
  if chat_data.second_user_id == current_user.id:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Нельзя создавать чат с самим собой",
    )
  
  # 2. Проверка существования второго пользователя
  second_user = db.query(User).filter(
    User.id == chat_data.second_user_id,
  ).first()
  
  # 3. Если нет - ошибка
  if not second_user:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Пользователь не найден",
    )
  
  # 4. Поиск существующего личного чата
  existing_chat = (
    db.query(ChatRoom)
    .join(participants)
    .filter(ChatRoom.is_group == False, participants.c.user_id
    .in_([current_user.id, chat_data.second_user_id]))
    .group_by(ChatRoom.id)
    .having(func.count(participants.c.user_id) == 2)
    .first()
  )

  # 5. Если найден - возвращаем
  if existing_chat:
    return existing_chat
  
  # 6. Если нет - создаем
  new_chat = ChatRoom(name=None, is_group=False)
  db.add(new_chat)
  db.commit()
  db.refresh(new_chat)

  # 7. Добавляем обоих участников в БД 
  db.execute(
    participants.insert().values([
      {"user_id": current_user.id, "chat_id": new_chat.id},
      {"user_id": chat_data.second_user_id, "chat_id": new_chat.id}
    ])
  )
  db.commit()

  # 8. Возвращаем чат
  return new_chat


@router.get("/", response_model=List[ChatRoomResponse])
async def get_user_chats(
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """
  Список чатов текущего пользователя
  1. Получаем объект чатов
  2. Присоединяем к объекту таблицу участников
  3. Соединяем там, где ID совпадает с chat_id в таблице участников 
  4. Фильтруем по конкретным участникам чата
  5. Возвращаем список чатов
  """

  chats = (
    db.query(ChatRoom)
    .join(participants, ChatRoom.id == participants.c.chat_id)
    .filter(participants.c.user_id == current_user.id)
    .all()
  )
  return chats







