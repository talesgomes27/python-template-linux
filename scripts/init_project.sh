#!/usr/bin/env bash
# ==============================================================================
# init_project.sh: Inicializador universal de projetos Python para Linux
# Integração: uv, pyproject.toml (PEP 621), Ruff, Pytest, VS Code, Positron e RStudio
# ==============================================================================

set -euo pipefail
# Não herdar uma umask permissiva do terminal.
umask 077

UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
PYTHON_DEFAULT="3.12"
ARCHETYPE="universal"
TARGET_DIR="."
FIX_PERMISSIONS=false
SYNC=false
ALLOW_DIRENV=false
INIT_OPTIONS=false
TARGET_SET=false

show_help() {
    cat <<EOF
Uso: $(basename "$0") [DIRETORIO] [OPCOES]

Argumentos:
  DIRETORIO              Caminho ou nome da pasta do novo projeto (padrao: diretorio atual)

Opcoes:
  -p, --python VERSAO    Versao do Python a fixar (padrao: 3.12)
  -a, --archetype TIPO   Arquétipo do projeto:
                           universal : Base limpa com pytest e ruff (padrao)
                           ds        : Data Science (polars, duckdb, pyarrow, ipykernel)
                           api       : Web APIs (fastapi, pydantic, httpx)
                           cli       : Linha de comando (typer, rich)
  -h, --help             Exibe esta mensagem de ajuda

Manutencao de projeto existente (exige .venv; nao reinicializa o projeto):
  --fix-permissions      Revisa e repara permissoes via Data Lab Dotfiles
  --sync                 Com --fix-permissions, confirma e executa uv sync
  --allow-direnv         Com --fix-permissions, revisa e confirma direnv allow

DEVSHELL_BIN deve apontar para /caminho/data-lab-dotfiles/bin/devshell
quando devshell nao estiver no PATH. Requer Python do sistema em /usr/bin/python3.

Exemplos:
  $(basename "$0") meu-projeto
  $(basename "$0") analise-vendas --archetype ds --python 3.12
  $(basename "$0") api-pedidos -a api -p 3.13
  $(basename "$0") --fix-permissions
  $(basename "$0") --fix-permissions --sync --allow-direnv

Cria .envrc para Data Lab Dotfiles, preservando um arquivo existente.
Na criacao, revise-o e execute direnv allow . manualmente para habilitar a troca.
Na criacao, umask 077 protege novos caminhos; permissoes existentes sao preservadas.
Git pode ser inicializado, sem stage, commit ou push automatico.
EOF
}

fail() {
    echo "Erro: $*" >&2
    exit 2
}

confirm() {
    local answer
    printf '%s [s/N] ' "$1" >&2
    if ! IFS= read -r answer || [[ "${answer,,}" != s && "${answer,,}" != sim ]]; then
        echo "Etapa cancelada; as etapas seguintes nao foram executadas." >&2
        exit 1
    fi
}

# O Python do sistema inspeciona bytes/metadados sem importar codigo do projeto.
envrc_snapshot() {
    /usr/bin/python3 -I -B - "$1" "${2-}" <<'PY'
import hashlib
import os
import stat
import sys

try:
    fd = os.open('.envrc', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o022 or info.st_nlink != 1):
            raise ValueError('.envrc deve ser arquivo regular proprio, sem escrita de grupo/outros e sem hardlinks')
        data = stream.read()
    identity = (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink)
    token = hashlib.sha256(repr(identity).encode() + data).hexdigest()
    if sys.argv[1] == 'review':
        print('\n.envrc completo (controles escapados; nao executado):', file=sys.stderr)
        content = data.decode('utf-8', errors='backslashreplace')
        print(''.join(c if c.isprintable() or c in '\n\t' else ascii(c)[1:-1]
                      for c in content), file=sys.stderr)
        print(token)
    elif token != sys.argv[2]:
        raise ValueError('.envrc mudou apos a revisao; execute novamente e revise o novo conteudo')
except (OSError, ValueError) as exc:
    print(f'Erro: {exc}', file=sys.stderr)
    sys.exit(2)
PY
}

resolve_uv() {
    if command -v "$UV_BIN" &>/dev/null; then
        UV_CMD="$(command -v "$UV_BIN")"
    elif command -v uv &>/dev/null; then
        UV_CMD="$(command -v uv)"
    else
        fail "uv nao encontrado; instale-o explicitamente antes de continuar."
    fi
}

maintain_project() {
    local devshell_cmd direnv_cmd envrc_token workspace_dir project_dir
    local -a sync_args
    [[ -d "$TARGET_DIR" ]] || fail "o diretorio do projeto deve existir."
    if ! devshell_cmd=$(command -v "${DEVSHELL_BIN:-devshell}"); then
        fail "Data Lab CLI ausente. Defina DEVSHELL_BIN=/caminho/data-lab-dotfiles/bin/devshell."
    fi
    [[ "$devshell_cmd" == /* && -x "$devshell_cmd" ]] || fail "DEVSHELL_BIN deve ser um executavel com caminho absoluto."
    if "$SYNC"; then
        resolve_uv
        [[ -f "$TARGET_DIR/pyproject.toml" ]] || fail "--sync exige pyproject.toml existente."
        # --project ainda pode descobrir o workspace pai e alterar seu lock.
        if ! workspace_dir=$(
            unset VIRTUAL_ENV UV_PROJECT UV_WORKING_DIR
            "$UV_CMD" workspace dir --no-cache --offline --project "$TARGET_DIR"
        ); then
            fail "nao foi possivel inspecionar o workspace; --sync exige uv com workspace dir."
        fi
        project_dir=$(cd -- "$TARGET_DIR" && pwd -P)
        [[ "$workspace_dir" == "$project_dir" ]] || fail "--sync recusado: raiz do workspace fora do projeto ($workspace_dir). Administre esse workspace explicitamente."
    fi
    if "$ALLOW_DIRENV"; then
        [[ -x /usr/bin/python3 ]] || fail "Python do sistema ausente em /usr/bin/python3."
        if ! direnv_cmd=$(command -v direnv); then
            fail "direnv nao encontrado; instale-o explicitamente antes de continuar."
        fi
    fi
    # O backend valida o caminho original, incluindo symlinks e componentes .. .
    "$devshell_cmd" project fix-permissions --path "$TARGET_DIR"
    "$devshell_cmd" project doctor --path "$TARGET_DIR"
    cd -- "$TARGET_DIR"
    if "$SYNC"; then
        sync_args=(sync --project "$PWD" --python "$PWD/.venv/bin/python" --no-python-downloads)
        if [[ -e uv.lock || -L uv.lock ]]; then
            sync_args+=(--locked)
        else
            echo "Sem uv.lock: a sincronizacao podera criar o lock." >&2
        fi
        printf 'Comando solicitado: ' >&2
        printf '%q ' "$UV_CMD" "${sync_args[@]}" >&2
        printf '\n' >&2
        confirm "Sincronizar dependencias nesta .venv? Pode instalar/remover pacotes e executar builds do projeto."
        (
            unset VIRTUAL_ENV UV_PROJECT UV_WORKING_DIR
            # Nunca usar um destino compartilhado herdado do terminal.
            export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
            "$UV_CMD" "${sync_args[@]}"
        )
        "$devshell_cmd" project doctor --path "$PWD"
    fi
    if "$ALLOW_DIRENV"; then
        envrc_token=$(envrc_snapshot review)
        confirm "Autorizar este .envrc com direnv allow .? Seu conteudo podera executar comandos."
        envrc_snapshot verify "$envrc_token"
        "$direnv_cmd" allow .
    fi
    echo "Manutencao concluida. Execute direnv reload para repetir a selecao do ambiente."
}

# Parsing de argumentos
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p | --python)
            [[ $# -ge 2 && "$2" != -* ]] || fail "--python exige uma versao."
            INIT_OPTIONS=true
            PYTHON_DEFAULT="$2"
            shift 2
            ;;
        -a | --archetype)
            [[ $# -ge 2 && "$2" != -* ]] || fail "--archetype exige um tipo."
            INIT_OPTIONS=true
            ARCHETYPE="$2"
            shift 2
            ;;
        --fix-permissions)
            FIX_PERMISSIONS=true
            shift
            ;;
        --sync)
            SYNC=true
            shift
            ;;
        --allow-direnv)
            ALLOW_DIRENV=true
            shift
            ;;
        -h | --help)
            show_help
            exit 0
            ;;
        -*)
            echo "Erro: Opcao desconhecida $1" >&2
            show_help
            exit 1
            ;;
        *)
            "$TARGET_SET" && fail "informe somente um diretorio."
            TARGET_DIR="$1"
            TARGET_SET=true
            shift
            ;;
    esac
done

if "$FIX_PERMISSIONS"; then
    "$INIT_OPTIONS" && fail "--fix-permissions nao aceita --python ou --archetype."
    maintain_project
    exit 0
fi
if "$SYNC" || "$ALLOW_DIRENV"; then
    fail "--sync e --allow-direnv exigem --fix-permissions."
fi
resolve_uv

echo "==> Configurando projeto Python..."
echo "    Diretorio: $TARGET_DIR"
echo "    Python:    $PYTHON_DEFAULT"
echo "    Arquetipo: $ARCHETYPE"

# 1. Criar e entrar no diretorio
if [ "$TARGET_DIR" != "." ]; then
    mkdir -p "$TARGET_DIR"
    cd "$TARGET_DIR"
fi

PROJECT_NAME="$(basename "$PWD")"

# 2. Garantir runtime do Python
echo "==> Verificando runtime Python $PYTHON_DEFAULT..."
"$UV_CMD" python install "$PYTHON_DEFAULT"

# 3. Inicializar projeto com uv
if [ ! -f "pyproject.toml" ]; then
    echo "==> Inicializando pyproject.toml e estrutura base..."
    "$UV_CMD" init --app --package --python "$PYTHON_DEFAULT" --name "$PROJECT_NAME"
fi

# 4. Fixar versao no .python-version
"$UV_CMD" python pin "$PYTHON_DEFAULT"

# 5. Adicionar dependencias de desenvolvimento
echo "==> Configurando ferramentas de teste e lint..."
"$UV_CMD" add --dev pytest pytest-cov ruff

# 6. Adicionar pacotes especificos de cada arquetipo
case "$ARCHETYPE" in
    ds)
        echo "==> Adicionando stack de Data Science (polars, duckdb, pyarrow, ipykernel)..."
        "$UV_CMD" add polars duckdb pyarrow
        "$UV_CMD" add --dev ipykernel
        ;;
    api)
        echo "==> Adicionando stack de APIs (fastapi, pydantic, httpx)..."
        "$UV_CMD" add fastapi pydantic httpx
        ;;
    cli)
        echo "==> Adicionando stack de CLI (typer, rich)..."
        "$UV_CMD" add typer rich
        ;;
    universal)
        # Nenhuma dependencia extra alem das de dev
        ;;
    *)
        echo "Aviso: Arquetipo desconhecido '$ARCHETYPE'. Usando universal." >&2
        ;;
esac

# 7. Injetar configuracoes do Ruff e Pytest no pyproject.toml se ausentes
if ! grep -q '\[tool\.ruff\]' pyproject.toml; then
    cat >>pyproject.toml <<'EOF'

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra -q --strict-markers"
EOF
fi

# 8. Integracao com IDEs (VS Code e Positron)
echo "==> Configurando integracao para VS Code e Positron (.vscode/settings.json)..."
mkdir -p .vscode
cat >.vscode/settings.json <<'EOF'
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
EOF

# 9. Integracao com RStudio e Quarto CLI (.Renviron e .Rprofile)
echo "==> Configurando integracao para RStudio e Quarto (.Renviron e .Rprofile)..."
cat >.Renviron <<'EOF'
RETICULATE_PYTHON=.venv/bin/python
EOF

cat >.Rprofile <<'EOF'
# Vincula o reticulate ao ambiente virtual gerenciado pelo uv
if (file.exists(".venv/bin/python")) {
  Sys.setenv(RETICULATE_PYTHON = file.path(getwd(), ".venv/bin/python"))
}
EOF

# 10. Sincronizar ambiente virtual
echo "==> Criando e sincronizando .venv..."
"$UV_CMD" sync

# 11. Preparar a integracao opcional com direnv sem conceder autorizacao.
if [ -e ".envrc" ] || [ -L ".envrc" ]; then
    echo "==> .envrc existente preservado; revise a integracao manualmente."
else
    (
        set -o noclobber
        printf '%s\n' 'use devshell_python' >.envrc
    )
fi

# 12. Ajustar .gitignore
if [ -f ".gitignore" ]; then
    if ! grep -q '\.Renviron' .gitignore; then
        cat >>.gitignore <<'EOF'

# RStudio e reticulate locais
.Rhistory
.RData
.Rproj.user/
EOF
    fi
fi

# 13. Inicializar Git caso ainda nao exista, inclusive em worktrees.
if [ ! -e ".git" ] && [ ! -L ".git" ] && command -v git &>/dev/null; then
    echo "==> Inicializando repositorio Git..."
    git init -b main
fi

echo ""
echo "=============================================================================="
echo " Projeto configurado com sucesso!"
echo " Pasta: $(pwd)"
echo " Interpretador: $(pwd)/.venv/bin/python"
echo "=============================================================================="
echo ""
echo "Como usar:"
echo "  uv run pytest                     # Executar testes"
echo "  uv run ruff check .               # Verificar linter"
echo "  uv run python <script.py>         # Executar sem precisar de 'source venv'"
echo ""
echo "Troca automatica opcional (Data Lab Dotfiles + direnv):"
echo "  Revise o .envrc completo; se ja existia, inclua use devshell_python quando apropriado."
echo "  direnv allow .                   # Autorizacao manual apos a revisao"
echo "  A troca ocorre no proximo prompt; ancestrais existentes precisam ser seguros."
echo "Nenhum arquivo foi colocado em stage e nenhum commit ou push foi executado."
echo ""
echo "Compatibilidade de IDEs detectada:"
echo "  - VS Code e Positron: .vscode/settings.json configurado."
echo "  - RStudio e Quarto:   .Renviron e .Rprofile apontam RETICULATE_PYTHON para .venv."
echo ""
