#!/usr/bin/env bash
# ARQUIVO GERADO por scripts/build_init_project.py: nao edite diretamente.
# Fontes: scripts/init_project.sh.in e scripts/pyinit/*.py
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
MIGRATE=false
DRY_RUN=false
PYTHON_SET=false
ARCHETYPE_SET=false
CREATE_ONLY=false
WITH_IDE=true
WITH_R=true
WITH_GIT=true
RESTORE_ID=""
LIST_BACKUPS=false
PYINIT_VERSION="0.2.0"

show_help() {
    cat <<EOF
Uso: $(basename "$0") [DIRETORIO] [OPCOES]

Argumentos:
  DIRETORIO              Caminho ou nome da pasta do novo projeto (padrao: diretorio atual)

Opcoes:
  -p, --python VERSAO    Versao do Python a fixar (padrao: 3.12)
  -a, --archetype TIPO   Arquétipo do projeto:
                           universal : Base limpa com pytest e ruff (padrao)
                           ds        : Data Science (polars, duckdb, pyarrow, ipykernel; JupyterLab no grupo notebook)
                           api       : Web APIs (fastapi, pydantic, httpx)
                           cli       : Linha de comando (typer, rich)
  --no-ide               Nao cria .vscode/settings.json
  --no-r                 Nao cria .Renviron/.Rprofile nem regras R no .gitignore
  --no-git               Nao inicializa repositorio Git
  --dry-run              Mostra o plano de criacao sem criar nada nem chamar uv
  -V, --version          Exibe a versao do gerador
  -h, --help             Exibe esta mensagem de ajuda

Migracao de projeto legado (Python do sistema >=3.11):
  --migrate              Detecta formato, revisa plano e migra com backup
  --dry-run              Com --migrate ou --restore, apenas diagnostica
  --python VERSAO        Na migracao, usa CPython gerenciado ja instalado
                         (padrao: versao do geral, fallback 3.12)

Backups de migracao (Python do sistema >=3.11; nao usa uv):
  --list-backups         Lista os backups em .pyinit-backups como JSON
  --restore ID           Revisa e restaura arquivos e .venv de um backup;
                         o estado atual substituido fica em after-restore

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
  $(basename "$0") projeto-legado --migrate --dry-run
  $(basename "$0") projeto-legado --migrate --python 3.13.11
  $(basename "$0") projeto-legado --list-backups
  $(basename "$0") projeto-legado --restore ID --dry-run
  $(basename "$0") api-pedidos -a api --no-r --dry-run
  $(basename "$0") --fix-permissions
  $(basename "$0") --fix-permissions --sync --allow-direnv

Cria .envrc para Data Lab Dotfiles, preservando um arquivo existente.
Na criacao, revise-o e execute direnv allow . manualmente para habilitar a troca.
Na criacao, umask 077 protege novos caminhos; permissoes existentes sao preservadas.
Configuracoes IDE/R regulares de vinculo unico sao preservadas.
Symlinks, hardlinks e tipos inesperados nesses destinos bloqueiam antes do uv.
Criacao usa a .venv local; projetos pais e ambientes redirecionados sao recusados.
Criacao recusa caminhos fisicos terminados em LF, inclusive destino . e aliases.
Criacao exige /usr/bin/python3 >=3.11 para compor Ruff/pytest com tomllib.
Configuracoes Ruff/pytest existentes sao preservadas; somente familias ausentes recebem padroes.
Falhas podem preservar etapas anteriores; nao ha rollback automatico da criacao.
Sem tests/ existente, cria tests/test_smoke.py; arquetipo desconhecido e recusado.
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
"""Revisa e confere o .envrc do diretorio atual sem executa-lo.

Uso: envrc_snapshot.py review | verify TOKEN
"""

import hashlib
import os
import stat
import sys


def snapshot() -> tuple[str, bytes]:
    """Retorna o token de identidade/conteudo e os bytes do .envrc."""
    fd = os.open(".envrc", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o022
            or info.st_nlink != 1
        ):
            raise ValueError(
                ".envrc deve ser arquivo regular proprio, "
                "sem escrita de grupo/outros e sem hardlinks"
            )
        data = stream.read()
    identity = (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
    )
    return hashlib.sha256(repr(identity).encode() + data).hexdigest(), data


def escaped(data: bytes) -> str:
    """Torna visiveis os caracteres de controle, preservando LF e TAB."""
    content = data.decode("utf-8", errors="backslashreplace")
    return "".join(
        c if c.isprintable() or c in "\n\t" else ascii(c)[1:-1] for c in content
    )


def main(argv: list[str]) -> int:
    try:
        token, data = snapshot()
        if argv[1] == "review":
            print(
                "\n.envrc completo (controles escapados; nao executado):",
                file=sys.stderr,
            )
            print(escaped(data), file=sys.stderr)
            print(token)
        elif token != argv[2]:
            raise ValueError(
                ".envrc mudou apos a revisao; "
                "execute novamente e revise o novo conteudo"
            )
    except (OSError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
PY
}

resolve_uv() {
    # type -P considera somente arquivos executaveis, nunca funcoes ou builtins.
    if ! UV_CMD=$(type -P "$UV_BIN") && ! UV_CMD=$(type -P uv); then
        fail "uv nao encontrado; instale-o explicitamente antes de continuar."
    fi
    [[ "$UV_CMD" == /* ]] || UV_CMD="$PWD/$UV_CMD"
}

creation_uv() (
    local status
    unset UV_PROJECT UV_WORKING_DIR UV_WORKING_DIRECTORY UV_ACTIVE UV_PYTHON
    unset VIRTUAL_ENV CONDA_PREFIX CONDA_DEFAULT_ENV PYTHONHOME PYTHONPATH
    if UV_PROJECT_ENVIRONMENT="$creation_project/.venv" "$UV_CMD" "$@"; then
        return 0
    else
        status=$?
        echo "Preparo interrompido: etapas anteriores podem permanecer aplicadas; nenhuma reversao automatica foi executada." >&2
        return "$status"
    fi
)

inspect_creation_scope() {
    local parent=${creation_project%/*}
    [[ -n "$parent" ]] || parent=/
    while :; do
        if [[ -d "$parent" && ! -x "$parent" ]]; then
            fail "Diretorio pai sem permissao de busca: $parent."
        fi
        # Sem parser TOML novo: nao descobrir/administrar projetos pais implicitamente.
        if [[ -e "$parent/pyproject.toml" || -L "$parent/pyproject.toml" ]]; then
            fail "Projeto/workspace pai detectado em $parent; administre esse escopo explicitamente com uv. Nenhuma etapa de criacao foi executada."
        fi
        [[ "$parent" != / ]] || break
        parent=${parent%/*}
        [[ -n "$parent" ]] || parent=/
    done
}

inspect_venv_paths() {
    local directory=$1 path name resolved
    [[ ! -L "$directory" && -d "$directory" && -r "$directory" && -x "$directory" ]] || fail ".venv com diretorio irregular ou sem acesso: $directory."
    for path in "$directory"/* "$directory"/.[!.]* "$directory"/..?*; do
        [[ -e "$path" || -L "$path" ]] || continue
        if [[ -L "$path" ]]; then
            name=${path##*/}
            if [[ ${path%/*} == "$creation_project/.venv/bin" && ("$name" == python || "$name" == python3 || "$name" =~ ^python3\.[0-9]+$) ]]; then
                [[ -f "$path" && -x "$path" ]] || fail "Interpretador da .venv irregular: $path."
                continue
            fi
            resolved=$(realpath -m -- "$path")
            [[ "$resolved" == "$creation_project/.venv/"* ]] || fail ".venv com link para fora do ambiente: $path. Prepare o ambiente explicitamente."
        elif [[ -d "$path" ]]; then
            inspect_venv_paths "$path"
        fi
    done
}

inspect_creation_venv() {
    local required=${1:-false} venv="$creation_project/.venv" directory
    if [[ ! -e "$venv" && ! -L "$venv" ]]; then
        if "$required"; then fail ".venv local ausente apos sync; etapas anteriores podem ter sido concluidas."; fi
        return 0
    fi
    inspect_venv_paths "$venv"
    [[ ! -L "$venv/pyvenv.cfg" && -f "$venv/pyvenv.cfg" && $(stat -c '%h' -- "$venv/pyvenv.cfg") == 1 ]] || fail ".venv/pyvenv.cfg ausente ou irregular."
    for directory in "$venv/bin/python" "$venv/bin/python3"; do
        [[ -f "$directory" && -x "$directory" ]] || fail "Interpretador da .venv ausente ou nao executavel: $directory."
    done
    [[ "$venv/bin/python" -ef "$venv/bin/python3" ]] || fail "Interpretadores da .venv divergentes."
}

# Somente os destinos IDE/R da criacao; nenhum arquivo existente e reescrito.
inspect_creation_configs() {
    local base=$1 file path state directory
    local -a directories=("$base")
    "$WITH_IDE" && directories+=("$base/.vscode")
    for directory in "${directories[@]}"; do
        if [[ -d "$directory" && ! -x "$directory" ]]; then
            fail "Conflito em $directory: diretorio sem permissao de busca; configuracoes nao podem ser inspecionadas."
        fi
    done
    if "$WITH_IDE" && [[ -L "$base/.vscode" || (-e "$base/.vscode" && ! -d "$base/.vscode") ]]; then
        fail "Conflito em $base/.vscode: esperado diretorio sem symlink."
    fi
    for file in "${CONFIG_FILES[@]}"; do
        path="$base/$file"
        if [[ -L "$path" || (-e "$path" && ! -f "$path") ]]; then
            fail "Conflito em $path: esperado arquivo regular sem symlink."
        fi
        state=absent
        if [[ -e "$path" ]]; then
            [[ $(stat -c '%h' -- "$path") == 1 ]] || fail "Conflito em $path: arquivo com multiplos links ou impossivel de inspecionar."
            state=preserved
        fi
        if [[ -n ${CONFIG_STATES[$file]-} && ${CONFIG_STATES[$file]} != "$state" ]]; then
            fail "Conflito em $path: destino surgiu ou mudou apos a inspecao."
        fi
        CONFIG_STATES[$file]=$state
    done
}

write_creation_config() {
    local file=$1 temporary
    [[ ${CONFIG_STATES[$file]} != preserved ]] || return 0
    (
        if [[ "$file" == .vscode/settings.json ]]; then
            [[ ! -L .vscode && -d .vscode ]] || fail "Conflito em .vscode: diretorio mudou antes da escrita."
            # Gravar pelo cwd fisico evita atravessar um novo link em .vscode.
            cd -P -- .vscode || exit 2
            [[ "$PWD" == "$creation_project/.vscode" ]] || fail "Conflito em .vscode: caminho fisico inesperado."
            file=settings.json
        fi
        temporary=$(mktemp -d -- .pyinit-config.XXXXXX) || exit 2
        trap 'rm -f -- "$temporary/content"; rmdir -- "$temporary"' EXIT
        cat >"$temporary/content" || exit 2
        # ln -T sem force recusa qualquer destino existente, inclusive FIFO/link.
        ln -T -- "$temporary/content" "$file"
    ) || fail "Conflito em $1: criacao exclusiva recusada; configuracao existente preservada."
}

configure_creation_tools() {
    /usr/bin/python3 -I -B - "$1" "$2" <<'PYINIT_TOOLS'
"""Compoe os padroes Ruff/pytest ausentes em um pyproject.toml.

Uso: configure_tools.py PYPROJECT check|apply
"""

import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    print("Erro: a criacao exige /usr/bin/python3 >=3.11 com tomllib.", file=sys.stderr)
    sys.exit(2)


DEFAULTS = {
    "ruff": """
[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
""",
    "pytest": """
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra -q --strict-markers"
""",
}


def main(argv: list[str]) -> int:
    path = Path(argv[1])
    mode = argv[2]
    try:
        if mode == "check" and not path.is_file():
            return 0
        original = path.read_bytes()
        document = tomllib.loads(original.decode("utf-8"))
        tool = document.get("tool", {})
        if not isinstance(tool, dict):
            raise ValueError(
                "tool deve ser uma tabela; revise a configuracao manualmente"
            )
        for name in ("ruff", "pytest"):
            if name in tool and not isinstance(tool[name], dict):
                raise ValueError(
                    f"tool.{name} deve ser uma tabela; "
                    "revise a configuracao manualmente"
                )
        addition = "".join(
            block for name, block in DEFAULTS.items() if name not in tool
        )
        if addition:
            try:
                tomllib.loads(original.decode("utf-8") + addition)
            except tomllib.TOMLDecodeError as exc:
                raise ValueError(
                    "composicao exige reescrever tabelas existentes "
                    "(por exemplo inline); revise manualmente"
                ) from exc
        if mode == "apply":
            if addition:
                with path.open("ab") as stream:
                    stream.write(addition.encode("utf-8"))
            for name in DEFAULTS:
                state = "preservado" if name in tool else "configuracao padrao criada"
                print(f"  {name}: {state}.")
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Erro: {path}: composicao Ruff/pytest recusada: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
PYINIT_TOOLS
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

migrate_project() {
    local migration_python=""
    "$PYTHON_SET" && migration_python="$PYTHON_DEFAULT"
    /usr/bin/python3 -I -B - "$TARGET_DIR" "$migration_python" "$DRY_RUN" "$1" "${2-}" 3<&0 <<'PYINIT_MIGRATE'
"""Migra um projeto Python legado para uv com plano revisado e backup.

Uso: migrate.py PROJETO [VERSAO_PYTHON|""] true|false  (confirmacao no fd 3)
"""

import ast
import configparser
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import uuid
from pathlib import Path


class Refused(Exception):
    pass


def require(condition: object, message: str) -> None:
    if not condition:
        raise Refused(message)


def fingerprint(path: Path) -> dict:
    try:
        s = path.lstat()
    except FileNotFoundError:
        return {}
    return dict(
        device=s.st_dev,
        inode=s.st_ino,
        mode=s.st_mode,
        uid=s.st_uid,
        gid=s.st_gid,
        size=s.st_size,
        mtime_ns=s.st_mtime_ns,
        links=s.st_nlink,
    )


def safe_directories(path: Path, project: Path) -> None:
    system_uid = Path("/").stat().st_uid
    for part in reversed((path, *path.parents)):
        s = part.lstat()
        require(
            stat.S_ISDIR(s.st_mode),
            f"Diretorio ou ancestral simbolico/invalido: {part}",
        )
        require(
            s.st_uid in (0, system_uid, os.getuid()),
            f"Diretorio de outro usuario: {part}",
        )
        shared_tmp = s.st_uid in (0, system_uid) and bool(s.st_mode & stat.S_ISVTX)
        require(
            not s.st_mode & 0o022 or shared_tmp or part == project,
            f"Ancestral inseguro; revise suas permissoes: {part}",
        )
    require(
        path.stat().st_uid == os.getuid(), "O projeto deve pertencer ao usuario atual."
    )


def version_constraint(value: str, poetry: bool = False) -> str:
    require(isinstance(value, str), "Versao de dependencia invalida.")
    value = value.strip()
    if value in ("", "*"):
        return ""
    if poetry and value[0] in "^~" and not value.startswith("~="):
        op, raw = value[0], value[1:]
        require(
            bool(re.fullmatch(r"\d+(?:\.\d+){0,2}", raw)),
            "Restricao Poetry complexa; revise manualmente.",
        )
        parts = list(map(int, raw.split(".")))
        index = (
            next((i for i, p in enumerate(parts) if p), len(parts) - 1)
            if op == "^"
            else min(1, len(parts) - 1)
        )
        upper = parts[: index + 1]
        upper[index] += 1
        upper.extend([0] * (len(parts) - len(upper)))
        return ">=" + raw + ",<" + ".".join(map(str, upper))
    require(
        "||" not in value and not re.search(r"[\n\r;@/]", value),
        "Restricao de versao nao suportada.",
    )
    if re.match(r"^\d", value):
        value = "==" + value
    require(
        bool(
            re.fullmatch(
                (
                    "(?:===|==|!=|~=|>=|<=|>|<)\\s*[\\w.*+!-]+(?:\\s*,\\s*(?:"
                    "===|==|!=|~=|>=|<=|>|<)\\s*[\\w.*+!-]+)*"
                ),
                value,
            )
        ),
        "Restricao de versao nao suportada.",
    )
    return value.replace(" ", "")


def python_allows(spec: str, requested: str) -> bool:
    actual = tuple(map(int, requested.split(".")))
    if len(actual) == 2:
        # Cada clausula muda de resultado somente nos limites de patch.
        boundaries = [int(p) for p in re.findall(r"\b\d+\.\d+\.(\d+)", spec)]
        patches = {0, 1} | {max(0, p + step) for p in boundaries for step in (-1, 0, 1)}
        return any(python_allows(spec, requested + "." + str(p)) for p in patches)
    actual += (0,) * (3 - len(actual))
    for item in spec.split(","):
        m = re.fullmatch(
            r"\s*(>=|<=|==|!=|>|<|~=)\s*(\d+(?:\.\d+){0,2})(\.\*)?\s*", item
        )
        require(m is not None, "Restricao Python complexa; revise manualmente.")
        op, raw, wildcard = m.groups()
        parts = tuple(map(int, raw.split(".")))
        target = parts + (0,) * (3 - len(parts))
        equal = actual[: len(parts)] == parts if wildcard else actual == target
        ok = {
            "==": equal,
            "!=": not equal,
            ">=": actual >= target,
            "<=": actual <= target,
            ">": actual > target,
            "<": actual < target,
            "~=": actual >= target
            and actual[: max(1, len(parts) - 1)] == parts[: max(1, len(parts) - 1)],
        }[op]
        if not ok:
            return False
    return True


def make_requirement(
    name: str, value: object, poetry: bool = False
) -> tuple[str, bool]:
    require(
        bool(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9,._-]+\])?", name)
        ),
        "Nome de dependencia invalido.",
    )
    optional = False
    extras = markers = ""
    if isinstance(value, dict):
        require(
            not set(value) - {"version", "extras", "markers", "optional"},
            f"Dependencia {name}: origem, Python ou opcoes especiais exigem revisao.",
        )
        optional = value.get("optional", False)
        require(isinstance(optional, bool), "optional deve ser booleano.")
        if "extras" in value:
            require(
                isinstance(value["extras"], list)
                and all(
                    isinstance(x, str) and re.fullmatch(r"[\w.-]+", x)
                    for x in value["extras"]
                ),
                "Extras invalidos.",
            )
            extras = "[" + ",".join(value["extras"]) + "]"
        if "markers" in value:
            require(
                isinstance(value["markers"], str) and "\n" not in value["markers"],
                "Marcador invalido.",
            )
            markers = "; " + value["markers"]
        value = value.get("version", "*")
    require(
        isinstance(value, str),
        f"Dependencia {name}: declaracao dinamica ou multipla nao suportada.",
    )
    return name + extras + version_constraint(value, poetry) + markers, optional


def static_setup(raw: bytes) -> dict:
    module = ast.parse(raw.decode())
    calls = []
    imported = False
    for node in module.body:
        if isinstance(node, ast.ImportFrom):
            require(
                node.module in ("setuptools", "distutils.core")
                and all(n.name == "setup" and n.asname is None for n in node.names),
                "setup.py deve ser um wrapper estatico de setuptools.setup.",
            )
            imported = True
        elif isinstance(node, ast.Import):
            require(
                all(n.name == "setuptools" and n.asname is None for n in node.names),
                "Imports dinamicos em setup.py exigem revisao.",
            )
            imported = True
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            require(isinstance(node.value.value, str), "setup.py dinamico.")
        else:
            require(
                isinstance(node, ast.Expr) and isinstance(node.value, ast.Call),
                "setup.py condicional/dinamico exige revisao; nao foi executado.",
            )
            call = node.value
            require(
                isinstance(call.func, ast.Name)
                and call.func.id == "setup"
                or isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "setuptools"
                and call.func.attr == "setup",
                "Chamada desconhecida em setup.py exige revisao.",
            )
            calls.append(call)
    require(imported and len(calls) == 1, "Wrapper setup.py ambiguo/dinamico.")
    call = calls[0]
    require(
        not call.args and all(k.arg is not None for k in call.keywords),
        "Argumentos dinamicos em setup.py exigem revisao.",
    )
    require(
        not {k.arg for k in call.keywords}
        & {"setup_requires", "tests_require", "dependency_links", "cmdclass"},
        "Requisitos/hooks de build/teste setuptools exigem revisao manual.",
    )
    try:
        return {k.arg: ast.literal_eval(k.value) for k in call.keywords}
    except (ValueError, TypeError):
        raise Refused(
            "setup.py nao literal exige revisao; nao foi executado."
        ) from None


def plan_migration(
    project: Path, python: str
) -> tuple[dict, dict[str, bytes | None], bytes | None]:
    safe_directories(project, project)
    for parent in (project, *project.parents):
        config = parent / "pyproject.toml"
        if config.is_file():
            require(not config.is_symlink(), "pyproject.toml simbolico nao permitido.")
            data = tomllib.loads(config.read_text())
            require(
                "workspace" not in data.get("tool", {}).get("uv", {}),
                "Workspace uv exige migracao explicita separada.",
            )
    originals: dict[str, bytes | None] = {}
    inputs: dict[str, dict] = {}

    def read(name: str) -> bytes | None:
        require(
            not Path(name).is_absolute() and ".." not in Path(name).parts,
            "Referencia de arquivo fora do projeto nao permitida.",
        )
        path = project / name
        safe_directories(path.parent, project)
        if name in originals:
            return originals[name]
        info = fingerprint(path)
        inputs[name] = info
        if not info:
            originals[name] = None
            return None
        require(
            stat.S_ISREG(info["mode"])
            and info["uid"] == os.getuid()
            and info["links"] == 1,
            f"Arquivo deve ser regular, proprio, sem symlink/hardlink: {name}",
        )
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as f:
            require(
                os.fstat(f.fileno()).st_ino == info["inode"],
                "Arquivo mudou durante a leitura.",
            )
            raw = f.read(5 * 1024 * 1024 + 1)
        require(
            len(raw) <= 5 * 1024 * 1024, f"Arquivo grande demais para inspecao: {name}"
        )
        info["sha256"] = hashlib.sha256(raw).hexdigest()
        originals[name] = raw
        return raw

    names = [
        "pyproject.toml",
        "uv.lock",
        "Pipfile",
        "Pipfile.lock",
        "setup.cfg",
        "setup.py",
        "environment.yml",
        "environment.yaml",
        ".envrc",
        ".python-version",
        ".gitignore",
        "requirements.in",
        "requirements.txt",
        "requirements-dev.in",
        "requirements-dev.txt",
        "dev-requirements.txt",
    ]
    for name in names:
        read(name)
    for name in (".venv", ".pyinit-backups"):
        info = fingerprint(project / name)
        inputs[name] = info
        if info:
            require(
                stat.S_ISDIR(info["mode"]) and info["uid"] == os.getuid(),
                f"Diretorio invalido ou simbolico: {name}",
            )
            if name == ".pyinit-backups":
                require(
                    not info["mode"] & 0o077,
                    "Diretorio de backups deve ser privado (0700).",
                )
    require(
        not (project / "conda-meta").exists(),
        "O alvo e um ambiente Conda, nao uma raiz de projeto.",
    )
    warnings: list[str] = []
    deps: list[str] = []
    groups: dict[str, list[str]] = {}
    extras: dict[str, list[str]] = {}
    constraints: list[str] = []
    default_groups = None
    metadata = {}
    requires = ""
    raw_project = originals["pyproject.toml"]
    config = tomllib.loads(raw_project.decode()) if raw_project else {}
    project_config = config.get("project", {})
    poetry = config.get("tool", {}).get("poetry")
    kinds = []
    if project_config:
        kinds.append("uv" if originals["uv.lock"] else "pep621")
    elif poetry is not None:
        kinds.append("poetry")
    if originals["Pipfile"] is not None or originals["Pipfile.lock"] is not None:
        kinds.append("pipenv")
    if (
        originals["environment.yml"] is not None
        or originals["environment.yaml"] is not None
    ):
        kinds.append("conda")
    if not config and (
        originals["setup.cfg"] is not None or originals["setup.py"] is not None
    ):
        kinds.append("setuptools")
    has_requirements = any(
        originals[n] is not None for n in ("requirements.in", "requirements.txt")
    )
    if has_requirements and not kinds:
        kinds.append("requirements")
    elif has_requirements and kinds:
        require(
            kinds == ["uv"],
            (
                "Manifestos de formatos diferentes: requirements e out"
                "ro gerenciador; revise a fonte principal."
            ),
        )
        warnings.append(
            "requirements suplementares preservados; o manifesto d"
            "o gerenciador detectado sera a fonte."
        )
    if not kinds and any(
        (project / d / "conda-meta").is_dir() and not (project / d).is_symlink()
        for d in (".venv", "venv", "env")
    ):
        raise Refused(
            "Inventario Conda detectado sem manifesto: exporte/rev"
            "ise environment.yml antes de migrar; pacotes instalad"
            "os nao definem as dependencias diretas."
        )
    require(
        len(kinds) == 1,
        (
            "Formato ausente ou ambiguo; escolha/revise o manifesto pr"
            "incipal antes da migracao."
        ),
    )
    kind = kinds[0]
    has_dev_requirements = any(
        originals[n] is not None
        for n in ("requirements-dev.in", "requirements-dev.txt", "dev-requirements.txt")
    )
    if has_dev_requirements:
        require(
            kind in ("requirements", "uv"),
            "Requirements dev junto de outro gerenciador exigem "
            "revisao da fonte principal.",
        )
        if kind == "uv" and not has_requirements:
            warnings.append(
                "Requirements dev suplementares preservados; "
                "grupos uv fixados sao a fonte."
            )
    require(
        not originals["uv.lock"] or kind == "uv",
        "uv.lock existente sem projeto PEP 621; revise manualmente.",
    )
    if kind in ("uv", "pep621"):
        require(
            kind == "uv"
            or not poetry
            or not set(poetry)
            & {"dependencies", "dev-dependencies", "group", "extras", "source"},
            "Metadados de dependencias Poetry junto de PEP 621 exigem revisao.",
        )
        require(
            not project_config.get("dynamic"),
            "Metadados PEP 621 dinamicos exigem revisao manual.",
        )
        require(
            isinstance(project_config.get("dependencies", []), list),
            "Dependencias PEP 621 invalidas.",
        )
        deps = project_config.get("dependencies", [])
        groups = config.get("dependency-groups", {})
        requires = project_config.get("requires-python", "")
    elif kind in ("poetry", "pipenv"):
        data = (
            poetry
            if kind == "poetry"
            else (
                tomllib.loads(originals["Pipfile"].decode())
                if originals["Pipfile"] is not None
                else json.loads(originals["Pipfile.lock"])
            )
        )
        if kind == "poetry":
            metadata = data
            require(
                not data.get("source"),
                "Fontes Poetry personalizadas exigem revisao manual.",
            )
            main = data.get("dependencies", {})
            requires = version_constraint(main.get("python", "*"), True)
            main = {k: v for k, v in main.items() if k != "python"}
            require(
                all(
                    isinstance(v, dict)
                    and not set(v) - {"dependencies", "optional"}
                    and isinstance(v.get("optional", False), bool)
                    for v in data.get("group", {}).values()
                ),
                "Grupo Poetry com include-groups/opcoes nao suportadas exige revisao.",
            )
            group_data = {
                k: v.get("dependencies", {}) for k, v in data.get("group", {}).items()
            }
            default_groups = [
                k
                for k, v in data.get("group", {}).items()
                if not v.get("optional", False)
            ]
            if data.get("dev-dependencies"):
                require(
                    "dev" not in group_data,
                    "Grupos dev Poetry duplicados; revise manualmente.",
                )
                group_data["dev"] = data["dev-dependencies"]
                default_groups.append("dev")
        else:
            sources = data.get("source", data.get("_meta", {}).get("sources", []))
            require(
                all(
                    s.get("url", "").rstrip("/") == "https://pypi.org/simple"
                    and s.get("verify_ssl", True)
                    for s in sources
                ),
                "Fontes Pipenv personalizadas exigem revisao manual.",
            )
            require(
                not set(data)
                - {
                    "source",
                    "_meta",
                    "default",
                    "develop",
                    "packages",
                    "dev-packages",
                    "requires",
                    "scripts",
                    "pipenv",
                },
                "Categorias Pipenv adicionais exigem revisao manual.",
            )
            req = data.get("requires", data.get("_meta", {}).get("requires", {}))
            if req.get("python_full_version"):
                requires = "==" + req["python_full_version"]
            elif req.get("python_version"):
                requires = "==" + req["python_version"] + ".*"
            main = data.get("packages", data.get("default", {}))
            group_data = {"dev": data.get("dev-packages", data.get("develop", {}))}
            if originals["Pipfile"] is None:
                main = {
                    k: {a: b for a, b in v.items() if a != "hashes"}
                    for k, v in main.items()
                }
                group_data = {
                    g: {
                        k: {a: b for a, b in v.items() if a != "hashes"}
                        for k, v in entries.items()
                    }
                    for g, entries in group_data.items()
                }
        optionals = {}
        for name, value in main.items():
            requirement, optional = make_requirement(name, value, kind == "poetry")
            if optional:
                optionals[name] = requirement
            else:
                deps.append(requirement)
        for group, entries in group_data.items():
            groups[group] = [
                make_requirement(k, v, kind == "poetry")[0] for k, v in entries.items()
            ]
        for extra, entries in data.get("extras", {}).items():
            require(
                all(n in optionals for n in entries),
                "Extras Poetry ambiguos; revise manualmente.",
            )
            extras[extra] = [optionals[n] for n in entries]
        require(
            set(optionals)
            == {n for entries in data.get("extras", {}).values() for n in entries},
            "Dependencia opcional sem extra; revise manualmente.",
        )
        warnings.append(
            "O uv resolvera um novo lock; locks do gerenciador ant"
            "erior ficam preservados e as versoes podem mudar."
        )
    elif kind == "setuptools":
        if originals["setup.cfg"] is not None:
            if originals["setup.py"] is not None:
                require(
                    not static_setup(originals["setup.py"]),
                    "setup.cfg com setup.py configurado exige revisao manual.",
                )
            cfg = configparser.ConfigParser(interpolation=None)
            cfg.read_string(originals["setup.cfg"].decode())
            metadata = (
                dict(cfg.items("metadata")) if cfg.has_section("metadata") else {}
            )
            require(
                not cfg.has_section("options")
                or not cfg.has_option("options", "setup_requires"),
                "setup_requires exige revisao manual.",
            )
            deps = cfg.get("options", "install_requires", fallback="").splitlines()
            requires = cfg.get("options", "python_requires", fallback="").strip()
            if cfg.has_section("options.extras_require"):
                extras = {
                    k: v.splitlines() for k, v in cfg.items("options.extras_require")
                }
        else:
            values = static_setup(originals["setup.py"])
            metadata = values
            deps = values.get("install_requires", [])
            requires = values.get("python_requires", "")
            extras = values.get("extras_require", {})
        require(
            isinstance(extras, dict), "extras_require deve ser um mapeamento estatico."
        )
        normalized_extras = {}
        for extra, entries in extras.items():
            require(
                isinstance(extra, str)
                and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", extra),
                "Extra setuptools condicional/dinamico exige revisao.",
            )
            if isinstance(entries, str):
                entries = entries.splitlines()
            require(
                isinstance(entries, (list, tuple))
                and all(isinstance(x, str) for x in entries),
                "Extra setuptools deve conter requisitos estaticos de texto.",
            )
            normalized_extras[extra] = [x.strip() for x in entries if x.strip()]
        extras = normalized_extras
        require(
            all(
                isinstance(x, str) and not x.strip().startswith(("file:", "attr:"))
                for x in deps
            ),
            "Dependencias setuptools dinamicas exigem revisao.",
        )
        warnings.append(
            "Migracao de ambiente; metadados de distribuicao/entry"
            " points setuptools permanecem no legado e exigem revi"
            "sao separada."
        )

    def requirements(name: str, stack: tuple = ()) -> list[str]:
        require(name not in stack, "Inclusao circular em requirements.")
        raw = read(name)
        require(raw is not None, f"Requirements ausente: {name}")
        result = []
        for line in raw.decode().replace("\\\n", " ").splitlines():
            line = re.split(r"\s+#", line.strip(), maxsplit=1)[0].strip()
            if not line or line.startswith("#"):
                continue
            include = re.fullmatch(
                r"(-r|--requirement|-c|--constraint)\s+([^\s]+)", line
            )
            if include:
                flag, target = include.groups()
                target = str(Path(name).parent / target)
                entries = requirements(target, (*stack, name))
                (constraints if flag in ("-c", "--constraint") else result).extend(
                    entries
                )
                continue
            line = re.sub(r"\s+--hash=\S+", "", line)
            require(
                not line.startswith("-") and not any(c in line for c in "\x00\r"),
                (
                    "Opcao de requirements nao suportada; revise indic"
                    "es/editaveis e restricoes."
                ),
            )
            require(
                bool(re.match(r"[A-Za-z0-9]", line)),
                "Dependencia requirements invalida.",
            )
            result.append(line)
        return result

    if kind == "requirements":
        deps = requirements(
            "requirements.in"
            if originals["requirements.in"] is not None
            else "requirements.txt"
        )
        require(
            not (
                originals["dev-requirements.txt"] is not None
                and any(
                    originals[n] is not None
                    for n in ("requirements-dev.in", "requirements-dev.txt")
                )
            ),
            "Manifestos dev concorrentes exigem revisao; "
            "nenhuma dependencia foi descartada.",
        )
        for name in (
            "requirements-dev.in",
            "requirements-dev.txt",
            "dev-requirements.txt",
        ):
            if originals[name] is not None:
                groups["dev"] = [x for x in requirements(name) if x not in deps]
                break
    elif kind == "conda":
        require(
            not (
                originals["environment.yml"] is not None
                and originals["environment.yaml"] is not None
            ),
            "Dois manifestos Conda; revise qual e o principal.",
        )
        raw = (
            originals["environment.yml"]
            if originals["environment.yml"] is not None
            else originals["environment.yaml"]
        )
        section = ""
        pip_indent = None
        packages = {
            "numpy",
            "pandas",
            "scipy",
            "scikit-learn",
            "matplotlib",
            "seaborn",
            "jupyter",
            "jupyterlab",
            "notebook",
            "ipykernel",
            "ipython",
            "pytest",
            "pytest-cov",
            "ruff",
            "requests",
            "httpx",
            "flask",
            "fastapi",
            "pydantic",
            "polars",
            "duckdb",
            "pyarrow",
            "pillow",
            "beautifulsoup4",
            "lxml",
            "tqdm",
            "click",
            "typer",
            "rich",
            "sympy",
            "statsmodels",
            "sqlalchemy",
            "lightgbm",
            "xgboost",
            "openpyxl",
            "plotly",
            "bokeh",
            "dask",
            "nltk",
            "spacy",
            "pyspark",
            "joblib",
            "pyyaml",
            "python-dotenv",
        }
        for line in raw.decode().splitlines():
            clean = re.split(r"\s+#", line.strip(), maxsplit=1)[0].strip()
            if not clean or clean.startswith("#"):
                continue
            if not line.startswith(" "):
                require(
                    bool(
                        re.fullmatch(r"(name|prefix|channels|dependencies):.*", clean)
                    ),
                    "Estrutura YAML Conda nao suportada.",
                )
                section, value = clean.split(":", 1)
                require(
                    section not in ("channels", "dependencies") or not value.strip(),
                    "Use listas YAML em bloco, sem anchors/tags/flow.",
                )
                pip_indent = None
                continue
            require(clean.startswith("- "), "Estrutura YAML Conda nao suportada.")
            if section != "dependencies":
                continue
            item = clean[2:].strip()
            indent = len(line) - len(line.lstrip())
            if item == "pip:":
                pip_indent = indent
                continue
            require(
                not re.search(r"[&*!{}\[\]]", item),
                "YAML avancado exige revisao manual.",
            )
            if pip_indent is not None and indent > pip_indent:
                deps.append(item.strip("\"'"))
                continue
            pip_indent = None
            item = item.strip("\"'")
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)\s*([=<>!~].*)?", item)
            require(match is not None, "Especificacao Conda complexa exige revisao.")
            name, spec = match.groups()
            spec = spec or ""
            if spec.startswith("=") and not spec.startswith("=="):
                require(
                    bool(re.fullmatch(r"=\d+(?:\.\d+)*(?:\.\*)?", spec)),
                    "Build/channel Conda exige revisao.",
                )
                spec = "==" + spec[1:] + ("" if spec.endswith(".*") else ".*")
            if name == "python":
                requires = spec
            elif name != "pip":
                require(
                    name in packages or name in ("setuptools", "wheel"),
                    f"Pacote Conda sem equivalencia revisada no PyPI: {name}",
                )
                deps.append(name + version_constraint(spec))
        require(section or deps, "Manifesto Conda vazio.")
        warnings.append(
            "Canais/builds Conda nao sao transportados para PyPI; "
            "somente pacotes Python reconhecidos sao aceitos."
        )
    require(
        isinstance(deps, list) and all(isinstance(x, str) for x in deps),
        "Lista de dependencias invalida.",
    )
    require(isinstance(requires, str), "Restricao Python invalida.")
    require(
        not requires or python_allows(requires, python),
        (
            "Python solicitado incompativel com a restricao do projeto"
            "; escolha --python compativel ou revise o manifesto."
        ),
    )
    deps = list(dict.fromkeys(x.strip() for x in deps if x.strip()))
    constraints = list(dict.fromkeys(constraints))
    output = None
    if kind not in ("uv", "pep621"):
        require(
            not config.get("dependency-groups")
            and not config.get("tool", {}).get("uv"),
            "Configuracao uv/grupos existente exige revisao antes da conversao.",
        )
        name = (
            re.sub(r"[^a-z0-9._-]+", "-", project.name.lower()).strip("-._")
            or "migrated-project"
        )
        name = metadata.get("name", name)
        version = metadata.get("version", "0.1.0")
        require(
            isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name),
            "Nome de projeto invalido/dinamico; revise os metadados.",
        )
        require(
            isinstance(version, str) and not version.startswith(("attr:", "file:")),
            "Versao de projeto dinamica; revise os metadados.",
        )
        text = (raw_project.decode().rstrip() + "\n\n") if raw_project else ""
        text += (
            "[project]\nname = "
            + json.dumps(name)
            + "\nversion = "
            + json.dumps(version)
            + "\n"
        )
        text += (
            "requires-python = "
            + json.dumps(requires or ">=" + ".".join(python.split(".")[:2]))
            + "\n"
        )
        text += "dependencies = " + json.dumps(deps, ensure_ascii=False) + "\n"
        if extras:
            text += "\n[project.optional-dependencies]\n"
            for key, entries in extras.items():
                text += (
                    json.dumps(key)
                    + " = "
                    + json.dumps([x.strip() for x in entries if x.strip()])
                    + "\n"
                )
        if groups:
            text += "\n[dependency-groups]\n"
            for key, entries in groups.items():
                text += (
                    json.dumps(key)
                    + " = "
                    + json.dumps(entries, ensure_ascii=False)
                    + "\n"
                )
        if not config.get("build-system") or constraints or default_groups is not None:
            text += "\n[tool.uv]\n"
            if not config.get("build-system"):
                text += "package = false\n"
            if constraints:
                text += "constraint-dependencies = " + json.dumps(constraints) + "\n"
            if default_groups is not None:
                text += "default-groups = " + json.dumps(default_groups) + "\n"
        tomllib.loads(text)
        output = text.encode()
    if kind == "uv":
        if poetry:
            warnings.append(
                "Projeto uv fixado: PEP 621 e grupos uv sao a fonte; "
                "metadados Poetry remanescentes ficam preservados."
            )
        warnings.append(
            "uv.lock existente sera preservado com --locked; incom"
            "patibilidade interrompe a migracao."
        )
    if originals[".envrc"] is not None:
        warnings.append(
            ".envrc existente sera preservado; revise o conteudo e"
            " suas permissoes antes de direnv allow."
        )
    plan = dict(
        operation="migrate",
        project=str(project),
        format=kind,
        python=python,
        dependencies=deps,
        groups=groups,
        requires_python=requires,
        constraints=constraints,
        inputs=inputs,
        root=fingerprint(project),
        changes=[".venv", ".python-version", ".gitignore"]
        + (["pyproject.toml"] if output else [])
        + ([] if kind == "uv" else ["uv.lock"])
        + ([] if originals[".envrc"] is not None else [".envrc"]),
        warnings=warnings,
        blockers=[],
        backup=".pyinit-backups/ID",
    )
    for name in ("pyproject.toml", "uv.lock"):
        if inputs[name] and inputs[name]["mode"] & 0o022:
            plan["changes"].append("permissoes privadas de " + name)
    if plan["root"]["mode"] & 0o022:
        plan["changes"].append("permissoes da raiz: remover escrita de grupo/outros")
    plan["approval"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True).encode()
    ).hexdigest()
    return plan, originals, output


def atomic(path: Path, raw: bytes, mode: int = 0o600) -> None:
    fd, name = tempfile.mkstemp(prefix=".pyinit-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, stat.S_IMODE(mode))
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


# Arquivos que a migracao pode criar ou regravar na raiz do projeto.
MANAGED = ("pyproject.toml", "uv.lock", ".python-version", ".envrc", ".gitignore")
LIMIT = 5 * 1024 * 1024
BACKUP_IGNORE = b"# pyinit: backups privados de migracao\n.pyinit-backups/\n"


def protect_backup_ignore(project: Path) -> None:
    path = project / ".gitignore"
    raw = path.read_bytes() if path.exists() else b""
    block = BACKUP_IGNORE
    # A regra precisa ser a ultima para prevalecer sobre negacoes anteriores.
    if not raw.endswith(block):
        atomic(path, raw + (b"\n" if raw and not raw.endswith(b"\n") else b"") + block)


def apply_migration(plan: dict, originals: dict, output: bytes | None, uv: str) -> Path:
    project = Path(plan["project"])
    rootfd = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(rootfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current, _, _ = plan_migration(project, plan["python"])
        require(
            current["approval"] == plan["approval"],
            "Projeto mudou apos a revisao; execute novamente.",
        )
        # Primeiro fecha a escrita compartilhada; o modo anterior consta no plano.
        os.fchmod(rootfd, stat.S_IMODE(os.fstat(rootfd).st_mode) & ~0o022)
        parent = project / ".pyinit-backups"
        backup = parent / uuid.uuid4().hex
        record = dict(status="pending", approval=plan["approval"], plan=plan)

        def save() -> None:
            atomic(
                backup / "manifest.json", (json.dumps(record, indent=2) + "\n").encode()
            )

        moved = False
        started = False
        try:
            protect_backup_ignore(project)
            parent.mkdir(mode=0o700, exist_ok=True)
            backup.mkdir(mode=0o700)
            save()
            for name, raw in originals.items():
                if raw is not None:
                    dest = backup / "files" / name
                    dest.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                    atomic(dest, raw)
            if (project / ".venv").exists():
                os.rename(project / ".venv", backup / "venv-before")
                moved = True
            started = True
            # Metadados lidos pelo uv nao podem continuar gravaveis por outro UID.
            for name in ("pyproject.toml", "uv.lock"):
                if originals[name] is not None and plan["inputs"][name]["mode"] & 0o022:
                    atomic(project / name, originals[name])
            if output is not None:
                atomic(project / "pyproject.toml", output)
            atomic(project / ".python-version", (plan["python"] + "\n").encode())
            if originals[".envrc"] is None:
                atomic(project / ".envrc", b"use devshell_python\n")
            # Inserir antes do bloco final de backups, sem duplica-lo.
            ignore = (project / ".gitignore").read_bytes().removesuffix(BACKUP_IGNORE)
            if b".venv/" not in ignore.splitlines():
                atomic(
                    project / ".gitignore",
                    ignore
                    + (b"\n" if ignore and not ignore.endswith(b"\n") else b"")
                    + b".venv/\n"
                    + BACKUP_IGNORE,
                )
            protect_backup_ignore(project)
            env = {
                k: v
                for k, v in os.environ.items()
                if (
                    not k.startswith("UV_")
                    or k in ("UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR", "UV_OFFLINE")
                )
                and k
                not in (
                    "VIRTUAL_ENV",
                    "CONDA_PREFIX",
                    "CONDA_DEFAULT_ENV",
                    "PYTHONPATH",
                    "PYTHONHOME",
                )
            }
            env["UV_PROJECT_ENVIRONMENT"] = str(project / ".venv")
            command = [
                uv,
                "--no-config",
                "sync",
                "--project",
                str(project),
                "--python",
                plan["python"],
                "--managed-python",
                "--no-python-downloads",
            ]
            if plan["format"] == "uv":
                command.append("--locked")
            subprocess.run(command, cwd=project, env=env, check=True)
            for directory in (project, project / ".venv", project / ".venv/bin"):
                safe_directories(directory, project)
            cfg = project / ".venv/pyvenv.cfg"
            require(
                cfg.is_file()
                and not cfg.is_symlink()
                and not cfg.stat().st_mode & 0o022,
                ".venv criada com pyvenv.cfg ausente ou inseguro.",
            )
            require(
                all(
                    os.access(project / ".venv/bin" / x, os.X_OK)
                    for x in ("python", "python3")
                ),
                "Interpretador da nova .venv ausente.",
            )
            if plan["format"] == "uv":
                require(
                    (project / "uv.lock").read_bytes() == originals["uv.lock"],
                    "uv.lock foi alterado; migracao interrompida.",
                )
            record["status"] = "complete"
            save()
        except BaseException:
            if started and (project / ".venv").exists():
                os.rename(project / ".venv", backup / "failed-venv")
            if moved:
                os.rename(backup / "venv-before", project / ".venv")
            if started:
                for name in MANAGED:
                    raw = originals[name]
                    if raw is None:
                        (project / name).unlink(missing_ok=True)
                    else:
                        mode = plan["inputs"][name]["mode"]
                        if name in ("pyproject.toml", "uv.lock"):
                            mode &= ~0o022
                        atomic(project / name, raw, mode)
            protect_backup_ignore(project)
            record["retained_gitignore_backup_rule"] = True
            record["status"] = "rolled-back"
            if backup.is_dir():
                save()
            print(
                f"Migracao revertida; backup e artefatos da falha: {backup}",
                file=sys.stderr,
            )
            raise
        return backup
    finally:
        os.close(rootfd)


def read_private(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        s = os.fstat(f.fileno())
        require(
            stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid() and s.st_nlink == 1,
            f"Arquivo deve ser regular, proprio, sem symlink/hardlink: {path.name}",
        )
        raw = f.read(LIMIT + 1)
    require(len(raw) <= LIMIT, f"Arquivo grande demais para inspecao: {path.name}")
    return raw


def private_directory(path: Path) -> bool:
    try:
        s = path.lstat()
    except FileNotFoundError:
        return False
    require(
        stat.S_ISDIR(s.st_mode) and s.st_uid == os.getuid() and not s.st_mode & 0o077,
        f"Diretorio de backups deve ser proprio e privado (0700): {path.name}",
    )
    return True


def list_backups(project: Path) -> list[dict]:
    safe_directories(project, project)
    parent = project / ".pyinit-backups"
    if not private_directory(parent):
        return []
    items = []
    for entry in sorted(
        parent.iterdir(), key=lambda p: (p.lstat().st_mtime_ns, p.name)
    ):
        if not re.fullmatch(r"[0-9a-f]{32}", entry.name):
            continue
        item = dict(
            id=entry.name,
            status="ilegivel",
            modified=time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(entry.lstat().st_mtime)
            ),
        )
        try:
            private_directory(entry)
            record = json.loads(read_private(entry / "manifest.json"))
            plan = record["plan"]
            item.update(
                status=str(record["status"]),
                format=str(plan["format"]),
                python=str(plan["python"]),
            )
        except (Refused, OSError, ValueError, KeyError, TypeError):
            pass
        items.append(item)
    return items


def plan_restore(project: Path, ident: str) -> tuple[dict, dict]:
    require(
        bool(re.fullmatch(r"[0-9a-f]{32}", ident)),
        "ID de backup invalido; consulte --list-backups.",
    )
    safe_directories(project, project)
    backup = project / ".pyinit-backups" / ident
    require(
        private_directory(backup.parent) and private_directory(backup),
        f"Backup inexistente: {ident}",
    )
    record = json.loads(read_private(backup / "manifest.json"))
    require(
        isinstance(record, dict)
        and isinstance(record.get("plan"), dict)
        and isinstance(record["plan"].get("inputs"), dict),
        "Manifesto de backup invalido.",
    )
    status = record.get("status")
    require(
        status in ("complete", "pending"),
        f"Backup com estado {status!r} nao pode ser restaurado.",
    )
    inputs = record["plan"]["inputs"]
    files = {}
    for name in MANAGED:
        current = fingerprint(project / name)
        if fingerprint(backup / "files" / name):
            files[name] = "restaurar do backup"
        elif inputs.get(name) == {} and current:
            files[name] = "remover (ausente antes da migracao)"
        else:
            # Copia ausente de um original existente: a migracao nao o alterou.
            files[name] = "manter"
        require(
            files[name] == "manter" or not current or stat.S_ISREG(current["mode"]),
            f"Arquivo atual deve ser regular: {name}",
        )
    venv = fingerprint(project / ".venv")
    require(
        not venv or stat.S_ISDIR(venv["mode"]),
        "Diretorio invalido ou simbolico: .venv",
    )
    if fingerprint(backup / "venv-before"):
        environment = "restaurar a .venv anterior; a atual vai para o backup"
    elif inputs.get(".venv") == {} and venv:
        environment = "mover a .venv atual para o backup (ausente antes da migracao)"
    else:
        environment = "manter"
    require(
        not fingerprint(backup / "after-restore"),
        "Backup ja contem after-restore; revise manualmente.",
    )
    plan = dict(
        operation="restore",
        project=str(project),
        backup=ident,
        status=status,
        format=record["plan"].get("format"),
        python=record["plan"].get("python"),
        files=files,
        environment=environment,
        current={name: fingerprint(project / name) for name in (*MANAGED, ".venv")},
        saved=".pyinit-backups/" + ident + "/after-restore",
        warnings=[
            "Arquivos atuais substituidos ou removidos sao copiados antes para "
            "after-restore; nao ha reversao automatica de uma restauracao parcial.",
            "Permissoes da raiz do projeto nao sao afrouxadas novamente.",
        ],
    )
    plan["approval"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True).encode()
    ).hexdigest()
    return plan, record


def apply_restore(plan: dict) -> Path:
    project = Path(plan["project"])
    rootfd = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(rootfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current, record = plan_restore(project, plan["backup"])
        require(
            current["approval"] == plan["approval"],
            "Projeto mudou apos a revisao; execute novamente.",
        )
        backup = project / ".pyinit-backups" / plan["backup"]
        inputs = record["plan"]["inputs"]
        after = backup / "after-restore"
        after.mkdir(mode=0o700)
        (after / "files").mkdir(mode=0o700)
        changed = [n for n in MANAGED if plan["files"][n] != "manter"]
        # Nada e substituido antes de todas as copias do estado atual existirem.
        for name in changed:
            if fingerprint(project / name):
                atomic(after / "files" / name, read_private(project / name))
        venv = project / ".venv"
        if plan["environment"] != "manter":
            if venv.exists():
                os.rename(venv, after / "venv")
            if (backup / "venv-before").exists():
                os.rename(backup / "venv-before", venv)
        for name in changed:
            if plan["files"][name].startswith("remover"):
                (project / name).unlink(missing_ok=True)
                continue
            mode = inputs.get(name, {}).get("mode", 0o600)
            if name in ("pyproject.toml", "uv.lock"):
                mode &= ~0o022
            atomic(project / name, read_private(backup / "files" / name), mode)
        protect_backup_ignore(project)
        record["status"] = "restored"
        atomic(backup / "manifest.json", (json.dumps(record, indent=2) + "\n").encode())
        return after
    finally:
        os.close(rootfd)


def confirmed(question: str) -> bool:
    print(question + " [s/N] ", end="", file=sys.stderr, flush=True)
    answer = os.fdopen(3).readline()
    return answer.endswith("\n") and answer.strip().lower() in ("s", "sim")


def restore(project: Path, ident: str, dry: bool) -> int:
    plan, _ = plan_restore(project, ident)
    print(json.dumps(plan, indent=2, ensure_ascii=False), flush=True)
    if dry:
        return 0
    if not confirmed(
        "Restaurar este backup? Arquivos e .venv atuais listados serao "
        "substituidos; copias ficam em after-restore."
    ):
        print("Restauracao cancelada; nenhum arquivo alterado.", file=sys.stderr)
        return 1
    after = apply_restore(plan)
    print(
        f"Restauracao concluida. Estado anterior a ela: {after}\n"
        "Nenhum stage, commit ou push foi executado."
    )
    return 0


def main() -> int:
    project = Path(os.path.abspath(sys.argv[1]))
    action = sys.argv[4] if len(sys.argv) > 4 else "migrate"
    if action == "list":
        print(json.dumps(list_backups(project), indent=2, ensure_ascii=False))
        return 0
    if action == "restore":
        return restore(project, sys.argv[5], sys.argv[3] == "true")
    python = sys.argv[2]
    dry = sys.argv[3] == "true"
    if not python:
        cfg = (
            Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
            / "devshell/venvs/geral/pyvenv.cfg"
        )
        if cfg.is_file() and not cfg.is_symlink():
            match = re.search(
                r"(?m)^(?:version_info|version)\s*=\s*(3\.\d+(?:\.\d+)?)\s*$",
                cfg.read_text(),
            )
            if match:
                python = match[1]
        python = python or "3.12"
    require(
        bool(re.fullmatch(r"3\.\d+(?:\.\d+)?", python)),
        "--python deve indicar CPython 3.MINOR[.PATCH].",
    )
    plan, originals, output = plan_migration(project, python)

    # URLs podem conter credenciais; o plano publico indica sua presenca sem expo-las.
    def public(value: object) -> object:
        if isinstance(value, dict):
            return {k: public(v) for k, v in value.items()}
        if isinstance(value, list):
            return [public(v) for v in value]
        return (
            "<valor com URL; revise o manifesto original>"
            if isinstance(value, str) and "://" in value
            else value
        )

    print(json.dumps(public(plan), indent=2, ensure_ascii=False), flush=True)
    if dry:
        return 0
    uv = shutil.which(
        os.environ.get("UV_BIN", str(Path.home() / ".local/bin/uv"))
    ) or shutil.which("uv")
    require(uv is not None, "uv ausente; instale-o explicitamente antes de migrar.")
    uv = os.path.abspath(uv)
    print(
        (
            "Migrar este plano? Cria backup e nova .venv; pode baixar "
            "pacotes e executar builds. CPython gerenciado deve estar "
            "instalado. [s/N] "
        ),
        end="",
        file=sys.stderr,
        flush=True,
    )
    answer = os.fdopen(3).readline()
    if not answer.endswith("\n") or answer.strip().lower() not in ("s", "sim"):
        print("Migracao cancelada; nenhum arquivo alterado.", file=sys.stderr)
        return 1
    backup = apply_migration(plan, originals, output, uv)
    print(
        f"Migracao concluida. Backup: {backup}\n"
        "Revise o .envrc completo e suas permissoes; "
        "execute direnv allow . manualmente.\n"
        "Valide os testes do projeto com uv run. "
        "Nenhum stage, commit ou push foi executado."
    )
    return 0


if __name__ == "__main__":
    try:
        # Encerramento e terminal fechado seguem o mesmo rollback do Ctrl+C.
        for number in (signal.SIGTERM, signal.SIGHUP):
            signal.signal(number, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        sys.exit(main())
    except (
        Refused,
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        SyntaxError,
        configparser.Error,
        subprocess.CalledProcessError,
        KeyboardInterrupt,
    ) as exc:
        message = (
            str(exc)
            if isinstance(exc, (Refused, OSError, subprocess.CalledProcessError))
            else "Operacao interrompida por sinal."
            if isinstance(exc, KeyboardInterrupt)
            else f"Arquivo invalido ({type(exc).__name__}); revise os manifestos."
        )
        if len(sys.argv) > 3 and sys.argv[3] == "true":
            print(
                json.dumps(
                    dict(
                        operation=sys.argv[4] if len(sys.argv) > 4 else "migrate",
                        project=sys.argv[1],
                        blockers=[message],
                    ),
                    ensure_ascii=False,
                )
            )
        print(f"Erro de migracao: {message}", file=sys.stderr)
        sys.exit(2)
PYINIT_MIGRATE
}

# Chamadas uv add do arquetipo; $1 executa (creation_uv) ou apenas mostra (show_uv).
archetype_additions() {
    case "$ARCHETYPE" in
        ds)
            "$1" add --python "$PYTHON_DEFAULT" polars duckdb pyarrow
            "$1" add --python "$PYTHON_DEFAULT" --dev ipykernel
            "$1" add --python "$PYTHON_DEFAULT" --group notebook jupyterlab
            ;;
        api) "$1" add --python "$PYTHON_DEFAULT" fastapi pydantic httpx ;;
        cli) "$1" add --python "$PYTHON_DEFAULT" typer rich ;;
        universal) ;; # Nenhuma dependencia extra alem das de dev
    esac
}

show_uv() {
    printf '  uv'
    printf ' %q' "$@"
    printf '\n'
}

# Plano da criacao: somente leitura, apos as mesmas conferencias iniciais.
plan_creation() {
    local base=$creation_project name file
    name=$(basename -- "$(realpath -ms -- "$TARGET_DIR")")
    echo "Plano de criacao (--dry-run): nada foi criado e uv nao foi chamado."
    if [[ -d "$base" ]]; then
        echo "Diretorio: $base (existente)"
    else
        echo "Diretorio: $base (sera criado)"
    fi
    echo "Python: $PYTHON_DEFAULT | Arquetipo: $ARCHETYPE | uv: $UV_CMD"
    echo "Chamadas uv, nesta ordem:"
    show_uv python install "$PYTHON_DEFAULT"
    if [[ ! -f "$base/pyproject.toml" ]]; then
        show_uv init --app --package --python "$PYTHON_DEFAULT" --name "$name" --no-workspace
    fi
    show_uv python pin "$PYTHON_DEFAULT" --no-project
    show_uv add --python "$PYTHON_DEFAULT" --dev pytest pytest-cov ruff
    archetype_additions show_uv
    show_uv sync --python "$PYTHON_DEFAULT"
    echo "Arquivos:"
    if [[ -f "$base/pyproject.toml" ]]; then
        echo "  pyproject.toml: existente; somente familias Ruff/pytest ausentes sao acrescentadas"
    else
        echo "  pyproject.toml: criar via uv init, com padroes Ruff/pytest"
    fi
    for file in "${CONFIG_FILES[@]}"; do
        if [[ ${CONFIG_STATES[$file]} == preserved ]]; then
            echo "  $file: preservar"
        else
            echo "  $file: criar"
        fi
    done
    if [[ -e "$base/tests" || -L "$base/tests" ]]; then
        echo "  tests/: preservar"
    else
        echo "  tests/test_smoke.py: criar"
    fi
    if [[ -e "$base/.envrc" || -L "$base/.envrc" ]]; then
        echo "  .envrc: preservar"
    else
        echo "  .envrc: criar (direnv allow continua manual)"
    fi
    if ! "$WITH_GIT"; then
        echo "  Git: nao inicializar (--no-git)"
    elif [[ -e "$base/.git" || -L "$base/.git" ]]; then
        echo "  Git: repositorio existente preservado"
    elif command -v git &>/dev/null; then
        echo "  Git: inicializar com git init -b main, sem stage ou commit"
    else
        echo "  Git: ausente no PATH; nao inicializar"
    fi
}

# Parsing de argumentos
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p | --python)
            [[ $# -ge 2 && "$2" != -* ]] || fail "--python exige uma versao."
            INIT_OPTIONS=true
            PYTHON_SET=true
            PYTHON_DEFAULT="$2"
            shift 2
            ;;
        -a | --archetype)
            [[ $# -ge 2 && "$2" != -* ]] || fail "--archetype exige um tipo."
            INIT_OPTIONS=true
            ARCHETYPE_SET=true
            ARCHETYPE="$2"
            case "$ARCHETYPE" in
                universal | ds | api | cli) ;;
                *) fail "Arquetipo desconhecido '$ARCHETYPE'; use universal, ds, api ou cli." ;;
            esac
            shift 2
            ;;
        --migrate)
            MIGRATE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-ide)
            CREATE_ONLY=true
            WITH_IDE=false
            shift
            ;;
        --no-r)
            CREATE_ONLY=true
            WITH_R=false
            shift
            ;;
        --no-git)
            CREATE_ONLY=true
            WITH_GIT=false
            shift
            ;;
        --restore)
            [[ $# -ge 2 && "$2" != -* ]] || fail "--restore exige o ID de um backup."
            RESTORE_ID="$2"
            shift 2
            ;;
        --list-backups)
            LIST_BACKUPS=true
            shift
            ;;
        -V | --version)
            echo "pyinit $PYINIT_VERSION"
            exit 0
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

if "$CREATE_ONLY" && { "$MIGRATE" || "$FIX_PERMISSIONS" || "$LIST_BACKUPS" || [[ -n "$RESTORE_ID" ]]; }; then
    fail "--no-ide, --no-r e --no-git pertencem somente a criacao."
fi
if "$LIST_BACKUPS" || [[ -n "$RESTORE_ID" ]]; then
    if "$MIGRATE" || "$FIX_PERMISSIONS" || "$SYNC" || "$ALLOW_DIRENV" || "$INIT_OPTIONS"; then
        fail "--restore e --list-backups nao aceitam outros modos, --python ou --archetype."
    fi
    if "$LIST_BACKUPS"; then
        [[ -z "$RESTORE_ID" ]] || fail "use --restore ou --list-backups, nao ambos."
        migrate_project list
    else
        migrate_project restore "$RESTORE_ID"
    fi
    exit 0
fi
if "$MIGRATE"; then
    if "$FIX_PERMISSIONS" || "$SYNC" || "$ALLOW_DIRENV" || "$ARCHETYPE_SET"; then
        fail "--migrate nao aceita --fix-permissions, --sync, --allow-direnv ou --archetype."
    fi
    migrate_project migrate
    exit 0
fi

if "$FIX_PERMISSIONS"; then
    "$DRY_RUN" && fail "--dry-run nao se aplica a --fix-permissions."
    "$INIT_OPTIONS" && fail "--fix-permissions nao aceita --python ou --archetype."
    maintain_project
    exit 0
fi
if "$SYNC" || "$ALLOW_DIRENV"; then
    fail "--sync e --allow-direnv exigem --fix-permissions."
fi
resolve_uv

for tool in stat mktemp ln rm rmdir realpath; do
    command -v "$tool" &>/dev/null || fail "$tool (coreutils) necessario para criar configuracoes sem sobrescrita."
done
CONFIG_FILES=()
"$WITH_IDE" && CONFIG_FILES+=(.vscode/settings.json)
"$WITH_R" && CONFIG_FILES+=(.Renviron .Rprofile)
declare -A CONFIG_STATES=()
inspect_creation_configs "$TARGET_DIR"
# A sentinela conserva LFs finais; retirar apenas o LF emitido pelo comando.
creation_project=$(realpath -m -- "$TARGET_DIR" && printf .) || fail "Nao foi possivel resolver o caminho fisico do projeto."
creation_project=${creation_project%$'\n.'}
[[ "$creation_project" != *$'\n' ]] || fail "Caminho fisico terminado em LF nao suportado; nenhuma chamada uv foi executada."
inspect_creation_scope
inspect_creation_venv
[[ -x /usr/bin/python3 ]] || fail "Criacao exige /usr/bin/python3 >=3.11 com tomllib."
configure_creation_tools "$TARGET_DIR/pyproject.toml" check

if "$DRY_RUN"; then
    plan_creation
    exit 0
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
creation_location=$(pwd -P && printf .) || fail "Nao foi possivel conferir o diretorio fisico do projeto."
creation_location=${creation_location%$'\n.'}
[[ "$creation_location" == "$creation_project" ]] || fail "Diretorio do projeto mudou durante o preparo."

# 2. Garantir runtime do Python
echo "==> Verificando runtime Python $PYTHON_DEFAULT..."
creation_uv python install "$PYTHON_DEFAULT"

# 3. Inicializar projeto com uv
if [ ! -f "pyproject.toml" ]; then
    echo "==> Inicializando pyproject.toml e estrutura base..."
    creation_uv init --app --package --python "$PYTHON_DEFAULT" --name "$PROJECT_NAME" --no-workspace
fi

# 4. Fixar versao no .python-version
creation_uv python pin "$PYTHON_DEFAULT" --no-project

# 5. Adicionar dependencias de desenvolvimento
echo "==> Configurando ferramentas de teste e lint..."
creation_uv add --python "$PYTHON_DEFAULT" --dev pytest pytest-cov ruff

# 6. Adicionar pacotes especificos de cada arquetipo
[[ "$ARCHETYPE" == universal ]] || echo "==> Adicionando stack do arquetipo $ARCHETYPE..."
archetype_additions creation_uv

# 7. Compor somente familias ausentes, sem reescrever configuracoes existentes.
echo "==> Preparando configuracoes Ruff/pytest..."
configure_creation_tools pyproject.toml apply

# 8. Integracao com IDEs (VS Code e Positron)
inspect_creation_configs .
if "$WITH_IDE"; then
    [[ -d .vscode ]] || mkdir -- .vscode
    echo "==> Preparando configuracoes IDE; arquivos existentes serao preservados..."
    write_creation_config .vscode/settings.json <<'EOF'
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

fi

# 9. Integracao com RStudio e Quarto CLI (.Renviron e .Rprofile)
if "$WITH_R"; then
    write_creation_config .Renviron <<'EOF'
RETICULATE_PYTHON=.venv/bin/python
EOF

    write_creation_config .Rprofile <<'EOF'
# Vincula o reticulate ao ambiente virtual gerenciado pelo uv
if (file.exists(".venv/bin/python")) {
  Sys.setenv(RETICULATE_PYTHON = file.path(getwd(), ".venv/bin/python"))
}
EOF
fi

# 9b. Teste inicial: testpaths aponta para tests/; um diretorio existente e preservado.
if [ ! -e tests ] && [ ! -L tests ]; then
    mkdir -- tests
    (
        set -o noclobber
        cat >tests/test_smoke.py <<'EOF'
"""Teste inicial do projeto; substitua pelos testes reais."""


def test_smoke() -> None:
    assert True
EOF
    )
fi

# 10. Sincronizar ambiente virtual
echo "==> Criando e sincronizando .venv..."
creation_uv sync --python "$PYTHON_DEFAULT"
inspect_creation_venv true

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
if "$WITH_R" && [ -f ".gitignore" ]; then
    if ! grep -qxF '.Rproj.user/' .gitignore; then
        cat >>.gitignore <<'EOF'

# RStudio e reticulate locais
.Rhistory
.RData
.Rproj.user/
EOF
    fi
fi

# 13. Inicializar Git caso ainda nao exista, inclusive em worktrees.
if "$WITH_GIT" && [ ! -e ".git" ] && [ ! -L ".git" ] && command -v git &>/dev/null; then
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
[[ ${#CONFIG_FILES[@]} -eq 0 ]] || echo "Arquivos de configuracao IDE/R:"
for file in "${CONFIG_FILES[@]}"; do
    if [[ ${CONFIG_STATES[$file]} == preserved ]]; then
        echo "  $file: preservado; conteudo e integracao nao foram alterados nem verificados."
    else
        echo "  $file: criado com a configuracao padrao para .venv."
    fi
done
echo ""
