import pytest 

from sqlalchemy import select 

from app.services.message_service import MessageService 
from app.services.chat_service import ChatService
from app.models.message import Message, MessageDelivery

@pytest.fixture 
def mock_chat_members(mocker):
  """
  ChatService - внешний dependency для MessageService
  """

  return mocker.patch.object(
    ChatService,
    "get_chat_members",
    return_value=[1,2]
  )


@pytest.mark.asyncio 
async def test_create_message_success(
  async_session,
  mock_chat_members,
):
  
  chat_id = 1
  sender_id = 1 
  content = "Hello World"

  message = await MessageService.create_message(
    chat_id=chat_id,
    sender_id=sender_id,
    content=content,
    db=async_session
  )

  assert message is not None 
  assert message.id is not None 
  assert message.chat_id == chat_id
  assert message.sender_id == sender_id
  assert message.content == content 

  result = await async_session.execute(
    select(Message).where(
      Message.id == message.id
    )
  )
  db_message = result.scalar_one()

  assert db_message.content == content 

  result = await async_session.execute(
    select(MessageDelivery).where(
      MessageDelivery.message_id == message.id
    )
  )
  deliveries = result.scalars().all()

  assert len(deliveries) == 1
  assert deliveries[0].user_id == 2
  assert deliveries[0].delivered_at is None


