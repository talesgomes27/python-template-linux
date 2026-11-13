# python-template-linux

Template universal e reprodutivo para projetos Python em qualquer distribuição Linux (Ubuntu, Debian, Fedora, Arch Linux, openSUSE, Alpine).

Baseado no ecossistema moderno da Astral: **`uv` + `pyproject.toml` (PEP 621) + `ruff` + `pytest`**.

## Por que esta abordagem?

Sistemas Linux frequentemente vinculam o Python do sistema a utilitários da distribuição (`apt`, `dnf`, `pacman`). Tentar modificar esses pacotes ou compilar versões com `pyenv` costuma quebrar dependências do sistema operacional ou exigir bibliotecas C ausentes (`libssl-dev`, `zlib1g-dev`).

Com o `uv`, os runtimes do Python são binários portáveis (*standalone builds* manylinux) baixados sob demanda para `~/.local/share/uv/python/`. Cada projeto declara sua versão exata no `.python-version` e suas dependências no `pyproject.toml`, gerando um lockfile multiplataforma determinístico (`uv.lock`).

## Pré-requisitos

Para sincronizar e usar o template, basta o binário do `uv`. O modo de criação
do gerador também exige `/usr/bin/python3` >=3.11, com `tomllib` da biblioteca
padrão, para compor configurações TOML. O gerador não instala nem altera esse
Python do sistema. Se ainda não possuir o `uv`, instale-o com um comando (sem sudo):

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

## Criar um novo projeto pelo gerador

Na raiz deste template, com Bash, uv, `/usr/bin/python3` >=3.11 e coreutils:

```bash
bash scripts/init_project.sh ../meu-projeto --python 3.12
bash scripts/init_project.sh ../analise --archetype ds
bash scripts/init_project.sh ../api-pedidos --archetype api --no-r --dry-run
```

O gerador instala o runtime, cria o projeto com `uv init`, adiciona as
dependências do arquétipo, compõe os padrões Ruff/pytest e sincroniza a
`.venv`. Essas etapas podem baixar arquivos.

| Arquétipo | Dependências além de pytest, pytest-cov e ruff |
|---|---|
| `universal` (padrão) | nenhuma |
| `ds` | polars, duckdb, pyarrow; ipykernel (dev); JupyterLab no grupo `notebook` |
| `api` | fastapi, pydantic, httpx |
| `cli` | typer, rich |

| Opção | Efeito |
|---|---|
| `-p, --python VERSAO` | Versão do Python a instalar e fixar (padrão 3.12). |
| `-a, --archetype TIPO` | Arquétipo; um valor desconhecido é recusado. |
| `--dry-run` | Mostra o plano sem criar nada nem chamar uv. |
| `--no-ide` | Não cria `.vscode/settings.json`. |
| `--no-r` | Não cria `.Renviron`/`.Rprofile` nem as regras R do `.gitignore`. |
| `--no-git` | Não inicializa repositório Git (nem `.gitignore` do `uv init`). |
| `--no-ci` | Não cria `.github/workflows/ci.yml`. |
| `--no-pre-commit` | Não cria `.pre-commit-config.yaml`. |
| `--version` | Mostra a versão do gerador. |

O que esperar:

- Arquivos existentes são preservados; o gerador só cria o que está ausente
  e recusa symlinks, hardlinks e tipos inesperados nos destinos que grava.
- Novos caminhos são privados (`umask 077`); não há chmod recursivo.
- Projetos sem `tests/` recebem `tests/test_smoke.py`.
- O `.envrc` criado (`use devshell_python`) integra com
  [Data Lab Dotfiles](https://github.com/talesgomes27/data-lab-dotfiles) e
  direnv; `direnv allow .` continua manual.
- Git é inicializado sem stage, commit ou push.
- Não há rollback da criação: uma falha pode deixar etapas já concluídas.

Para manutenção de um projeto existente (`--fix-permissions`, `--sync`,
`--allow-direnv`), JupyterLab no arquétipo `ds` e todas as garantias e
limites, veja a [referência do gerador](docs/generator.md).

## Migrar um projeto legado

`--migrate` reconhece requirements/pip-tools, Conda, Poetry, Pipenv,
setuptools estático e PEP 621/uv. Mostra o plano, pede confirmação, preserva
os manifestos e prepara uma nova `.venv` com backup da anterior.

```bash
bash scripts/init_project.sh /caminho/absoluto/projeto --migrate --dry-run
bash scripts/init_project.sh /caminho/absoluto/projeto --migrate --python 3.13.11
bash scripts/init_project.sh /caminho/absoluto/projeto --list-backups
bash scripts/init_project.sh /caminho/absoluto/projeto --restore ID --dry-run
```

Falha no sync, Ctrl+C, SIGTERM ou SIGHUP revertem a migração. `--restore ID`
desfaz uma migração concluída, guardando o estado substituído em
`.pyinit-backups/ID/after-restore`. Detalhes na
[referência do gerador](docs/generator.md#migrar-um-projeto-legado) e em
[formatos, limites e recuperação](docs/migration-recipe-for-agents.md).

## Desenvolver o gerador

`scripts/init_project.sh` continua sendo um único arquivo, mas é gerado: o
Bash vive em `scripts/init_project.sh.in` e o Python embutido em
`scripts/pyinit/*.py`, onde é verificado pelo Ruff e testado diretamente.
Não edite o arquivo gerado; altere as fontes e regrave-o:

```bash
uv run python scripts/build_init_project.py
uv run python scripts/build_init_project.py --check   # falha se desatualizado
```

A suíte de testes e o CI recusam um `init_project.sh` fora de sincronia.
As actions do CI gerado para novos projetos são copiadas, com SHA, de
`.github/workflows/ci.yml`; depois de atualizar uma action ali (inclusive em
um PR do Dependabot), regrave o gerador. O CI também roda ShellCheck no
script e exige cobertura mínima de 90% no pacote (`uv run pytest --cov`).

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
├── .github/workflows/ci.yml       # CI: Python 3.11 a 3.14, cobertura e ShellCheck
├── .github/dependabot.yml         # Atualizações semanais de actions e dependências uv
├── docs/                          # Documentação técnica e ADRs de arquitetura
│   ├── generator.md               # Referência completa do gerador pyinit
│   ├── migration-recipe-for-agents.md # Receita de migração de repositórios legados
│   ├── VALIDATION.md              # Registro de validações e limites
│   └── archive/                   # Artefatos do planejamento inicial, já concluído
├── scripts/
│   ├── init_project.sh            # Script pyinit distribuído (arquivo único, gerado)
│   ├── init_project.sh.in         # Modelo Bash do gerador
│   ├── pyinit/                    # Módulos Python embutidos no gerador
│   └── build_init_project.py      # Monta init_project.sh a partir das fontes
├── src/python_template_linux/     # Código fonte (src-layout)
├── tests/                         # Testes unitários com pytest
├── .gitignore                     # Filtro de arquivos efêmeros
├── .python-version                # Versão ativa do interpretador (ex: 3.12)
├── LICENSE                        # Licença MIT
├── AGENTS.md                      # Regras operacionais para agentes e LLMs
├── MIGRATION_RECIPE_FOR_AGENTS.md # Ponteiro para docs/migration-recipe-for-agents.md
├── pyproject.toml                 # Metadados e configurações (Ruff, Pytest)
└── README.md
```
