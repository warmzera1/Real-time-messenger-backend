// Импортируем функцию apiRequest из api.js
import { apiRequest } from "./api.js";

// Ждем полную загрузку DOM, чтобы все элементы страницы были доступны
document.addEventListener("DOMContentLoaded", function () {
  // Находит форму логина по ID
  const loginForm = document.getElementById("loginForm");

  // Элемент для отображения сообщений об ошибках
  const errorElement = document.getElementById("error");

  // Обработчик отправки формы
  loginForm.addEventListener("submit", async function (event) {
    // Отменяем стандартную отправку формы (предотвращаем перезагрузку страницы)
    event.preventDefault();
    console.log("Форма отправлена");

    // Скрываем предыдущую ошибку перед новой попыткой
    errorElement.style.display = "none";
    errorElement.textContent = "";

    // Получаем значения полей, убирая лишние пробелы
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value.trim();
    console.log("Введено:", { username, password });

    // Простая валидация: проверяем, что поля заполнены
    if (!username || !password) {
      showError("Заполните все поля");
      return; // Прерывая дальнейшее выполнение
    }

    try {
      console.log("Отправляю запрос на /auth/login...");
      // Отправляем POST запрос на сервер для авторизации
      const response = await apiRequest("/auth/login", "POST", {
        username: username,
        password: password,
      });
      console.log("Успешный ответ:", response);

      // Если запрос успешен - переходим на главную страницу
      window.location.href = "/index.html";
    } catch (error) {
      // Логируем ошибку в консоль для отладки
      console.error("Ошибка входа:", error);
      console.error("Детали:", error.message);

      // Определяем тип ошибки и показываем соответствующее сообщение
      if (error.message.includes("401")) {
        showError("Неверный логин или пароль");
      } else {
        showError("Ошибка сервера. Попробуй позже");
      }
    }
  });
});

// Функция для показа ошибки пользователю
function showError(message) {
  const errorElement = document.getElementById("error");
  errorElement.textContent = message; // Устанавливаем текст
  errorElement.style.display = "block"; // Делаем видимым
  // Автоматически скрываем через 5 секунд
  setTimeout(() => {
    errorElement.style.display = "none";
  }, 5000);
}

// Дополнительно: отправка формы по Enter в любом поле ввода
document.addEventListener("keypress", function (event) {
  // Нажата клавиша Enter
  if (event.key === "Enter") {
    const activeElement = document.activeElement; // Текущий фокусированный элемент

    // Если фокус в input и он внутри нужной формы
    if (activeElement.tagName === "INPUT") {
      const form = activeElement.closest("form");
      if (form && form.id === "loginForm") {
        // Программно вызываем submit формы
        form.dispatchEvent(new Event("submit"));
      }
    }
  }
});
