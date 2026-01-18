// Импорт функций из api.js
import { apiRequest, setTokens, hasToken } from "./api.js";

// Если токен уже есть - сразу на главную страницу
if (hasToken()) {
  window.location.href = "index.html";
}

// Ждем загрузки DOM
document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("loginForm");
  const registerButton = document.getElementById("registerButton");
  const errorElement = document.getElementById("error");

  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const togglePassword = document.getElementById("togglePassword");

  // Показать/скрыть пароль
  if (togglePassword) {
    togglePassword.addEventListener("click", () => {
      const type = passwordInput.type === "password" ? "text" : "password";
      passwordInput.type = type;

      // Меняем иконку глаза
      const icon = this.querySelector("i");
      icon.classList.toggle("fa-eye");
      icon.classList.toggle("fa-eye-slash");
    });
  }

  // Обработка отправки формы логина
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault(); // Отменяем обычную отправку формы
    clearError();

    const identifier = usernameInput.value.trim();
    const password = passwordInput.value.trim();

    if (!identifier && !password) {
      showError("Заполните логин и пароль");
      return;
    }

    disableForm(loginForm, true);

    try {
      // Запрос на сервер
      const response = await apiRequest("/auth/login", "POST", {
        username: identifier,
        password: password,
      });

      // Успех - сохраняем токен и редирект
      if (!response.access_token || !response.refresh_token) {
        throw new Error("Ошибка сервера: токены не получен");
      }

      setTokens(response.access_token, response.refresh_token);
      window.location.href = "index.html";
    } catch (error) {
      handleAuthError(error);
    } finally {
      // Всегда возвращаем кнопку в нормальное состояние
      disableForm(loginForm, false);
    }
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

  function clearError() {
    const errorElement = document.getElementById("error");
    errorElement.textContent = "";
    errorElement.style.display = "none";
  }

  function disableForm(form, disabled) {
    const button = form.querySelector("button[type='submit']");
    if (!button) return;

    button.disabled = disabled;
    button.textContent = disabled ? "Загрузка..." : "Войти";
  }

  function handleAuthError(error) {
    if (error?.status === 401) {
      showError("Неверный логин или пароль");
    } else if (error?.status === 400) {
      showError("Некорректные данные");
    } else if (error?.message?.includes("Failed to fetch")) {
      showError("Нет соединения с сервером");
    } else {
      showError(error.message || "Ошибка сервера");
    }
  }

  document.getElementById("goToRegister")?.addEventListener("click", () => {
    window.location.href = "register.html";
  });
});
