from sqlalchemy.ext.declarative import declarative_base 


# Базовый класс для ВСЕХ моделей
# Все модели наследуем от него, получают общие методы и метаданные
Base = declarative_base()

