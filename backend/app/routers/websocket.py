import logging

from fastapi import APIRouter, WebSocket, status 

from app.websocket.manager import websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("")
async def websocket_endpoint(
  websocket: WebSocket,
):
  """
  Подключение: ws://localhost:8000/ws
  """

  try:     
    await websocket.accept()

    user_id = await websocket_manager.connection_manager.connect(websocket)
    if not user_id:
      await websocket.close(
        code=status.WS_1011_INTERNAL_ERROR
      )
      return 
    
    await websocket_manager.delivery_manager.send_pending_messages(user_id, websocket)
    await websocket_manager.message_handler.receive_loop(websocket)

  except Exception as e:
    logger.error(f"WebSocket ошибка: {e}", exc_info=True)
    try:
      await websocket.close(
        code=status.WS_1011_INTERNAL_ERROR
      )
    except:
      pass
  finally:
    await websocket_manager.connection_manager.disconnect(websocket)
