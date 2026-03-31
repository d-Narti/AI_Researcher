# System Design — мультиагентная система для автоматизации написания кода

## 1. Обзор системы

Система представляет собой PoC мультиагентной архитектуры, предназначенной для автоматизации этапов научных исследований.

Ключевая идея:
декомпозиция задачи → генерация кода → тестирование → оптимизация → финализация

Целевая аудитория:
- исследователи
- разработчики

## 2. Ключевые архитектурные решения

- Использование LLM как ядра системы
- Оркестрация через единый state (dict)
- Итеративный цикл TEST ↔ OPTIMIZE
- Изоляция агентов
- Выполнение кода через subprocess
- AST-проверка безопасности

## 3. Состав модулей

### Агенты

- DecomposerAgent — декомпозиция задачи
- CodeGeneratorAgent — генерация кода
- TestingAgent — тестирование
- OptimizationAgent — оптимизация
- FormatterAgent — форматирование результата

### Оркестратор

- AgentRouter — управление workflow

## 4. Workflow выполнения

User → AgentRouter → DecomposerAgent → CodeGeneratorAgent → (TEST ↔ OPTIMIZE loop) → FormatterAgent → Result  

Шаги:
1. Декомпозиция
2. Генерация
3. Тестирование
4. Оптимизация (если нужно)
5. Повтор
6. Форматирование

## 5. State / Memory / Context

Единый state:

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

Особенности:

state передается между агентами
нет persistent memory
ограничение контекста LLM

## 6. Retrieval-контур

В текущей версии отсутствует.

Минимально возможная реализация:

- подключение к DecomposerAgent или CodeGeneratorAgent

Источники:
- документация
- примеры кода

## 7. Tool / API интеграции
- LLM (LangChain + OpenAI compatible)
- subprocess (выполнение кода)
- tempfile
- AST
- logging

## 8. Failure modes и guardrails

Ошибки:

- синтаксические ошибки
- runtime ошибки
- неверный вывод
- timeout
- небезопасный код

Guardrails:

- AST-проверка
- blacklist модулей
- timeout 
- ограничение числа итераций
- fallback → TEST

## 9. Ограничения

Latency:

- высокий (LLM + subprocess)

Cost:

- зависит от количества итераций

Reliability:

- зависит от LLM
- повышается через тестирование

## 10. Точки контроля
- после генерации кода
- после тестирования
- при решении router
- при завершении