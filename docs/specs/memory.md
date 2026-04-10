# Memory / Context Spec

## 1. Тип памяти

В текущей версии используется исключительно **in-memory state** (Python dict), передаваемый между агентами в рамках одного Celery-задания.

**Persistent memory отсутствует.**

Обоснование:
- PoC-задачи самодостаточны — каждая задача решается независимо
- Нет long-term задач, требующих истории между сессиями
- Упрощение архитектуры для PoC

## 2. Структура state

```python
state: dict = {
    "task": str,                  # исходная задача пользователя
    "decomposition": str,         # пошаговый план от DecomposerAgent
    "code": str,                  # текущий Python-код
    "generated_tests": list,      # список {"input": str, "output": str}
    "test_results": dict,         # {total, passed, failed, errors, test_details, success_rate}
    "final_solution": str,        # финальный ответ от FormatterAgent
    "workflow_metadata": dict     # {total_steps, optimization_cycles, final_success_rate, step_sequence}
}
```

## 3. Memory policy

| Свойство | Значение |
|----------|----------|
| Тип | In-memory dict (per-request) |
| Персистентность | Нет (только в рамках Celery task) |
| Shared state между запросами | Нет |
| История итераций | Только последние 3 шага (sliding window) |
| Доступность после завершения | Через Redis (Celery result backend, TTL по умолчанию) |

## 4. Context budget

Проблема: state + промпты могут превысить context window LLM.

### Стратегии управления

**1. Selective passing** — каждый агент получает только нужные поля:

| Агент | Получает из state |
|-------|------------------|
| DecomposerAgent | `task` |
| CodeGeneratorAgent | `task`, `decomposition` |
| TestingAgent | `task`, `code` |
| OptimizationAgent | `task`, `code`, `test_results` |
| FormatterAgent | `task`, `code`, `test_results`, `generated_tests` |

**2. Sliding window** — роутер хранит только последние 3 шага истории (`_get_recent_history`).

**3. Smart truncation** — OptimizationAgent обрезает код (лимит 15 000 символов) и тест-репорт (лимит 5 000 символов) с сохранением критических секций.

### Что происходит при overflow

1. `_truncate_content` усекает контент до `max_chars // 2` с начала и конца
2. Сохраняются критические части: определения функций, сообщения об ошибках
3. В промпт добавляется маркер `...TRUNCATED...`
4. Если и после этого LLM не отвечает корректно — следующий цикл TEST/OPTIMIZE

## 5. Session state

Прогресс задачи хранится в Redis через Celery:
- Состояние: `PENDING → PROGRESS → SUCCESS / FAILURE`
- Промежуточные обновления через `self.update_state(state='PROGRESS', meta={...})`
- Доступен через `GET /task/{task_id}` (polling)
- TTL результата: определяется конфигурацией Redis (по умолчанию без истечения)

## 6. Будущее

- **Vector DB** (FAISS / Chroma) для RAG: поиск по документации и примерам кода
- **Session memory**: сохранение успешных решений для повторного использования
- **Prompt caching**: кеширование системных промптов для снижения стоимости
