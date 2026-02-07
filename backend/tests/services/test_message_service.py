import pytest 

from sqlalchemy import select, insert

from app.services.message_service import MessageService 
from app.services.chat_service import ChatService
from app.models.message import Message, MessageDelivery, MessageEdit
from app.models.participant import participants

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


@pytest.mark.asyncio
async def test_get_chat_messages(async_session):
    messages = [] 

    await async_session.execute(
        participants.insert().values(chat_id=1, user_id=1)
    )

    for i in range(3):
        msg = await MessageService.create_message(
            chat_id=1, 
            sender_id=1, 
            content=f"msg {i}",
            db=async_session
        )
        async_session.add(msg)
        messages.append(msg)
    await async_session.commit()

    result = await MessageService.get_chat_messages(chat_id=1, user_id=1, db=async_session)
    assert len(result) == 3
    assert result[0].content == "msg 0"
    assert result[1].content == "msg 1"
    assert result[2].content == "msg 2"


@pytest.mark.asyncio 
async def test_get_message_by_id(async_session):
    msg = Message(chat_id=1, sender_id=1, content="test msg")
    async_session.add(msg)
    await async_session.commit()

    fetched = await MessageService.get_message_by_id(msg.id, async_session)
    assert fetched is not None
    assert fetched.id == msg.id 

    fetched_none = await MessageService.get_message_by_id(9999, async_session)
    assert fetched_none is None 


@pytest.mark.asyncio
async def test_mark_delivered(async_session):
    msg = Message(chat_id=1, sender_id=1, content="test")
    async_session.add(msg)
    await async_session.flush()

    delivery = MessageDelivery(message_id=msg.id, user_id=2, delivered_at=None)
    async_session.add(delivery)
    await async_session.commit() 

    success = await MessageService.mark_delivered(msg.id, 2, async_session)
    assert success is True 

    result = await async_session.execute(
        select(MessageDelivery).where(
        MessageDelivery.id == delivery.id
        )
    )
    updated = result.scalar_one()
    assert updated.delivered_at is not None 


@pytest.mark.asyncio 
async def test_mark_messages_as_read(async_session):
    chat_id = 1
    reader_id = 3 

    await async_session.execute(
        insert(participants).values(chat_id=chat_id, user_id=reader_id)
    )

    msgs = [ 
        Message(chat_id=1, sender_id=1, content="msg1"),
        Message(chat_id=1, sender_id=2, content="msg2"),  
    ]
    async_session.add_all(msgs)
    await async_session.commit() 

    msg_ids = [m.id for m in msgs]

    updated_count = await MessageService.mark_messages_as_read(
        message_ids=msg_ids, 
        reader_id=reader_id, 
        db=async_session
    )

    assert updated_count == 2

    result = await async_session.execute(
        select(Message).where(Message.id.in_(msg_ids))
    )
    updated_msgs = result.scalars().all()
    assert all(m.read_at is not None for m in updated_msgs)

    own_msg = Message(chat_id=chat_id, sender_id=reader_id, content="own msg")
    async_session.add(own_msg)
    await async_session.commit() 

    count = await MessageService.mark_messages_as_read(
        message_ids=[own_msg.id],
        reader_id=reader_id,
        db=async_session
    )
    assert count == 0


@pytest.mark.asyncio
async def test_delete_message(async_session):
    msg = Message(chat_id=1, sender_id=1, content="to delete", is_deleted=False)
    async_session.add(msg)
    await async_session.commit() 
    await async_session.refresh(msg)

    success = await MessageService.delete_message(msg.id, 1, async_session)
    assert success is True 

    result = await async_session.execute(
        select(Message).where(
        Message.id == msg.id
        )
    )
    updated = result.scalar_one() 
    assert updated.is_deleted is True 

    with pytest.raises(ValueError) as exc:
        await MessageService.delete_message(msg.id, 1, async_session)
    assert str(exc.value) == "MESSAGE_NOT_FOUND"

    msg_new = Message(chat_id=1, sender_id=2, content="other", is_deleted=False)
    async_session.add(msg_new)
    await async_session.commit()
    await async_session.refresh(msg_new)

    with pytest.raises(ValueError) as exc:
        await MessageService.delete_message(msg_new.id, 1, async_session)
    assert str(exc.value) == "FORBIDDEN"


@pytest.mark.asyncio
async def test_edit_message(async_session):
    msg = Message(chat_id=1, sender_id=1, content="old content", is_deleted=False)
    async_session.add(msg)
    await async_session.commit() 

    success = await MessageService.edit_message(msg.id, 1, "new content", async_session)
    assert success is True 

    with pytest.raises(ValueError) as exc:
        await MessageService.edit_message(555, 1, "new_content", async_session)
    assert str(exc.value) == "MESSAGE_NOT_FOUND"

    result = await async_session.execute(
        select(Message).where(
        Message.id == msg.id
        )
    )
    updated = result.scalar_one()
    assert updated.content == "new content"
    assert updated.is_edited is True 

    result = await async_session.execute(
        select(MessageEdit).where(
        MessageEdit.message_id == msg.id
        )
    )
    edit_record = result.scalar_one()
    assert edit_record.old_content == "old content"
    assert edit_record.new_content == "new content"

    with pytest.raises(ValueError) as exc:
        await MessageService.edit_message(msg.id, 2, "fail edit", async_session)
    assert str(exc.value) == "FORBIDDEN"


