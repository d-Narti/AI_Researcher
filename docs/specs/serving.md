# Serving / Config спецификация

## 1. Роль

Serving слой отвечает за:
- запуск системы
- конфигурацию
- доступ пользователя


## 2. Компоненты

### Backend

- FastAPI
- обрабатывает запросы
- вызывает AgentRouter

### Frontend

- Streamlit
- UI для ввода задач
- отображение результата


## 3. API (минимально)

POST /solve

Input:
- task: string

Output:
- final_solution
- workflow_metadata


## 4. Конфигурация

Параметры:

- MODEL_API_KEY
- MODEL_NAME
- MAX_STEPS

## 5. Ограничения
- нет очередей
- один процесс

## 6. Failure modes
- недоступен LLM API
- ошибка backend
- таймаут запроса

Fallback:

- возврат ошибки пользователю