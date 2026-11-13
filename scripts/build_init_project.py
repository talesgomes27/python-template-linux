"""Gera scripts/init_project.sh a partir do modelo e dos modulos em scripts/pyinit.

O gerador distribuido continua sendo um unico arquivo Bash; o Python embutido
vive em modulos proprios, verificados por Ruff e importaveis nos testes.

Uso:
  uv run python scripts/build_init_project.py           # regrava o script
  uv run python scripts/build_init_project.py --check   # falha se desatualizado
"""

import re
import sys
import tomllib
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
TEMPLATE = SCRIPTS / "init_project.sh.in"
OUTPUT = SCRIPTS / "init_project.sh"
MODULES = SCRIPTS / "pyinit"
EMBED = re.compile(r"^@@PYINIT_EMBED:([a-z_]+\.py)@@$")
VERSION = "@@PYINIT_VERSION@@"
ACTION = re.compile(r"@@ACTION:([\w.-]+/[\w.-]+)@@")
WORKFLOW = SCRIPTS.parent / ".github/workflows/ci.yml"
HEREDOC = re.compile(r"<<'([A-Z_]+)'$")
NOTICE = (
    "# ARQUIVO GERADO por scripts/build_init_project.py: nao edite diretamente.\n"
    "# Fontes: scripts/init_project.sh.in e scripts/pyinit/*.py\n"
)


def pinned_actions() -> dict[str, str]:
    """Le do CI do template as actions fixadas por SHA, com o comentario de versao.

    O CI gerado para novos projetos reutiliza exatamente essas referencias, que
    o Dependabot mantem atualizadas no workflow do template.
    """
    pattern = re.compile(r"uses:\s*(([\w.-]+/[\w.-]+)@[0-9a-f]{40}\s+#\s*v\S+)\s*$")
    found = {}
    for line in WORKFLOW.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if match:
            found[match[2]] = match[1]
    return found


def render() -> str:
    """Monta o script final, embutindo cada modulo em seu heredoc."""
    lines = TEMPLATE.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or not lines[0].startswith("#!"):
        raise ValueError("o modelo deve comecar com a linha shebang")
    manifest = tomllib.loads((SCRIPTS.parent / "pyproject.toml").read_text())
    version = manifest["project"]["version"]
    actions = pinned_actions()

    def action(match: re.Match[str]) -> str:
        if match[1] not in actions:
            raise ValueError(f"{match[1]}: action sem SHA fixado em {WORKFLOW.name}")
        return actions[match[1]]

    output = [lines[0], NOTICE]
    for previous, line in zip(lines, lines[1:], strict=False):
        line = ACTION.sub(action, line.replace(VERSION, version))
        match = EMBED.match(line.rstrip("\n"))
        if match is None:
            output.append(line)
            continue
        opener = HEREDOC.search(previous.rstrip("\n"))
        if opener is None:
            raise ValueError(f"{match[1]}: marcador fora de um heredoc citado")
        body = (MODULES / match[1]).read_text(encoding="utf-8")
        if opener[1] in body.splitlines():
            raise ValueError(f"{match[1]}: contem o delimitador {opener[1]}")
        output.append(body if body.endswith("\n") else body + "\n")
    return "".join(output)


def main(argv: list[str]) -> int:
    rendered = render()
    if argv[1:] == ["--check"]:
        if OUTPUT.read_text(encoding="utf-8") != rendered:
            print(
                "scripts/init_project.sh desatualizado; "
                "execute uv run python scripts/build_init_project.py",
                file=sys.stderr,
            )
            return 1
        return 0
    if argv[1:]:
        print("Uso: build_init_project.py [--check]", file=sys.stderr)
        return 2
    OUTPUT.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
