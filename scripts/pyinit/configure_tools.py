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
