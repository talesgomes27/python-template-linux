# python-template-linux

Template universal e reprodutivo para projetos Python em qualquer distribuição Linux (Ubuntu, Debian, Fedora, Arch Linux, openSUSE, Alpine).

Baseado no ecossistema moderno da Astral: **`uv` + `pyproject.toml` (PEP 621) + `ruff` + `pytest`**.

## Por que esta abordagem?

Sistemas Linux frequentemente vinculam o Python do sistema a utilitários da distribuição (`apt`, `dnf`, `pacman`). Tentar modificar esses pacotes ou compilar versões com `pyenv` costuma quebrar dependências do sistema operacional ou exigir bibliotecas C ausentes (`libssl-dev`, `zlib1g-dev`).

Com o `uv`, os runtimes do Python são binários portáveis (*standalone builds* manylinux) baixados sob demanda para `~/.local/share/uv/python/`. Cada projeto declara sua versão exata no `.python-version` e suas dependências no `pyproject.toml`, gerando um lockfile multiplataforma determinístico (`uv.lock`).

## Pré-requisitos

Apenas o binário do `uv` precisa estar instalado na máquina. Se ainda não possuir o `uv`, instale-o com um comando (sem sudo):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

O instalador coloca o executável em `~/.local/bin/uv`.

## Início Rápido

### 1. Clonar e sincronizar o ambiente

```bash
git clone <url-do-seu-repositorio>
cd python-template-linux
uv sync
```

O `uv sync` realiza três ações automaticamente:
1. Lê o `.python-version` (padrão: 3.12). Se essa versão não estiver instalada na máquina, baixa o binário imediatamente.
2. Cria o ambiente virtual isolado em `.venv/`.
3. Instala as dependências travadas no `uv.lock`.

### 2. Executar o código

Não é necessário ativar o ambiente virtual (`source .venv/bin/activate`). O comando `uv run` executa qualquer comando dentro do contexto correto:

```bash
uv run python -m python_template_linux.core
```

### 3. Executar testes e checagem de qualidade

```bash
# Rodar suíte de testes com pytest
uv run pytest

# Verificar conformidade de linter (Ruff)
uv run ruff check .

# Formatar o código automaticamente
uv run ruff format .
```

## Como alternar a versão do Python no projeto

Se outro projeto precisar de uma versão específica (exemplo: Python 3.11 ou 3.13), execute na raiz do repositório:

```bash
# 1. Instalar o runtime desejado (se ainda não baixado)
uv python install 3.13

# 2. Fixar no projeto local (atualiza o arquivo .python-version)
uv python pin 3.13

# 3. Recriar/sincronizar o ambiente virtual para a nova versão
uv sync
```

Para listar todos os interpretadores Python disponíveis e instalados na sua máquina:

```bash
uv python list
```

## Gerenciamento de Dependências

```bash
# Adicionar pacote de produção
uv add httpx pydantic

# Adicionar pacote de desenvolvimento
uv add --dev ipykernel mypy

# Remover pacote
uv remove httpx

# Atualizar todas as dependências respeitando os limites do pyproject.toml
uv lock --upgrade
```

## Estrutura do Repositório

```text
python-template-linux/
├── .github/workflows/ci.yml       # Esteira de CI testando Python 3.11, 3.12 e 3.13
├── docs/                          # Documentação técnica e ADRs de arquitetura
│   └── migration-recipe-for-agents.md # Receita detalhada para migração de repositórios legados
├── scripts/
│   └── init_project.sh            # Script utilitário pyinit para novos projetos
├── src/python_template_linux/     # Código fonte (src-layout)
├── tests/                         # Testes unitários com pytest
├── .gitignore                     # Filtro de arquivos efêmeros
├── .python-version                # Versão ativa do interpretador (ex: 3.12)
├── AGENTS.md                      # Regras operacionais para agentes e LLMs
├── MIGRATION_RECIPE_FOR_AGENTS.md # Atalho para o playbook de migração para IAs
├── pyproject.toml                 # Metadados e configurações (Ruff, Pytest)
└── README.md
```
