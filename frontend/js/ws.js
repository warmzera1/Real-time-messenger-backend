// Глобальная переменная для хранения объекта WebSocket
let socket = null;

// Массив для хранения дополнительных обработчиков сообщений
let messageHandlers = [];

// Функция подключения к WebSocket серверу
// OnMessage - основной обработчик сообщений, onOpen - при открытии, onError - при ошибке
export function connectWebSocket(onMessage, onOpen, onError) {
  // Создаем новое WebSocket-соединение с сервером
  // Куки отправляются автоматически (если тот же домен)
  socket = new WebSocket(`ws://localhost:8000/ws`);

  // Обработчик события открытия соединения
  socket.onopen = (event) => {
    console.log("WebSocket соединение установлено"); // Лог в консоль
    if (onOpen) onOpen(event); // Вызываем пользовательский callback
  };

  // Обработчик входящих сообщений
  socket.onmessage = (event) => {
    try {
      // Парсим строку в JSON-объект
      const message = JSON.parse(event.data);
      // Вызываем все зарегистрированные обработчики
      messageHandlers.forEach((handler) => handler(message));
      // Вызываем основной обработчик, переданный в connectWebSocket
      if (onMessage) onMessage(message);
    } catch (error) {
      // Логируем ошибку парсинга
      console.log("Ошибка парсинга сообщения:", error);
    }
  };

  // Обработчик ошибок соединения
  socket.onerror = (error) => {
    console.log("WebSocket error:", error);
    if (onError) onError(error); // Передаем ошибку в пользовательский callback
  };

  // Возвращем объекта сокета
  return socket;
}

// Функция отправки сообщений через WebSocket
export function sendMessage(message) {
  // Проверяем, что сокен существует и соединение открыто
  if (socket && socket.readyState === WebSocket.OPEN) {
    // Сериализуем объект в JSON и отправляем
    socket.send(JSON.stringify(message));
  } else {
    // Если соединение не готово - выводим ошибку
    console.error("WebSocket соединение закрыто");
  }
}

// Дополнительный обработчик входящих сообщений
export function addMessageHandler(handler) {
  // Добавляем функцию в массив обработчика
  messageHandlers.push(handler);
}
