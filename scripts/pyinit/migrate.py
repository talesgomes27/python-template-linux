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
                    "(?:===|==|!=|~=|>=|<=|>|<)[\\w.*+!-]+(?:\\s*,\\s*(?:"
                    "===|==|!=|~=|>=|<=|>|<)[\\w.*+!-]+)*"
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
                for name in (
                    "pyproject.toml",
                    "uv.lock",
                    ".python-version",
                    ".envrc",
                    ".gitignore",
                ):
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


def main() -> int:
    project = Path(os.path.abspath(sys.argv[1]))
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
        signal.signal(
            signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt())
        )
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
            else f"Arquivo invalido ({type(exc).__name__}); revise os manifestos."
        )
        if len(sys.argv) > 3 and sys.argv[3] == "true":
            print(
                json.dumps(
                    dict(operation="migrate", project=sys.argv[1], blockers=[message]),
                    ensure_ascii=False,
                )
            )
        print(f"Erro de migracao: {message}", file=sys.stderr)
        sys.exit(2)
