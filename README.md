# Hitalent Organization API

JSON API для управления организационной структурой: подразделения, дерево подразделений и сотрудники.

## Запуск

Требования:

- Docker Desktop или Docker Engine
- свободные порты `5432` и `8000`

Запуск приложения и PostgreSQL:

```bash
docker compose up --build
```

API будет доступен по адресу:

```text
http://localhost:8000
```

При запуске контейнер `web` автоматически применяет Django migrations.

## Локальный запуск без Docker для Django

Если PostgreSQL уже запущен через Docker:

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe myapi\manage.py migrate
.\.venv\Scripts\python.exe myapi\manage.py runserver
```

По умолчанию локальные настройки используют:

```text
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=hitalent_db
POSTGRES_USER=hitalent_user
POSTGRES_PASSWORD=hitalent_password
```

В Docker Compose для приложения используется `POSTGRES_HOST=db`, потому что Django и PostgreSQL находятся в разных контейнерах одной compose-сети.

## API

Создать подразделение:

```http
POST /departments/
Content-Type: application/json

{
  "name": "Backend",
  "parent_id": null
}
```

Создать сотрудника:

```http
POST /departments/{id}/employees/
Content-Type: application/json

{
  "full_name": "Ivan Petrov",
  "position": "Developer",
  "hired_at": "2026-05-28"
}
```

Получить подразделение с деревом:

```http
GET /departments/{id}?depth=2&include_employees=true
```

Обновить подразделение:

```http
PATCH /departments/{id}
Content-Type: application/json

{
  "name": "Platform",
  "parent_id": null
}
```

Удалить подразделение каскадно:

```http
DELETE /departments/{id}?mode=cascade
```

Удалить подразделение с переносом сотрудников:

```http
DELETE /departments/{id}?mode=reassign&reassign_to_department_id={target_id}
```

## Проверки

```bash
.\.venv\Scripts\python.exe myapi\manage.py test organization
```

Покрыта базовая бизнес-логика: создание подразделений и сотрудников, получение дерева, запрет циклов, удаление с переносом сотрудников.
