import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status 

from app.dependencies.websocket_auth import get_current_user_ws
from app.websocket.manager import websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("")
async def websocket_endpoint(
  websocket: WebSocket,
  token: str = Query(..., description="JWT token"),
):
  """
  WebSocket endpoint для обмена сообщениями в реальном времени
  Подключение: ws://localhost:8000/ws?token=<JWT>
  """

  user = None 
  try:
    await websocket.accept()

    # 1. Аутентификация
    user = await get_current_user_ws(token)
    if not user:
      await websocket.close(
        code=status.WS_1008_POLICY_VIOLATION
      )
      return 

    logger.info(f"Аутентификация WebSocket прошла успешно для пользователя {user['id']}")

    # 2. Подключение к менеджеру
    connected = await websocket_manager.connect(websocket, user)
    if not connected:
      await websocket.close(
        code=status.WS_1011_INTERNAL_ERROR
      )
      return 
    
    # 3. Основной цикл обработки сообщений
    await websocket_manager.handle_incoming_message(websocket)

  except WebSocketDisconnect as e:
    # Нормальное отключение клиента
    if user:
      logger.info(f"Пользователь {user.get('id')} отключился успешно")
    else:
      logger.info(f"Неподтвержденный пользователь отключился")

  except Exception as e:
    # Неожиданная ошибка
    logger.error(f"WebSocket ошибка: {e}", exc_info=True)
    try:
      await websocket.close(
        code=status.WS_1011_INTERNAL_ERROR
      )
    except:
      pass
  finally:
    # Гарантированное отключение
    if user:
      await websocket_manager.disconnect(websocket)
