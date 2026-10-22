"""Módulo central com utilitários de diagnóstico de ambiente."""

import platform
import sys
from typing import Any


def system_diagnostic() -> dict[str, Any]:
    """Retorna dados estruturados do runtime Python e do sistema host."""
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "system": platform.system(),
        "release": platform.release(),
        "architecture": platform.machine(),
        "is_virtual_env": sys.prefix != sys.base_prefix,
    }


def format_environment_info() -> str:
    """Gera uma string legível para depuração rápida no terminal."""
    info = system_diagnostic()
    env_type = "Isolado (.venv)" if info["is_virtual_env"] else "Global / Sistema"
    return (
        f"Python {info['python_version']} ({info['python_implementation']}) "
        f"no {info['system']} {info['architecture']} | Ambiente: {env_type}"
    )


if __name__ == "__main__":
    print(format_environment_info())
