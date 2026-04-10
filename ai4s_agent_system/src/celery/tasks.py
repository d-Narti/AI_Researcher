from src.celery.app import celery_app
from langchain_openai import ChatOpenAI as LangchainOpenAI
import os
from src.agent_system import AgentRouter
from src.logging_setup import setup_logging

logger = setup_logging(__name__)

# Connection-related exceptions that warrant a retry
_RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

try:
    import openai
    _RETRYABLE_EXCEPTIONS = _RETRYABLE_EXCEPTIONS + (
        openai.APIConnectionError,
        openai.APITimeoutError,
    )
except Exception:
    pass

try:
    import httpx
    _RETRYABLE_EXCEPTIONS = _RETRYABLE_EXCEPTIONS + (httpx.ConnectError,)
except Exception:
    pass


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def solve_task_async(self, task_data):
    try:
        self.update_state(state='PROGRESS', meta={'progress': 0, 'message': 'Инициализация...'})

        task = task_data['task']
        model_name = task_data.get('model_name', 'gemma4:e4b')
        temperature = task_data.get('temperature', 0.2)
        max_steps = task_data.get('max_steps', 8)
        max_new_tokens = task_data.get('max_new_tokens', 2048)
        use_custom_model = task_data.get('use_custom_model', True)
        base_url = task_data.get('base_url', os.getenv('OPENAI_API_BASE', 'http://localhost:11434/v1'))
        api_key = task_data.get('api_key', os.getenv('OPENAI_API_KEY', 'ollama'))

        logger.debug("task_data=%s", task_data)
        logger.debug(
            "use_custom_model=%s model_name=%s base_url=%s max_new_tokens=%s",
            use_custom_model, model_name, base_url, max_new_tokens
        )
        logger.debug("api_key starts with: %s", (api_key[:10] + "...") if api_key else "None")

        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': 'Инициализация модели...'})

        try:
            if use_custom_model:
                llm = LangchainOpenAI(
                    model=model_name,
                    temperature=temperature,
                    openai_api_base=base_url,
                    openai_api_key=api_key,
                    max_tokens=max_new_tokens
                )
            else:
                if api_key:
                    os.environ["OPENAI_API_KEY"] = api_key
                os.environ.pop("OPENAI_API_BASE", None)
                llm = LangchainOpenAI(
                    model_name=model_name,
                    temperature=temperature,
                    max_tokens=max_new_tokens
                )
        except _RETRYABLE_EXCEPTIONS as exc:
            retry_count = self.request.retries
            wait = 10 * (2 ** retry_count)  # exponential backoff: 10s, 20s, 40s
            logger.warning(
                "LLM init failed (attempt %d/3), retrying in %ds: %s",
                retry_count + 1, wait, exc
            )
            raise self.retry(exc=exc, countdown=wait)

        self.update_state(state='PROGRESS', meta={'progress': 20, 'message': 'Создание системы агентов...'})
        router = AgentRouter(llm)

        def on_update(state, info):
            try:
                meta = {
                    'progress': 30,
                    'message': f"Step: {info.get('type', 'UNKNOWN')}",
                    'partial': {
                        'decomposition': state.get('decomposition'),
                        'code': state.get('code'),
                        'test_results': state.get('test_results'),
                        'final_solution': state.get('final_solution'),
                    }
                }
                t = info.get('type')
                if t == 'DECOMPOSE':
                    meta['progress'] = 35
                elif t == 'GENERATE':
                    meta['progress'] = 55
                elif t == 'TEST':
                    meta['progress'] = 70
                elif t == 'OPTIMIZE':
                    meta['progress'] = 80
                elif t == 'FORMAT':
                    meta['progress'] = 90
                self.update_state(state='PROGRESS', meta=meta)
            except Exception as _e:
                logger.debug("on_update error (ignored): %s", _e)

        self.update_state(state='PROGRESS', meta={'progress': 30, 'message': 'Анализ задачи...'})

        try:
            result = router.execute_workflow(task=task, max_steps=max_steps, on_update=on_update)
        except _RETRYABLE_EXCEPTIONS as exc:
            retry_count = self.request.retries
            wait = 10 * (2 ** retry_count)
            logger.warning(
                "LLM call failed during workflow (attempt %d/3), retrying in %ds: %s",
                retry_count + 1, wait, exc
            )
            raise self.retry(exc=exc, countdown=wait)

        self.update_state(state='PROGRESS', meta={'progress': 90, 'message': 'Форматирование результата...'})

        agents_used = [agent.name for agent in result.get('agents', [])]
        test_results = result.get("test_results", {})
        success_rate = test_results.get("success_rate", 0)

        final_result = {
            'final_solution': result.get("final_solution", ""),
            'code': result.get("code", ""),
            'success_rate': success_rate,
            'agents_used': agents_used,
            'test_results': test_results,
            'decomposition': result.get("decomposition", ""),
            'status': 'completed'
        }

        self.update_state(state='PROGRESS', meta={'progress': 100, 'message': 'Завершено'})

        logger.info(
            "Task %s completed successfully with success_rate=%.2f",
            self.request.id, success_rate
        )
        return final_result

    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        logger.exception(
            "Task %s failed: %s",
            getattr(self.request, 'id', 'unknown'), error_msg
        )
        return {
            'final_solution': "",
            'code': "",
            'success_rate': 0.0,
            'agents_used': [],
            'test_results': {'error': error_msg},
            'decomposition': "",
            'status': 'failed',
            'error': error_msg
        }
