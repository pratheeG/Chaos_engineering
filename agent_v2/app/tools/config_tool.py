"""Tools for reading fault configurations."""

import os
from langchain_core.tools import tool

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fault_configs")

@tool
def list_fault_configs() -> str:
    """Lists all available fault YAML configuration files in the base directory.
    Use this to find templates for creating new chaos experiments."""
    try:
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
        files = [f for f in os.listdir(CONFIG_DIR) if f.endswith((".yaml", ".yml"))]
        if not files:
            return "No fault configuration files found."
        return "Available files:\n" + "\n".join(f"- {f}" for f in files)
    except Exception as e:
        return f"Error listing config files: {e}"

@tool
def read_fault_config(file_name: str) -> str:
    """Reads the contents of a fault configuration YAML file from the fault_configs directory.
    Use this to get the base manifest which you can then customize before creating the experiment."""
    try:
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
        path = os.path.join(CONFIG_DIR, file_name)
        if not os.path.exists(path):
            return f"Error: File {file_name} does not exist in {CONFIG_DIR}"
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {file_name}: {e}"

config_tools = [
    list_fault_configs,
    read_fault_config,
]
