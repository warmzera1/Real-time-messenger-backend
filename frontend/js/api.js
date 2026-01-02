// Базовый URL локального сервера
const API_URL = "http://localhost:8000";

// Кеш для CSRF токена для повторного использования
let csrfTokenCache = null;

// Функция получения JWT токена: сначала из localStorage, потом из кук
function getJWTToken() {
  // 1. Основное хранилище - localStorage
  const token = localStorage.getItem("access_token");
  if (token) {
    console.log("JWT токен найден в localStorage");
    return token;
  }

  // 2. Резерв: проверяем куки
  const cookies = document.cookie.split(";");
  for (let cookie of cookies) {
    const [name, value] = cookie.trim().split("=");
    if (name === "access_token" && value) {
      console.log("JWT токен найден в куках");
      localStorage.setItem("access_token", value); // Кэшируем в localStorage
      return value;
    }
  }

  console.log("JWT токен не найден");
  return null;
}

// Вспомогательная функция: извлекает значение csrftoken из кук с кэшированием
function getCSRFToken() {
  // Используем кэш для оптимизации
  if (csrfTokenCache) return csrfTokenCache;

  const cookies = document.cookie.split(";");
  for (let cookie of cookies) {
    const [name, value] = cookie.trim().split("=");
    if (name === "csrftoken") {
      csrfTokenCache = value; // Сохраняем в кэш
      return value;
    }
  }
  return ""; // Не найден
}

// Основная асинхронная функция для API-запросов
export async function apiRequest(endpoint, method = "GET", data = null) {
  // Базовые заголовки
  const headers = {
    "Content-Type": "application/json",
    "X-CSRFToken": getCSRFToken(), // Для защиты от CSRF
  };

  // Добавляем JWT токен в Authorization, если есть
  const jwtToken = getJWTToken();
  if (jwtToken) {
    headers["Authorization"] = `Bearer ${jwtToken}`;
  }

  // Настройки fetch
  const options = {
    method,
    headers,
    credentials: "include", // Отправляем/принимаем куки (сессии, httpOnly)
  };

  // Если переданы данные, сериализуем их в JSON и добавляем в тело
  if (data) {
    options.body = JSON.stringify(data);
  }

  // Логируем запрос (для отладки)
  console.log(`API Request: ${method} ${endpoint}`, data ? "[DATA]" : "");

  try {
    // Выполняем fetch-запрос
    const response = await fetch(`${API_URL}${endpoint}`, options);

    // Логируем ответ (для отладки)
    console.log(`API Response: ${response.status} ${response.statusText}`);

    // Парсим тело: JSON или текст
    let responseData;
    const contentType = response.headers.get("content-type");

    if (contentType && contentType.includes("application/json")) {
      responseData = await response.json();
    } else {
      responseData = await response.text();
    }

    // Обрабатываем HTTP-ошибки
    if (!response.ok) {
      const error = new Error(
        responseData.detail || `HTTP ошибка! status: ${response.status}`
      );
      error.status = response.status;
      error.response = responseData;
      throw error;
    }

    // Возвращаем данные
    return responseData; // Успешный ответ
  } catch (error) {
    console.error("API Request ошибка:", error);

    // Специальная обработка 401 (истек/невалидный токен)
    if (error.status === 401) {
      console.log("Очищаю токен из-за 401 ошибки");
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");

      // Редиректим на страницу логина (если не там уже)
      if (!window.location.pathname.includes("auth.html")) {
        window.location.href = "auth.html";
      }
    }

    throw error; // Пробрасываем данные
  }
}

// Утилиты для работы с токенами
export const tokenManager = {
  // Сохраняем токены
  setTokens: (accessToken, refreshToken) => {
    if (accessToken) {
      localStorage.setItem("access_token", accessToken);
      // Также устанавливаем куку для совместимости
      document.cookie = `access_token=${accessToken}; path=/; max-age=86400`;
    }
    if (refreshToken) {
      localStorage.setItem("refresh_token", refreshToken);
      document.cookie = `refresh_token=${refreshToken}; path=/; max-age=604800`; // 7 дней
    }
  },

  // Полная очистка токенов (выход)
  clearTokens: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    // Очищаем куки
    document.cookie =
      "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    document.cookie =
      "refresh_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  },

  // Проверка наличия access-токена
  hasToken: () => {
    return !!localStorage.getItem("access_token");
  },
};
