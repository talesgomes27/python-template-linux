"""Executa o gerador sem downloads, autorização direnv ou commits reais."""

import json
import os
import shutil
import stat
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/init_project.sh"


@pytest.fixture
def scaffold(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    home = tmp_path / "home"
    tools = tmp_path / "tools"
    git_template = tmp_path / "git-template"
    workspace = tmp_path / "workspace com espaços"
    for directory in (home, tools, git_template, workspace):
        directory.mkdir(mode=0o700)
    uv = shutil.which("uv")
    git = shutil.which("git")
    assert uv and git, "Os testes do gerador exigem uv e Git instalados"
    env = {
        "HOME": str(home),
        "PATH": str(tools) + os.pathsep + os.defpath,
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "UV_CACHE_DIR": str(home / ".cache/uv"),
        "UV_PYTHON_INSTALL_DIR": str(home / ".local/share/uv/python"),
        "UV_BIN": str(tools / "uv"),
        "TEST_REAL_UV": uv,
        "TEST_REAL_GIT": git,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TEMPLATE_DIR": str(git_template),
        "PYTHONDONTWRITEBYTECODE": "1",
        "TEST_COMMAND_LOG": str(home / "commands.jsonl"),
        "TEST_UV_DETAILS": str(home / "uv-details.jsonl"),
    }
    # Simular somente instalação/resolução; a .venv é criada pelo uv real offline.
    (tools / "uv").write_text(
        f"#!{sys.executable}\n"
        "import json, os, subprocess, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['TEST_COMMAND_LOG'], 'a') as log:\n"
        "    log.write(json.dumps(['uv', *args]) + '\\n')\n"
        "keys = ('UV_PROJECT_ENVIRONMENT', 'UV_PROJECT', 'UV_WORKING_DIR',\n"
        "        'UV_WORKING_DIRECTORY', 'VIRTUAL_ENV', 'CONDA_PREFIX',\n"
        "        'CONDA_DEFAULT_ENV', 'UV_ACTIVE', 'UV_PYTHON', 'UV_INDEX_URL',\n"
        "        'UV_INDEX_USERNAME', 'SSL_CERT_FILE', 'UV_CACHE_DIR',\n"
        "        'UV_PYTHON_INSTALL_DIR')\n"
        "with open(os.environ['TEST_UV_DETAILS'], 'a') as log:\n"
        "    log.write(json.dumps(dict(executable=sys.argv[0], args=args,\n"
        "        cwd=os.getcwd(), env={k: os.environ.get(k) for k in keys})) + '\\n')\n"
        "stage = args[1] if args[0] == 'python' else args[0]\n"
        "if os.environ.get('TEST_FAIL_AT') == stage:\n"
        "    sys.exit(29)\n"
        "if os.environ.get('TEST_MODEL_REDIRECTION') and stage != 'install':\n"
        "    for key in ('UV_PROJECT', 'UV_WORKING_DIR', 'UV_WORKING_DIRECTORY'):\n"
        "        if os.environ.get(key):\n"
        "            (Path(os.environ[key]) / ('unexpected-' + stage)).touch()\n"
        "    if args[0] in ('add', 'sync'):\n"
        "        target = os.environ.get('UV_PROJECT_ENVIRONMENT')\n"
        "        if os.environ.get('UV_ACTIVE') and os.environ.get('VIRTUAL_ENV'):\n"
        "            target = os.environ['VIRTUAL_ENV']\n"
        "        if target and Path(target).resolve() != Path('.venv').resolve():\n"
        "            Path(target).mkdir(parents=True, exist_ok=True)\n"
        "            (Path(target) / ('unexpected-' + stage)).touch()\n"
        "if args[:2] == ['python', 'install']:\n"
        "    if os.environ.get('TEST_PROJECT_AFTER_INSTALL'):\n"
        "        Path('pyproject.toml').write_text(\n"
        "            os.environ['TEST_PROJECT_AFTER_INSTALL'])\n"
        "    if os.environ.get('TEST_CONFIG_APPEARS'):\n"
        "        path = Path(os.environ['TEST_CONFIG_APPEARS'])\n"
        "        path.parent.mkdir(parents=True, exist_ok=True)\n"
        "        path.write_bytes(b'configuration appeared during uv\\n')\n"
        "    if os.environ.get('TEST_VSCODE_LINK'):\n"
        "        Path('.vscode').symlink_to(os.environ['TEST_VSCODE_LINK'])\n"
        "elif args[:1] == ['init']:\n"
        "    Path('pyproject.toml').write_text(\n"
        '        \'[project]\\nname = "sample"\\nversion = "0.1.0"\\n\')\n'
        "    Path('.gitignore').write_text('.venv/\\n')\n"
        "elif args[:2] == ['python', 'pin']:\n"
        "    Path('.python-version').write_text(args[2] + '\\n')\n"
        "elif args[:1] == ['add']:\n"
        "    pass\n"
        "elif args[:2] == ['workspace', 'dir']:\n"
        "    sys.exit(subprocess.call([os.environ['TEST_REAL_UV'], *args]))\n"
        "elif args[:1] == ['sync']:\n"
        "    Path(os.environ['HOME'], 'sync-env.json').write_text(json.dumps(\n"
        "        {key: os.environ.get(key) for key in (\n"
        "            'UV_PROJECT_ENVIRONMENT', 'UV_PROJECT',\n"
        "            'UV_WORKING_DIR', 'VIRTUAL_ENV')}))\n"
        "    if os.environ.get('TEST_SYNC_FAILURE'):\n"
        "        sys.exit(27)\n"
        "    if os.environ.get('TEST_SKIP_ENV_CREATION'):\n"
        "        pass\n"
        "    elif os.environ.get('TEST_SKIP_VENV'):\n"
        "        Path('.venv/bin').mkdir(parents=True, exist_ok=True)\n"
        "        Path('.venv/pyvenv.cfg').write_text('version = 3.12\\n')\n"
        "        for name in ('python', 'python3'):\n"
        "            path = Path('.venv/bin') / name\n"
        "            if not path.exists(): path.symlink_to(sys.executable)\n"
        "    elif not Path('.venv/pyvenv.cfg').exists():\n"
        "        subprocess.run([os.environ['TEST_REAL_UV'],\n"
        "            '--no-config', '--no-cache', '--offline', 'venv',\n"
        "            '--no-project', '--no-python-downloads',\n"
        "            '--python', sys.executable, '.venv'], check=True)\n"
        "else:\n"
        "    raise SystemExit('uv inesperado: ' + repr(args))\n"
    )
    # Registrar tentativas proibidas sem criar commits nem stage, mesmo no teste RED.
    (tools / "git").write_text(
        f"#!{sys.executable}\n"
        "import os, subprocess, sys\n"
        "from pathlib import Path\n"
        "if sys.argv[1] in ('add', 'commit', 'push'):\n"
        "    with (Path(os.environ['HOME']) / 'forbidden-git').open('a') as log:\n"
        "        log.write(sys.argv[1] + '\\n')\n"
        "else:\n"
        "    sys.exit(subprocess.call([os.environ['TEST_REAL_GIT'], *sys.argv[1:]]))\n"
    )
    (tools / "direnv").write_text(
        "#!/bin/sh\n"
        'printf \'["direnv", "allow", "."]\\n\' >>"$TEST_COMMAND_LOG"\n'
        'mkdir -p "$XDG_DATA_HOME/direnv/allow"\n'
        'touch "$XDG_DATA_HOME/direnv/allow/unreviewed"\n'
    )
    for tool in ("uv", "git", "direnv"):
        (tools / tool).chmod(0o700)
    return workspace, env


def run_init(
    scaffold: tuple[Path, dict[str, str]],
    target: Path | None,
    *args: str,
    answers: str = "",
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    workspace, env = scaffold
    return subprocess.run(
        ["bash", str(SCRIPT), *([] if target is None else [str(target)]), *args],
        cwd=workspace if cwd is None else cwd,
        env=env,
        capture_output=True,
        text=True,
        input=answers,
        preexec_fn=lambda: os.umask(0o002),
        timeout=30,
    )


@pytest.fixture
def config_creation(
    scaffold: tuple[Path, dict[str, str]],
) -> tuple[Path, dict[str, str]]:
    # A1 cobre arquivos e ordem das chamadas; não precisa criar uma .venv real.
    scaffold[1]["TEST_SKIP_VENV"] = "1"
    return scaffold


CONFIG_FILES = (".vscode/settings.json", ".Renviron", ".Rprofile")


@pytest.mark.parametrize(
    ("source", "requires_python", "configuration", "expected_minor"),
    [
        ("template", ">=3.10", "", 10),
        ("generated", ">=3.10", "", 10),
        ("generated", ">=3.11", "", 11),
        ("generated", ">=3.12", "", 12),
        ("generated", ">=3.13", "", 13),
        ("generated", ">=3.10", '[tool.ruff.lint]\nselect = ["F"]\n', 10),
        ("generated", ">=3.13", '[tool.ruff]\ntarget-version = "py39"\n', 9),
    ],
    ids=["template", "py310", "py311", "py312", "py313", "partial", "explicit"],
)
def test_ruff_target_follows_project_floor_or_existing_override(
    config_creation: tuple[Path, dict[str, str]],
    source: str,
    requires_python: str,
    configuration: str,
    expected_minor: int,
) -> None:
    workspace, env = config_creation
    ruff = shutil.which("ruff")
    assert ruff, "Os testes de inferencia exigem Ruff instalado no ambiente de testes"
    target = workspace / "ruff project"
    target.mkdir()
    manifest = target / "pyproject.toml"
    if source == "template":
        manifest.write_bytes((SCRIPT.parent.parent / "pyproject.toml").read_bytes())
    else:
        original = (
            '[project]\nname = "sample"\nversion = "0.1.0"\n'
            f'requires-python = "{requires_python}"\n' + configuration
        ).encode()
        manifest.write_bytes(original)
        result = run_init(config_creation, target, "--python", "3.13")
        assert result.returncode == 0, result.stderr
        assert manifest.read_bytes().startswith(original)
    before = manifest.read_bytes()
    sample = target / "version_checks.py"
    sample.write_text(
        "import sys\n\n"
        f"if sys.version_info < (3, {expected_minor}):\n"
        '    print("older")\n'
        f"if sys.version_info < (3, {expected_minor + 1}):\n"
        '    print("next")\n'
    )
    # UP036 distingue o piso exato sem depender do formato de --show-settings.
    checked = subprocess.run(
        [
            ruff,
            "check",
            "--no-cache",
            "--select",
            "UP036",
            "--output-format",
            "json",
            str(sample),
        ],
        cwd=target,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert checked.returncode == 1, checked.stderr
    assert [(d["code"], d["location"]["row"]) for d in json.loads(checked.stdout)] == [
        ("UP036", 3)
    ]
    assert manifest.read_bytes() == before
    data = tomllib.loads(before.decode())
    assert data["project"]["requires-python"] == requires_python
    if configuration:
        assert data["tool"]["ruff"] == tomllib.loads(configuration)["tool"]["ruff"]
    else:
        assert "target-version" not in data["tool"]["ruff"]


@pytest.mark.parametrize(
    ("configuration", "ruff", "pytest_config"),
    [
        ("", None, None),
        ("[tool.ruff]\nline-length = 101\n", {"line-length": 101}, None),
        (
            '[tool.pytest.ini_options]\naddopts = "-x"\ntestpaths = ["specs"]\n',
            None,
            {"ini_options": {"addopts": "-x", "testpaths": ["specs"]}},
        ),
        (
            '[tool.ruff.lint]\nselect = ["F"]\n',
            {"lint": {"select": ["F"]}},
            None,
        ),
        ("[\"tool\" . 'ruff']\nline-length = 101\n", {"line-length": 101}, None),
        (
            'tool.ruff.line-length = 101\ntool.pytest.ini_options.addopts = "-x"\n',
            {"line-length": 101},
            {"ini_options": {"addopts": "-x"}},
        ),
        (
            "tool = {ruff = {line-length = 101}, "
            'pytest = {ini_options = {addopts = "-x"}}}\n',
            {"line-length": 101},
            {"ini_options": {"addopts": "-x"}},
        ),
        ('[tool.pytest]\naddopts = ["-x"]\n', None, {"addopts": ["-x"]}),
        (
            '# [tool.ruff]\nnote = """\n[tool.ruff]\n[tool.pytest.ini_options]\n"""\n',
            None,
            None,
        ),
    ],
)
def test_creation_tool_configuration_composes_missing_families(
    config_creation: tuple[Path, dict[str, str]],
    configuration: str,
    ruff: dict | None,
    pytest_config: dict | None,
) -> None:
    workspace, _ = config_creation
    target = workspace / "existing project"
    target.mkdir()
    manifest = target / "pyproject.toml"
    original = (
        configuration + '[project]\nname = "sample"\nversion = "0.1.0"\n'
    ).encode()
    manifest.write_bytes(original)
    result = run_init(config_creation, target)
    assert result.returncode == 0, result.stderr
    final = manifest.read_bytes()
    assert final.startswith(original), "A composicao reescreveu configuracao existente"
    data = tomllib.loads(final.decode())
    assert data["tool"]["ruff"] == (
        ruff
        if ruff is not None
        else {
            "line-length": 88,
            "lint": {"select": ["E", "F", "I", "B", "UP"]},
            "format": {"quote-style": "double", "indent-style": "space"},
        }
    )
    assert data["tool"]["pytest"] == (
        pytest_config
        if pytest_config is not None
        else {
            "ini_options": {
                "minversion": "8.0",
                "testpaths": ["tests"],
                "pythonpath": ["src"],
                "addopts": "-ra -q --strict-markers",
            }
        }
    )
    if ruff is not None and pytest_config is not None:
        assert final == original


@pytest.mark.parametrize("ending", ["crlf", "no-final-newline"])
def test_creation_tool_configuration_preserves_original_bytes(
    config_creation: tuple[Path, dict[str, str]], ending: str
) -> None:
    workspace, _ = config_creation
    target = workspace / "existing project"
    target.mkdir()
    manifest = target / "pyproject.toml"
    original = b'[tool.pytest.ini_options]\naddopts = "-x"\n'
    original += b'[project]\nname = "sample"\nversion = "0.1.0"\n'
    original = (
        original.replace(b"\n", b"\r\n") if ending == "crlf" else original.rstrip(b"\n")
    )
    manifest.write_bytes(original)
    result = run_init(config_creation, target)
    assert result.returncode == 0, result.stderr
    assert manifest.read_bytes().startswith(original)
    data = tomllib.loads(manifest.read_text())
    assert data["tool"]["pytest"]["ini_options"] == {"addopts": "-x"}
    assert data["tool"]["ruff"]["lint"]["select"] == ["E", "F", "I", "B", "UP"]


@pytest.mark.parametrize(
    "configuration",
    [
        'tool = "not a table"\n',
        'tool.ruff = "not a table"\n',
        "tool.pytest = []\n",
        "tool = {ruff = {line-length = 101}}\n",
        "[tool.pytest.ini_options\n",
    ],
)
def test_creation_tool_configuration_refuses_uncomposable_toml_before_uv(
    config_creation: tuple[Path, dict[str, str]], configuration: str
) -> None:
    workspace, env = config_creation
    target = workspace / "existing project"
    target.mkdir()
    manifest = target / "pyproject.toml"
    manifest.write_text(
        configuration + '[project]\nname = "sample"\nversion = "0.1.0"\n'
    )
    before = config_snapshot(target)
    result = run_init(config_creation, target)
    assert result.returncode == 2, result.stderr
    assert "pyproject.toml" in result.stderr
    assert "Traceback" not in result.stderr
    assert not Path(env["TEST_COMMAND_LOG"]).exists()
    assert config_snapshot(target) == before


@pytest.mark.parametrize(
    "changed", ["[project\n", "tool = {ruff = {line-length = 101}}\n"]
)
def test_creation_tool_configuration_rechecks_before_appending(
    config_creation: tuple[Path, dict[str, str]], changed: str
) -> None:
    workspace, env = config_creation
    target = workspace / "existing project"
    target.mkdir()
    manifest = target / "pyproject.toml"
    manifest.write_text('[project]\nname = "sample"\nversion = "0.1.0"\n')
    env["TEST_PROJECT_AFTER_INSTALL"] = changed
    result = run_init(config_creation, target)
    assert result.returncode == 2, result.stderr
    assert manifest.read_text() == changed
    assert not (target / ".vscode").exists()
    assert "Projeto configurado com sucesso" not in result.stdout


def test_creation_tool_configuration_rerun_preserves_toml(
    config_creation: tuple[Path, dict[str, str]],
) -> None:
    workspace, _ = config_creation
    target = workspace / "new project"
    first = run_init(config_creation, target)
    assert first.returncode == 0, first.stderr
    manifest = target / "pyproject.toml"
    original, before = manifest.read_bytes(), manifest.stat()
    second = run_init(config_creation, target)
    assert second.returncode == 0, second.stderr
    assert manifest.read_bytes() == original
    assert manifest.stat() == before


def config_snapshot(
    path: Path,
) -> dict[str, tuple[int, int, int, int, bytes | str | None]]:
    result = {}
    for entry in path.rglob("*"):
        info = entry.lstat()
        content = (
            os.readlink(entry)
            if entry.is_symlink()
            else entry.read_bytes()
            if stat.S_ISREG(info.st_mode)
            else None
        )
        result[str(entry.relative_to(path))] = (
            info.st_mode,
            info.st_ino,
            info.st_nlink,
            info.st_mtime_ns,
            content,
        )
    return result


@pytest.mark.parametrize("current_directory", [False, True])
def test_creation_config_defaults(
    config_creation: tuple[Path, dict[str, str]], current_directory: bool
) -> None:
    workspace, _ = config_creation
    target = workspace if current_directory else workspace / "new project com espaços"
    result = run_init(config_creation, None if current_directory else target)
    assert result.returncode == 0, result.stderr
    settings = json.loads((target / CONFIG_FILES[0]).read_text())
    assert (
        settings["python.defaultInterpreterPath"]
        == "${workspaceFolder}/.venv/bin/python"
    )
    renviron = (target / ".Renviron").read_bytes()
    assert renviron == b"RETICULATE_PYTHON=.venv/bin/python\n"
    assert (target / ".Rprofile").read_text() == (
        "# Vincula o reticulate ao ambiente virtual gerenciado pelo uv\n"
        'if (file.exists(".venv/bin/python")) {\n'
        '  Sys.setenv(RETICULATE_PYTHON = file.path(getwd(), ".venv/bin/python"))\n'
        "}\n"
    )
    for relative in CONFIG_FILES:
        path = target / relative
        assert path.is_file() and not path.is_symlink()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert f"{relative}: criado" in result.stdout


@pytest.mark.parametrize("relative", CONFIG_FILES)
def test_creation_config_preserves_regular_files_and_vscode_neighbors(
    config_creation: tuple[Path, dict[str, str]], relative: str
) -> None:
    workspace, _ = config_creation
    target = workspace / "existing project"
    (target / ".vscode").mkdir(parents=True)
    neighbor = target / ".vscode/launch.json"
    neighbor.write_bytes(b'{"personal": true}\n')
    path = target / relative
    original = b'source("renv/activate.R")\n# personal\x00\xff\n'
    path.write_bytes(original)
    path.chmod(0o640)
    before = config_snapshot(target)
    result = run_init(config_creation, target)
    assert result.returncode == 0, result.stderr
    assert path.read_bytes() == original
    assert config_snapshot(target)[relative] == before[relative]
    assert neighbor.read_bytes() == b'{"personal": true}\n'
    assert f"{relative}: preservado" in result.stdout
    assert "settings.json configurado" not in result.stdout
    assert ".Renviron e .Rprofile apontam" not in result.stdout


@pytest.mark.parametrize("relative", CONFIG_FILES)
@pytest.mark.parametrize(
    "kind", ["symlink", "dangling", "hardlink", "directory", "fifo"]
)
def test_creation_config_conflict_blocks_uv_and_preserves_links(
    config_creation: tuple[Path, dict[str, str]], relative: str, kind: str
) -> None:
    workspace, env = config_creation
    target = workspace / "existing project"
    (target / ".vscode").mkdir(parents=True)
    path = target / relative
    outside = workspace / "external artificial config"
    if kind != "dangling":
        outside.write_bytes(b"external configuration\n")
    if kind in ("symlink", "dangling"):
        path.symlink_to(outside)
    elif kind == "hardlink":
        path.hardlink_to(outside)
    elif kind == "directory":
        path.mkdir()
    else:
        os.mkfifo(path)
    before = config_snapshot(workspace)
    result = run_init(config_creation, target)
    assert result.returncode == 2, result.stderr
    assert relative in result.stderr
    assert not Path(env["TEST_COMMAND_LOG"]).exists(), "uv executou antes do bloqueio"
    assert config_snapshot(workspace) == before


@pytest.mark.parametrize("kind", ["symlink", "file"])
def test_creation_config_rejects_vscode_conflicts_before_uv(
    config_creation: tuple[Path, dict[str, str]], kind: str
) -> None:
    workspace, env = config_creation
    target = workspace / "existing project"
    target.mkdir()
    outside = workspace / "external vscode"
    outside.mkdir()
    (outside / "settings.json").write_bytes(b"external settings\n")
    if kind == "symlink":
        (target / ".vscode").symlink_to(outside, target_is_directory=True)
    else:
        (target / ".vscode").write_bytes(b"not a directory\n")
    before = config_snapshot(workspace)
    result = run_init(config_creation, target)
    assert result.returncode == 2, result.stderr
    assert ".vscode" in result.stderr
    assert not Path(env["TEST_COMMAND_LOG"]).exists()
    assert config_snapshot(workspace) == before


def test_creation_config_rerun_preserves_all_defaults(
    config_creation: tuple[Path, dict[str, str]],
) -> None:
    workspace, _ = config_creation
    target = workspace / "new project"
    first = run_init(config_creation, target)
    assert first.returncode == 0, first.stderr
    before = config_snapshot(target)
    contents = {relative: (target / relative).read_bytes() for relative in CONFIG_FILES}
    second = run_init(config_creation, target)
    assert second.returncode == 0, second.stderr
    for relative in CONFIG_FILES:
        assert config_snapshot(target)[relative] == before[relative]
        assert (target / relative).read_bytes() == contents[relative]
        assert f"{relative}: preservado" in second.stdout


@pytest.mark.parametrize("relative", CONFIG_FILES)
def test_creation_config_refuses_file_appearing_during_uv(
    config_creation: tuple[Path, dict[str, str]], relative: str
) -> None:
    workspace, env = config_creation
    target = workspace / "new project"
    path = target / relative
    env["TEST_CONFIG_APPEARS"] = str(path)
    result = run_init(config_creation, target)
    assert result.returncode == 2, result.stderr
    assert relative in result.stderr
    assert path.read_bytes() == b"configuration appeared during uv\n"
    assert all(
        not (target / other).exists() for other in CONFIG_FILES if other != relative
    )


def test_creation_config_rechecks_vscode_after_uv(
    config_creation: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = config_creation
    outside = workspace / "external vscode"
    outside.mkdir()
    (outside / "settings.json").write_bytes(b"external settings\n")
    before = config_snapshot(outside)
    env["TEST_VSCODE_LINK"] = str(outside)
    result = run_init(config_creation, workspace / "new project")
    assert result.returncode == 2, result.stderr
    assert ".vscode" in result.stderr
    assert config_snapshot(outside) == before


@pytest.mark.parametrize("kind", ["regular", "fifo-symlink"])
def test_creation_config_exclusive_write_refuses_late_file(
    config_creation: tuple[Path, dict[str, str]], kind: str
) -> None:
    workspace, env = config_creation
    target = workspace / "new project"
    env["TEST_LATE_CONFIG"] = str(target / ".Renviron")
    env["TEST_LATE_KIND"] = kind
    outside = workspace / "external fifo"
    os.mkfifo(outside)
    env["TEST_EXTERNAL_FIFO"] = str(outside)
    before = config_snapshot(workspace)
    fake_cat = Path(env["UV_BIN"]).with_name("cat")
    fake_cat.write_text(
        "#!/bin/sh\n"
        "/usr/bin/cat\n"
        'if [ "${PWD##*/}" = .vscode ]; then\n'
        '    if [ "$TEST_LATE_KIND" = regular ]; then\n'
        '        printf "late configuration\\n" >"$TEST_LATE_CONFIG"\n'
        "    else\n"
        '        ln -s "$TEST_EXTERNAL_FIFO" "$TEST_LATE_CONFIG"\n'
        "    fi\n"
        "fi\n"
    )
    fake_cat.chmod(0o700)
    reader = os.open(outside, os.O_RDONLY | os.O_NONBLOCK)
    try:
        result = run_init(config_creation, target)
        received = os.read(reader, 4096)
    finally:
        os.close(reader)
    assert result.returncode == 2, result.stderr
    assert ".Renviron" in result.stderr
    assert received == b"", "O gerador escreveu no FIFO externo"
    assert config_snapshot(workspace)[outside.name] == before[outside.name]
    if kind == "regular":
        assert (target / ".Renviron").read_bytes() == b"late configuration\n"
    else:
        assert (target / ".Renviron").is_symlink()
        assert (target / ".Renviron").readlink() == outside


@pytest.mark.parametrize("relative", [".", ".vscode"])
def test_creation_config_refuses_unsearchable_directory_before_uv(
    config_creation: tuple[Path, dict[str, str]], relative: str
) -> None:
    workspace, env = config_creation
    target = workspace / "existing project"
    (target / ".vscode").mkdir(parents=True)
    outside = workspace / "external config"
    outside.write_bytes(b"external configuration\n")
    (target / ".vscode/settings.json").symlink_to(outside)
    directory = target / relative
    original_mode = stat.S_IMODE(directory.stat().st_mode)
    directory.chmod(0o600)
    before = outside.stat()
    try:
        result = run_init(config_creation, target)
        assert result.returncode == 2, result.stderr
        assert str(directory) in result.stderr
        assert not Path(env["TEST_COMMAND_LOG"]).exists()
        assert stat.S_IMODE(directory.stat().st_mode) == 0o600
        assert outside.stat() == before
        assert outside.read_bytes() == b"external configuration\n"
    finally:
        # Somente limpeza, depois de testar a recusa com o modo inseguro intacto.
        directory.chmod(original_mode)


def test_creation_config_does_not_publish_partial_content(
    config_creation: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = config_creation
    target = workspace / "new project"
    fake_cat = Path(env["UV_BIN"]).with_name("cat")
    fake_cat.write_text(
        "#!/bin/sh\n"
        'if [ "${PWD##*/}" = .vscode ]; then\n'
        "    printf partial\n"
        "    exit 17\n"
        "fi\n"
        "exec /usr/bin/cat\n"
    )
    fake_cat.chmod(0o700)
    result = run_init(config_creation, target)
    assert result.returncode == 2, result.stderr
    assert all(not (target / relative).exists() for relative in CONFIG_FILES)
    assert list((target / ".vscode").iterdir()) == []


def uv_details(env: dict[str, str]) -> list[dict]:
    path = Path(env["TEST_UV_DETAILS"])
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.mark.parametrize(
    "lookup", ["override", "relative-path", "empty-path", "dot-path"]
)
def test_creation_uv_is_resolved_before_cd(
    scaffold: tuple[Path, dict[str, str]], lookup: str
) -> None:
    workspace, env = scaffold
    target = workspace / "project com espaços"
    chosen = workspace / "tools com espaços/uv"
    chosen.parent.mkdir()
    shutil.copy2(env["UV_BIN"], chosen)
    if lookup == "override":
        env["UV_BIN"] = "./tools com espaços/uv"
        wrong = target / "tools com espaços/uv"
    elif lookup == "relative-path":
        del env["UV_BIN"]
        env["PATH"] = "tools com espaços" + os.pathsep + os.defpath
        wrong = target / "tools com espaços/uv"
    else:
        chosen = workspace / "uv"
        shutil.copy2(env["UV_BIN"], chosen)
        del env["UV_BIN"]
        env["PATH"] = ("" if lookup == "empty-path" else ".") + os.pathsep + os.defpath
        wrong = target / "uv"
    wrong.parent.mkdir(parents=True)
    wrong.write_text("#!/bin/sh\ntouch wrong-uv-executed\nexit 73\n")
    wrong.chmod(0o700)
    result = run_init(scaffold, target, "--python", "3.13.11", "--archetype", "cli")
    assert result.returncode == 0, result.stderr
    assert not (target / "wrong-uv-executed").exists()
    calls = uv_details(env)
    assert all(Path(call["executable"]) == chosen for call in calls)
    assert calls[0]["args"] == ["python", "install", "3.13.11"]
    init = next(call["args"] for call in calls if call["args"][0] == "init")
    assert init[init.index("--name") + 1] == target.name
    assert init[init.index("--python") + 1] == "3.13.11"
    assert any(call["args"][-2:] == ["typer", "rich"] for call in calls)


def test_creation_uv_missing_fails_before_writes(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = scaffold
    tools = workspace / "only bash"
    tools.mkdir()
    (tools / "bash").symlink_to(shutil.which("bash"))
    env["PATH"] = str(tools)
    env["UV_BIN"] = str(tools / "missing-uv")
    target = workspace / "new project"
    result = run_init(scaffold, target)
    assert result.returncode == 2
    assert not target.exists()
    assert not Path(env["TEST_COMMAND_LOG"]).exists()


@pytest.mark.parametrize("stage", ["install", "init", "pin", "add", "sync"])
def test_creation_uv_failure_propagates_without_success(
    scaffold: tuple[Path, dict[str, str]], stage: str
) -> None:
    workspace, env = scaffold
    env["TEST_FAIL_AT"] = stage
    result = run_init(scaffold, workspace / "new project")
    assert result.returncode == 29
    assert "Projeto configurado com sucesso" not in result.stdout
    assert "anteriores" in result.stderr
    last = uv_details(env)[-1]["args"]
    assert (last[1] if last[0] == "python" else last[0]) == stage


@pytest.mark.parametrize(
    "override",
    [
        "none",
        "env-absolute",
        "env-relative",
        "project",
        "directory",
        "directory-alias",
        "active",
        "conda",
    ],
)
def test_creation_uv_keeps_all_project_calls_local(
    scaffold: tuple[Path, dict[str, str]], override: str
) -> None:
    workspace, env = scaffold
    target = workspace / "new project"
    outside = workspace / "external study"
    outside.mkdir()
    (outside / "pyproject.toml").write_text("external manifest\n")
    (outside / "uv.lock").write_text("external lock\n")
    (outside / "keep").write_bytes(b"external environment\n")
    before = config_snapshot(outside)
    env["TEST_MODEL_REDIRECTION"] = "1"
    if override.startswith("env-"):
        env["UV_PROJECT_ENVIRONMENT"] = (
            str(outside)
            if override == "env-absolute"
            else os.path.relpath(outside, target)
        )
    elif override in ("project", "directory", "directory-alias"):
        key = {
            "project": "UV_PROJECT",
            "directory": "UV_WORKING_DIR",
            "directory-alias": "UV_WORKING_DIRECTORY",
        }[override]
        env[key] = str(outside)
    elif override == "active":
        env.update(VIRTUAL_ENV=str(outside), UV_ACTIVE="1")
    elif override == "conda":
        env.update(CONDA_PREFIX=str(outside), CONDA_DEFAULT_ENV="fixture-conda")
    env.update(
        UV_INDEX_URL="https://index.invalid/simple",
        UV_INDEX_USERNAME="fixture-user",
        SSL_CERT_FILE="fixture-ca.pem",
    )
    result = run_init(scaffold, target, "--archetype", "ds")
    assert result.returncode == 0, result.stderr
    assert config_snapshot(outside) == before
    assert (target / ".venv/pyvenv.cfg").is_file()
    for call in uv_details(env):
        assert call["cwd"] == str(target)
        child = call["env"]
        assert child["UV_PROJECT_ENVIRONMENT"] == str(target / ".venv")
        for key in (
            "UV_PROJECT",
            "UV_WORKING_DIR",
            "UV_WORKING_DIRECTORY",
            "VIRTUAL_ENV",
            "CONDA_PREFIX",
            "CONDA_DEFAULT_ENV",
            "UV_ACTIVE",
        ):
            assert child[key] is None, key
        for key in (
            "UV_INDEX_URL",
            "UV_INDEX_USERNAME",
            "SSL_CERT_FILE",
            "UV_CACHE_DIR",
            "UV_PYTHON_INSTALL_DIR",
        ):
            assert child[key] == env[key]


@pytest.mark.parametrize("archetype", ["universal", "ds", "api", "cli"])
def test_creation_notebook_group_is_only_added_for_ds(
    config_creation: tuple[Path, dict[str, str]], archetype: str
) -> None:
    workspace, env = config_creation
    result = run_init(
        config_creation,
        workspace / "study",
        "--archetype",
        archetype,
        "--python",
        "3.13.11",
    )
    assert result.returncode == 0, result.stderr
    additions = [c["args"] for c in uv_details(env) if c["args"][0] == "add"]
    notebook = [a for a in additions if "jupyterlab" in a or "--group" in a]
    assert notebook == (
        [["add", "--python", "3.13.11", "--group", "notebook", "jupyterlab"]]
        if archetype == "ds"
        else []
    )
    if archetype == "ds":
        assert [
            "add",
            "--python",
            "3.13.11",
            "polars",
            "duckdb",
            "pyarrow",
        ] in additions
        assert ["add", "--python", "3.13.11", "--dev", "ipykernel"] in additions


@pytest.mark.parametrize("state", ["new", "existing-group", "missing-package"])
def test_ds_notebook_group_real_uv_offline(
    scaffold: tuple[Path, dict[str, str]], state: str
) -> None:
    workspace, env = scaffold
    target = workspace / "notebook-study"
    wheels = workspace / "wheels"
    wheels.mkdir()
    # Wheel artificial: verifica grupo/lock/entry point, não o JupyterLab real.
    if state != "missing-package":
        with zipfile.ZipFile(
            wheels / "jupyterlab-0.1.0-py3-none-any.whl", "w"
        ) as wheel:
            wheel.writestr(
                "notebook_fixture.py",
                "import sys\ndef main():\n"
                "    assert sys.argv[1:] == ['lab', '--version']\n"
                "    print('fixture-notebook 0.1.0')\n",
            )
            meta = "jupyterlab-0.1.0.dist-info/"
            wheel.writestr(
                meta + "METADATA",
                "Metadata-Version: 2.1\nName: jupyterlab\nVersion: 0.1.0\n",
            )
            wheel.writestr(
                meta + "WHEEL",
                "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            )
            wheel.writestr(
                meta + "entry_points.txt",
                "[console_scripts]\njupyter = notebook_fixture:main\n",
            )
            wheel.writestr(meta + "RECORD", "")
    if state == "existing-group":
        target.mkdir()
        (target / "pyproject.toml").write_text(
            '[project]\nname = "study"\nversion = "0.1.0"\n'
            'requires-python = ">=3.11"\ndependencies = []\n'
            "[dependency-groups]\nshared = []\n"
            'notebook = ["jupyterlab==0.1.0", {include-group = "shared"}]\n'
        )
    env.update(UV_NO_INDEX="1", UV_FIND_LINKS=str(wheels), UV_PYTHON_DOWNLOADS="never")
    Path(env["UV_BIN"]).write_text(
        f"#!{sys.executable}\n"
        "import os, subprocess, sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['python', 'install'] or "
        "(args[0] == 'add' and '--group' not in args):\n"
        "    sys.exit(0)\n"
        "cmd = [os.environ['TEST_REAL_UV'], '--no-config', "
        "'--no-cache', '--offline', *args]\n"
        "if args[0] == 'sync': cmd += ['--no-install-project']\n"
        "sys.exit(subprocess.call(cmd))\n"
    )
    result = run_init(scaffold, target, "--python", sys.executable, "--archetype", "ds")
    if state == "missing-package":
        assert result.returncode != 0
        assert "jupyterlab" in result.stderr.lower()
        assert "Projeto configurado com sucesso" not in result.stdout
        return
    assert result.returncode == 0, result.stderr
    manifest = target / "pyproject.toml"
    groups = tomllib.loads(manifest.read_text())["dependency-groups"]
    assert any(
        isinstance(dep, str) and dep.startswith("jupyterlab")
        for dep in groups["notebook"]
    )
    if state == "existing-group":
        assert groups["shared"] == []
        assert groups["notebook"] == ["jupyterlab==0.1.0", {"include-group": "shared"}]
    lock = target / "uv.lock"
    before = (manifest.read_bytes(), lock.read_bytes())
    launch = subprocess.run(
        [
            env["TEST_REAL_UV"],
            "--no-config",
            "--no-cache",
            "--offline",
            "run",
            "--locked",
            "--group",
            "notebook",
            "jupyter",
            "lab",
            "--version",
        ],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert launch.returncode == 0, launch.stderr
    assert launch.stdout.strip() == "fixture-notebook 0.1.0"
    assert (manifest.read_bytes(), lock.read_bytes()) == before
    assert not Path(env["HOME"], "forbidden-git").exists()
    assert not (Path(env["XDG_DATA_HOME"]) / "direnv/allow").exists()


@pytest.mark.parametrize("existing", [False, True])
def test_creation_uv_refuses_parent_project_before_any_mutation(
    scaffold: tuple[Path, dict[str, str]], existing: bool
) -> None:
    workspace, env = scaffold
    parent = workspace / "parent workspace"
    parent.mkdir()
    (parent / "pyproject.toml").write_text('[tool.uv.workspace]\nmembers=["*"]\n')
    (parent / "uv.lock").write_bytes(b"parent lock\n")
    (parent / ".venv").mkdir()
    (parent / ".venv/keep").write_bytes(b"parent environment\n")
    target = parent / "child"
    if existing:
        target.mkdir()
    before = config_snapshot(parent)
    result = run_init(scaffold, target)
    assert result.returncode == 2, result.stderr
    assert "pai" in result.stderr.lower()
    assert config_snapshot(parent) == before
    assert not Path(env["TEST_COMMAND_LOG"]).exists()


@pytest.mark.parametrize(
    "relative",
    [
        ".venv",
        ".venv/bin",
        ".venv/lib",
        ".venv/lib/python3.12",
        ".venv/lib/python3.12/site-packages",
        ".venv/pyvenv.cfg",
    ],
)
def test_creation_uv_refuses_redirected_venv_before_calls(
    scaffold: tuple[Path, dict[str, str]], relative: str
) -> None:
    workspace, env = scaffold
    env["TEST_SKIP_ENV_CREATION"] = "1"
    target = workspace / "existing project"
    target.mkdir()
    outside = workspace / "external environment"
    outside.mkdir()
    (outside / "keep").write_bytes(b"external environment\n")
    path = target / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(outside, target_is_directory=True)
    before = config_snapshot(workspace)
    result = run_init(scaffold, target)
    assert result.returncode == 2, result.stderr
    assert ".venv" in result.stderr
    assert config_snapshot(workspace) == before
    assert not Path(env["TEST_COMMAND_LOG"]).exists()


def test_creation_uv_reuses_valid_venv_and_interpreter_links(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = scaffold
    target = workspace / "existing project"
    subprocess.run(
        [
            env["TEST_REAL_UV"],
            "--no-config",
            "--offline",
            "--no-cache",
            "venv",
            "--no-project",
            "--no-python-downloads",
            "--python",
            sys.executable,
            str(target / ".venv"),
        ],
        env=env,
        check=True,
        capture_output=True,
    )
    inode = (target / ".venv").stat().st_ino
    interpreter = (target / ".venv/bin/python").readlink()
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    assert (target / ".venv").stat().st_ino == inode
    assert (target / ".venv/bin/python").readlink() == interpreter


def test_creation_uv_requires_venv_before_announcing_success(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = scaffold
    env["TEST_SKIP_ENV_CREATION"] = "1"
    result = run_init(scaffold, workspace / "new project")
    assert result.returncode == 2, result.stderr
    assert ".venv" in result.stderr
    assert "Projeto configurado com sucesso" not in result.stdout
    assert not (workspace / "new project/.envrc").exists()


def test_creation_uv_explicit_missing_override_falls_back_to_path(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = scaffold
    chosen = env["UV_BIN"]
    env["UV_BIN"] = str(workspace / "missing-uv")
    result = run_init(scaffold, workspace / "new project")
    assert result.returncode == 0, result.stderr
    assert all(call["executable"] == chosen for call in uv_details(env))


@pytest.mark.parametrize(
    "relative",
    ["include/site", "include/site/python3.12", "lib/python3.12/site-packages/package"],
)
def test_creation_uv_refuses_nested_venv_links_before_mutations(
    scaffold: tuple[Path, dict[str, str]], relative: str
) -> None:
    workspace, env = scaffold
    target = workspace / "existing project"
    venv = target / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("version = 3.12\n")
    for name in ("python", "python3"):
        (venv / "bin" / name).symlink_to(sys.executable)
    outside = workspace / "external headers"
    outside.mkdir()
    (outside / "keep").write_bytes(b"external sentinel\n")
    path = venv / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(outside, target_is_directory=True)
    before = config_snapshot(workspace)
    result = run_init(scaffold, target)
    assert result.returncode == 2, result.stderr
    assert ".venv" in result.stderr
    assert not Path(env["TEST_COMMAND_LOG"]).exists()
    assert config_snapshot(workspace) == before


@pytest.mark.parametrize(
    "configuration",
    [
        None,
        "[tool.ruff]\nline-length = 101\n",
        '[tool.pytest.ini_options]\naddopts = "-x"\n',
        '[tool.ruff]\nline-length = 101\n[tool.pytest.ini_options]\naddopts = "-x"\n',
    ],
    ids=["new", "ruff-only", "pytest-only", "both"],
)
def test_creation_uv_real_offline_init_pin_and_sync(
    scaffold: tuple[Path, dict[str, str]], configuration: str | None
) -> None:
    workspace, env = scaffold
    target = workspace / "real-project"
    if configuration is not None:
        target.mkdir()
        (target / "pyproject.toml").write_text(
            '[project]\nname = "sample"\nversion = "0.1.0"\n'
            'requires-python = ">=3.11"\ndependencies = []\n' + configuration
        )
    outside = workspace / "external study"
    outside.mkdir()
    (outside / "pyproject.toml").write_text("external manifest\n")
    (outside / "uv.lock").write_bytes(b"external lock\n")
    before = config_snapshot(outside)
    env.update(
        UV_PROJECT_ENVIRONMENT=str(outside),
        UV_PROJECT=str(outside),
        UV_WORKING_DIR=str(outside),
        UV_WORKING_DIRECTORY=str(outside),
        VIRTUAL_ENV=str(outside),
        UV_ACTIVE="1",
        CONDA_PREFIX=str(outside),
    )
    wrapper = Path(env["UV_BIN"])
    wrapper.write_text(
        f"#!{sys.executable}\n"
        "import json, os, subprocess, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['TEST_COMMAND_LOG'], 'a') as log:\n"
        "    log.write(json.dumps(args) + '\\n')\n"
        "if args[:2] == ['python', 'install'] or args[0] == 'add':\n"
        "    sys.exit(0)\n"
        "cmd = [os.environ['TEST_REAL_UV'], '--no-config', '--no-cache',\n"
        "       '--offline', *args]\n"
        "if args[0] == 'sync':\n"
        "    cmd += ['--no-install-project', '--no-python-downloads']\n"
        "sys.exit(subprocess.call(cmd))\n"
    )
    result = run_init(scaffold, target, "--python", sys.executable)
    assert result.returncode == 0, result.stderr
    assert config_snapshot(outside) == before
    assert (target / "uv.lock").is_file()
    assert (target / ".venv/pyvenv.cfg").is_file()
    assert (target / ".venv/bin/python").is_symlink()
    assert (target / ".python-version").read_text().strip() == sys.executable
    calls = [
        json.loads(line)
        for line in Path(env["TEST_COMMAND_LOG"]).read_text().splitlines()
    ]
    assert any(c[0] == "init" and "--no-workspace" in c for c in calls) == (
        configuration is None
    )
    assert any(c[:2] == ["python", "pin"] and "--no-project" in c for c in calls)
    assert calls[-1][0] == "sync"
    tool = tomllib.loads((target / "pyproject.toml").read_text())["tool"]
    assert "ruff" in tool and "pytest" in tool
    if configuration is not None:
        for name, settings in tomllib.loads(configuration)["tool"].items():
            assert tool[name] == settings


@pytest.mark.parametrize(
    "access",
    ["absolute", "relative", "default", "multiple", "alias", "plain", "spaces"],
)
def test_creation_lf_destination_never_changes_the_sibling(
    config_creation: tuple[Path, dict[str, str]], access: str
) -> None:
    workspace, env = config_creation
    sibling = workspace / "project"
    sibling.mkdir()
    (sibling / "keep").write_bytes(b"external sibling sentinel\n")
    (sibling / "keep-hardlink").hardlink_to(sibling / "keep")
    (sibling / "keep-symlink").symlink_to("keep")
    name = {
        "multiple": "project\n\n",
        "plain": "plain-project",
        "spaces": "project with spaces",
    }.get(access, "project\n")
    target = workspace / name
    target.mkdir()
    argument: Path | None = target
    cwd = workspace
    if access == "relative":
        argument = Path(name)
    elif access == "default":
        argument = None
        cwd = target
    elif access == "alias":
        argument = workspace / "alias"
        argument.symlink_to(target, target_is_directory=True)
    env["TEST_MODEL_REDIRECTION"] = "1"
    before = config_snapshot(sibling)
    result = run_init(config_creation, argument, cwd=cwd)
    assert config_snapshot(sibling) == before, "Houve escrita na pasta irma externa"
    assert not (sibling / ".venv").exists()
    if access in ("plain", "spaces"):
        assert result.returncode == 0, result.stderr
        assert (target / ".venv/pyvenv.cfg").is_file()
    else:
        assert result.returncode == 2, result.stderr
        assert "LF" in result.stderr
        assert not Path(env["TEST_COMMAND_LOG"]).exists()
        assert not (target / ".venv").exists()


@pytest.mark.parametrize("producer", ["realpath", "pwd"])
def test_creation_path_producer_failure_cannot_approve_a_path(
    config_creation: tuple[Path, dict[str, str]], producer: str
) -> None:
    workspace, env = config_creation
    target = workspace / "existing-project"
    target.mkdir()
    if producer == "realpath":
        fake = Path(env["UV_BIN"]).with_name("realpath")
        fake.write_text('#!/bin/sh\nprintf "%s\\n" "$TEST_PRODUCER_PATH"\nexit 23\n')
        fake.chmod(0o700)
        env["TEST_PRODUCER_PATH"] = str(target)
    else:
        env["BASH_FUNC_pwd%%"] = "() { builtin pwd -P; return 23; }"
    before = config_snapshot(target)
    result = run_init(config_creation, target)
    assert config_snapshot(target) == before
    assert not Path(env["TEST_COMMAND_LOG"]).exists()
    assert result.returncode != 0


def test_creates_envrc_without_authorizing_it(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = scaffold
    target = workspace / "new-project"
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    assert (target / ".envrc").read_text() == "use devshell_python\n"
    assert stat.S_IMODE((target / ".envrc").stat().st_mode) == 0o600
    assert not (Path(env["XDG_DATA_HOME"]) / "direnv/allow").exists()
    assert "direnv allow ." in result.stdout


def test_new_directories_are_safe_under_permissive_umask(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, _ = scaffold
    target = workspace / "nested/new-project"
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    for directory in (target.parent, target, target / ".vscode", target / ".venv/bin"):
        assert not directory.stat().st_mode & 0o022, directory
    assert (target / ".venv/pyvenv.cfg").is_file()
    assert os.access(target / ".venv/bin/python", os.X_OK)


def test_git_is_initialized_without_staging_or_committing(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = scaffold
    target = workspace / "new-project"
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    assert (target / ".git").is_dir()
    assert not (Path(env["HOME"]) / "forbidden-git").exists()
    head = subprocess.run(
        [env["TEST_REAL_GIT"], "rev-parse", "--verify", "HEAD"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
    )
    assert head.returncode != 0
    staged = subprocess.run(
        [env["TEST_REAL_GIT"], "diff", "--cached", "--name-only"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert staged.stdout == ""


def test_existing_envrc_and_permissions_are_preserved(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, _ = scaffold
    target = workspace / "existing-project"
    target.mkdir()
    target.chmod(0o775)
    envrc = target / ".envrc"
    envrc.write_text("export PROJECT_VALUE=original\n")
    envrc.chmod(0o640)
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    assert envrc.read_text() == "export PROJECT_VALUE=original\n"
    assert stat.S_IMODE(envrc.stat().st_mode) == 0o640
    assert stat.S_IMODE(target.stat().st_mode) == 0o775


def test_dangling_envrc_symlink_is_not_followed(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, _ = scaffold
    target = workspace / "existing-project"
    target.mkdir()
    destination = workspace / "do-not-create"
    (target / ".envrc").symlink_to(destination)
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    assert (target / ".envrc").is_symlink()
    assert not destination.exists()


def test_existing_git_file_is_preserved(scaffold: tuple[Path, dict[str, str]]) -> None:
    workspace, _ = scaffold
    target = workspace / "existing-project"
    target.mkdir()
    git_file = target / ".git"
    git_file.write_text("gitdir: /worktree-metadata\n")
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    assert git_file.read_text() == "gitdir: /worktree-metadata\n"


def test_uv_failure_stops_before_creating_envrc(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = scaffold
    env["TEST_SYNC_FAILURE"] = "1"
    target = workspace / "new-project"
    result = run_init(scaffold, target)
    assert result.returncode == 27
    assert not (target / ".envrc").exists()
    assert not (Path(env["XDG_DATA_HOME"]) / "direnv/allow").exists()


@pytest.fixture
def maintenance(scaffold: tuple[Path, dict[str, str]]) -> tuple[Path, dict[str, str]]:
    """Isola a orquestração; o backend real tem integração no Data Lab."""
    _, env = scaffold
    target = Path(env["HOME"]) / "repos/project com espaços"
    target.mkdir(parents=True)
    subprocess.run(
        [
            env["TEST_REAL_UV"],
            "--no-config",
            "--no-cache",
            "--offline",
            "venv",
            "--no-project",
            "--no-python-downloads",
            "--python",
            sys.executable,
            str(target / ".venv"),
        ],
        env=env,
        capture_output=True,
        check=True,
    )
    (target / "pyproject.toml").write_text('[project]\nname="sample"\nversion="0.1"\n')
    (target / "uv.lock").write_text("lock original\n")
    (target / ".envrc").write_text("use devshell_python\nexport VALUE=original\n")
    (target / ".envrc").chmod(0o600)
    target.chmod(0o775)
    backend = Path(env["UV_BIN"]).with_name("devshell")
    backend.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['TEST_COMMAND_LOG'], 'a') as log:\n"
        "    log.write(json.dumps(['devshell', *args]) + '\\n')\n"
        "target = Path(args[args.index('--path') + 1])\n"
        "if os.environ.get('TEST_BACKEND_FAILURE'):\n"
        "    sys.exit(23)\n"
        "if not (target / '.venv/pyvenv.cfg').is_file():\n"
        "    sys.exit(3)\n"
        "if args[1] == 'fix-permissions' and target.stat().st_mode & 0o022:\n"
        "    print('Reparar? [s/N]', flush=True)\n"
        "    answer = bytearray()\n"
        "    while (byte := os.read(0, 1)) not in (b'', b'\\n'):\n"
        "        answer.extend(byte)\n"
        "    if byte != b'\\n' or answer.decode().strip() not in ('s', 'sim'):\n"
        "        sys.exit(1)\n"
        "    target.chmod(target.stat().st_mode & 0o755)\n"
    )
    backend.chmod(0o700)
    env["DEVSHELL_BIN"] = str(backend)
    return target, env


def commands(env: dict[str, str]) -> list[list[str]]:
    import json

    log = Path(env["TEST_COMMAND_LOG"])
    return (
        [json.loads(line) for line in log.read_text().splitlines()]
        if log.exists()
        else []
    )


def test_maintenance_uv_relative_lookup_keeps_the_chosen_executable(
    scaffold: tuple[Path, dict[str, str]], maintenance: tuple[Path, dict[str, str]]
) -> None:
    workspace, env = scaffold
    target, _ = maintenance
    chosen = workspace / "tools com espaços/uv"
    chosen.parent.mkdir()
    shutil.copy2(env["UV_BIN"], chosen)
    env["UV_BIN"] = "./tools com espaços/uv"
    result = run_init(scaffold, target, "--fix-permissions", "--sync", answers="s\ns\n")
    assert result.returncode == 0, result.stderr
    assert all(Path(call["executable"]) == chosen for call in uv_details(env))


def test_repair_only_preserves_project_and_does_not_require_uv(
    scaffold: tuple[Path, dict[str, str]], maintenance: tuple[Path, dict[str, str]]
) -> None:
    target, env = maintenance
    originals = {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()}
    inode = (target / ".venv").stat().st_ino
    Path(env["UV_BIN"]).unlink()
    result = run_init(scaffold, target, "--fix-permissions", answers="s\n")
    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(target.stat().st_mode) == 0o755
    assert (target / ".venv").stat().st_ino == inode
    assert {
        p.name: p.read_bytes() for p in target.iterdir() if p.is_file()
    } == originals
    assert [c[:3] for c in commands(env)] == [
        ["devshell", "project", "fix-permissions"],
        ["devshell", "project", "doctor"],
    ]
    assert not (target / ".git").exists()


@pytest.mark.parametrize("has_lock", [True, False])
def test_opt_in_chain_uses_separate_confirmations_and_local_env(
    scaffold: tuple[Path, dict[str, str]],
    maintenance: tuple[Path, dict[str, str]],
    has_lock: bool,
) -> None:
    target, env = maintenance
    if not has_lock:
        (target / "uv.lock").unlink()
    env["UV_PROJECT_ENVIRONMENT"] = str(Path(env["HOME"]) / "general")
    env["VIRTUAL_ENV"] = env["UV_PROJECT_ENVIRONMENT"]
    env["UV_PROJECT"] = env["UV_PROJECT_ENVIRONMENT"]
    env["UV_WORKING_DIR"] = env["UV_PROJECT_ENVIRONMENT"]
    result = run_init(
        scaffold,
        target,
        "--fix-permissions",
        "--sync",
        "--allow-direnv",
        answers="s\ns\ns\n",
    )
    assert result.returncode == 0, result.stderr
    calls = commands(env)
    sync = next(c for c in calls if c[:2] == ["uv", "sync"])
    assert ("--locked" in sync) == has_lock
    assert sync[sync.index("--project") + 1] == str(target)
    assert sync[sync.index("--python") + 1] == str(target / ".venv/bin/python")
    assert "--no-python-downloads" in sync
    assert calls[-1] == ["direnv", "allow", "."]
    assert "export VALUE=original" in result.stdout + result.stderr
    assert (target / ".envrc").read_text().endswith("export VALUE=original\n")
    assert not (Path(env["HOME"]) / "general").exists()
    import json

    assert json.loads((Path(env["HOME"]) / "sync-env.json").read_text()) == {
        "UV_PROJECT_ENVIRONMENT": str(target / ".venv"),
        "UV_PROJECT": None,
        "UV_WORKING_DIR": None,
        "VIRTUAL_ENV": None,
    }


@pytest.mark.parametrize(
    "answers,expected",
    [("", []), ("n\n", []), ("s\n", []), ("s\nn\n", []), ("s\ns\n", ["sync"])],
)
def test_refusal_or_eof_stops_later_stages(
    scaffold: tuple[Path, dict[str, str]],
    maintenance: tuple[Path, dict[str, str]],
    answers: str,
    expected: list[str],
) -> None:
    target, env = maintenance
    result = run_init(
        scaffold,
        target,
        "--fix-permissions",
        "--sync",
        "--allow-direnv",
        answers=answers,
    )
    assert result.returncode == 1
    assert [c[1] for c in commands(env) if c[:2] == ["uv", "sync"]] == expected
    assert not any(c[0] == "direnv" for c in commands(env))


@pytest.mark.parametrize(
    "failure,code", [("TEST_BACKEND_FAILURE", 23), ("TEST_SYNC_FAILURE", 27)]
)
def test_failure_never_authorizes_envrc(
    scaffold: tuple[Path, dict[str, str]],
    maintenance: tuple[Path, dict[str, str]],
    failure: str,
    code: int,
) -> None:
    target, env = maintenance
    env[failure] = "1"
    result = run_init(
        scaffold,
        target,
        "--fix-permissions",
        "--sync",
        "--allow-direnv",
        answers="s\ns\ns\n",
    )
    assert result.returncode == code
    assert not any(c[0] == "direnv" for c in commands(env))


@pytest.mark.parametrize(
    "kind", ["symlink", "writable", "hardlink", "missing", "directory"]
)
def test_unsafe_envrc_is_never_authorized(
    scaffold: tuple[Path, dict[str, str]],
    maintenance: tuple[Path, dict[str, str]],
    kind: str,
) -> None:
    target, env = maintenance
    envrc = target / ".envrc"
    if kind == "writable":
        envrc.chmod(0o666)
    elif kind == "hardlink":
        os.link(envrc, target / "another-link")
    else:
        envrc.unlink()
        if kind == "symlink":
            envrc.symlink_to(target / "pyproject.toml")
        elif kind == "directory":
            envrc.mkdir()
    result = run_init(
        scaffold, target, "--fix-permissions", "--allow-direnv", answers="s\ns\n"
    )
    assert result.returncode != 0
    assert not any(c[0] == "direnv" for c in commands(env))


@pytest.mark.parametrize(
    "args",
    [
        ("--sync",),
        ("--allow-direnv",),
        ("--fix-permissions", "--python", "3.12"),
        ("--fix-permissions", "--archetype", "ds"),
    ],
)
def test_incompatible_modes_fail_before_commands(
    scaffold: tuple[Path, dict[str, str]],
    maintenance: tuple[Path, dict[str, str]],
    args: tuple[str, ...],
) -> None:
    target, env = maintenance
    result = run_init(scaffold, target, *args)
    assert result.returncode != 0
    assert not commands(env)


def test_missing_backend_gives_actionable_message(
    scaffold: tuple[Path, dict[str, str]], maintenance: tuple[Path, dict[str, str]]
) -> None:
    target, env = maintenance
    Path(env["DEVSHELL_BIN"]).unlink()
    result = run_init(scaffold, target, "--fix-permissions")
    assert result.returncode != 0
    assert "DEVSHELL_BIN" in result.stderr
    assert not commands(env)


def test_maintenance_finds_devshell_in_path_without_override(
    scaffold: tuple[Path, dict[str, str]], maintenance: tuple[Path, dict[str, str]]
) -> None:
    target, env = maintenance
    del env["DEVSHELL_BIN"]
    result = run_init(scaffold, target, "--fix-permissions", answers="s\n")
    assert result.returncode == 0, result.stderr
    assert commands(env)[0][:3] == ["devshell", "project", "fix-permissions"]
    assert stat.S_IMODE(target.stat().st_mode) == 0o755


@pytest.mark.parametrize("change", ["content", "inode", "mode", "symlink"])
def test_envrc_changed_after_review_is_not_authorized(
    scaffold: tuple[Path, dict[str, str]],
    maintenance: tuple[Path, dict[str, str]],
    change: str,
) -> None:
    target, env = maintenance
    target.chmod(0o700)
    process = subprocess.Popen(
        ["bash", str(SCRIPT), str(target), "--fix-permissions", "--allow-direnv"],
        cwd=scaffold[0],
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert process.stdout and process.stdin
    output = ""
    try:
        while "Autorizar este .envrc" not in output:
            char = process.stdout.read(1)
            assert char, output
            output += char
        envrc = target / ".envrc"
        if change == "content":
            envrc.write_text("export VALUE=changed\n")
        elif change == "mode":
            envrc.chmod(0o666)
        else:
            replacement = target / "replacement"
            replacement.write_bytes(envrc.read_bytes())
            replacement.chmod(0o600)
            if change == "symlink":
                envrc.unlink()
                envrc.symlink_to(replacement)
            else:
                replacement.replace(envrc)
        remaining, _ = process.communicate("s\n", timeout=10)
        assert process.returncode == 2, output + remaining
        assert not any(c[0] == "direnv" for c in commands(env))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_review_escapes_terminal_controls_without_executing_envrc(
    scaffold: tuple[Path, dict[str, str]], maintenance: tuple[Path, dict[str, str]]
) -> None:
    target, env = maintenance
    target.chmod(0o700)
    (target / ".envrc").write_text("touch executed\n# \x1b[2J\n")
    result = run_init(
        scaffold, target, "--fix-permissions", "--allow-direnv", answers="n\n"
    )
    assert result.returncode == 1
    assert "\x1b" not in result.stdout + result.stderr
    assert "\\x1b[2J" in result.stdout + result.stderr
    assert not (target / "executed").exists()
    assert not any(c[0] == "direnv" for c in commands(env))


def test_missing_venv_is_not_created_by_maintenance(
    scaffold: tuple[Path, dict[str, str]], maintenance: tuple[Path, dict[str, str]]
) -> None:
    target, env = maintenance
    shutil.rmtree(target / ".venv")
    result = run_init(scaffold, target, "--fix-permissions", "--sync", answers="s\ns\n")
    assert result.returncode != 0
    assert not (target / ".venv").exists()
    assert not any(c[:2] == ["uv", "sync"] or c[0] == "direnv" for c in commands(env))


@pytest.mark.parametrize("args", [("--python",), ("--archetype",), ("other-target",)])
def test_malformed_arguments_fail_before_commands(
    scaffold: tuple[Path, dict[str, str]],
    maintenance: tuple[Path, dict[str, str]],
    args: tuple[str, ...],
) -> None:
    target, env = maintenance
    result = run_init(scaffold, target, *args)
    assert result.returncode == 2
    assert not commands(env)


def test_sync_refuses_workspace_member_before_repair_or_external_lock_write(
    scaffold: tuple[Path, dict[str, str]], maintenance: tuple[Path, dict[str, str]]
) -> None:
    target, env = maintenance
    root = target.parent
    (root / "pyproject.toml").write_text('[tool.uv.workspace]\nmembers=["*"]\n')
    (target / "uv.lock").unlink()
    subprocess.run(
        [
            env["TEST_REAL_UV"],
            "--no-cache",
            "--offline",
            "lock",
            "--project",
            str(target),
            "--python",
            sys.executable,
            "--no-python-downloads",
        ],
        env=env,
        capture_output=True,
        check=True,
    )
    original_lock = (root / "uv.lock").read_bytes()
    project = target / "pyproject.toml"
    project.write_text(project.read_text().replace('version="0.1"', 'version="0.2"'))
    env["UV_BIN"] = env["TEST_REAL_UV"]
    result = run_init(scaffold, target, "--fix-permissions", "--sync", answers="s\ns\n")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "workspace" in result.stderr
    assert stat.S_IMODE(target.stat().st_mode) == 0o775
    assert not commands(env)
    assert (root / "uv.lock").read_bytes() == original_lock
    assert not (target / "uv.lock").exists()
