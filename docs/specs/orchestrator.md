# Orchestrator (AgentRouter) спецификация

## 1. Роль

AgentRouter управляет:
- порядком выполнения агентов
- логикой переходов между шагами
- условиями остановки pipeline

## 2. Тип оркестратора

**Supervisor pattern** — централизованный оркестратор принимает все решения.

Альтернативы, которые рассматривались:
- **Peer-to-peer** — агенты общаются напрямую; избыточно для линейного workflow PoC
- **Hierarchical agents** — несколько уровней супервизоров; избыточно для 5 агентов

## 3. Основной pipeline

```
1. DECOMPOSE   — DecomposerAgent
2. GENERATE    — CodeGeneratorAgent
3. LOOP:
   a. TEST     — TestingAgent
   b. LLM-решение: TEST | OPTIMIZE | FORMAT
   c. OPTIMIZE — OptimizationAgent (если решение = OPTIMIZE)
4. FORMAT      — FormatterAgent
```

## 4. Принятие решений

Решение принимается через LLM-вызов (`sequence_decision_prompt`).

**Возможные действия:**
- `TEST` — запустить тестирование
- `OPTIMIZE` — оптимизировать код
- `FORMAT` — перейти к финальному форматированию

**Входные параметры для решения:**
- `success_rate` (%)
- `failed_count` / `total_tests`
- `error_types` (SYNTAX_ERROR, RUNTIME_ERROR, LOGIC_ERROR, PERFORMANCE_ISSUE)
- `optimization_cycles` (текущее число итераций)
- `recent_history` (последние 3 шага)

## 5. Правила переходов

| Условие | Действие |
|---------|---------|
| Начало цикла | LLM вызывается первым; промпт инструктирует начинать с TEST |
| `success_rate >= 95%` | FORMAT |
| `success_rate < 95%` и `cycles < max_steps` | OPTIMIZE (по инструкции LLM) |
| `optimization_cycles >= max_steps` | `_should_terminate()` → принудительный FORMAT |
| Повторяющийся паттерн шагов (стагнация) | `_should_terminate()` → принудительный FORMAT |
| Невалидное решение LLM | Fallback → TEST |

## 6. Stop conditions

1. `success_rate >= 0.95` → переход к FORMAT
2. `optimization_cycles >= max_steps` (по умолчанию 8) → принудительный FORMAT
3. Стагнация — если последние 4 шага образуют повторяющийся паттерн (например, `[TEST, OPTIMIZE, TEST, OPTIMIZE]`), pipeline останавливается независимо от LLM
4. LLM вернул `FORMAT` → выход из цикла

## 7. Обработка ошибок

| Ошибка | Реакция |
|--------|---------|
| Невалидный ответ LLM (не TEST/OPTIMIZE/FORMAT) | Fallback = TEST |
| Исключение в агенте | Логирование, продолжение pipeline |
| Пустые тест-кейсы (`total=0`) | `success_rate=0`, роутер переходит к OPTIMIZE |

## 8. История шагов

```python
step_history: list = [
    {"type": "TEST",     "result": {"test_results": {...}}},
    {"type": "OPTIMIZE", "result": {"code": "..."}},
    {"type": "TEST",     "result": {"test_results": {...}}},
]
```

Используется для:
- Передачи контекста роутеру (`recent_history`, последние 3 шага)
- Формирования `workflow_metadata` в финальном результате

## 9. Выход

```python
workflow_metadata = {
    "total_steps":         int,   # общее число шагов
    "optimization_cycles": int,   # число вызовов OptimizationAgent
    "final_success_rate":  float, # success_rate последнего тестирования
    "step_sequence":       list   # последовательность типов шагов
}
```
