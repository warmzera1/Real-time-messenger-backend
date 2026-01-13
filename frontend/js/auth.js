// Импорт функций из api.js
import { apiRequest, setTokens, hasToken } from "./api.js";

// Если токен уже есть - сразу на главную страницу
if (hasToken()) {
  window.location.href = "index.html";
}

// Ждем загрузки DOM
document.addEventListener("DOMContentLoaded", function () {
  const loginForm = document.getElementById("loginForm");
  const errorElement = document.getElementById("error");
  const togglePassword = document.getElementById("togglePassword");
  const passwordInput = document.getElementById("password");

  // Показать/скрыть пароль
  if (togglePassword && passwordInput) {
    togglePassword.addEventListener("click", function () {
      const type = passwordInput.type === "password" ? "text" : "password";
      passwordInput.type = type;

      // Меняем иконку глаза
      const icon = this.querySelector("i");
      if (icon) {
        icon.classList.toggle("fa-eye");
        icon.classList.toggle("fa-eye-slash");
      }
    });
  }

  // Обработка отправки формы логина
  loginForm.addEventListener("submit", async function (event) {
    event.preventDefault(); // Отменяем обычную отправку формы

    errorElement.style.display = "none";
    errorElement.textContent = "";

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value.trim();

    if (!username && !password) {
      showError("Заполните все поля");
      return;
    }

    // Блокировка кнопки + спиннер
    const submitButton = loginForm.querySelector("button[type='submit']");
    const originalText = submitButton.textContent;
    submitButton.disabled = true;
    submitButton.innerHTML = "<i class='fas fa-spinner fa-spin'></i> Вход...";

    try {
      // Запрос на сервер
      const response = await apiRequest("/auth/login", "POST", {
        username,
        password,
      });

      // Успех - сохраняем токен и редирект
      if (response.access_token) {
        setTokens(response.access_token);
        window.location.href = "index.html";
      } else {
        showError("Ошибка сервера: токен не получен");
      }
    } catch (error) {
      // Обработка разных ошибок
      if (error.status === 401) {
        showError("Неверный логин или пароль");
      } else if (error.status === 400) {
        showError("Неверный формат данных");
      } else if (error.message.includes("Failed to fetch")) {
        showError("Нет подключения к серверу");
      } else {
        showError(error.message || "Ошибка сервера");
      }
    } finally {
      // Всегда возвращаем кнопку в нормальное состояние
      submitButton.disabled = false;
      submitButton.textContent = originalText;
    }
  });

  // Заглушка для ссылки на регистрацию
  document
    .getElementById("registerLink")
    ?.addEventListener("click", function (e) {
      e.preventDefault();
      alert("Регистрация временно не реализована");
    });
});

// Функция показа ошибки + авто-скрытие
function showError(message) {
  const errorElement = document.getElementById("error");
  const passwordInput = document.getElementById("password");

  errorElement.textContent = message;
  errorElement.style.display = "block";

  // Очищаем поле пароля и фокус на него
  if (passwordInput) {
    passwordInput.value = "";
    passwordInput.focus();
  }

  // Автоскрытие ошибки через 5 секунд
  setTimeout(() => {
    errorElement.style.display = "none";
  }, 5000);
}
