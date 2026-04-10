# System Design — мультиагентная система для автоматизации написания кода

## 1. Обзор системы

Система представляет собой PoC мультиагентной архитектуры, предназначенной для автоматизации этапов научных исследований.

Ключевая идея:
декомпозиция задачи → генерация кода → тестирование → оптимизация → финализация

Целевая аудитория:
- исследователи
- разработчики

## 2. Ключевые архитектурные решения

1. Использование LLM как ядра системы
2. Оркестрация через единый state (dict)
3. Итеративный цикл TEST ↔ OPTIMIZE
4. Изоляция агентов
5. Выполнение кода через subprocess
6. AST-проверка безопасности

## 2.1 Trade-offs и альтернативы

### Почему единый state (dict), а не graph?

| | Dict | Graph (LangGraph) |
|---|---|---|
| Сложность | Низкая | Высокая |
| Скорость PoC | Быстро | Медленно |
| Масштабируемость | Плохая | Хорошая |
| Явные зависимости | Нет | Да |
| Дебаг | Просто | Сложнее |

**Выбор: dict.** Для PoC, мне показалось достаточно. При масштабировании — переход на LangGraph.

---

### Почему supervisor (AgentRouter), а не peer-to-peer?

| | Supervisor | Peer-to-peer |
|---|---|---|
| Контроль | Централизованный | Распределённый |
| Дебаг | Просто (один роутер) | Сложно (N агентов) |
| Гибкость | Ограничена | Высокая |
| Реализация | Простая | Комплексная |
| Bottleneck | Есть (роутер) | Нет |

**Выбор: supervisor.** Для PoC с линейным workflow оптимален. Альтернативы (hierarchical agents, peer-to-peer) избыточны.

---

### Почему Celery + RabbitMQ + Redis, а не синхронный FastAPI?

| | Sync FastAPI | Celery + queue |
|---|---|---|
| Latency UI | Блокирует на 40–70с | Не блокирует |
| Конкурентность | 1 запрос | N параллельных |
| Retry при ошибках | Нет | Есть (exponential backoff) |
| Сложность | Низкая | Средняя |

**Выбор: Celery.** Workflow занимает 40–70с — синхронный HTTP неприемлем для UX.

---

### Почему subprocess для выполнения кода, а не exec()?

`exec()` выполняет код в пространстве имён текущего процесса — опасно. `subprocess` изолирует выполнение: отдельный процесс, отдельная память, независимый таймаут, управляемый stdin/stdout.

## 3. Состав модулей

### Агенты

- **DecomposerAgent** — декомпозиция задачи в пошаговый план
- **CodeGeneratorAgent** — генерация Python-кода по задаче и плану
- **TestingAgent** — генерация тест-кейсов и запуск кода через subprocess
- **OptimizationAgent** — оптимизация кода на основе результатов тестов
- **FormatterAgent** — форматирование финального ответа для пользователя

### Оркестратор

- **AgentRouter** — управление workflow, принятие решений через LLM (TEST / OPTIMIZE / FORMAT)

### Serving слой

- **FastAPI** — REST API (POST /solve, GET /task/{id}, GET /health)
- **Celery worker** — асинхронное выполнение pipeline
- **RabbitMQ** — брокер задач
- **Redis** — backend для хранения результатов Celery

## 3.1 Интерфейсы агентов

### DecomposerAgent

Input:
- `task: str` — задача в свободной форме

Output (обновляет state):
- `decomposition: str` — пошаговый план решения в текстовом формате

---

### CodeGeneratorAgent

Input (из state):
- `task: str`
- `decomposition: str`

Output (обновляет state):
- `code: str` — Python-код, читающий из stdin и пишущий в stdout

---

### TestingAgent

Input (из state):
- `task: str`
- `code: str`

Output (обновляет state):
- `generated_tests: list[dict]` — список `{"input": str, "output": str}`
- `test_results: dict` — `{total, passed, failed, errors, test_details, success_rate}`

---

### OptimizationAgent

Input (из state):
- `task: str`
- `code: str`
- `test_results: dict`

Output (обновляет state):
- `code: str` — улучшенный Python-код

---

### FormatterAgent

Input (из state):
- `task: str`
- `code: str`
- `test_results: dict`
- `generated_tests: list`

Output (обновляет state):
- `final_solution: str` — финальный ответ в формате Markdown

---

### AgentRouter

Input:
- `task: str`

Output:
- `final_solution: str`
- `workflow_metadata: dict` — `{total_steps, optimization_cycles, final_success_rate, step_sequence}`

## 4. Workflow выполнения

```
User → POST /solve → Celery queue
  → AgentRouter.execute_workflow()
      1. DecomposerAgent    (всегда)
      2. CodeGeneratorAgent (всегда)
      3. LOOP (до max_steps):
           TestingAgent
           LLM-роутер решает: TEST | OPTIMIZE | FORMAT
           OptimizationAgent (если OPTIMIZE)
      4. FormatterAgent
  → GET /task/{id} (polling)
  → Результат
```

## 5. State / Memory / Context

Единый state (передаётся между агентами):

```python
{
  "task": str,
  "decomposition": str,
  "code": str,
  "generated_tests": list,
  "test_results": dict,
  "final_solution": str,
  "workflow_metadata": dict
}
```

**Нет persistent memory** — каждый запрос независим. Обоснование: PoC-задачи самодостаточны, не требуют истории между сессиями.

### Управление context window

Проблема: после нескольких итераций оптимизации state + история шагов может превысить лимит токенов модели.

Реализованные стратегии:

**1. Разделение state и prompt** — в каждый промпт передаются только необходимые поля (task + текущий code + последние test_results). История итераций не передаётся.

**2. Sliding window** — роутер хранит только последние 3 шага (`_get_recent_history(step_history, max_steps=3)`).

**3. Умная обрезка** (`_truncate_content`) — OptimizationAgent обрезает код и тест-репорт до лимита, сохраняя критические секции (def, class, Error).

**Fallback при overflow:**
- Контент усекается до `max_chars//2` с сохранением начала и конца
- При SyntaxError в коде — следующая итерация OPTIMIZE

## 6. Retrieval-контур

В текущей версии **отсутствует**.

Обоснование: задачи решаются по описанию, не требуют внешних знаний или документации.

Минимально возможная реализация (будущее):
- Подключение к DecomposerAgent или CodeGeneratorAgent
- Источники: Stack Overflow, документация библиотек, примеры кода

## 7. Tool / API интеграции

| Интеграция | Роль | Таймаут |
|-----------|------|---------|
| LangChain + OpenAI-compatible API | LLM-вызовы | Celery task limit: 600с |
| subprocess | Выполнение сгенерированного кода | 5с на тест-кейс |
| tempfile | Изоляция кода во временных файлах | — |
| AST | Статическая проверка безопасности кода | < 100 мс |
| logging (JSON/text) | Структурированные логи | — |

## 8. Failure modes и guardrails

| Ошибка | Детект | Реакция |
|--------|--------|---------|
| Синтаксические ошибки | `ast.parse()` в `_extract_code` | Возврат raw-ответа LLM |
| Runtime-ошибки | `subprocess.returncode != 0` | Фиксация в `test_results.errors` |
| Таймаут выполнения кода | `subprocess.TimeoutExpired` | Тест помечается как failed |
| Небезопасные импорты | AST-анализ (`_check_import_safety`) | Выполнение блокируется |
| Недоступность LLM | `openai.APIConnectionError`, `ConnectionError` | Celery retry × 3 с exponential backoff (10s, 20s, 40s) |
| Пустой парсинг тестов | `_parse_tests` возвращает `[]` | `total=0, success_rate=0.0`; роутер переходит к OPTIMIZE |
| Превышение max_steps | Счётчик итераций | Принудительный переход к FORMAT |

## 9. Ограничения

**Latency:**

| Этап | Оценка |
|------|--------|
| DecomposerAgent | 3–7 с |
| CodeGeneratorAgent | 10–20 с |
| TestingAgent (gen + run) | 5–15 с |
| OptimizationAgent (1 итерация) | 10–20 с |
| FormatterAgent | 3–7 с |
| **Full pipeline (1–2 итерации)** | **40–70 с** |

**Cost (remote API):**
- ~4–8 LLM-вызовов на задачу
- ~$0.002–0.10 в зависимости от модели и числа итераций

**Reliability:**
- Зависит от качества LLM
- Повышается через итеративное тестирование и retry-логику

## 10. Точки контроля

- После генерации кода (CodeGeneratorAgent)
- После каждого тестирования (TestingAgent)
- При каждом решении роутера (TEST / OPTIMIZE / FORMAT)
- При завершении pipeline (FormatterAgent)

## SLO / SLA

| Метрика | Целевое значение |
|---------|-----------------|
| p95 latency (full pipeline) | ≤ 70 с |
| Success rate (код выполнился без system-ошибок) | ≥ 80% |
| Cost per request (remote API) | ≤ $0.10 |
| Max optimization iterations | ≤ 8 (max_steps, по умолчанию) |
| LLM retry attempts | 3 (exponential backoff) |
| Code execution timeout | 5 с на тест-кейс |
| Celery task hard limit | 600 с |
