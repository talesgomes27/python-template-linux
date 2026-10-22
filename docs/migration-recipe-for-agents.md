# Receita de Migração para Agentes de IA (Antigravity, Claude Code, Codex, Cursor)

Este documento define o protocolo estrito para que um agente de IA migre qualquer repositório Python legado para o padrão canônico moderno: **`uv` + `pyproject.toml` (PEP 621) + `Ruff` + `pytest`**.

---

## Prompt para Disparo (Copie e Cole para o Agente)

Quando abrir um repositório legado em qualquer ferramenta de IA, envie o seguinte comando:

```text
Atue como engenheiro de software sênior. Migre o ambiente Python deste repositório para a stack moderna: uv + pyproject.toml (PEP 621) + Ruff + pytest, garantindo compatibilidade com distribuições Linux e IDEs (VS Code, Positron, RStudio). Siga rigorosamente o protocolo descrito abaixo:
1. Inspecione e faça o inventário das dependências existentes (requirements.txt, Pipfile, poetry.lock, environment.yml ou setup.py).
2. Não perca nenhuma dependência de produção nem versão restritiva necessária. Separe dependências de runtime das ferramentas de desenvolvimento (testes, linters).
3. Elimine ferramentas redundantes (black, flake8, isort, pipenv, poetry, virtualenv avulso) e centralize as regras no pyproject.toml usando Ruff.
4. Crie .python-version, configure .vscode/settings.json, .Renviron e .Rprofile apontando para .venv/bin/python.
5. Execute uv sync, rode uv run ruff check . --fix, uv run ruff format . e valide a suíte com uv run pytest.
6. Nunca sugira ou use 'source .venv/bin/activate' nem 'pip install'. Use sempre 'uv run'.
7. Finalize com um commit semântico no Git.
```

---

## Protocolo Operacional para o Agente

### Fase 1: Diagnóstico e Inventário
O agente deve inspecionar o repositório antes de alterar arquivos:
1. Localizar arquivos de configuração legados:
   - `requirements.txt`, `requirements-dev.txt`, `dev-requirements.txt`
   - `Pipfile`, `Pipfile.lock`
   - `pyproject.toml` no formato arcaico do Poetry (`[tool.poetry]`) ou Flit
   - `setup.py`, `setup.cfg`
   - `environment.yml` (Conda)
2. Identificar a versão mínima de Python suportada no código ou documentação. Se não especificada, adotar `3.12`.
3. Mapear:
   - **Pacotes de produção:** bibliotecas necessárias para rodar a aplicação/análise.
   - **Pacotes de desenvolvimento:** linters, test runners, formatadores e kernels (`pytest`, `black`, `flake8`, `isort`, `ipykernel`, `mypy`).

---

### Fase 2: Purga e Limpeza do Legado
Remover artefatos obsoletos que geram inconsistência ou conflito:
- Remover `.venv` antigo do sistema (pois pode estar corrompido ou apontando para caminhos absolutos da máquina anterior):
  ```bash
  rm -rf .venv
  ```
- Remover lockfiles e configurações obsoletas:
  - `Pipfile`, `Pipfile.lock`
  - `poetry.lock` (se não for mais usado)
  - `.flake8`, `.isort.cfg`, `tox.ini` (quando substituídos por Ruff)
- Manter o `requirements.txt` original temporariamente renomeado como `requirements.txt.bak` até validação final.

---

### Fase 3: Estruturação com PEP 621 e `uv`

1. **Fixar runtime:**
   Criar arquivo `.python-version` na raiz do projeto contendo a versão desejada (exemplo: `3.12`).
   ```bash
   uv python pin 3.12
   ```

2. **Inicializar `pyproject.toml` (se inexistente):**
   ```bash
   uv init --bare
   ```

3. **Migrar dependências de produção:**
   Para cada dependência identificada, adicionar via `uv`:
   ```bash
   # Exemplo a partir de lista ou requirements legado
   uv add $(cat requirements.txt | grep -v '^#' | grep -v '^-')
   ```

4. **Migrar ferramentas de desenvolvimento:**
   Substituir `black`, `flake8`, `isort` e `autopep8` exclusivamente por `ruff`:
   ```bash
   uv add --dev pytest pytest-cov ruff
   ```
   Se o projeto contiver notebooks Jupyter/Quarto, adicionar:
   ```bash
   uv add --dev ipykernel
   ```

5. **Configurar ferramentas no `pyproject.toml`:**
   Garantir que as seguintes seções existam no arquivo:
   ```toml
   [tool.ruff]
   line-length = 88
   target-version = "py312"

   [tool.ruff.lint]
   select = ["E", "F", "I", "B", "UP"]
   ignore = []

   [tool.ruff.format]
   quote-style = "double"
   indent-style = "space"

   [tool.pytest.ini_options]
   minversion = "8.0"
   testpaths = ["tests"]
   addopts = "-ra -q --strict-markers"
   ```

---

### Fase 4: Integração com IDEs (VS Code, Positron e RStudio)

Criar configurações para que editores no Linux selecionem o interpretador automaticamente:

1. **`.vscode/settings.json` (para VS Code e Positron):**
   ```json
   {
     "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
     "[python]": {
       "editor.defaultFormatter": "charliermarsh.ruff",
       "editor.formatOnSave": true,
       "editor.codeActionsOnSave": {
         "source.fixAll": "explicit",
         "source.organizeImports": "explicit"
       }
     }
   }
   ```

2. **`.Renviron` (para RStudio e Quarto CLI):**
   ```bash
   RETICULATE_PYTHON=.venv/bin/python
   ```

3. **`.Rprofile`:**
   ```r
   if (file.exists(".venv/bin/python")) {
     Sys.setenv(RETICULATE_PYTHON = file.path(getwd(), ".venv/bin/python"))
   }
   ```

4. **Atualizar `.gitignore`:**
   Garantir que `.venv/`, `.ruff_cache/`, `.pytest_cache/`, `.coverage`, `__pycache__/` e `.Rproj.user/` estejam listados.

---

### Fase 5: Sincronização, Refatoração de Lint e Validação

1. **Sincronizar o ambiente:**
   ```bash
   uv sync
   ```

2. **Formatar e sanitizar código:**
   ```bash
   uv run ruff check . --fix
   uv run ruff format .
   ```

3. **Executar os testes existentes:**
   ```bash
   uv run pytest
   ```

4. **Remover arquivos temporários de backup:**
   ```bash
   rm -f requirements.txt.bak
   ```

---

### Fase 6: Criação do `AGENTS.md` e Versionamento

1. Adicionar o arquivo `AGENTS.md` na raiz para blindar futuros agentes de IA contra comandos legados (`pip install`, `virtualenv`, ativações com `source`).
2. Registrar a migração no Git:
   ```bash
   git add .
   git commit -m "refactor: migrate python environment to modern uv, pyproject.toml, ruff and pytest"
   ```
