# Estrutura de Pastas e Convenções: python-template-linux

## 1. Árvore de Diretórios

```text
python-template-linux/
├── .github/
│   └── workflows/
│       └── ci.yml               # Pipeline de testes e linting no GitHub Actions
├── docs/                        # Documentação técnica e governança pré-código
│   ├── adr/
│   │   └── 0001-adocao-do-uv.md
│   ├── 00_archetype.md
│   ├── 02-PRD-and-specs.md
│   ├── 03-architecture-and-schema.md
│   ├── 04-scaffolding-and-conventions.md
│   ├── 05-implementation-plan.md
│   └── task.md
├── src/
│   └── python_template_linux/   # Código fonte seguindo o padrão src-layout
│       ├── __init__.py
│       └── core.py
├── tests/                       # Suíte de testes com pytest
│   ├── __init__.py
│   └── test_core.py
├── .gitignore                   # Exclusão estrita de artefatos efêmeros
├── .python-version              # Declaração do runtime padrão (ex: 3.12)
├── AGENTS.md                    # Diretrizes operacionais e comandos para IAs
├── pyproject.toml               # Configuração canônica de dependências e tooling
└── README.md                    # Documentação de uso e reprodução
```

## 2. Convenções Adotadas

- **Padrão `src-layout`:** Todo código produtivo reside sob `src/<nome_do_pacote>`. Isso impede que módulos locais sejam importados acidentalmente sem que o pacote esteja devidamente instalado no ambiente virtual.
- **Tipagem Estática:** Todo código Python novo deve incluir anotações de tipo (`type hints`).
- **Nomenclatura Semântica:** Módulos em `snake_case`, classes em `PascalCase`, constantes em `UPPER_CASE`.
- **Formatação de Commits:** Padrão Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`).

## 3. Gerador e integração opcional com direnv

`scripts/init_project.sh` prepara runtime, dependências, `.venv` e configurações
de IDE/R. A criação usa `umask 077`, preservando permissões já existentes e sem
chmod recursivo. Ancestrais com permissões incompatíveis com a guarda devem ser
revisados separadamente; o gerador não os corrige implicitamente.

Após `uv sync` bem-sucedido, cria `.envrc` com `use devshell_python` somente
quando o caminho não existe. Arquivos e links existentes são preservados.
Essa integração requer Data Lab Dotfiles configurado e revisão/autorização
manual com `direnv allow .` em cada projeto. O gerador não executa o `.envrc`,
autoriza diretórios ou configura whitelist. Git pode ser inicializado, mas
nenhum arquivo é colocado em stage e não há commit ou push automático.

Os testes em `tests/test_init_project.py` executam o script em HOME/XDG/cache
temporários. Instalação/resolução de pacotes são simuladas; a criação da `.venv`
usa uv real offline com interpretador já instalado. Git init é real; stage,
commit e push são interceptados para impedir alterações mesmo nos testes de
regressão. A suíte também confere `.envrc` existente, symlink pendente,
permissões sob umask permissiva, `.git` como arquivo e falha de sincronização.

Com as dependências deste template já preparadas, execute:

```bash
uv run --offline --no-sync pytest tests/test_init_project.py
```

A verificação local desta mudança passou nos dez testes da suíte completa,
Ruff check, Ruff format --check, ShellCheck e `bash -n`.

Um teste completo posterior executou o arquétipo `universal` com uv real,
HOME/XDG/cache temporários e download do CPython 3.12.15 e das dependências.
A aplicação gerada, Ruff, formatação e um pytest de smoke passaram. Na criação,
`.envrc` recebeu modo `600`; projeto, `.venv`, `.venv/bin`, `.vscode` e `.git`
receberam `700`. Direnv permaneceu sem autorização e Git sem stage, commits
ou remotos. Uma segunda execução offline preservou o conteúdo e o modo de
um `.envrc` existente e a identidade da `.venv`. O gerador e o HEAD do template
não foram alterados pelo teste.

Uma matriz posterior executou também `ds`, `api` e `cli` com uv real e
CPython 3.12.15, em projetos temporários separados, compartilhando somente
HOME, runtime e cache descartáveis. Instalação, aplicação gerada, Ruff,
formatação e dois pytest de smoke por projeto passaram (seis testes no total):

| Arquétipo | Verificação funcional da stack |
|---|---|
| `ds` | Parquet com Polars/PyArrow, soma SQL via DuckDB e importação de IPKernelApp. |
| `api` | Rota FastAPI com Pydantic, respostas 200/422 por HTTPX/ASGITransport dentro do processo. |
| `cli` | Comando Typer por CliRunner e formatação de texto Rich. |

Nos três projetos, `.envrc` foi criado com `600` e permaneceu sem autorização;
os diretórios conferidos receberam `700`. Git permaneceu sem stage, commits
ou remotos. A segunda execução offline preservou o `.envrc` existente e a
identidade da `.venv`. O gerador e o HEAD do template foram preservados.
Não houve consultas externas nos smokes funcionais; os downloads ficaram nas
etapas de instalação. CI remoto, outras versões de Python e outras plataformas
continuam fora desta evidência local.
