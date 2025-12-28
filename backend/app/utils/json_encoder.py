import json
from datetime import datetime, date 
from decimal import Decimal 
from uuid import UUID 
from typing import Any 
import enum 


class CustomJSONEncoder(json.JSONEncoder):
  """
  Кастомный JSON encoder для сериализации Python объектов
  Использование: json.dumps(data, cls=CustomJSONEncoder)
  """

  def default(self, obj: Any) -> Any:
    # 1. Дата и время
    if isinstance(obj, (datetime, date)):
      return obj.isoformat()
    
    # 2. Decimal (для денег)
    if isinstance(obj, Decimal):
      return float(obj)
    
    # 3. UUID 
    if isinstance(obj, UUID):
      return str(obj)
    
    # 4. Enum
    if isinstance(obj, enum.Enum):
      return obj.value

    # 5. Pydantic модель
    if hasattr(obj, "model_dump"):
      return obj.model_dump()
    
    # 6. SQLAlchemy модели
    if hasattr(obj, "__dict__"):
      return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    
    return super().default(obj)
  

# Упрощенная функция для удобства
def json_dumps(data: Any, **kwargs) -> str:
  """Сериализация с кастомный encoder"""

  kwargs.setdefault("ensure_ascii", False)    # Поддержка кириллицы
  kwargs.setdefault("separators", (",", ":"))
  return json.dumps(data, cls=CustomJSONEncoder, **kwargs)