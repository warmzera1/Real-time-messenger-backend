// Импортируем функцию apiRequest из api.js
import { apiRequest, tokenManager } from "./api.js";

// Ждем полную загрузку DOM
document.addEventListener("DOMContentLoaded", function () {
  // Находим элементы
  const loginForm = document.getElementById("loginForm");
  const errorElement = document.getElementById("error");

  // Если токен уже есть, редиректим на главную
  if (
    tokenManager.hasToken() &&
    !window.location.pathname.includes("auth.html")
  ) {
    window.location.href = "/index.html";
  }

  // Обработчик отправки формы
  loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    console.log("Форма отправлена");

    // Скрываем предыдущую ошибку
    errorElement.style.display = "none";
    errorElement.textContent = "";

    // Получаем значения полей
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value.trim();
    console.log("Введено имя пользователя:", username);

    // Валидация
    if (!username || !password) {
      showError("Заполните все поля");
      return;
    }

    // Показываем индикатор загрузки
    const submitButton = loginForm.querySelector('button[type="submit"]');
    const originalButtonText = submitButton.textContent;
    submitButton.textContent = "Вход...";
    submitButton.disabled = true;

    try {
      console.log("Отправляю запрос на /auth/login...");

      // Отправляем запрос на авторизацию
      const response = await apiRequest("/auth/login", "POST", {
        username: username,
        password: password,
      });

      console.log("Успешный ответ от сервера:", response);

      // ВАЖНО: Сохраняем токены
      if (response.access_token) {
        console.log("Сохраняю токены...");
        tokenManager.setTokens(response.access_token, response.refresh_token);
        console.log("Токены сохранены");
      } else {
        console.error("Сервер не вернул access_token!");
        showError("Ошибка сервера: не получен токен");
        return;
      }

      // Ждем немного чтобы токены точно сохранились
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Проверяем сохранение
      if (!tokenManager.hasToken()) {
        showError("Не удалось сохранить токен");
        return;
      }

      // Редирект на главную страницу
      console.log("Выполняю редирект на /index.html");
      window.location.href = "/index.html";
    } catch (error) {
      console.error("Ошибка входа:", error);
      console.error("Детали:", error.message, error.response);

      // Определяем тип ошибки
      let errorMessage = "Ошибка сервера. Попробуйте позже";

      if (
        error.status === 401 ||
        error.message.includes("401") ||
        (error.response && error.response.detail === "Неверные учетные данные")
      ) {
        errorMessage = "Неверный логин или пароль";
      } else if (error.status === 400 || error.message.includes("400")) {
        errorMessage = "Неверный формат данных";
      } else if (error.status === 429 || error.message.includes("429")) {
        errorMessage = "Слишком много попыток. Подождите 5 минут";
      } else if (
        error.message.includes("Failed to fetch") ||
        !navigator.onLine
      ) {
        errorMessage = "Нет подключения к серверу";
      } else if (error.response && error.response.detail) {
        errorMessage = error.response.detail;
      }

      showError(errorMessage);
    } finally {
      // Восстанавливаем кнопку
      submitButton.textContent = originalButtonText;
      submitButton.disabled = false;
    }
  });

  // Обработчик для показа/скрытия пароля
  const togglePassword = document.getElementById("togglePassword");
  const passwordInput = document.getElementById("password");

  if (togglePassword && passwordInput) {
    togglePassword.addEventListener("click", function () {
      const type =
        passwordInput.getAttribute("type") === "password" ? "text" : "password";
      passwordInput.setAttribute("type", type);
      // Меняем иконку если используем FontAwesome
      if (this.classList) {
        this.classList.toggle("fa-eye");
        this.classList.toggle("fa-eye-slash");
      }
    });
  }
});

// Функция для показа ошибки пользователю
function showError(message) {
  const errorElement = document.getElementById("error");
  const passwordInput = document.getElementById("password");

  // Устанавливаем текст ошибки
  errorElement.textContent = message;
  errorElement.style.display = "block";

  // Очищаем поле пароля для безопасности
  if (passwordInput) {
    passwordInput.value = "";
    passwordInput.focus();
  }

  // Автоматически скрываем через 5 секунд
  setTimeout(() => {
    errorElement.style.display = "none";
  }, 5000);
}

// Дополнительно: можно добавить проверку нажатия Enter
// (но стандартное поведение формы уже работает)
