#!/usr/bin/env bash
# ==============================================================================
# init_project.sh: Inicializador universal de projetos Python para Linux
# Integração: uv, pyproject.toml (PEP 621), Ruff, Pytest, VS Code, Positron e RStudio
# ==============================================================================

set -euo pipefail

UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
PYTHON_DEFAULT="3.12"
ARCHETYPE="universal"
TARGET_DIR="."

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

Exemplos:
  $(basename "$0") meu-projeto
  $(basename "$0") analise-vendas --archetype ds --python 3.12
  $(basename "$0") api-pedidos -a api -p 3.13
EOF
}

# Parsing de argumentos
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--python)
            PYTHON_DEFAULT="$2"
            shift 2
            ;;
        -a|--archetype)
            ARCHETYPE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -*)
            echo "Erro: Opcao desconhecida $1" >&2
            show_help
            exit 1
            ;;
        *)
            TARGET_DIR="$1"
            shift
            ;;
    esac
done

if ! command -v "$UV_BIN" &>/dev/null && ! command -v uv &>/dev/null; then
    echo "Erro: uv nao encontrado. Instale com: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

if command -v "$UV_BIN" &>/dev/null; then
    UV_CMD="$UV_BIN"
else
    UV_CMD="$(command -v uv)"
fi

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
    cat >> pyproject.toml <<'EOF'

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
cat > .vscode/settings.json <<'EOF'
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
cat > .Renviron <<'EOF'
RETICULATE_PYTHON=.venv/bin/python
EOF

cat > .Rprofile <<'EOF'
# Vincula o reticulate ao ambiente virtual gerenciado pelo uv
if (file.exists(".venv/bin/python")) {
  Sys.setenv(RETICULATE_PYTHON = file.path(getwd(), ".venv/bin/python"))
}
EOF

# 10. Sincronizar ambiente virtual
echo "==> Criando e sincronizando .venv..."
"$UV_CMD" sync

# 11. Ajustar .gitignore
if [ -f ".gitignore" ]; then
    if ! grep -q '\.Renviron' .gitignore; then
        cat >> .gitignore <<'EOF'

# RStudio e reticulate locais
.Rhistory
.RData
.Rproj.user/
EOF
    fi
fi

# 12. Inicializar Git caso ainda nao exista
if [ ! -d ".git" ] && command -v git &>/dev/null; then
    echo "==> Inicializando repositorio Git..."
    git init -b main
    git add .
    git commit -m "feat: initialize python project with uv, ruff, pytest and ide settings"
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
echo "Compatibilidade de IDEs detectada:"
echo "  - VS Code e Positron: .vscode/settings.json configurado."
echo "  - RStudio e Quarto:   .Renviron e .Rprofile apontam RETICULATE_PYTHON para .venv."
echo ""
