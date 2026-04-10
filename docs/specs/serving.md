# Serving / Config спецификация

## 1. Роль

Serving слой отвечает за:
- приём запросов от пользователя
- постановку задач в очередь и получение результатов
- конфигурацию системы

## 2. Компоненты

### Backend — FastAPI

- Обрабатывает HTTP-запросы
- Передаёт задачу в Celery queue
- Отдаёт статус и результат по task_id

### Worker — Celery

- Выполняет pipeline агентов асинхронно
- Поддерживает конкурентное выполнение нескольких задач
- Retry при недоступности LLM (до 3 раз, exponential backoff)

### Broker / Backend — RabbitMQ + Redis

- RabbitMQ: брокер задач (AMQP)
- Redis: хранение результатов и промежуточных состояний Celery

### Frontend — Streamlit

- UI для ввода задач и параметров модели
- Polling статуса задачи (раз в 2–3 секунды)
- Отображение промежуточного прогресса и финального результата

## 3. API

### POST /solve

Принимает задачу, ставит в очередь Celery, возвращает task_id.

**Request:**
```json
{
  "task": "Simulate Lotka-Volterra system...",
  "model_name": "gemma4:e4b",
  "temperature": 0.2,
  "max_steps": 8,
  "base_url": "http://localhost:11434/v1",
  "api_key": "ollama",
  "max_new_tokens": 2048
}
```

**Response:**
```json
{
  "task_id": "celery-uuid-...",
  "status": "pending",
  "message": "Task submitted successfully"
}
```

---

### GET /task/{task_id}

Polling статуса выполнения.

**Response (PROGRESS):**
```json
{
  "task_id": "...",
  "status": "PROGRESS",
  "progress": 55,
  "message": "Step: GENERATE",
  "partial": {
    "decomposition": "...",
    "code": null,
    "test_results": null,
    "final_solution": null
  }
}
```

**Response (SUCCESS):**
```json
{
  "task_id": "...",
  "status": "SUCCESS",
  "result": { ... }
}
```

---

### GET /task/{task_id}/result

Получить финальный результат завершённой задачи.

**Response:**
```json
{
  "final_solution": "...",
  "code": "import ...",
  "success_rate": 1.0,
  "agents_used": [],
  "test_results": { "total": 3, "passed": 3, ... },
  "decomposition": "..."
}
```

---

### GET /health

Health check сервера.

**Response:**
```json
{"status": "healthy"}
```

## 4. Конкурентность

- Celery worker обрабатывает задачи асинхронно
- Число конкурентных задач определяется параметром `--concurrency` при запуске worker
- На Windows: `--pool=solo` (ограничение платформы)
- `worker_prefetch_multiplier=1` — каждый worker берёт по одной задаче (fair scheduling)
- `task_acks_late=True` — задача подтверждается только после завершения (защита от потери при краше)

## 5. Конфигурация

Управляется через переменные окружения (`.env` файл):

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `OPENAI_API_BASE` | `http://localhost:11434/v1` | URL LLM API |
| `OPENAI_API_KEY` | `ollama` | API ключ |
| `CELERY_BROKER_URL` | `amqp://admin:admin@localhost:5672/` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Celery backend |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `LOG_FORMAT` | `text` | Формат логов (`text` / `json`) |

## 6. Timeout

| Контекст | Значение | Конфигурация |
|----------|----------|-------------|
| Celery hard timeout | 600 с | `task_time_limit` в `celery/app.py` |
| Celery soft timeout | 540 с | `task_soft_time_limit` |
| Код subprocess (один тест) | 5 с | `_run_tests()` в `agent_system.py` |
| FastAPI HTTP (нет) | — | Не ограничен (async) |

## 7. Failure modes

| Сценарий | Поведение |
|----------|-----------|
| LLM недоступен | Celery retry × 3 (10s, 20s, 40s backoff) |
| Celery worker упал | Задача остаётся в очереди, переназначается при перезапуске |
| Redis недоступен | Celery не может записать результат; задача зависает |
| RabbitMQ недоступен | POST /solve возвращает 500 |
| Код зависает (infinite loop) | subprocess убивается по таймауту 5с |
| Превышен Celery hard limit | Задача завершается с FAILURE |

## 8. Deployment

### Локальный запуск (текущий режим)

```bash
# 1. Инфраструктура (RabbitMQ + Redis)
docker compose up rabbitmq redis -d

# 2. Celery worker (отдельный терминал, --pool=solo для Windows)
celery -A src.celery.app worker --loglevel=info --pool=solo

# 3. FastAPI
python api.py

# 4. Streamlit UI
streamlit run streamlit_app.py
```

### Docker (все сервисы)

```bash
docker compose up --build
```

`docker-compose.yml` содержит: `rabbitmq`, `redis`, `celery_worker`, `api`, `streamlit`, `flower`.

### Environments

| Среда | LLM | Broker | Описание |
|-------|-----|--------|----------|
| local | Ollama (`localhost:11434`) | Docker compose | Разработка и демо |
| production | Remote API | Managed RabbitMQ + Redis | Развёртывание |

## 9. Health check

`GET /health` реализован в `api.py`. Проверяет только доступность FastAPI-процесса.

Для полной проверки инфраструктуры:
- RabbitMQ: `http://localhost:15672` (management UI, admin/admin)
- Redis: `redis-cli ping`
- Celery worker: `celery -A src.celery.app inspect ping`
