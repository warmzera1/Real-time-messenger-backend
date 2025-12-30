// Базовый URL сервера (локальный бэкенд на порту 8000)
const API_URL = "http://localhost:8000";

// Экспортируемая асинхронная функция для выполнения запросов к API
// endpoint - путь API (например, '/users'), method - HTTP-метод, data - тело запроса
export async function apiRequest(endpoint, method = "GET", data = null) {
  // Объект с настройками fetch-запроса
  const options = {
    method,
    headers: {
      "Content-Type": "application/json", // Отправляем JSON
      "X-CSRFToken": getCSRFToken(), // Добавляем CSRF токен для защиты
    },
    credentials: "include", // Автотически отправляем и получаем куки
  };

  // Если переданные данные, сериализуем их в JSON и добавляем в тело
  if (data) {
    options.body = JSON.stringify(data);
  }

  // Выполняем fetch-запрос к полному URL (API_URL + endpoint)
  const response = await fetch(`${API_URL}${endpoint}`, options);

  // Если сервер вернул ошибку - бросаем исключение
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  // Парсим и возвращаем JSON-ответ от сервера
  return response.json();
}

// Вспомогательная функция: извлекает значение csrftoken из кук браузера
function getCSRFToken() {
  // Разбиваем строку document.cookie на отдельные куки
  const cookies = document.cookie.split(";");

  // Перебираем каждую куку
  for (let cookie of cookies) {
    // Убираем пробелы и разделяем на имя=значение
    const [name, value] = cookie.trim().split("=");

    // Если нашли куку с именем 'csrftoken', возвращаем значение
    if (name === "csrftoken") {
      return value;
    }
  }
  // Если токен не найден, возвращаем пустую строку
  return "";
}
