import streamlit as st
import os
import time
import requests

# Configure custom model credentials
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_API_KEY = "ollama"


def execute_via_api(task, api_base_url, model_name, temperature, max_steps, use_custom_model, base_url, api_key, max_new_tokens):
    """Execute task via async API with polling"""
    with st.spinner("Submitting task to API..."):
        # Prepare request data
        request_data = {
            "task": task,
            "model_name": model_name,
            "temperature": temperature,
            "max_steps": max_steps,
            "use_custom_model": use_custom_model,
            "base_url": base_url,
            "api_key": api_key,
            "max_new_tokens": max_new_tokens
        }

        # Submit task
        response = requests.post(f"{api_base_url}/solve", json=request_data)
        response.raise_for_status()

        task_info = response.json()
        task_id = task_info["task_id"]

        st.success(f"Task submitted! Task ID: {task_id}")

        # Create progress containers
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Create output containers and placeholders for refreshable content
        decomposition_container = st.expander("Task Decomposition", expanded=True)
        code_container = st.expander("Generated Code", expanded=True)
        test_container = st.expander("Test Results", expanded=True)
        solution_container = st.expander("Final Solution", expanded=True)
        decomposition_placeholder = decomposition_container.empty()
        code_placeholder = code_container.empty()
        test_placeholder = test_container.empty()
        solution_placeholder = solution_container.empty()

        # Poll for status
        while True:
            try:
                status_response = requests.get(f"{api_base_url}/task/{task_id}")
                status_response.raise_for_status()
                status_data = status_response.json()

                current_status = status_data["status"]
                progress = status_data.get("progress", 0)
                message = status_data.get("message", "")

                progress_bar.progress(progress / 100)
                status_text.text(f"Status: {current_status} - {message}")

                # Render partial results during PROGRESS
                partial = status_data.get("partial") or {}
                if partial:
                    if partial.get("decomposition") is not None:
                        decomposition_placeholder.markdown(f"**Decomposition (partial):**\n{partial['decomposition']}")
                    if partial.get("code") is not None:
                        code_placeholder.code(partial['code'], language="python")
                    if partial.get("test_results") is not None:
                        test_results = partial["test_results"] or {}
                        success_rate = test_results.get("success_rate", 0)
                        # Rebuild the test section on each update
                        test_placeholder.empty()
                        with test_placeholder.container():
                            st.markdown(f"**Success Rate (partial):** {success_rate:.2f}")
                            details = test_results.get("test_details") or []
                            for i, test in enumerate(details):
                                st.markdown(f"**Test {i+1}:** {'✅' if test.get('success') else '❌'}")
                                if not test.get('success'):
                                    st.markdown(f"Input: `{test.get('input','')}`")
                                    st.markdown(f"Expected: `{test.get('expected','')}`")
                                    st.markdown(f"Received: `{test.get('received','')}`")
                    if partial.get("final_solution") is not None:
                        solution_placeholder.markdown(partial["final_solution"])                

                if current_status == "SUCCESS":
                    # Get final result
                    result_response = requests.get(f"{api_base_url}/task/{task_id}/result")
                    result_response.raise_for_status()
                    result_data = result_response.json()

                    # Check if task completed with error
                    if result_data.get("status") == "failed":
                        st.error(f"Task failed: {result_data.get('error', 'Unknown error')}")
                        break

                    # Display results (refresh each section)
                    decomposition_placeholder.empty()
                    code_placeholder.empty()
                    test_placeholder.empty()
                    solution_placeholder.empty()

                    if result_data.get("decomposition"):
                        decomposition_placeholder.markdown(f"**Decomposition:**\n{result_data['decomposition']}")

                    if result_data.get("code"):
                        code_placeholder.code(result_data['code'], language="python")

                    if result_data.get("test_results"):
                        test_results = result_data["test_results"]
                        success_rate = test_results.get("success_rate", 0)
                        with test_placeholder.container():
                            st.markdown(f"**Success Rate:** {success_rate:.2f}")
                            if "test_details" in test_results:
                                test_details = test_results["test_details"]
                                for i, test in enumerate(test_details):
                                    st.markdown(f"**Test {i+1}:** {'✅' if test['success'] else '❌'}")
                                    if not test['success']:
                                        st.markdown(f"Input: `{test['input']}`")
                                        st.markdown(f"Expected: `{test['expected']}`")
                                        st.markdown(f"Received: `{test['received']}`")

                    if result_data.get("final_solution"):
                        solution_placeholder.markdown(result_data["final_solution"])

                    if result_data.get("agents_used"):
                        st.subheader("Agent Workflow")
                        st.write(" → ".join(result_data["agents_used"]))

                    progress_bar.progress(1.0)
                    status_text.text("Task completed!")
                    break

                elif current_status == "FAILURE":
                    st.error(f"Task failed: {status_data.get('error', 'Unknown error')}")
                    break

                time.sleep(2)  # Poll every 2 seconds

            except requests.RequestException as e:
                st.error(f"Error polling task status: {str(e)}")
                break

st.markdown("---")
st.markdown("Agent System Interface") 

st.set_page_config(
    page_title="Agent System Interface",
    page_icon="🤖",
    layout="wide",
)

# Set default model credentials
os.environ["OPENAI_API_BASE"] = DEFAULT_BASE_URL
os.environ["OPENAI_API_KEY"] = DEFAULT_API_KEY

# Initialize variables
use_api = False
api_base_url = None
use_custom_model = True
model_name = "gemma4:e4b"
base_url = DEFAULT_BASE_URL
api_key = DEFAULT_API_KEY
temperature = 0.2
max_steps = 8
max_new_tokens = 2048

st.title("Agent System Interface")
st.markdown("""
This interface allows you to interact with an intelligent agent system that:
1. Decomposes coding tasks
2. Generates Python code solutions
3. Tests the solutions
4. Optimizes code
5. Formats final answers
""")

with st.sidebar:
    st.header("Settings")

    api_base_url = st.text_input("API Base URL", value="http://localhost:8000" if api_base_url is None else api_base_url, help="Base URL of the API server")
    use_custom_model = st.checkbox("Use Custom Model", value=use_custom_model)

    if use_custom_model:
        model_name = st.text_input("Model Name", value=model_name)
        base_url = st.text_input("Base URL", value=base_url)
        api_key = st.text_input("API Key", value=api_key, type="password")
    else:
        st.warning("⚠️ To use OpenAI models, please set your OPENAI_API_KEY environment variable")
        model_name = st.text_input("Model Name", value=model_name)
        api_key = st.text_input("OpenAI API Key:", value=api_key, type="password")
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            st.success("OpenAI API Key set successfully!")

    temperature = st.slider("Temperature", 0.0, 1.5, temperature, 0.1)
    max_new_tokens = st.slider("Max new tokens", 128, 32768, max_new_tokens, 128)
    max_steps = st.slider("Maximum Steps", 3, 12, max_steps, 1)

# Main input area
task = st.text_area("Enter your coding task:", height=150)

if st.button("Solve Task"):
    if not task:
        st.error("Please enter a task to solve.")
    else:
        try:

            execute_via_api(task, api_base_url, model_name, temperature, max_steps, use_custom_model, base_url, api_key, max_new_tokens)

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
