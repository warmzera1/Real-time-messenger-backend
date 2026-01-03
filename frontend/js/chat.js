import { apiRequest } from "./api.js";

// Глобальные переменные
let currentUser = null; // Данные текущего авторизованного пользователя
let currentChat = null; // Текущий выбранный чат
let chats = []; // Массив всех чатов пользователя
let ws = null; // WebSocket соединение

// Инициализация при запуске страницы
document.addEventListener("DOMContentLoaded", async function () {
  console.log("Страница чатов загружена");

  try {
    // 1. Получаем данные текущего пользователя
    currentUser = await loadCurrentUser();
    console.log("Текущий пользователь:", currentUser);

    // 2. Загружаем список чатов
    await loadChats();

    // 3. Настраиваем обработчики события
    setupEventListeners();
  } catch (error) {
    console.error("Ошибка инициализации:", error);
    // Если ошибка авторизаци - редирект на страницу входа
    if (error.message.includes("401") || error.message.includes("403")) {
      window.location.href = "auth.html";
    }
  }
});

// 1. Загрузка данных текущего пользователя
async function loadCurrentUser() {
  try {
    const user = await apiRequest("/users/me", "GET");
    return user;
  } catch (error) {
    console.error("Ошибка загрузки пользователя:", error);
    throw error;
  }
}

// 2. Функция загрузки списка чатов
async function loadChats() {
  try {
    chats = await apiRequest("/chats", "GET");
    console.log("Загружено чатов пользователя:", chats.length);

    const uniqueChats = [];
    const seenIds = new Set();

    for (const chat of chats) {
      if (!seenIds.has(chat.id)) {
        seenIds.add(chat.id);
        uniqueChats.push(chat);
      } else {
        console.warn(`Обнаружен дубликат чата ID: ${chat.id}`);
      }
    }

    chats = uniqueChats;
    console.log(
      "Уникальные чаты:",
      chats.map((c) => c.id)
    );

    // Отображаем список чатов
    renderChatList();
  } catch (error) {
    console.error("Ошибка загрузки чатов:", error);
    document.getElementById("chatList").innerHTML =
      '<div class="chat-item">Ошибка загрузки чатов</div>';
  }
}

// 3. Функция отображения списка чатов
function renderChatList() {
  const chatList = document.getElementById("chatList");

  if (chats.length === 0) {
    chatList.innerHTML = "<div class='chat-item'>Нет чатов</div>";
    return;
  }

  // Создаем HTML для каждого чата
  const chatItems = chats
    .map((chat) => {
      // Определяем название чата (имя собеседника или название группового чата)
      let chatName = chat.name || "Без названия";

      if (!chat.is_group && chat.participants) {
        const otherUser = chat.participants.find(
          (p) => p.id !== currentUser.id
        );
        if (otherUser) {
          chatName = otherUser.username;
        }
      }

      return `
        <div class="chat-item" data-chat-id="${chat.id}">
            <div style="font-weight: bold;">${chatName}</div>
            <div style="color: #666; font-size: 14px;">${
              chat.is_group ? "Групповой чат" : "Личный чат"
            }</div>
        </div>
    `;
    })
    .join("");

  chatList.innerHTML = chatItems;

  // Добавляем обработчики кликов на чаты
  document.querySelectorAll(".chat-item[data-chat-id]").forEach((item) => {
    item.addEventListener("click", function () {
      const chatId = Number(this.getAttribute("data-chat-id"));
      moveChatToTop(chatId);
      selectChat(chatId);
    });
  });
}

// 4. Функция выбора чата по ID
async function selectChat(chatId) {
  console.log("Выбран чат:", chatId);

  // 1. Находим текущий чат и сохраняем
  currentChat = chats.find((chat) => chat.id === chatId);
  if (!currentChat) {
    console.error("Чат не найден в chats:", chatId);
    return;
  }

  // 2. Убираем класс 'active' у всех элементов чата в списке
  document.querySelectorAll(".chat-item").forEach((item) => {
    item.classList.remove("active");
  });

  // 3. Находим элемент выбранного чата по data-атрибуту data-chat-id
  const selectedChat = document.querySelector(`[data-chat-id="${chatId}"]`);
  if (selectedChat) {
    // Добавляем класс 'active' для визуального выделения
    selectedChat.classList.add("active");
  }

  // 4. Асинхронно загружаем историю сообщений для этого чата
  await loadChatHistory(chatId);

  // 5. Обновляем заголовок чата (имя собеседника, аватар и т.д)
  updateChatHeader();

  // 6. Подключаемся к WebSocket этого чата
  connectWebSocket(chatId);

  // 7. Показываем блок ввода сообщения (был скрыт на экране логина)
  document.getElementById("inputArea").style.display = "flex";
}

// 5. Асинхронная функция загрузки истории сообщений чата по ID
async function loadChatHistory(chatId) {
  try {
    // GET-запрос к API для получения всех сообщений конкретного чата
    const messages = await apiRequest(`/${chatId}/messages`, `GET`);
    console.log("Загружено сообщений:", messages.length);

    // Отрисовываем полученные сообщения в контейнере
    renderMessages(messages);
  } catch (error) {
    // Логируем ошибку
    console.error("Ошибка загрузки сообщений:", error);

    // Показываем пользователю сообщение об ошибке в контейнере сообщений
    document.getElementById("messagesContainer").innerHTML =
      '<p style="color: red;">Ошибка загрузки сообщений</p>';
  }
}

// 6. Функция отрисовки сообщений в контейнере чата
function renderMessages(messages) {
  // Получаем контейнер для сообщений
  const container = document.getElementById("messagesContainer");

  // Если сообщений нет - показываем заглушку
  if (!messages || messages.length === 0) {
    container.innerHTML =
      '<p style="text-align: center; color: #666;">Нет сообщений</p>';
    return;
  }

  // Переворачиваем порядок
  const reversedMessages = [...messages].reverse();

  // Преобразуем массив сообщений в HTML строки
  const messagesHTML = reversedMessages
    .map((msg) => {
      // Определяем, исходящее ли сообщение (от текущего пользователя)
      const isOutgoing = msg.sender_id === currentUser.id;
      // Формируем время создания сообщения
      const time = new Date(msg.created_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });

      // Возвращаем HTML-блок одного сообщения с нужным классом
      return `
        <div class="message ${
          isOutgoing ? "message-outgoing" : "message-incoming"
        }">
          <div>${msg.content}</div>
          <div style="font-size: 12px; margin-top: 5px; text-align: right;">${time}</div>
        </div>
    `;
    })
    .join(""); // Объеденяем все строки без разделителя

  // Вставляет готовый HTML в контейнер
  container.innerHTML = messagesHTML;

  // Автоматически прокручиваем вниз, чтобы видно было последнее сообщение
  container.scrollTop = container.scrollHeight;
}

// 7. Функция настройки всех обработчиков событий на странице
function setupEventListeners() {
  // Элементы для отправки сообщения
  const sendButton = document.getElementById("sendButton");
  const messageInput = document.getElementById("messageInput");

  // Отправка по клику на кнопку
  sendButton.addEventListener("click", sendMessage);

  // Отправка на Enter (без Shift, чтобы Shift + Enter делал перенос строки)
  messageInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault(); // Делаем перенос стройки
      sendMessage(); // Вызываем функцию отправки
    }
  });

  // Фильтрация списков чатов при вводе в поиск
  document.getElementById("chatSearch").addEventListener("input", function (e) {
    searchChats(e.target.value);
  });

  // Кнопка "Новый чат", открывает модальное окно поиска пользователей
  document
    .getElementById("newChatButton")
    .addEventListener("click", showUserSearchModal);
  document
    .getElementById("closeModal")
    .addEventListener("click", hideUserSearchModal);

  // Поиск пользователей в модальном окно
  document
    .getElementById("userSearchInput")
    .addEventListener("input", function (e) {
      debouncedSearchUsers(e.target.value);
    });

  // Закрытие модального окна по клику на темный фон (не на содержание)
  document
    .getElementById("userSearchModal")
    .addEventListener("click", function (e) {
      if (e.target === this) {
        // Клик по фону
        hideUserSearchModal();
      }
    });
}

// 8. Асинхронная функция отправки сообщений в текущий чат
async function sendMessage() {
  // Проверяем, выбран ли чат
  if (!currentChat) {
    alert("Выберите чат");
    return;
  }

  // Получаем поле ввода и текст сообщения (убираем пробелы)
  const input = document.getElementById("messageInput");
  const content = input.value.trim();

  // Если текст пустой - ничего не отправляем
  if (!content) return;

  try {
    const newMessage = await apiRequest(`/${currentChat.id}/messages`, "POST", {
      content: content, // Текст сообщения
    });

    console.log("Сообщение отправлено:", newMessage);

    // Очищаем поле ввода после успешной отправки
    input.value = "";

    // Добавляем новое сообщение в интерфейс сразу (оптимистично)
    addMessageToUI(newMessage);
    moveChatToTop(currentChat.id);

    // Если WebSocket подключен, отправляем сообщение другим участникам
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          type: "message",
          content: content,
        })
      );
    }
  } catch (error) {
    console.error("Ошибка отправки сообщения:", error);
    alert("Не удалось отправить сообщение");
  }
}

// 9. Добавляем сообщение в интерфейс чата
function addMessageToUI(message) {
  // Контенейр для сообщений
  const container = document.getElementById("messagesContainer");

  // Определяем, исходящее ли сообщение (от текущего пользователя)
  const isOutgoing = message.sender_id === currentUser.id;

  // Текущее время для отображения
  const time = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  // HTML-разметка одного сообщения
  const messageHTML = `
  <div class="message ${isOutgoing ? "message-outgoing" : "message-incoming"}">
      <div>${message.content}</div>
      <div style="font-size: 12px; margin-top: 5px; text-align: right;">${time}</div>
  </div>
  `;

  // Вставляем новое сообщение в конец контейнера
  container.insertAdjacentHTML("beforeend", messageHTML);

  // Прокручиваем вниз, чтобы было видно новое сообщение
  container.scrollTop = container.scrollHeight;
}

// 10. Функция поиска чатов по введеному запросу
function searchChats(query) {
  // Если запрос пустой - показывай полный список чатов
  if (!query.trim()) {
    renderChatList();
    return;
  }

  // Фильтруем массив chats
  const filteredChats = chats.filter((chat) => {
    let chatName = chat.name || "";
    if (!chat.is_group && chat.participants) {
      const otherUser = chat.participants.find((p) => p.id !== currentUser.id);
      if (otherUser) {
        chatName = otherUser.username;
      }
    }

    return chatName.toLowerCase().includes(query.toLowerCase());
  });

  // Отрисовываем только отфильтрованные чаты
  renderFilteredChats(filteredChats);
}

// 11. Функция показа модального окна поиска пользователей
function showUserSearchModal() {
  document.getElementById("userSearchModal").style.display = "flex";
  document.getElementById("userSearchInput").value = "";
  document.getElementById("userList").innerHTML =
    "<div>Введите имя для поиска</div>";
}

// 12. Функция скрыть модальное окно поиска пользователей
function hideUserSearchModal() {
  document.getElementById("userSearchModal").style.display = "none";
}

// 13. Функция создания нового чата
async function createNewChat(userId) {
  try {
    // Эндпоинт для создания чата
    const newChat = await apiRequest("/chats/", "POST", {
      second_user_id: Number(userId),
    });

    console.log("Создан новый чат:", newChat);

    // Закрываем модальное окно
    hideUserSearchModal();

    // Проверяем, существует ли уже такой же чат
    const existingChatIndex = chats.findIndex((c) => c.id === newChat.id);

    if (existingChatIndex === -1) {
      // Новый чат - добавляем в начало
      chats.unshift(newChat);
    } else {
      // Чат уже есть - перемещаем в начало
      const [existingChat] = chats.splice(existingChatIndex, 1);
      chats.unshift(existingChat);
    }

    // // Обновляем список чатов
    // chats.unshift(newChat);
    renderChatList();

    // Выбираем новый чат
    selectChat(newChat.id);
  } catch (error) {
    console.error("Ошибка создания чата:", error);
    if (error.message.includes("400")) {
      alert("Нельзя создать чат с самим собой");
    } else if (error.message.includes("404")) {
      alert("Пользователь не найден");
    } else {
      alert("Не удалось создать чат");
    }
  }
}

// 14. Функция обновления заголовока чата
function updateChatHeader() {
  const header = document.getElementById("chatHeader");

  if (!currentChat) {
    header.innerHTML = "<h2>Выберите чат</h2>";
    return;
  }

  let chatName = currentChat.name || "Без названия";
  let participantsCount = 1;

  if (!currentChat.is_group && currentChat.participants) {
    const otherUser = currentChat.participants.find(
      (p) => p.id !== currentUser.id
    );
    if (otherUser) {
      chatName = otherUser.username;
    }
    participantsCount = currentChat.participants.length;
  }

  header.innerHTML = `
      <h2>${chatName}</h2>
      <div style="color: #666; font-size: 14px;">
          ${participantsCount} участник${participantsCount > 1 ? "a" : ""}
      </div>
  `;
}

// 15. WebSocket подключение
function connectWebSocket(chatId) {
  // Закрываем предыдущее соединение
  if (ws) {
    ws.close(); // Закрываем старое соединение
  }

  // Получаем токен из localStorage
  const token = localStorage.getItem("access_token");
  if (!token) {
    console.error("Токен не найден в localStorage");
    return;
  }

  // Подключаемся к WebSocket конкретного чата
  const wsUrl = `ws://localhost:8000/ws/${chatId}?token=${encodeURIComponent(
    token
  )}`;
  ws = new WebSocket(wsUrl);

  ws.onopen = function () {
    console.log(`WebSocket подключен к чату: ${chatId}`);
  };

  ws.onmessage = function (event) {
    try {
      const data = JSON.parse(event.data);
      console.log("WebSocket сообщение:", data);

      if (
        data.type === "message" &&
        data.message.sender_id !== currentUser.id
      ) {
        // Добавляем новое сообщение
        addMessageToUI(data.message);
      } else if (data.type === "system") {
        console.log("Системное сообщение:", data.message);
      }
    } catch (error) {
      console.error("Ошибка парсинга WebSocket сообщения:", error);
    }
  };

  ws.onerror = function (error) {
    console.error("WebSocket ошибка:", error);
  };

  ws.onclose = function (error) {
    console.error("WebSocket отключен");
  };
}

// 16. Обработка WebSocket сообщений
function handleWebSocketMessage(data) {
  console.log("WebSocket сообщение:", data);

  switch (data.type) {
    case "new_message":
      if (data.message.chat_id === currentChat?.id) {
        // Добавляем новое сообщение в текущий чат
        addMessageToUI(data.message);
      }
      break;

    case "chat_updated":
      // Обновляем информацию о чате
      updateChatInfo(data.chat);
      break;

    default:
      console.log("Неизвестный тип сообщения:", data.type);
  }
}

// 17. Обновляем информацию о чате в массиве chats
function updateChatInfo(updatedChat) {
  // Находим индекс чата с таким же ID
  const index = chats.findIndex((chat) => chat.id === updatedChat.id);

  // Если чат найден (index !== -1)
  if (index !== -1) {
    // Заменяем старые данные чата на новые
    chats[index] = updatedChat;
    // Переписываем весь список чатов для отображения
    renderChatList();
  }
}

// // Функция для получения токена из кук
// function getTokenFromCookies() {
//   const cookies = document.cookie.split(";");
//   for (let cookie of cookies) {
//     const [name, value] = cookie.trim().split("=");
//     // Ищем access token или другой токен
//     if (name === "access_token" || name.includes("token")) {
//       return value;
//     }
//   }
//   return null;
// }

// 18. Функция поиска пользователей для нового чата
async function searchUsers(query) {
  const userList = document.getElementById("userList");

  if (!query.trim() || query.length < 2) {
    userList.innerHTML = "<div>Введите минимум 2 символа</div>";
    return;
  }

  userList.innerHTML = "<div>Поиск...</div>";

  try {
    const users = await apiRequest(
      `/chats/search?q=${encodeURIComponent(query)}`,
      "GET"
    );

    if (!users || users.length === 0) {
      userList.innerHTML = "<div>Пользователи не найдены</div>";
      return;
    }

    const userItems = users
      .map((user) => {
        if (user.id === currentUser.id) return "";

        const existingChat = findPrivateChatWithUser(user.id);
        const isExisting = Boolean(existingChat);

        return `
          <div class="user-item">
            <div>
              <strong>${user.username}<strong>
              <div style="color: #666; font-size: 14px;">${
                user.email || ""
              }</div>
            </div>

            <button 
            class="start-chat-button"
            data-mode='${isExisting ? "open" : "create"}'
            data-user-id="${user.id}"
            ${isExisting ? `data-chat-id="${existingChat.id}"` : ""}
            >
              ${isExisting ? "Открыть чат" : "Написать"}
            </button>
          </div>
      `;
      })
      .join("");

    userList.innerHTML = userItems;

    document.querySelectorAll(".start-chat-button").forEach((button) => {
      button.addEventListener("click", function () {
        const mode = this.dataset.mode;

        if (mode === "open") {
          const chatId = Number(this.dataset.chatId);
          hideUserSearchModal();
          moveChatToTop(chatId);
          selectChat(chatId);
        } else {
          createNewChat(this.dataset.userId);
        }
      });
    });
  } catch (error) {
    console.error("Ошибка поиска пользователей:", error);
    userList.innerHTML = "<div style='color: red;'>Ошибка поиска</div>";
  }
}

// 19. Функция отрисовки отфильтрованных чатов (для поиска)
function renderFilteredChats(filteredChats) {
  const chatList = document.getElementById("chatList"); // Список чатов

  // Если ничего не найдено - показываем заглушку
  if (filteredChats.length === 0) {
    chatList.innerHTML = "<div class='chat-item'>Чаты не найдены</div>";
    return;
  }

  // Формируем HTML для каждого отфильтрованного чата
  const chatItems = filteredChats
    .map((chat) => {
      let chatName = chat.name || "Без названия";

      if (!chat.is_group && chat.participants) {
        const otherUser = chat.participants.find(
          (p) => p.id !== currentUser.id
        );
        if (otherUser) {
          chatName = otherUser.username;
        }
      }

      // HTML-элемент одного чата с data-атрибутами для выбора
      return `
      <div class="chat-item" data-chat-id="${chat.id}">
        <div style="font-weight: bold;">${chatName}</div>
        // <div style="color: #666; font-size: 14px;">${lastMessage}</div>
      </div>
    `;
    })
    .join(""); // Объединяем в одну строку

  // Вставляем контейнер в списка чатов
  chatList.innerHTML = chatItems;

  document.querySelectorAll(".chat-item[data-chat-id]").forEach((item) => {
    item.addEventListener("click", function () {
      const chatId = Number(this.getAttribute("data-chat-id"));
      moveChatToTop(chatId);
      selectChat(chatId);
    });
  });
}

// 20. Универсальная функция debounce - задержка
function debounce(fn, delay = 300) {
  // Переменная для хранения ID таймера
  let timeoutId;

  // Возвращаем новую функцию обертку
  return function (...args) {
    // При каждом вызове сбрасываем предыдущий таймер
    clearTimeout(timeoutId);

    // Запускаем новый таймер
    timeoutId = setTimeout(() => {
      // По истечению delay вызываем оригинальную функцию fn
      // apply сохраняет контекст this и передает все аргументы
      fn.apply(this, args);
    }, delay);
  };
}

// 21. Вспомогательная функция поиска чата
function findPrivateChatWithUser(userId) {
  return chats.find(
    (chat) =>
      !chat.is_group &&
      chat.participants.length == 2 &&
      chat.participants.some((u) => u.id === Number(userId))
  );
}

// 22. Функция "поднятия чат вверх" (после отправки сообщения, поиска пользователя)
function moveChatToTop(chatId) {
  const index = chats.findIndex((c) => c.id === Number(chatId));
  if (index === -1) return;

  const [chat] = chats.splice(index, 1);
  chats.unshift(chat);

  renderChatList();
}

const debouncedSearchUsers = debounce(searchUsers, 400);

// Экспортиуем ключевые функции в глобальный объект для удобной отладки в консоли
window.chatApp = {
  loadChats,
  selectChat,
  sendMessage,
  searchUsers,
  createNewChat,
  currentUser,
  currentChat,
  chats,
};

// Лог в консоль при загрузке модуля
console.log("Chat модель загружен");
