"""
Multi-Agent AI System for Automated Programming Task Solving

This module implements a sophisticated multi-agent system that can automatically
solve programming tasks through a coordinated workflow of specialized agents.
Each agent has a specific role in the problem-solving process:

1. DecomposerAgent: Breaks down complex tasks into manageable steps
2. CodeGeneratorAgent: Generates Python code solutions
3. TestingAgent: Creates and executes comprehensive test cases
4. OptimizationAgent: Improves code performance and correctness
5. FormatterAgent: Formats the final solution presentation
6. AgentRouter: Orchestrates the workflow and agent selection

The system uses LangChain for LLM integration and supports both custom models
and standard OpenAI models.

Usage:
    from src.agent_system import AgentRouter
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="gpt-4")
    router = AgentRouter(llm)
    result = router.execute_workflow("Your programming task here")
"""
from langchain_openai import ChatOpenAI 
from langchain_classic.chains import LLMChain
from langchain_classic.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, PrivateAttr
from typing import Dict, List, Any, Optional
import ast
import re
import subprocess
import sys
import os
import tempfile
import warnings
from src.logging_setup import setup_logging

logger = setup_logging(__name__)

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")


class BaseAgent(BaseModel):
    """
    Abstract base class for all agents in the multi-agent system.
    
    This class defines the common interface and structure that all agents must implement.
    It uses Pydantic for data validation and provides a consistent execution pattern
    across all agent types.
    
    Attributes:
        name (str): The human-readable name of the agent
        description (str): A brief description of the agent's purpose
        llm (Any): The language model instance used by the agent
        _prompt (Any): Private attribute storing the prompt template
        
    Example:
        class MyAgent(BaseAgent):
            def execute(self, state: Dict) -> Dict:
                # Implementation here
                return {"result": "value"}
    """
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    llm: Any = Field(exclude=True, description="Language model instance")
    _prompt: Any = PrivateAttr()
    
    class Config:
        """Pydantic configuration for BaseAgent."""
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's main functionality.
        
        This method must be implemented by all concrete agent classes.
        It defines the core logic for how each agent processes the workflow state.
        
        Args:
            state (Dict[str, Any]): The current state of the workflow containing
                                  task information and results from previous agents
        
        Returns:
            Dict[str, Any]: Updated state with the agent's contributions
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement the execute method")


class FormatterAgent(BaseAgent):
    """
    Agent responsible for formatting the final solution output.
    
    This agent takes the task, generated code, and test results to create
    a well-formatted final solution that presents the results in a clear,
    structured manner suitable for presentation to users.
    
    The FormatterAgent is typically the final step in the workflow, ensuring
    that all previous work is presented in a professional, readable format.
    """
    
    def __init__(self, llm: Any):
        """
        Initialize the FormatterAgent with a language model.
        
        Args:
            llm (Any): The language model instance to use for formatting
        """
        super().__init__(
            name="Solution Formatter",
            description="Formats final solution for task presentation",
            llm=llm
        )
        
        # Create the formatting prompt template
        self._prompt = ChatPromptTemplate.from_messages([
            ("human", 
             "You are a technical writer tasked with creating a clear, professional "
             "solution presentation.\n\n"
             "Task: {task}\n\n"
             "Generated Code:\n{code}\n\n"
             "Test Results:\n{generated_tests}\n{test_results}\n\n"
             "Please format this into a comprehensive solution that includes:\n"
             "1. Problem summary\n"
             "2. Solution approach\n"
             "3. Code explanation\n"
             "4. Test results summary\n"
             "5. Final answer\n\n"
             "Make it clear, professional, and easy to understand, include real Test Results and Generated Code.\n\n"
             "Return final presentation on original language of the task."
             )
        ])
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format the final solution based on task, code, and test results.
        
        Args:
            state (Dict[str, Any]): Current workflow state containing:
                - task: The original programming task
                - code: The generated/optimized code (optional)
                - test_results: Results from testing the code (optional)
        
        Returns:
            Dict[str, Any]: State update with 'final_solution' key containing formatted output
        """
        chain = LLMChain(llm=self.llm, prompt=self._prompt)
        
        # Safely extract values from state
        task = state.get("task", "")
        code = str(state.get("code", ""))
        test_results = str(state.get("test_results", ""))
        generated_tests = str(state.get("generated_tests", ""))

        formatted_solution = chain.run(
            task=task,
            code=code,
            test_results=test_results,
            generated_tests=generated_tests
        )
        
        return {"final_solution": formatted_solution}

        
class DecomposerAgent(BaseAgent):
    """
    Agent responsible for breaking down complex programming tasks into manageable steps.
    
    This agent analyzes the input task and creates a structured plan that guides
    the subsequent code generation and optimization process. It uses a sophisticated
    prompt template with examples to ensure high-quality task decomposition.
    
    The DecomposerAgent is typically the first step in the workflow, providing
    a roadmap for all subsequent agents to follow.
    """
    
    def __init__(self, llm: Any):
        """
        Initialize the DecomposerAgent with a language model.
        
        Args:
            llm (Any): The language model instance to use for task decomposition
        """
        super().__init__(
            name="Task Decomposer",
            description="Breaks down complex programming tasks into manageable steps",
            llm=llm
        )
        self._prompt = ChatPromptTemplate.from_messages([
          ("system",
          "Ты — системный архитектор, помогающий мультиагентной системе по генерации кода. "
          "На вход ты получаешь описание задачи, а на выходе — чёткий, строгий пошаговый план. "
          "Каждый шаг должен быть **изолированной технической подзадачей**, пригодной для передачи отдельному агенту. "
          "Избегай шагов, требующих ручного участия человека (например, 'изучить документацию'). "
          "План должен использовать современные технологии и best practices. "
          "Структурируй план по фазам: Архитектура, Модели данных, API, Логика, Тесты, Деплой. "
          "Пиши конкретно: указывай имена моделей, схем, эндпоинтов, поля, инструменты. "
          "Формат ответа — строго как в примерах ниже.\n"),
          # Пример 1 — Python + FastAPI
          ("human", "Задача:\nРеализовать модуль сбора и отображения метрик в веб-приложении FastAPI."),
          ("ai",
          "План:\n\n"
          "Фаза 1. Архитектура:\n"
          "- Добавить отдельный модуль `metrics` в проекте FastAPI\n"
          "- Настроить роутинг: префикс `/metrics`\n\n"
          "Фаза 2. Модели данных:\n"
          "- Создать Pydantic-схему `MetricResponse` с полями: name:str, value:float\n"
          "- Создать SQLAlchemy-модель `MetricRecord` с полями: id:int, name:str, value:float, timestamp:datetime\n"
          "- Настроить Alembic миграцию для `MetricRecord`\n\n"
          "Фаза 3. API и логика:\n"
          "- Создать GET `/metrics/recent` — получить последние N метрик\n"
          "- Создать POST `/metrics/submit` — добавить метрику\n"
          "- Реализовать сбор системных метрик (CPU, RAM) с использованием `psutil`\n"
          "- Настроить фоновую задачу (FastAPI BackgroundTasks) для периодической отправки\n\n"
          "Фаза 4. Тестирование:\n"
          "- Написать unit-тесты для эндпоинтов с использованием httpx и pytest\n"
          "- Покрыть модели и фоновые задачи тестами\n\n"
          "Фаза 5. Деплой:\n"
          "- Добавить конфигурацию `.env` для метрик\n"
          "- Обновить docker-compose с сервисом `metrics-db`\n"
          "- Проверить доступность `/metrics/recent` после запуска"),
          # Пример 2 — Go + Gin
          ("human", "Задача:\nРазработать сервис управления пользователями на Go с фреймворком Gin."),
          ("ai",
          "План:\n\n"
          "Фаза 1. Архитектура:\n"
          "- Создать структуру проекта в стиле Clean Architecture\n"
          "- Настроить маршруты: `/users`, `/users/:id`\n\n"
          "Фаза 2. Модели данных:\n"
          "- Создать структуру `User` с полями: ID, Name, Email, CreatedAt\n"
          "- Настроить GORM-модель `User` и подключить PostgreSQL\n"
          "- Создать миграцию с использованием `gormigrate`\n\n"
          "Фаза 3. API:\n"
          "- Реализовать POST `/users` — создание пользователя\n"
          "- Реализовать GET `/users/:id` — получить пользователя по ID\n"
          "- Реализовать PUT `/users/:id` — обновление пользователя\n"
          "- Реализовать DELETE `/users/:id` — удаление пользователя\n"
          "- Добавить валидацию email и имени с помощью `go-playground/validator`\n\n"
          "Фаза 4. Документация:\n"
          "- Сгенерировать Swagger документацию через `swaggo/swag`\n"
          "- Добавить описание схем и запросов\n\n"
          "Фаза 5. Тестирование и деплой:\n"
          "- Написать unit-тесты для сервисов с `testify`\n"
          "- Собрать образ с помощью Dockerfile\n"
          "- Запустить PostgreSQL и сервис через docker-compose"),
          # Пример 3 — Node.js + Express
          ("human", "Задача:\nСделать webhook-сервер на Node.js, который принимает события оплаты от платежной системы."),
          ("ai",
          "План:\n\n"
          "Фаза 1. Архитектура:\n"
          "- Создать проект на Express с TypeScript\n"
          "- Настроить роутинг `/webhook`\n\n"
          "Фаза 2. API и логика:\n"
          "- Создать POST `/webhook` с парсингом JSON тела\n"
          "- Реализовать проверку подписи события через секретный ключ\n"
          "- Добавить логирование событий в базу MongoDB\n"
          "- Поддержать idempotency: игнорировать дубликаты событий\n\n"
          "Фаза 3. Тесты:\n"
          "- Написать e2e-тесты на `/webhook` с использованием Jest + supertest\n"
          "- Добавить тест с фальшивой подписью (negative case)\n\n"
          "Фаза 4. Деплой:\n"
          "- Добавить `.env` для секретов\n"
          "- Настроить `PM2` для продакшн-запуска\n"
          "- Обновить `Dockerfile` и `docker-compose.yml` с `node`, `mongo`, `ngrok`"),
          # Новый юзерский input
          ("human", "Задача:\n{task}")
      ])
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decompose the programming task into a structured plan.

        Args:
            state (Dict[str, Any]): Current workflow state containing:
                - task: The programming task to decompose

        Returns:
            Dict[str, Any]: State update with 'decomposition' key containing the step-by-step plan
        """
        chain = LLMChain(llm=self.llm, prompt=self._prompt)
        
        # Safely extract task from state
        task = state.get("task", "")
        if not task:
            return {"decomposition": "No task provided for decomposition"}
        
        decomposition = chain.run(task=task)
        return {"decomposition": decomposition}


class CodeGeneratorAgent(BaseAgent):
    """
    Agent responsible for generating Python code solutions.
    
    This agent takes a programming task (and optional decomposition) and generates
    complete, runnable Python code that solves the problem. It focuses on creating
    syntactically correct, immediately executable code with proper error handling.
    
    The CodeGeneratorAgent uses a specialized prompt designed for competitive
    programming and production-ready code generation.
    """
    
    def __init__(self, llm: Any):
        """
        Initialize the CodeGeneratorAgent with a language model.
        
        Args:
            llm (Any): The language model instance to use for code generation
        """
        super().__init__(
            name="Code Generator",
            description="Generates Python code solutions for programming tasks",
            llm=llm
        )
        # Converted to ChatPromptTemplate
        self._prompt = ChatPromptTemplate.from_messages([
            ("human", 
'''You are a highly skilled competitive programmer and Python developer with expertise in producing precise, efficient, and fully functional solutions.

Your task is to carefully read a programming problem and its decomposition, then generate a complete Python 3 program that fully solves the problem, strictly respecting all input-output specifications and problem constraints.

Problem description:

{task}

Decomposition of the problem:

{decomposition}

Write a Python 3 program that adheres exactly to the following requirements:
- Reads input only from standard input, matching the problem's specified format precisely.
- Prints output only to standard output, matching output formatting and requirements exactly.
- Implements the complete logic, including all necessary functions and helpers.
- Includes the if __name__ == "__main__": guard with runnable sample input handling embedded.
- Uses only standard Python libraries—no third-party imports.
- Produces immediately runnable code that can be executed without modifications.
- Does not contain any explanations, comments, markdown, or extraneous text—output must be raw Python code only.
- The code must be syntactically valid, logically correct, and produce correct output for sample inputs.

Your final output should be a single contiguous .py file contained within a markdown-style code block, showing the entire working solution.

Output **only** the code, nothing else. Your python code in markdown code block:'''
            )
        ])
        
    def _extract_code(self, response: str) -> str:
        """
        Extract Python code from various markdown formats or raw text.
        
        This method handles different ways the LLM might format code responses,
        including markdown code blocks, quotes, and raw text. It also validates
        the extracted code for syntax correctness.
        
        Args:
            response (str): The raw response from the language model
            
        Returns:
            str: Extracted Python code, validated for syntax correctness
        """
        # Define patterns to match different code block formats
        patterns = [
            r"```python\n(.*?)```",
            r"```.*?\n(.*?)```",
            r"'(.*?)'",
            r"\"\"\"(.*?)\"\"\"",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                code = matches[-1].strip()
                try:
                    # Validate syntax
                    ast.parse(code)
                    return code
                except SyntaxError:
                    continue
        
        # If no pattern matches, return the original response
        return response
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate Python code solution for the given task.
        
        Args:
            state (Dict[str, Any]): Current workflow state containing:
                - task: The programming task to solve
                - decomposition: Optional step-by-step plan
        
        Returns:
            Dict[str, Any]: State update with 'code' key containing the generated Python code
        """
        chain = LLMChain(llm=self.llm, prompt=self._prompt)
        
        # Safely extract values from state
        task = state.get("task", "")
        decomposition = state.get("decomposition", "")
        
        if not task:
            return {"code": "# No task provided for code generation"}
        
        # Generate code using the LLM
        code_response = chain.run(
            task=task,
            decomposition=decomposition
        )
        
        # Extract and validate the generated code
        extracted_code = self._extract_code(code_response)
        
        return {"code": extracted_code}

        
class TestingAgent(BaseAgent):
    """
    Agent responsible for generating and executing test cases for code solutions.
    
    This agent creates comprehensive test cases, runs them against the generated code,
    and provides detailed results including success rates and error analysis. It uses
    subprocess execution to safely test code in isolated environments.
    
    The TestingAgent is crucial for validating code correctness and providing
    feedback for optimization iterations.
    """
    
    def __init__(self, llm: Any):
        """
        Initialize the TestingAgent with a language model.
        
        Args:
            llm (Any): The language model instance to use for test generation
        """
        super().__init__(
            name="Testing Agent",
            description="Generates and executes test cases for code solutions",
            llm=llm
        )
        # Converted to ChatPromptTemplate
        self._prompt = ChatPromptTemplate.from_messages([
             ("system",
                """You are a precise generator of unit test inputs/outputs for Python programs that read from STDIN.

OUTPUT FORMAT (STRICT):
- Return ONLY a single markdown block starting with ```test-cases and ending with ``` (no prose before/after).
- Inside the block: a valid Python list of dicts. Each dict has exactly the keys:
  - "input": a multi-line string that includes T on the first line and then T input lines
  - "output": a string with the exact expected stdout (end each printed line with \n)
- List length must be <= 10.
- No comments, no explanations, no extra keys, no trailing text after the block.
- Do not echo instructions or the code snippet."""
                ),
                # Первый пример
                ("human", """EXAMPLE 1 — SIMPLE, CLEAN INPUTS
Task: Sum two integers per line and print the sum for each of T lines.

Function code:
```python
def solve():
    import sys
    data = sys.stdin.read().strip().splitlines()
    t = int(data[0])
    for i in range(1, t + 1):
        a, b = map(int, data[i].split())
        print(a + b)
if __name__ == "__main__":
    solve()
```

Generate GOOD test cases following the OUTPUT FORMAT (STRICT)."""),
                
                ("ai", """```test-cases
[
  {{"input": "2\\n4 2\\n3 5\\n", "output": "6\\n8\\n"}}
]
```"""),
                # Второй пример
                ("human", """EXAMPLE 2 — VARIED VALUES AND SPACING (STILL VALID)
Same task. More diverse numbers and benign spacing. Generate GOOD test cases following the OUTPUT FORMAT (STRICT).
"""),
                ("ai", """```test-cases
[
  {{"input": "3\\n0 0\\n10 -10\\n1000000 999999\\n", "output": "0\\n0\\n1999999\\n"}},
  {{"input": "1\\n   7    8   \\n", "output": "15\\n"}}
]
```
"""),
                # Основной промпт
                ("human","""YOUR TASK — FOLLOW THE OUTPUT FORMAT (STRICT)

READING FORMAT:
1) First line contains T (number of test cases)
2) Next T lines contain the input for each test case

Each element of the output list must be a dict:
- "input": full stdin for one run (including T + T lines)
- "output": exact expected stdout

Each test case should be a dictionary with:
- 'input': a multi-line string representing the entire input to the script (including T and test cases)
- 'output': a string representing the expected output of the script.

Example valid test case:
{{'input': '2\\n4 2\\n3 5\\n', 'output': '6\\n8\\n'}}

Requirements:
1. Only valid Python list of dictionaries
2. No additional text, comments, or code

Task:
{task}

Function code:
```python
{code}
```

Output ONLY the test list with max size 5 within a markdown block:
```test-cases
# Your tests here
```
""")
            ])

    def _parse_tests(self, raw: str) -> List[Dict]:
        """
        Parse test cases from the LLM response.
        
        Args:
            raw (str): Raw response containing test cases in markdown format
            
        Returns:
            List[Dict]: List of test case dictionaries with 'input' and 'output' keys
        """

        try:
            clean = re.search(r'```.*?\n(.*?)```', raw, re.DOTALL).group(1)
            return ast.literal_eval(clean.strip())
        except (SyntaxError, ValueError, AttributeError) as e:
            logger.exception("Test parsing error: %s", e)
            return []
    
    def _extract_function_name(self, code: str) -> Optional[str]:
        """
        Extract the main function name from Python code.
        
        Args:
            code (str): Python source code
            
        Returns:
            Optional[str]: Name of the first function found, or None if no function exists
        """
        try:
            tree = ast.parse(code)
            return next(
                node.name for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
            )
        except (StopIteration, SyntaxError):
            return None
    
    def _parse_output(self, output: str) -> str:
        """
        Parse and clean output from subprocess execution.
        
        Args:
            output (str): Raw output from subprocess
            
        Returns:
            str: Cleaned output string
        """
        return output.strip()

    def _check_import_safety(self, code: str) -> str:
        """
        Inspect code AST to block dangerous imports/usages before execution.

        Returns empty string if safe; otherwise a short error description.
        """
        forbidden_modules = {
            "subprocess", "socket", "requests", "urllib", "http", "ftplib",
            "paramiko", "psutil", "ctypes", "multiprocessing", "threading",
            "signal", "webbrowser", "pexpect", "shutil"
        }
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return "Syntax error before safety check"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = (alias.name or "").split(".")[0]
                    if root in forbidden_modules:
                        return f"Forbidden import: {root}"
            if isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in forbidden_modules:
                    return f"Forbidden import from: {root}"
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "__import__":
                    return "Forbidden dynamic import: __import__"
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    base = func.value.id
                    attr = func.attr
                    if base == "os" and attr in {"system", "popen", "spawnl", "spawnv", "spawnve", "spawnle"}:
                        return f"Forbidden call: os.{attr}"
                    if base == "subprocess" and attr in {"Popen", "call", "run", "check_output", "check_call"}:
                        return f"Forbidden call: subprocess.{attr}"
                    if base == "socket":
                        return "Forbidden socket usage"
        return ""
        
    def _run_tests(self, code: str, tests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute test cases against the provided code.
        
        This method creates a temporary file with the code, runs each test case
        through subprocess execution, and collects detailed results.
        
        Args:
            code (str): Python code to test
            tests (List[Dict[str, Any]]): List of test cases with 'input' and 'output'
            
        Returns:
            Dict[str, Any]: Comprehensive test results including:
                - total: Total number of tests
                - passed: Number of passed tests
                - failed: Number of failed tests
                - errors: List of error messages
                - test_details: Detailed results for each test
                - success_rate: Percentage of tests passed
        """
        results = {
            "total": len(tests),
            "passed": 0,
            "failed": 0,
            "errors": [],
            "test_details": [],
            "success_rate": 0.0
        }
        unsafe = self._check_import_safety(code)
        if unsafe:
            results["errors"].append(unsafe)
            return results
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', encoding='utf-8', delete=False) as f:
                temp_file_path = f.name
                f.write(code)
                
        except Exception as e:
            results["errors"].append(f"Code generation failed: {str(e)}")
            return results
        for i, test in enumerate(tests, 1):
            test_result = {
                "test_number": i,
                "input": test["input"],
                "expected": test["output"],
                "received": None,
                "success": False,
                "error": None
            }
            try:
                input_data = test["input"]
                result = subprocess.run(
                    [sys.executable, temp_file_path],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    timeout=5
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr.strip() or f"Exit code {result.returncode}"
                    test_result["error"] = error_msg
                    test_result["success"] = test["output"] == "Exception"
                else:
                    received = self._parse_output(result.stdout.strip())
                    test_result["received"] = received
                    test_result["success"] = str(received).strip() == str(test["output"]).strip()
                if test_result["success"]:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                test_result["error"] = f"System error: {str(e)}"
                results["failed"] += 1
                results["errors"].append(str(e))
            results["test_details"].append(test_result)
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        if results["total"] > 0:
            results["success_rate"] = round(results["passed"] / results["total"], 2)
        return results

    def _generate_tests(self, task: str, code: str) -> List[Dict]:
        """
        Generate test cases for the given task and code.
        
        Args:
            task (str): The original programming task
            code (str): The code to generate tests for
            
        Returns:
            List[Dict]: List of generated test cases
        """
        chain = LLMChain(llm=self.llm, prompt=self._prompt)
        raw_tests = chain.run(task=task, code=code)
        return self._parse_tests(raw_tests)
        
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate and execute test cases for the code solution.
        
        Args:
            state (Dict[str, Any]): Current workflow state containing:
                - task: The programming task
                - code: The generated code to test
        
        Returns:
            Dict[str, Any]: State update with:
                - generated_tests: List of generated test cases
                - test_results: Comprehensive test execution results
        """
        # Safely extract code from state
        code = state.get("code", "")
        task = state.get("task", "")
        
        if not code or not task:
            return {
                "generated_tests": [],
                "test_results": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "errors": ["No code or task provided for testing"],
                    "test_details": [],
                    "success_rate": 0.0
                }
            }
        
        # Generate test cases
        generated_tests = self._generate_tests(task, code)
        
        # Execute tests
        test_results = self._run_tests(code, generated_tests)
        
        return {
            "generated_tests": generated_tests,
            "test_results": test_results
        }


class OptimizationAgent(BaseAgent):
    """
    Agent responsible for optimizing and enhancing existing code solutions.
    
    This agent analyzes code performance, test results, and failure patterns to
    create improved versions that maintain functionality while enhancing performance,
    readability, and test success rates. It uses intelligent content truncation
    to handle large codebases efficiently.
    
    The OptimizationAgent is typically used when test results indicate issues
    with correctness or performance.
    """
    
    def __init__(self, llm: Any):
        """
        Initialize the OptimizationAgent with a language model.
        
        Args:
            llm (Any): The language model instance to use for code optimization
        """
        super().__init__(
            name="Code Optimizer",
            description="Improves existing solutions for performance, readability, and correctness",
            llm=llm
        )
        # Converted to ChatPromptTemplate
        self._prompt = ChatPromptTemplate.from_messages([
            ("human",
            """As expert optimizer:
1. ANALYZE: Code, test results, task
2. DIAGNOSE: Root causes of failures/bottlenecks
3. OPTIMIZE: Fix tests, improve performance, enhance readability
4. VERIFY: Maintain functionality

Priorities: Correctness > Performance > Readability

**Examples:**

Example 1 (Performance):
Task: "Find duplicates in string"
Original (O(N²)):
```python
def find_dups(s):
    res = []
    for i, c1 in enumerate(s):
        for j, c2 in enumerate(s):
            if i != j and c1 == c2:
                res.append(c1)
    return list(set(res))

Test: Correct but slow on large inputs
Optimized (O(N)):
```
def find_dups(s):
    seen, dups = set(), set()
    for c in s:
        (dups.add(c) if c in seen else seen.add(c))
    return list(dups)
```

Example 2 (Correctness):
Task: "Running median"
Original (incorrect output):
```
def running_median(stream):
    med = []
    for i in range(1, len(stream)+1):
        w = sorted(stream[:i])
        mid = i//2
        med.append(w[mid] if i%2 else (w[mid-1]+w[mid])/2)
    return med
```
Test: Failed for [5,2,7] (expected [5,3.5,5], got [5,3.5,2])
Optimized (fixed + efficient):
```
import heapq
def running_median(stream):
    lo, hi = [], []  # max_heap, min_heap
    med = []
    for n in stream:
        heapq.heappush(lo, -n)
        heapq.heappush(hi, -heapq.heappop(lo))
        if len(lo) < len(hi):
            heapq.heappush(lo, -heapq.heappop(hi))
        m = -lo[0] if len(lo)>len(hi) else (-lo[0]+hi[0])/2
        med.append(m)
    return med
```


Current Task:
Task: {task}
Metric: {metric}

Original code:
{truncated_code}```

Test summary:
{truncated_tests}

Return ONLY optimized Python code in markdown block.""")
        ])

    def _extract_code(self, response: str) -> str:
        patterns = [
            r"```python\n(.*?)```",
            r"```.*?\n(.*?)```",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                code = matches[-1].strip()
                try:
                    ast.parse(code)
                    return code
                except SyntaxError:
                    continue
        return response

    def _truncate_content(self, content: str, max_chars: int) -> str:
        """Smart truncation preserving critical sections"""
        if len(content) <= max_chars:
            return content

        # Preserve important parts: function definitions and error messages
        important = []
        for pattern in [r"def .+\):", r"class .+\):", r"Error:.+", r"FAILED:.+"]:
            important.extend(re.findall(pattern, content))

        truncated = content[:max_chars//2]
        if important:
            truncated += "\n\n...TRUNCATED...\n\n" + "\n".join(important[-5:])
        truncated += content[-max_chars//2:]

        return truncated

    def _summarize_tests(self, test_results: str) -> str:
        """Condense test results to critical information"""
        # Extract key metrics
        metrics = re.findall(r"(Pass rate:.+|Fail count:.+)", test_results)

        # Extract failure details
        failures = re.findall(r"FAILED:.+?(?=\nPASSED|\Z)", test_results, re.DOTALL)

        summary = []
        if metrics:
            summary.append("Key metrics:")
            summary.extend(metrics[:3])

        if failures:
            summary.append("\nCritical failures:")
            summary.extend(failures[:5])

        return "\n".join(summary) if summary else test_results[:2000]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize code based on task requirements and test results.
        
        Args:
            state (Dict[str, Any]): Current workflow state containing:
                - task: The original programming task
                - code: The code to optimize
                - test_results: Results from testing the code
        
        Returns:
            Dict[str, Any]: State update with 'code' key containing optimized code
        """
        # Safely extract values from state
        task = state.get("task", "")
        raw_code = state.get("code", "")
        raw_tests = str(state.get("test_results", ""))
        
        if not task or not raw_code:
            return {"code": "# No task or code provided for optimization"}
        
        # Process and truncate content for LLM processing
        processed_tests = self._summarize_tests(raw_tests)
        truncated_tests = self._truncate_content(processed_tests, 5000)
        truncated_code = self._truncate_content(raw_code, 15000)
        
        # Generate optimized code
        chain = LLMChain(llm=self.llm, prompt=self._prompt)
        optimized_response = chain.invoke({
            "task": task,
            "metric": "efficiency",
            "truncated_code": truncated_code,
            "truncated_tests": truncated_tests
        })["text"]
        
        # Extract and return optimized code
        optimized_code = self._extract_code(optimized_response)
        return {"code": optimized_code}


class AgentRouter:
    """
    Central orchestrator that manages the workflow of different agents.
    
    The AgentRouter uses LLM to decide the sequence of optimization steps.
    """
    
    def __init__(self, llm: ChatOpenAI):
        """
        Initialize the AgentRouter with all available agents.
        
        Args:
            llm (ChatOpenAI): The language model instance to use for routing decisions
        """
        self.llm = llm
        self.agents = {
            "decomposer": DecomposerAgent(llm),
            "generator": CodeGeneratorAgent(llm),
            "tester": TestingAgent(llm),
            "optimizer": OptimizationAgent(llm),
            "formatter": FormatterAgent(llm)
        }
        
        # Prompt for LLM-based optimization sequence decision
        self.sequence_decision_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software development workflow orchestrator. 
Analyze the current state and decide the optimal next step in the optimization cycle.

AVAILABLE ACTIONS:
- TEST: Run tests on the current code
- OPTIMIZE: Improve the code based on test results  
- FORMAT: Proceed to final solution formatting (only when success rate >= 95%)

CURRENT STATE:
Task: {task}
Success Rate: {success_rate}%
Failed Tests: {failed_count}/{total_tests}
Error Types: {error_types}
Optimization Cycles: {optimization_cycles}

RECENT HISTORY (last 3 steps):
{recent_history}

DECISION GUIDELINES:
1. Always start with TEST to assess current state
2. If success rate < 95% and optimization_cycles < max_steps, consider OPTIMIZE
3. If success rate >= 95%, choose FORMAT to complete
4. Avoid infinite loops - limit optimization attempts
5. If recent steps were TEST→OPTIMIZE→TEST, consider if further optimization will help
6. For syntax errors or fundamental issues, OPTIMIZE is needed
7. For flaky tests or system errors, TEST again may be appropriate
8. If the original code is empty or invalid, OPTIMIZE is needed

Respond ONLY with one of: TEST, OPTIMIZE, or FORMAT without any other text or comments

Example responses:
TEST
OPTIMIZE
FORMAT
""")

        ])

    def _analyze_test_results(self, test_results: Dict) -> Dict:
        """Analyze test results to extract key metrics for decision making"""
        return {
            "success_rate": round(test_results.get("success_rate", 0) * 100, 1),
            "failed_count": test_results.get("failed", 0),
            "total_tests": test_results.get("total", 0),
            "error_types": self._categorize_errors(test_results.get("errors", [])),
            "test_details": test_results.get("test_details", [])
        }

    def _categorize_errors(self, errors: List[str]) -> List[str]:
        """Categorize errors for better decision making"""
        categories = []
        for error in errors:
            error_lower = str(error).lower()
            if any(e in error_lower for e in ["syntax", "parse", "indentation"]):
                categories.append("SYNTAX_ERROR")
            elif any(e in error_lower for e in ["timeout", "performance", "slow", "efficiency"]):
                categories.append("PERFORMANCE_ISSUE")
            elif any(e in error_lower for e in ["logic", "incorrect", "wrong output", "expected"]):
                categories.append("LOGIC_ERROR")
            elif any(e in error_lower for e in ["exception", "runtime", "attribute", "index"]):
                categories.append("RUNTIME_ERROR")
            elif any(e in error_lower for e in ["system", "process", "subprocess", "execution"]):
                categories.append("SYSTEM_ERROR")
            else:
                categories.append("UNKNOWN_ERROR")
        return list(set(categories))

    def _get_recent_history(self, step_history: List[Dict], max_steps: int = 3) -> str:
        """Format recent step history for context"""
        recent = step_history[-max_steps:] if step_history else []
        if not recent:
            return "No recent history"
        
        history_str = []
        for i, step in enumerate(recent, 1):
            step_type = step.get('type', 'UNKNOWN')
            result = step.get('result', {})
            if 'test_results' in result:
                success_rate = result['test_results'].get('success_rate', 0) * 100
                history_str.append(f"{i}. {step_type} (Success: {success_rate:.1f}%)")
            else:
                history_str.append(f"{i}. {step_type}")
        
        return "\n".join(history_str)

    def _llm_decide_next_step(self, task: str, state: Dict, step_history: List[Dict], 
                             optimization_cycles: int, max_steps: int) -> str:
        """
        Use LLM to decide the next optimal step in the workflow.
        
        Returns:
            str: One of "TEST", "OPTIMIZE", or "FORMAT"
        """
        test_analysis = self._analyze_test_results(state.get("test_results", {}))
        recent_history = self._get_recent_history(step_history)
        
        chain = LLMChain(llm=self.llm, prompt=self.sequence_decision_prompt)
        
        try:
            decision = chain.run({
                "task": task,
                "success_rate": test_analysis["success_rate"],
                "failed_count": test_analysis["failed_count"],
                "total_tests": test_analysis["total_tests"],
                "error_types": ", ".join(test_analysis["error_types"]),
                "optimization_cycles": optimization_cycles,
                "recent_history": recent_history
            }).strip().upper()
            
            # Validate the decision
            valid_decisions = {"TEST", "OPTIMIZE", "FORMAT"}

            if decision in valid_decisions:
                return decision
            else:
                logger.info("Invalid decision: %s", decision)
                return "TEST"
                
        except Exception as e:
            logger.exception("Error in _llm_decide_next_step")
            return "TEST"

    def _should_terminate(self, state: Dict, step_history: List[Dict], 
                         optimization_cycles: int, max_cycles: int) -> bool:
        """Determine if the workflow should terminate"""
        test_results = state.get("test_results", {})
        success_rate = test_results.get("success_rate", 0)
        
        # Success condition
        if success_rate >= 0.95:
            return True
            
        # Maximum optimization cycles reached
        if optimization_cycles >= max_cycles:
            return True
            
        # Check for repetitive patterns that indicate stagnation
        recent_steps = [step.get('type') for step in step_history[-4:]]
        if len(recent_steps) >= 4 and recent_steps[-2:] == recent_steps[-4:-2]:
            return True
            
        return False

    def execute_workflow(self, task: str, max_steps: int = 5, on_update: Optional[Any] = None) -> Dict:
        """
        Execute the complete workflow with LLM-driven optimization sequence.
        
        Args:
            task (str): The programming task to solve
            max_optimization_cycles (int): Maximum optimization attempts
            
        Returns:
            Dict: Final workflow state with all results
        """
        logger.info("Workflow start: max_steps=%s", max_steps)
        state = {"task": task}
        step_history = []  # Track each step for context
        optimization_cycles = 0

        # Step 1: Decompose
        logger.info("Step 1/?: DECOMPOSE start")
        state.update(self.agents["decomposer"].execute(state))
        step_history.append({"type": "DECOMPOSE", "result": state})
        logger.info("DECOMPOSE done: has_decomposition=%s", bool(state.get("decomposition")))
        if on_update:
            try:
                on_update(state, {"type": "DECOMPOSE"})
            except Exception:
                logger.exception("on_update failed for DECOMPOSE")
        
        # Step 2: Code Generation (always second)
        logger.info("Step 2/?: GENERATE start")
        state.update(self.agents["generator"].execute(state))
        step_history.append({"type": "GENERATE", "result": state})
        logger.info("GENERATE done: code_chars=%s", len(state.get("code", "")))
        if on_update:
            try:
                on_update(state, {"type": "GENERATE"})
            except Exception:
                logger.exception("on_update failed for GENERATE")
        
        # Optimization loop with LLM-driven decisions
        while not self._should_terminate(state, step_history, optimization_cycles, max_steps):
            # Get LLM decision for next step
            next_step = self._llm_decide_next_step(task, state, step_history, optimization_cycles, max_steps)
            logger.info("Decision: next_step=%s, cycle=%s", next_step, optimization_cycles)
            
            if next_step == "TEST":
                logger.info("TEST start")
                test_result = self.agents["tester"].execute(state)
                state.update(test_result)
                step_history.append({"type": "TEST", "result": test_result})
                logger.info(
                    "TEST done: passed=%s failed=%s success_rate=%.2f",
                    state.get("test_results", {}).get("passed", 0),
                    state.get("test_results", {}).get("failed", 0),
                    state.get("test_results", {}).get("success_rate", 0.0),
                )
                if on_update:
                    try:
                        on_update(state, {"type": "TEST"})
                    except Exception:
                        logger.exception("on_update failed for TEST")
                
            elif next_step == "OPTIMIZE":
                logger.info("OPTIMIZE start")
                optimize_result = self.agents["optimizer"].execute(state)
                state.update(optimize_result)
                step_history.append({"type": "OPTIMIZE", "result": optimize_result})
                optimization_cycles += 1
                logger.info("OPTIMIZE done: cycles=%s code_chars=%s", optimization_cycles, len(state.get("code", "")))
                if on_update:
                    try:
                        on_update(state, {"type": "OPTIMIZE", "cycle": optimization_cycles})
                    except Exception:
                        logger.exception("on_update failed for OPTIMIZE")
                
            elif next_step == "FORMAT":
                logger.info("FORMAT decision reached; exiting loop")
                break
                
            # Add small delay to avoid rapid API calls
            import time
            time.sleep(1)
        
        # Final step: Formatting (always last)
        logger.info("FORMAT start")
        state.update(self.agents["formatter"].execute(state))
        step_history.append({"type": "FORMAT", "result": state})
        logger.info("FORMAT done: final_solution_chars=%s", len(state.get("final_solution", "")))
        if on_update:
            try:
                on_update(state, {"type": "FORMAT"})
            except Exception:
                logger.exception("on_update failed for FORMAT")
        
        # Add workflow metadata to final state
        state["workflow_metadata"] = {
            "total_steps": len(step_history),
            "optimization_cycles": optimization_cycles,
            "final_success_rate": state.get("test_results", {}).get("success_rate", 0),
            "step_sequence": [step["type"] for step in step_history]
        }
        logger.info(
            "Workflow complete: steps=%s cycles=%s final_success_rate=%.2f",
            state["workflow_metadata"]["total_steps"],
            state["workflow_metadata"]["optimization_cycles"],
            state["workflow_metadata"]["final_success_rate"],
        )

        return state

