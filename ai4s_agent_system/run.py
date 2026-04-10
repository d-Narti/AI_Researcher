"""
Agent System Launcher

This module provides a command-line interface for launching different components
of the AI agent system. It supports running the FastAPI server, Streamlit app,
or both services simultaneously.

Usage:
    python run.py api          # Run FastAPI server only
    python run.py streamlit    # Run Streamlit app only  
    python run.py all          # Run both services in parallel
"""

import argparse
import os
import subprocess
import sys
import threading
from typing import Optional
from dotenv import load_dotenv
from src.logging_setup import setup_logging

logger = setup_logging(__name__)

# Configuration constants
DEFAULT_BASE_URL = "https://api.proxyapi.ru/openai/v1"
DEFAULT_API_KEY = ""
DEFAULT_STREAMLIT_PORT = "8501"
DEFAULT_STREAMLIT_HEADLESS = "true"

# Set default model credentials
os.environ["OPENAI_API_BASE"] = DEFAULT_BASE_URL
os.environ["OPENAI_API_KEY"] = DEFAULT_API_KEY

# Load environment variables from .env file if it exists
load_dotenv()


def check_api_key() -> bool:
    """
    Check if the API key is properly configured.
    
    Returns:
        bool: True if API key is configured, False otherwise
    """
    api_key = os.getenv("OPENAI_API_KEY")
    return api_key and api_key != DEFAULT_API_KEY


def run_api() -> None:
    """
    Launch the FastAPI server.
    
    Raises:
        SystemExit: If the API server fails to start
    """
    logger.info("Starting API server...")
    try:
        subprocess.run([sys.executable, "api.py"], check=True)
    except subprocess.CalledProcessError as e:
        logger.exception("Error running API server: %s", e)
        sys.exit(1)
    except FileNotFoundError:
        logger.error("Error: api.py not found. Make sure you're in the correct directory.")
        sys.exit(1)


def run_streamlit() -> None:
    """
    Launch the Streamlit application.
    
    Raises:
        SystemExit: If the Streamlit app fails to start
    """
    logger.info("Starting Streamlit app...")
    try:
        port = os.getenv("STREAMLIT_SERVER_PORT", DEFAULT_STREAMLIT_PORT)
        headless = os.getenv("STREAMLIT_SERVER_HEADLESS", DEFAULT_STREAMLIT_HEADLESS)
        
        subprocess.run([
            "streamlit", "run", "streamlit_app.py",
            "--server.port", port,
            "--server.headless", headless
        ], check=True)
    except subprocess.CalledProcessError as e:
        logger.exception("Error running Streamlit app: %s", e)
        sys.exit(1)
    except FileNotFoundError:
        logger.error("Error: streamlit not found. Please install streamlit: pip install streamlit")
        sys.exit(1)


def run_both() -> None:
    """
    Run both API server and Streamlit app concurrently.
    
    This function starts both services in separate threads and waits for
    keyboard interrupt to gracefully shutdown all services.
    """
    logger.info("Starting both API server and Streamlit app...")
    
    api_thread = threading.Thread(target=run_api, name="API-Server")
    streamlit_thread = threading.Thread(target=run_streamlit, name="Streamlit-App")
    
    api_thread.daemon = True
    streamlit_thread.daemon = True
    
    api_thread.start()
    streamlit_thread.start()
    
    try:
        api_thread.join()
        streamlit_thread.join()
    except KeyboardInterrupt:
        logger.info("Stopping all services...")
        sys.exit(0)

def main() -> None:
    """
    Main entry point for the agent system launcher.
    
    Parses command line arguments and launches the requested service(s).
    """
    parser = argparse.ArgumentParser(
        description="Run Agent System components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py api          # Run FastAPI server only
  python run.py streamlit    # Run Streamlit app only
  python run.py all          # Run both services in parallel
        """
    )
    
    parser.add_argument(
        "service", 
        choices=["api", "streamlit", "all"], 
        help="Service to run: 'api' for FastAPI server, 'streamlit' for web UI, 'all' for both"
    )
    
    args = parser.parse_args()
    
    # Check for API key configuration
    if not check_api_key():
        logger.warning("Using default API key. Consider setting OPENAI_API_KEY environment variable.")
    
    # Launch the requested service
    try:
        if args.service == "api":
            run_api()
        elif args.service == "streamlit":
            run_streamlit()
        elif args.service == "all":
            run_both()
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main() 