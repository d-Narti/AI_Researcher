# Orchestrator (AgentRouter) спецификация

## 1. Роль

AgentRouter управляет:
- порядком выполнения агентов
- логикой переходов
- остановкой процесса

## 2. Основной pipeline

1. DECOMPOSE
2. GENERATE
3. LOOP:
   - TEST
   - OPTIMIZE
4. FORMAT

## 3. Принятие решений

Решение принимается через LLM:

Возможные действия:
- TEST
- OPTIMIZE
- FORMAT

## 4. Входные параметры для решения

- success_rate
- количество ошибок
- типы ошибок
- история шагов
- количество итераций

## 5. Правила

- сначала всегда TEST
- если success_rate < 95% → OPTIMIZE
- если success_rate ≥ 95% → FORMAT
- ограничение числа итераций

## 6. Stop conditions

- success_rate ≥ 0.95
- достигнут max_steps
- обнаружена стагнация

## 7. Обработка ошибок

- при ошибке решения → fallback = TEST
- при исключении → логирование и продолжение


## 8. История шагов

Хранится:

```python
[
  {"type": "TEST", "result": ...},
  {"type": "OPTIMIZE", "result": ...}
]
```
Используется для:

- анализа
- предотвращения циклов


## 9. Выход

Добавляется:

```python
workflow_metadata = {
  "total_steps": int,
  "optimization_cycles": int,
  "final_success_rate": float,
  "step_sequence": list
}
```