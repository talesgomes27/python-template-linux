# Diretrizes do Repositório para Agentes de IA (AGENTS.md)

Este repositório adota a arquitetura canônica de Python moderno para Linux baseada em `uv`, `pyproject.toml` (PEP 621), `ruff` e `pytest`.

## 1. Regras de Execução e Dependências

- **Proibido:** Nunca execute `pip install`, `poetry`, `pipenv` ou ativação manual de ambiente com `source .venv/bin/activate`.
- **Adicionar pacotes de produção:** `uv add <nome-do-pacote>`
- **Adicionar pacotes de desenvolvimento:** `uv add --dev <nome-do-pacote>`
- **Execução isolada:** Sempre execute scripts, testes e ferramentas via `uv run`:
  - `uv run python -m python_template_linux.core`
  - `uv run pytest`
  - `uv run ruff check . --fix`
  - `uv run ruff format .`

## 2. Gestão de Runtimes de Python

- Para alternar ou fixar a versão de Python deste projeto:
  ```bash
  uv python install <versao>
  uv python pin <versao>
  uv sync
  ```
- O arquivo `.python-version` na raiz define a versão utilizada pelo `uv run` e `uv sync`.

## 3. Qualidade de Código e Testes

- Todo código novo deve incluir type hints e testes unitários sob `tests/`.
- Antes de submeter ou finalizar qualquer alteração, certifique-se de que os comandos a seguir passam sem erros:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uv run pytest
  ```

## 4. Gerador `scripts/init_project.sh`

- O arquivo é **gerado**; nunca o edite diretamente. As fontes são
  `scripts/init_project.sh.in` (Bash) e `scripts/pyinit/*.py` (Python embutido).
- Após alterar as fontes, execute `uv run python scripts/build_init_project.py`
  e inclua o arquivo regravado no mesmo commit.
- O mesmo vale após alterar a versão em `pyproject.toml` ou as actions fixadas
  em `.github/workflows/ci.yml`, que são copiadas para o arquivo gerado.

## 5. Migração de Repositórios Legados

Para instruções completas sobre como migrar projetos que utilizam `requirements.txt`, `pipenv`, `poetry` ou `environment.yml` para este padrão, consulte [docs/migration-recipe-for-agents.md](docs/migration-recipe-for-agents.md).
