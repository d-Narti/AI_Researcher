# Tools / API спецификация

## 1. Общая роль

Tools слой отвечает за:
- взаимодействие с LLM
- безопасное выполнение сгенерированного кода
- статическую проверку безопасности

## 2. LLM (через LangChain)

### Контракт

```
Input:  ChatPromptTemplate + переменные (task, code, test_results, ...)
Output: str — ответ модели
```

### Использование

| Агент | Промпт |
|-------|--------|
| DecomposerAgent | Декомпозиция задачи в план |
| CodeGeneratorAgent | Генерация Python-кода |
| TestingAgent | Генерация тест-кейсов в формате JSON |
| OptimizationAgent | Оптимизация кода по ошибкам |
| AgentRouter | Принятие решений (TEST / OPTIMIZE / FORMAT) |
| FormatterAgent | Форматирование финального ответа |

### Конфигурация

- `openai_api_base`: URL LLM API (по умолчанию `http://localhost:11434/v1`)
- `openai_api_key`: API ключ (по умолчанию `ollama`)
- `model`: имя модели (по умолчанию `gemma4:e4b`)
- `temperature`: 0.2
- `max_tokens`: 2048

### Ограничения

- Latency зависит от модели и размера промпта (5–20с на вызов)
- Нестабильные ответы (не соответствуют ожидаемому формату) — обрабатываются парсерами
- Ограничение context window — управляется через truncation и sliding window

### Retry при недоступности

При `ConnectionError`, `APIConnectionError`, `APITimeoutError` — Celery retry × 3 с exponential backoff (10с, 20с, 40с).

## 3. Subprocess (выполнение кода)

### Контракт

```
Input:
  - python_file: str (путь к временному файлу)
  - stdin: str (тестовый ввод)
  - timeout: 5с

Output:
  - stdout: str
  - stderr: str
  - returncode: int
```

### Реализация

```python
subprocess.run(
    [sys.executable, temp_file_path],
    input=test_input,
    capture_output=True,
    text=True,
    encoding='utf-8',
    timeout=5
)
```

### Side effects

- Создаётся временный `.py` файл через `tempfile.NamedTemporaryFile`
- Файл удаляется после выполнения всех тест-кейсов
- Запускается дочерний процесс (изолирован от основного процесса)

### Ограничения

- Таймаут: 5с на тест-кейс
- Только стандартные библиотеки Python (ограничение промпта CodeGeneratorAgent)
- Одиночный файл (нет поддержки multi-file проектов)

## 4. AST-анализ (безопасность)

### Запрещённые модули

```python
forbidden_modules = {
    "subprocess", "socket", "requests", "urllib", "http",
    "ftplib", "paramiko", "psutil", "ctypes",
    "multiprocessing", "threading", "signal",
    "webbrowser", "pexpect", "shutil"
}
```

### Запрещённые вызовы

- `os.system`, `os.popen`, `os.spawn*`
- `subprocess.Popen`, `subprocess.run`, `subprocess.call`
- `socket.*` (любые)
- `__import__()` (динамические импорты)

### Поведение

- При обнаружении → выполнение блокируется, `test_results.errors` содержит причину
- Проверка выполняется до `subprocess.run`, занимает < 100 мс
- Синтаксические ошибки в коде → `"Syntax error before safety check"`

## 5. Tempfile

- Создаётся `NamedTemporaryFile(suffix='.py', encoding='utf-8', delete=False)`
- Код записывается в UTF-8
- Файл удаляется в блоке `finally` после выполнения тестов
- `delete=False` нужен, чтобы файл был доступен subprocess после закрытия дескриптора

## 6. Guardrails

| Guardrail | Реализация |
|-----------|-----------|
| Ограничение времени выполнения | `subprocess timeout=5s` |
| Проверка импортов | AST blocklist |
| Ограничение числа тестов | Максимум 5–10 тест-кейсов (промпт) |
| Очистка временных файлов | `os.remove(temp_file_path)` |
| Ограничение числа итераций | `max_steps` (по умолчанию 8) |

## 7. Failure modes

| Ошибка | Поведение |
|--------|-----------|
| Зависание кода (infinite loop) | subprocess убивается по таймауту; тест = failed |
| Небезопасный импорт | AST-блокировка; ошибка в test_results |
| Некорректный stdout | Сравнение `received.strip() != expected.strip()` → failed |
| Ошибка записи tempfile | `test_results.errors = "Code generation failed"` |
| LLM не вернул корректный JSON для тестов | `_parse_tests` возвращает `[]`; `total=0` |
