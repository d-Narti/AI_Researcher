# Observability / Evals спецификация

## 1. Роль

Обеспечивает:
- мониторинг выполнения pipeline
- структурированное логирование
- оценку качества системы

## 2. Логирование

### Формат

Поддерживаются два режима (управляется через `LOG_FORMAT` env var):

**text** (по умолчанию, для локальной разработки):
```
2024-01-15 12:00:01 | INFO | src.celery.tasks | Task abc-123 completed with success_rate=1.00
```

**json** (для production / log aggregation):
```json
{
  "timestamp": "2024-01-15T12:00:01.123Z",
  "level": "INFO",
  "logger": "src.celery.tasks",
  "message": "Task abc-123 completed with success_rate=1.00",
  "task_id": "abc-123",
  "step": "FORMAT"
}
```

Включить JSON логи: `LOG_FORMAT=json` в `.env` или переменной окружения.

### Что логируется

| Событие | Уровень | Поля |
|---------|---------|------|
| Задача принята в очередь | INFO | task_id, model_name, max_steps |
| Инициализация агентов | DEBUG | model, base_url |
| Шаг агента начат | DEBUG | step type |
| Тестирование завершено | INFO | task_id, success_rate, total, passed, failed |
| Задача завершена | INFO | task_id, success_rate |
| LLM недоступен (retry) | WARNING | attempt, countdown, error |
| Задача провалена | ERROR | task_id, error, traceback |
| AST-блокировка кода | WARNING | forbidden_module |

### Уровни логирования

Управляется через `LOG_LEVEL` env var (по умолчанию `INFO`).

## 3. Метрики

### Основные (из логов)

| Метрика | Источник |
|---------|---------|
| `success_rate` | TestingAgent, финальный результат |
| Число итераций оптимизации | `workflow_metadata.optimization_cycles` |
| Время выполнения pipeline | Celery task duration |
| Доля ошибок | `status == 'failed'` в результатах |

### LLM метрики (future)

Не реализованы в текущей версии. Планируемые:
- `prompt_tokens` / `completion_tokens` — токены на вызов
- `total_tokens` — суммарно на pipeline
- `cost_per_request` — стоимость (при remote API)

Для реализации потребуется LangChain callback (`TokenUsageTracker`).

## 4. Трейсинг

**Текущая реализация:**
- Последовательность шагов логируется через Celery task state (`PROGRESS` events)
- Каждый шаг содержит тип (`DECOMPOSE`, `GENERATE`, `TEST`, `OPTIMIZE`, `FORMAT`) и прогресс (0–100%)
- Промежуточные результаты доступны через `GET /task/{id}` (поле `partial`)

**Будущая интеграция:**
- **LangSmith** — нативный трейсинг LangChain-цепочек (промпты, latency, токены)
- **LangFuse** — open-source альтернатива LangSmith
- **OpenTelemetry** — стандартизированный трейсинг для инфраструктурной интеграции

## 5. Evals

### Автоматические

| Проверка | Метрика | Порог |
|----------|---------|-------|
| Корректность кода | `success_rate` | ≥ 0.95 для FORMAT |
| Pipeline завершился | `status == completed` | — |
| Код валиден синтаксически | `ast.parse()` | — |

### Ручные (PoC)

- Выборочный просмотр 5–10 запросов в неделю
- Оценка качества декомпозиции (структурированность, полнота плана)
- Оценка качества кода (стиль, корректность алгоритма)

## 6. Точки контроля

- После генерации кода (CodeGeneratorAgent)
- После каждого тестирования (TestingAgent)
- После каждой оптимизации (OptimizationAgent)
- Финальный результат (FormatterAgent)

## 7. Health check

`GET /health` → `{"status": "healthy"}`

Проверяет доступность FastAPI-сервера. Не проверяет Celery worker или LLM.

## 8. Ограничения текущей версии

- Нет внешних систем мониторинга (Prometheus, Grafana)
- Нет алертов при деградации качества
- Нет трейсинга LLM-вызовов (только текстовые логи)
- Нет метрик токенов и стоимости
- Только локальные логи (stdout)
