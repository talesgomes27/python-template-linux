# Plano de Implementação e Verificação: python-template-linux

## 1. Grafo de Precedência Técnica

1. Criação do arquivo de pinagem de runtime (`.python-version`).
2. Configuração declarativa do projeto (`pyproject.toml`) com metadados PEP 621, Ruff e pytest.
3. Criação de `.gitignore` abrangente para ecossistema Python moderno.
4. Inicialização do código fonte base (`src/python_template_linux/core.py`) e pacote.
5. Implementação de teste unitário verificável (`tests/test_core.py`).
6. Configuração da esteira de CI (`.github/workflows/ci.yml`).
7. Criação do arquivo de guardrails de IA (`AGENTS.md`) e documentação principal (`README.md`).
8. Inicialização do repositório Git local (`git init`).
9. Execução da sincronização e validação de qualidade:
   - `uv sync`
   - `uv run ruff check .`
   - `uv run ruff format --check .`
   - `uv run pytest`

## 2. Comandos de Verificação Automatizada

```bash
# Sincronização do ambiente
uv sync

# Verificação estática e formatação
uv run ruff check .
uv run ruff format --check .

# Execução da suíte de testes
uv run pytest -v
```
