// Базовый URL бэкенда
const API_URL = "http://localhost:8000";

// Возвращает текущий JWT-токен из localStorage
export function getJWTToken() {
  return localStorage.getItem("access_token");
}

// Сохраняет accessToken в localStorage
export function setTokens(accessToken) {
  if (accessToken) {
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refresh);
  }
}

// Удаляет токен из localStorage (выход из системы)
export function clearTokens() {
  localStorage.removeItem("access_token");
}

// Проверка: есть ли вообще сохраненный токен
export function hasToken() {
  return !!getJWTToken(); // Превращает в True/False
}

// Функция для ВСЕХ запросов к API
export async function apiRequest(endpoint, method = "GET", data = null) {
  // Базовые заголовки
  const headers = {
    "Content-Type": "application/json",
  };

  // Если есть токен - добавляем его в заголовок Authorization
  const token = getJWTToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Формируем объект настроек для fetch
  const options = {
    method,
    headers,
  };

  // Если передали данные (POST/PUT/PATCH) - добавляем тело запроса
  if (data) {
    options.body = JSON.stringify(data);
  }

  // Отладка
  console.log(`API: ${method} ${endpoint}`);

  // Запрос
  const response = await fetch(`${API_URL}${endpoint}`, options);

  // Если статус не 2хх - ошибка
  if (!response.ok) {
    // Пытаемся прочитать сообщение об ошибке от сервера
    const errorData = await response.json().catch(() => ({}));

    const error = new Error(errorData.detail || `HTTP ${response.status}`);
    error.status = response.status;

    throw error; // Выбрасываем - catch
  }

  // Все ок - возвращаем распарсенные данные
  return await response.json();
}
