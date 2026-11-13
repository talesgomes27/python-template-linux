"""Fixtures compartilhadas pelos testes."""

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

PYINIT = Path(__file__).resolve().parents[1] / "scripts/pyinit"


@pytest.fixture
def load_script() -> Callable[[Path], ModuleType]:
    """Importa um arquivo Python avulso sem executar sua entrada de CLI."""

    def load(path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return load


@pytest.fixture
def pyinit(load_script: Callable[[Path], ModuleType]) -> Callable[[str], ModuleType]:
    """Carrega uma copia nova de um modulo embutido no gerador."""
    return lambda name: load_script(PYINIT / f"{name}.py")
