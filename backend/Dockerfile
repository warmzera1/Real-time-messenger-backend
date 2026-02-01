FROM python:3.11-slim

RUN pip install poetry 

WORKDIR /app 

RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock /app/

RUN ls -la /app && poetry install --no-root --no-interaction --no-ansi 

COPY . .

CMD ["/app/entrypoint.sh"]