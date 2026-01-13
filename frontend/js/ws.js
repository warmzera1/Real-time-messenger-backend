let socket = null; // Текущий WebSocket (один на все приложение)
let messageHandlers = []; // Массив функций-обработчиков входящих сообщений

// Подключение к WebSocket
export function connectWebSocket(onMessage, onOpen, onClose, onError) {
  const token = localStorage.getItem("access_token");

  if (!token) {
    console.error("Нет JWT токена");
    if (onError) onError("Нет токена");
    return null;
  }

  // Подключаемся с токеном в query-параметре
  socket = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

  socket.onopen = (event) => {
    console.log("WebSocket подключен");
    if (onOpen) onOpen(event);
  };

  socket.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);

      // Специальные системные типы
      if (message.type === "connection_established") {
        console.log("Connection established");
        return;
      }
      if (message.type === "ping") {
        socket.send(JSON.stringify({ type: "pong" }));
        return;
      }

      // Обычные сообщения - всем обработчикам
      messageHandlers.forEach((handler) => handler(message));
      if (onMessage) onMessage(message);
    } catch (error) {
      console.error("Ошибка парсинга сообщения:", error);
    }
  };

  socket.onclose = (event) => {
    console.log("WebSocket закрыт");
    if (onClose) onClose(event);
  };

  socket.onerror = (error) => {
    console.log("WebSocket ошибка:", error);
    if (onError) onError(error);
  };

  return socket;
}

// Отправка сообщения в чат
export function sendChatMessage(chatId, content) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    const message = {
      type: "chat_message",
      chat_id: chatId,
      content: content,
    };
    socket.send(JSON.stringify(message));
    return true;
  }
  console.error("WebSocket не подключен");
  return false;
}

// Обработчик входящий сообщений
export function addMessageHandler(handler) {
  messageHandlers.push(handler);
}

// Отключиться и все очистить
export function disconnectWebSocket() {
  if (socket) {
    socket.close();
    socket = null;
  }
  messageHandlers = [];
}

// Проверка состояния подключения
export function isConnected() {
  return socket && socket.readyState === WebSocket.OPEN;
}
