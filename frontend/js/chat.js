import { apiRequest, clearTokens } from "./api.js";
import { connectWebSocket, sendChatMessage, addMessageHandler } from "./ws.js";

class ChatApp {
  constructor() {
    this.currentUser = null;
    this.currentChat = null;
    this.chats = [];
    this.messages = [];

    this.init();
  }

  async init() {
    try {
      // Загружаем пользователя
      await this.loadCurrentUser();

      // Загружаем чаты
      await this.loadChats();

      // Подключаем WebSocket
      this.setupWebSocket();

      // Настраиваем обработчики
      this.setupEventListeners();

      console.log("Приложение мессенджер инициализировано");
    } catch (error) {
      console.log("Ошибка инициализации", error);

      // Если 401 - редирект на авторизацию
      if (error.status === 401) {
        this.redirectToAuth();
      }
    }
  }

  async loadCurrentUser() {
    try {
      this.currentUser = await apiRequest("/users/me");
      console.log("Пользователь загружен", this.currentUser);
    } catch (error) {
      console.error("Ошибка загрузки пользователя", error);
      throw error;
    }
  }

  async loadChats() {
    try {
      this.chats = await apiRequest("/chats");
      console.log("Чаты загружены, количество чатов:", this.chats.length);
    } catch (error) {
      console.error("Ошибка загрузки чатов", error);
      this.showError("Не удалось загрузить чаты");
    }
  }

  async selectChat(chatId) {
    console.log("Выбран чат:", chatId);

    // Находим чат
    this.currentChat = this.chats.find((c) => c.id === chatId);
    if (!this.currentChat) {
      console.error("Чат не найден", chatId);
      return;
    }

    // Обновляем UI
    this.updateChatSelection(chatId);
    this.updateChatHeader();

    // Показываем область ввода
    document.getElementById("inputArea").style.display = "flex";

    // Загружаем сообщения
    await this.loadMessages(chatId);
  }

  async loadMessages(chatId) {
    try {
      this.messages = await apiRequest(`/messages/?chat_id=${chatId}`);
      this.messages.reverse(); // Старые сообщения в начале, новые - в конце
      this.renderMessages();
    } catch (error) {
      console.error("Ошибка загрузки сообщений:", error);
      this.showMessageError();
    }
  }

  setupWebSocket() {
    connectWebSocket(
      (message) => this.handleWebSocketMessage(message),
      () => console.log("WebSocket подключен"),
      () => console.log("WebSocket отключен"),
      (error) => console.log("WebSocket ошибка", error)
    );

    // Добавляем обработчик сообщений чата
    addMessageHandler((message) => {
      if (message.type === "chat_message") {
        this.handleIncomingMessage(message.data);
      }
    });
  }

  handleWebSocketMessage(message) {
    console.log("WebSocket сообщение:", message);

    if (message.type === "connection_established") {
      console.log("Connection established");
    } else if (message.type === "chat_message") {
      this.handleIncomingMessage(message.data);
    } else if (message.type === "error") {
      this.showError(message.error);
    }
  }

  handleIncomingMessage(messageData) {
    // Если сообщение для текущего чата - показываем
    if (this.currentChat && messageData.chat_id === this.currentChat.id) {
      this.addMessageToUI(messageData);
    } else {
      // Уведомление для других чатов
      this.showNotification(messageData);
    }
  }

  async sendMessage() {
    if (!this.currentChat) {
      this.showError("Выберите чат");
      return;
    }

    const input = document.getElementById("messageInput");
    const content = input.value.trim();

    if (!content) {
      return;
    }

    try {
      // Отправляем через WebSocket
      const success = sendChatMessage(this.currentChat.id, content);

      if (success) {
        // Обновление UI
        const tempMessage = {
          id: Date.now(), // Временный ID
          chat_id: this.currentChat.id,
          sender_id: this.currentUser.id,
          content: content,
          created_at: new Date().toISOString(),
        };

        this.addMessageToUI(tempMessage);

        // Очищаем поле ввода
        input.value = "";
        input.focus();
      } else {
        this.showError("Не удалось отправить сообщение");
      }
    } catch (error) {
      console.error("Ошибка отправки", error);
      this.showError("Ошибка отправки сообщения");
    }
  }

  // UI методы
  renderChatList() {
    const container = document.getElementById("chatList");

    if (!this.chats || this.chats.length === 0) {
      container.innerHTML = "<div class='chat-item'>Нет чатов</div>";
      return;
    }

    const html = this.chats
      .map((chat) => {
        const chatName = this.getChatName(chat);

        return `
      <div class="chat-item" data-chat-id="${chat.id}">
        <div class="chat-name">${chatName}</div>
        <div class="chat-meta">${chat.is_group ? "Группа" : "Личный"}</div>
      </div>
    `;
      })
      .join("");

    container.innerHTML = html;

    // Обработчики кликов
    container.querySelectorAll(".chat-item").forEach((item) => {
      item.addEventListener("click", () => {
        const chatId = parseInt(item.dataset.chatId);
        this.selectChat(chatId);
      });
    });
  }

  renderMessages() {
    const container = document.getElementById("messagesContainer");

    if (!this.messages || this.messages.length === 0) {
      container.innerHTML =
        "<p style='text-align: center; color: #666;'>Нет сообщений</p>";
      return;
    }

    const html = this.messages
      .map((msg) => {
        const isOutgoing = msg.sender_id === this.currentUser.id;
        const time = new Date(msg.created_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });

        return `
        <div class="message ${
          isOutgoing ? "message-outgoing" : "message-incoming"
        }">
          <div class="message-content">${msg.content}</div>
          <div class="message-time">${time}</div>
        </div>
      `;
      })
      .join("");

    container.innerHTML = html;

    // Прокручиваем вниз
    container.scrollTop = container.scrollHeight;
  }

  addMessageToUI(message) {
    const container = document.getElementById("messagesContainer");

    const isOutgoing = message.sender_id === this.currentUser.id;
    const time = new Date(message.created_at).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

    const messageHTML = `
    <div class="message ${
      isOutgoing ? "message-outgoing" : "message-incoming"
    }">
      <div class="message-content">${message.content}</div>
      <div class="message-time">${time}</div>
    </div>
    `;

    container.insertAdjacentHTML("beforeend", messageHTML);
    container.scrollTop = container.scrollHeight;
  }

  updateChatSelection(chatId) {
    // Убираем активный класс у всех чатов
    document.querySelectorAll(".chat-item").forEach((item) => {
      item.classList.remove("active");
    });

    // Добавляем активный класс выбранному чату
    const selectedChat = document.querySelector(`[data-chat-id="${chatId}"]`);
    if (selectedChat) {
      selectedChat.classList.add("active");
    }
  }

  updateChatHeader() {
    const header = document.getElementById("chatHeader");

    if (!this.currentChat) {
      header.innerHTML = "<h2>Выберите чат</h2>";
      return;
    }

    const chatName = this.getChatName(this.currentChat);
    header.innerHTML = `<h2>${chatName}</h2>`;
  }

  getChatName(chat) {
    if (chat.name) return chat.name;

    if (!chat.is_group && chat.participants) {
      const otherUser = chat.participants.find(
        (p) => p.id !== this.currentUser.id
      );
      return otherUser ? otherUser.username : "Неизвестный";
    }

    return "Чат";
  }

  // Обработчики событий
  setupEventListeners() {
    // Отправка сообщений
    document
      .getElementById("sendButton")
      .addEventListener("click", () => this.sendMessage());

    document
      .getElementById("messageInput")
      .addEventListener("keypress", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });

    // Поиск чатов
    document.getElementById("chatSearch")?.addEventListener("input", (e) => {
      this.searchChats(e.target.value);
    });

    // Новый чат
    document.getElementById("newChatButton")?.addEventListener("click", () => {
      this.showNewChatModal();
    });

    // Закрытие модального окна
    document.getElementById("closeModal")?.addEventListener("click", () => {
      this.hideModal();
    });

    // Поиск пользователей
    document
      .getElementById("userSearchInput")
      ?.addEventListener("input", (e) => {
        this.debouncedSearchUsers(e.target.value);
      });
  }

  searchChats(query) {
    if (!query.trim()) {
      this.renderChatList();
      return;
    }

    const filtered = this.chats.filter((chat) => {
      const name = this.getChatName(chat).toLowerCase();
      return name.includes(query.toLowerCase());
    });

    this.renderFilteredChats(filtered);
  }

  renderFilteredChats(chats) {
    const container = document.getElementById("chatList");

    if (chats.length === 0) {
      container.innerHTML = "<div class='chat-item'>Чаты не найдены</div>";
      return;
    }

    const html = chats
      .map((chat) => {
        const chatName = this.getChatName(chat);

        return `
          <div class="chat-item" data-chat-id="${chat.id}">
            <div class="chat-name">${chatName}</div>
            <div class="chat-meta">${chat.is_group ? "Группа" : "Личный"}</div>
          </div>
      `;
      })
      .join("");

    container.innerHTML = html;

    container.querySelectorAll(".chat-item").forEach((item) => {
      item.addEventListener("click", () => {
        const chatId = parseInt(item.dataset.chatId);
        this.selectChat(chatId);
      });
    });
  }

  showNewChatModal() {
    document.getElementById("userSearchModal").style.display = "flex";
  }

  hideModal() {
    document.getElementById("userSearchModal").style.display = "none";
  }

  async searchUsers(query) {
    if (query.length < 2) return;

    try {
      const users = await apiRequest(
        `/chats/search?q=${encodeURIComponent(query)}`
      );
      this.renderUserList(users);
    } catch (error) {
      console.error("Ошибка поиска пользователей:", error);
    }
  }

  renderUserList(users) {
    const container = document.getElementById("userList");

    if (!users || users.length === 0) {
      container.innerHTML =
        "<div class='user-item'>Пользователи не найдены</div>";
      return;
    }

    const html = users
      .filter((user) => user.id !== this.currentUser.id)
      .map((user) => {
        return `
          <div class="user-item">
            <div>
              <strong>${user.username}</strong>
              <div>${user.email || ""}</div>
            </div>
            <button class "start-chat" data-user-id="${user.id}">
              Написать
            </button>
          </div>
      `;
      })
      .join("");

    container.innerHTML = html;

    // Обработчики для кнопок
    container.querySelectorAll(".start-chat").forEach((button) => {
      button.addEventListener("click", async () => {
        const userId = button.dataset.userId;
        await this.createNewChat(userId);
      });
    });
  }

  async createNewChat(userId) {
    try {
      const newChat = await apiRequest("/chats/", "POST", {
        second_user_id: parseInt(userId),
      });

      console.log("Чат создан", newChat);

      // Добавляем список
      this.chats.unshift(newChat);
      this.renderChatList();

      // Закрываем модальное окно
      this.hideModal();

      // Выбираем новый чат
      await this.selectChat(newChat.id);
    } catch (error) {
      console.error("При создании нового чата возникла ошибка", error);

      if (error.message.includes("400")) {
        this.showError("Нельзя создать чат с самим собой");
      } else if (error.message.includes("404")) {
        this.showError("Пользователь не найден");
      } else {
        this.showError("Не удалось создать чат");
      }
    }
  }

  debouncedSearchUsers = this.debounce(this.searchUsers.bind(this), 300);

  debounce(func, delay) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), delay);
    };
  }

  showNotification(message) {
    console.log("Новое сообщение из другого чата", message);
    // Реализация уведомлений
  }

  showError(message) {
    console.error("Ошибка:", message);
    // Отображение ошибки в UI
  }

  showMessageError() {
    const container = document.getElementById("messagesContainer");
    container.innerHTML =
      "<p style='color: red; text-align: center;'>Ошибка загрузки сообщений</p>";
  }

  redirectToAuth() {
    clearTokens();
    window.location.href = "auth.html";
  }

  logout() {
    this.redirectToAuth();
  }
}

// Инициализация приложения
document.addEventListener("DOMContentLoaded", () => {
  window.chatApp = new ChatApp();
});
