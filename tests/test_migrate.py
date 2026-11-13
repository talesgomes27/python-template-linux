"""Migração real de arquivos; somente resolução/downloads do uv são simulados."""

import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
import tomllib
import zipfile
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/init_project.sh"


@pytest.fixture
def legacy(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    home = tmp_path / "home"
    project = home / "repos/projeto com espaços"
    tools = tmp_path / "tools"
    for path in (home, project, tools):
        path.mkdir(parents=True, mode=0o700)
    project.parent.chmod(0o700)
    env = {
        "HOME": str(home),
        "PATH": str(tools) + os.pathsep + os.defpath,
        "UV_BIN": str(tools / "uv"),
        "XDG_DATA_HOME": str(home / "data"),
        "XDG_STATE_HOME": str(home / "state"),
        "XDG_CACHE_HOME": str(home / "cache"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "TEST_LOG": str(tmp_path / "uv-log.jsonl"),
    }
    (tools / "uv").write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['TEST_LOG'], 'a') as f:\n"
        "    f.write(json.dumps({'args': args, 'env': {k: os.environ.get(k) "
        "for k in ('VIRTUAL_ENV','CONDA_PREFIX','UV_PROJECT_ENVIRONMENT',"
        "'UV_PROJECT','UV_WORKING_DIR')}}) + '\\n')\n"
        "assert 'sync' in args, args\n"
        "assert '--managed-python' in args and '--no-python-downloads' in args\n"
        "p = Path(args[args.index('--project') + 1])\n"
        "assert not (p / 'pyproject.toml').stat().st_mode & 0o022\n"
        "if (p / 'uv.lock').exists():\n"
        "    assert not (p / 'uv.lock').stat().st_mode & 0o022\n"
        "assert os.environ['UV_PROJECT_ENVIRONMENT'] == str(p / '.venv')\n"
        "if '--locked' not in args:\n"
        "    (p / 'uv.lock').write_text('version = 1\\n')\n"
        "v = p / '.venv'\n"
        "(v / 'bin').mkdir(parents=True)\n"
        "(v / 'pyvenv.cfg').write_text('version_info = 3.13.11\\n')\n"
        "for name in ('python', 'python3'):\n"
        "    (v / 'bin' / name).symlink_to(sys.executable)\n"
        "if os.environ.get('TEST_SYNC_FAILURE'):\n"
        "    sys.exit(27)\n"
    )
    (tools / "uv").chmod(0o700)
    return project, env


def run(
    legacy: tuple[Path, dict[str, str]], *args: str, answers: str = ""
) -> subprocess.CompletedProcess[str]:
    project, env = legacy
    return subprocess.run(
        ["bash", str(SCRIPT), str(project), "--migrate", *args],
        env=env,
        input=answers,
        capture_output=True,
        text=True,
        timeout=30,
    )


def tree(path: Path) -> dict[str, tuple[int, bytes | str]]:
    return {
        str(f.relative_to(path)): (
            f.lstat().st_mode,
            os.readlink(f) if f.is_symlink() else f.read_bytes(),
        )
        for f in path.rglob("*")
        if not f.is_dir() or f.is_symlink()
    }


@pytest.mark.parametrize(
    ("files", "kind", "dependencies"),
    [
        ({"requirements.txt": "requests>=2\n"}, "requirements", ["requests>=2"]),
        (
            {"requirements.in": "numpy>=1.26\n", "requirements.txt": "numpy==2.0\n"},
            "requirements",
            ["numpy>=1.26"],
        ),
        (
            {
                ("environment.yml"): (
                    "name: old\nchannels:\n  - conda-forge\ndependencies:"
                    "\n  - python>=3.11\n  - numpy=1.26\n  - pip:\n    - r"
                    "equests>=2\n"
                )
            },
            "conda",
            ["numpy==1.26.*", "requests>=2"],
        ),
        (
            {
                ("pyproject.toml"): (
                    '[tool.poetry]\nname="old"\nversion="0.1.0"\n[tool.po'
                    'etry.dependencies]\npython=">=3.11"\nrequests="^2.3'
                    '1"\n'
                )
            },
            "poetry",
            ["requests>=2.31,<3.0"],
        ),
        (
            {"Pipfile": '[packages]\nrequests="~=2.31"\n[dev-packages]\npytest="*"\n'},
            "pipenv",
            ["requests~=2.31"],
        ),
        (
            {
                ("Pipfile.lock"): (
                    '{"default":{"requests":{"version":"==2.31.0"}},"develop":{}}'
                )
            },
            "pipenv",
            ["requests==2.31.0"],
        ),
        (
            {
                ("setup.cfg"): (
                    "[metadata]\nname = old\n[options]\ninstall_requires "
                    "=\n    requests>=2\npython_requires = >=3.11\n"
                )
            },
            "setuptools",
            ["requests>=2"],
        ),
        (
            {
                ("setup.py"): (
                    'from setuptools import setup\nsetup(name="old", in'
                    'stall_requires=["requests>=2"], python_requires="'
                    '>=3.11")\n'
                )
            },
            "setuptools",
            ["requests>=2"],
        ),
        (
            {
                ("pyproject.toml"): (
                    '[project]\nname="old"\nversion="0.1.0"\ndependencies'
                    '=["requests>=2"]\n'
                )
            },
            "pep621",
            ["requests>=2"],
        ),
        (
            {
                ("pyproject.toml"): (
                    '[project]\nname="old"\nversion="0.1.0"\ndependencies=[]\n'
                ),
                "uv.lock": "version=1\n",
            },
            "uv",
            [],
        ),
    ],
)
def test_detects_formats_without_writes_or_commands(
    legacy: tuple[Path, dict[str, str]],
    files: dict[str, str],
    kind: str,
    dependencies: list[str],
) -> None:
    project, env = legacy
    for name, data in files.items():
        (project / name).write_text(data)
    before = tree(Path(env["HOME"]))
    result = run(legacy, "--dry-run", "--python", "3.13.11")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["format"] == kind
    assert plan["dependencies"] == dependencies
    assert plan["python"] == "3.13.11"
    assert not plan["blockers"]
    assert tree(Path(env["HOME"])) == before
    assert not Path(env["TEST_LOG"]).exists()


def test_default_python_comes_from_general_metadata(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, env = legacy
    (project / "requirements.txt").write_text("requests\n")
    general = Path(env["XDG_DATA_HOME"]) / "devshell/venvs/geral"
    general.mkdir(parents=True, mode=0o700)
    (general / "pyvenv.cfg").write_text("version_info = 3.13.11\n")
    result = run(legacy, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["python"] == "3.13.11"


@pytest.mark.parametrize(
    "files",
    [
        {},
        {"requirements.txt": "requests", "Pipfile": "[packages]\n"},
        {"environment.yml": "dependencies:\n - openssl=3.0\n"},
        {"environment.yml": "dependencies: [numpy]\n"},
        {"environment.yml": "dependencies:\n - &pkg numpy\n"},
        {
            ("setup.py"): (
                "from setuptools import setup\nsetup(install_requires=l"
                "oad_dependencies())\n"
            )
        },
        {"setup.cfg": "[options]\ninstall_requires = file: requirements.txt\n"},
        {"requirements.txt": "-r ../outside.txt\n"},
        {
            ("requirements.txt"): (
                "--extra-index-url https://example.invalid/simple\nrequests\n"
            )
        },
        {"pyproject.toml": '[project]\nname="old"\ndynamic=["dependencies"]\n'},
        {
            ("pyproject.toml"): (
                '[tool.poetry.dependencies]\nrequests={version="*",source="private"}\n'
            )
        },
        {"Pipfile": '[packages]\nrequests={git="https://example.invalid/repo"}\n'},
        {"Pipfile": '[requires]\npython_version="3.10"\n[packages]\nrequests="*"\n'},
    ],
)
def test_unsupported_inputs_block_without_mutating(
    legacy: tuple[Path, dict[str, str]], files: dict[str, str]
) -> None:
    project, env = legacy
    for name, data in files.items():
        (project / name).write_text(data)
    before = tree(Path(env["HOME"]))
    result = run(legacy, "--python", "3.13.11", answers="s\n")
    assert result.returncode == 2, result.stdout + result.stderr
    assert tree(Path(env["HOME"])) == before
    assert not Path(env["TEST_LOG"]).exists()


@pytest.mark.parametrize(
    "name", ["requirements.txt", ".envrc", ".venv", ".python-version"]
)
def test_refuses_symlinks_before_writes(
    legacy: tuple[Path, dict[str, str]], name: str
) -> None:
    project, env = legacy
    (project / "requirements.txt").write_text("requests\n")
    outside = Path(env["HOME"]) / "outside"
    outside.write_text("original\n")
    f = project / name
    f.unlink(missing_ok=True)
    f.symlink_to(outside)
    result = run(legacy, answers="s\n")
    assert result.returncode == 2
    assert outside.read_text() == "original\n"
    assert f.is_symlink()
    assert not (project / ".pyinit-backups").exists()


def test_migrates_with_private_backup_and_manual_direnv(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, env = legacy
    (project / "requirements.txt").write_text("requests>=2\n")
    (project / "requirements-dev.txt").write_text("pytest>=8\n")
    (project / "analysis.py").write_text("# preserve scientific code\n")
    (project / ".gitignore").write_text("private-data/\n")
    old = project / ".venv"
    old.mkdir()
    (old / "conda-meta").mkdir()
    (old / "old-file").write_text("preserve me\n")
    inode = old.stat().st_ino
    project.chmod(0o775)
    env.update(
        VIRTUAL_ENV="/other/venv",
        CONDA_PREFIX="/other/conda",
        UV_PROJECT="/outside",
        UV_PROJECT_ENVIRONMENT="/shared",
        UV_WORKING_DIR="/outside",
    )
    result = run(legacy, "--python", "3.13.11", answers="s\n")
    assert result.returncode == 0, result.stdout + result.stderr
    pyproject = tomllib.loads((project / "pyproject.toml").read_text())
    assert pyproject["project"]["dependencies"] == ["requests>=2"]
    assert pyproject["dependency-groups"]["dev"] == ["pytest>=8"]
    assert (project / ".python-version").read_text() == "3.13.11\n"
    assert (project / ".envrc").read_text() == "use devshell_python\n"
    assert (project / "analysis.py").read_text() == "# preserve scientific code\n"
    assert (project / "requirements.txt").read_text() == "requests>=2\n"
    assert (project / ".gitignore").read_text() == (
        "private-data/\n.venv/\n"
        "# pyinit: backups privados de migracao\n.pyinit-backups/\n"
    )
    backups = list((project / ".pyinit-backups").iterdir())
    assert len(backups) == 1
    backup = backups[0]
    assert (backup / "venv-before").stat().st_ino == inode
    assert (backup / "venv-before/old-file").read_text() == "preserve me\n"
    assert (project / ".venv").stat().st_ino != inode
    assert stat.S_IMODE(backup.stat().st_mode) == 0o700
    assert stat.S_IMODE((project / ".envrc").stat().st_mode) == 0o600
    assert stat.S_IMODE(project.stat().st_mode) == 0o755
    record = json.loads((backup / "manifest.json").read_text())
    assert record["status"] == "complete"
    assert record["approval"]
    call = json.loads(Path(env["TEST_LOG"]).read_text())
    assert all(
        call["env"][key] is None
        for key in ("VIRTUAL_ENV", "CONDA_PREFIX", "UV_PROJECT", "UV_WORKING_DIR")
    )
    assert not (Path(env["XDG_DATA_HOME"]) / "direnv").exists()
    assert "direnv allow ." in result.stdout
    assert not (project / ".git").exists()


def test_failed_sync_restores_original_files_and_environment(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, env = legacy
    originals = {
        "requirements.txt": "requests\n",
        ".envrc": "export ORIGINAL=yes\n",
        ".python-version": "3.10\n",
        ".gitignore": "private/\n",
    }
    for name, data in originals.items():
        (project / name).write_text(data)
    old = project / ".venv"
    old.mkdir()
    inode = old.stat().st_ino
    env["TEST_SYNC_FAILURE"] = "1"
    result = run(legacy, answers="s\n")
    assert result.returncode != 0
    assert old.stat().st_ino == inode
    for name, data in originals.items():
        if name != ".gitignore":
            assert (project / name).read_text() == data
    assert not (project / "pyproject.toml").exists()
    assert not (project / "uv.lock").exists()
    backup = next((project / ".pyinit-backups").iterdir())
    assert (backup / "failed-venv").is_dir()
    assert json.loads((backup / "manifest.json").read_text())["status"] == "rolled-back"
    assert (backup / "files/.gitignore").read_text() == originals[".gitignore"]
    assert (project / ".gitignore").read_text().startswith(originals[".gitignore"])
    assert ".pyinit-backups/" in (project / ".gitignore").read_text()


def test_uv_migration_preserves_manifest_lock_and_custom_envrc(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, env = legacy
    original = (
        '[project]\nname="existing"\nversion="0.1.0"\ndependencies=[]\n[to'
        "ol.ruff]\nline-length=100\n"
    )
    (project / "pyproject.toml").write_text(original)
    (project / "uv.lock").write_text("version=1\n# unchanged\n")
    (project / ".envrc").write_text("export CUSTOM=yes\nuse devshell_python\n")
    result = run(legacy, answers="s\n")
    assert result.returncode == 0, result.stderr
    assert (project / "pyproject.toml").read_text() == original
    assert (project / "uv.lock").read_text() == "version=1\n# unchanged\n"
    assert (
        project / ".envrc"
    ).read_text() == "export CUSTOM=yes\nuse devshell_python\n"
    assert "--locked" in json.loads(Path(env["TEST_LOG"]).read_text())["args"]


@pytest.mark.parametrize("answer", ["", "n\n", "s"])
def test_cancellation_and_incomplete_answer_leave_no_state(
    legacy: tuple[Path, dict[str, str]], answer: str
) -> None:
    project, env = legacy
    (project / "requirements.txt").write_text("requests\n")
    before = tree(Path(env["HOME"]))
    result = run(legacy, answers=answer)
    assert result.returncode != 0
    assert tree(Path(env["HOME"])) == before
    assert not Path(env["TEST_LOG"]).exists()


@pytest.mark.parametrize(
    "option", ["--archetype", "--fix-permissions", "--sync", "--allow-direnv"]
)
def test_migration_rejects_creation_or_maintenance_flags(
    legacy: tuple[Path, dict[str, str]], option: str
) -> None:
    project, _ = legacy
    (project / "requirements.txt").write_text("requests\n")
    args = [option, "ds"] if option == "--archetype" else [option]
    assert run(legacy, *args, answers="s\n").returncode == 2


def test_input_change_after_review_cancels_before_backup(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, env = legacy
    source = project / "requirements.txt"
    source.write_text("requests\n")
    process = subprocess.Popen(
        ["bash", str(SCRIPT), str(project), "--migrate"],
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout
    while process.stdout.readline() != "}\n":
        assert process.poll() is None, "A migracao terminou antes de mostrar o plano"
    source.write_text("requests>=2\n")
    _, error = process.communicate("s\n", timeout=15)
    assert process.returncode == 2, error
    assert not (project / ".pyinit-backups").exists()
    assert not Path(env["TEST_LOG"]).exists()


def test_requirements_includes_constraints_and_dev_groups_are_preserved(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    (project / "requirements.txt").write_text("-r base.txt\n-c constraints.txt\n")
    (project / "base.txt").write_text("requests>=2 ; python_version >= '3.11'\n")
    (project / "constraints.txt").write_text("urllib3<3\n")
    (project / "requirements-dev.txt").write_text("-r requirements.txt\npytest>=8\n")
    result = run(legacy, answers="s\n")
    assert result.returncode == 0, result.stderr
    data = tomllib.loads((project / "pyproject.toml").read_text())
    assert data["project"]["dependencies"] == ["requests>=2 ; python_version >= '3.11'"]
    assert data["dependency-groups"]["dev"] == ["pytest>=8"]
    assert data["tool"]["uv"]["constraint-dependencies"] == ["urllib3<3"]


def test_poetry_groups_markers_and_optional_extras_are_converted(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    (project / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\npython=">=3.11"\n'
        'httpx={version="^0.27", extras=["http2"], '
        "markers=\"sys_platform == 'linux'\"}\n"
        'rich={version="~13.2", optional=true}\n'
        '[tool.poetry.extras]\npretty=["rich"]\n'
        '[tool.poetry.group.dev.dependencies]\npytest="^8"\n'
    )
    result = run(legacy, answers="s\n")
    assert result.returncode == 0, result.stderr
    data = tomllib.loads((project / "pyproject.toml").read_text())
    assert data["project"]["dependencies"] == [
        "httpx[http2]>=0.27,<0.28; sys_platform == 'linux'"
    ]
    assert data["project"]["optional-dependencies"]["pretty"] == ["rich>=13.2,<13.3"]
    assert data["dependency-groups"]["dev"] == ["pytest>=8,<9"]


def test_hardlinked_manifest_and_unsafe_ancestor_block(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, env = legacy
    source = project / "requirements.txt"
    source.write_text("requests\n")
    os.link(source, Path(env["HOME"]) / "outside")
    assert run(legacy, answers="s\n").returncode == 2
    assert not (project / ".pyinit-backups").exists()
    (Path(env["HOME"]) / "outside").unlink()
    project.parent.chmod(0o775)
    assert run(legacy, answers="s\n").returncode == 2
    assert not Path(env["TEST_LOG"]).exists()


def test_dry_run_reports_blockers_as_json(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    (project / "setup.py").write_text(
        "from setuptools import setup\nsetup(**read_config())\n"
    )
    result = run(legacy, "--dry-run")
    assert result.returncode == 2
    assert json.loads(result.stdout)["blockers"]
    assert not (project / ".pyinit-backups").exists()


def test_setup_cfg_does_not_hide_dynamic_setup_py_dependencies(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    (project / "setup.cfg").write_text("[options]\ninstall_requires = requests\n")
    (project / "setup.py").write_text(
        "from setuptools import setup\nsetup(install_requires=load_dependencies())\n"
    )
    result = run(legacy, "--dry-run")
    assert result.returncode == 2
    assert not (project / ".pyinit-backups").exists()


def test_repository_urls_are_not_exposed_in_plan(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    (project / "requirements.txt").write_text(
        "private @ https://user:secret@example.invalid/pkg.whl\n"
    )
    result = run(legacy, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "secret" not in result.stdout + result.stderr


def test_repeated_migration_retains_each_previous_environment(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    (project / "requirements.txt").write_text("requests\n")
    assert run(legacy, answers="s\n").returncode == 0
    inode = (project / ".venv").stat().st_ino
    assert run(legacy, answers="s\n").returncode == 0
    backups = list((project / ".pyinit-backups").iterdir())
    assert len(backups) == 2
    retained = [p / "venv-before" for p in backups if (p / "venv-before").exists()]
    assert len(retained) == 1
    assert retained[0].stat().st_ino == inode


def test_private_backup_ignore_overrides_existing_negation(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    (project / "requirements.txt").write_text("requests\n")
    (project / ".gitignore").write_text(".pyinit-backups/\n!.pyinit-backups/\n")
    result = run(legacy, answers="s\n")
    assert result.returncode == 0, result.stderr
    assert (project / ".gitignore").read_text().endswith(".pyinit-backups/\n")


def test_conda_inventory_without_manifest_requests_export(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    (project / ".venv/conda-meta").mkdir(parents=True)
    result = run(legacy, "--dry-run")
    assert result.returncode == 2
    assert "Conda" in json.loads(result.stdout)["blockers"][0]


def test_poetry_nonoptional_groups_remain_default_and_optional_dev_is_not_forced(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    (project / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\nrequests="*"\n'
        '[tool.poetry.group.analytics.dependencies]\nnumpy="*"\n'
        "[tool.poetry.group.dev]\noptional=true\n"
        '[tool.poetry.group.dev.dependencies]\npytest="*"\n'
    )
    result = run(legacy, answers="s\n")
    assert result.returncode == 0, result.stderr
    data = tomllib.loads((project / "pyproject.toml").read_text())
    assert data["tool"]["uv"]["default-groups"] == ["analytics"]
    assert data["dependency-groups"] == {"analytics": ["numpy"], "dev": ["pytest"]}


def test_conda_preserves_explicit_build_tool_dependencies(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    (project / "environment.yml").write_text(
        "dependencies:\n  - setuptools=75\n  - wheel>=0.40\n"
    )
    result = run(legacy, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dependencies"] == [
        "setuptools==75.*",
        "wheel>=0.40",
    ]


@pytest.mark.parametrize(
    "kind", ["requirements", "conda", "poetry", "pipenv", "setuptools", "pep621", "uv"]
)
def test_real_uv_offline_migration_with_retained_old_environment(
    legacy: tuple[Path, dict[str, str]], kind: str
) -> None:
    project, env = legacy
    real_uv = shutil.which("uv")
    assert real_uv, "Teste de integracao exige uv"
    version = ".".join(map(str, sys.version_info[:3]))
    if not Path(sys.base_prefix).name.startswith("cpython-"):
        pytest.skip("integracao exige uv run com CPython gerenciado pelo uv")
    env.update(
        UV_BIN=real_uv,
        UV_OFFLINE="1",
        UV_CACHE_DIR=str(Path(env["HOME"]) / "cache/uv"),
        # Runtime instalado somente para leitura; HOME/XDG/cache sao descartaveis.
        UV_PYTHON_INSTALL_DIR=str(Path(sys.base_prefix).parent),
    )
    wheel = project / "demo_migration-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("demo_migration.py", "VALUE = 42\n")
        archive.writestr(
            "demo_migration-0.1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: demo-migration\nVersion: 0.1.0\n",
        )
        archive.writestr(
            "demo_migration-0.1.0.dist-info/WHEEL",
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr("demo_migration-0.1.0.dist-info/RECORD", "")
    files = {
        "requirements": {"requirements.txt": f"demo-migration @ {wheel.as_uri()}\n"},
        "conda": {"environment.yml": "dependencies:\n  - python>=3.11\n"},
        "poetry": {"pyproject.toml": '[tool.poetry.dependencies]\npython=">=3.11"\n'},
        "pipenv": {"Pipfile": "[packages]\n"},
        "setuptools": {"setup.cfg": "[options]\npython_requires = >=3.11\n"},
        "pep621": {
            "pyproject.toml": '[project]\nname="demo"\nversion="0.1.0"\n'
            'requires-python=">=3.11"\ndependencies=["demo-migration"]\n'
            '[tool.uv.sources]\ndemo-migration={path="' + wheel.name + '"}\n'
        },
        "uv": {
            "pyproject.toml": '[project]\nname="demo"\nversion="0.1.0"\n'
            'requires-python=">=3.11"\ndependencies=[]\n'
        },
    }[kind]
    requested_version = version
    if kind == "pep621":
        requested_version = ".".join(map(str, sys.version_info[:2]))
        floor = requested_version + (".1" if sys.version_info.micro else ".0")
        files["pyproject.toml"] = files["pyproject.toml"].replace(
            'requires-python=">=3.11"', 'requires-python=">=' + floor + '"'
        )
    for name, data in files.items():
        (project / name).write_text(data)
    lock_before = None
    if kind == "uv":
        subprocess.run(
            [
                real_uv,
                "--no-config",
                "lock",
                "--project",
                str(project),
                "--python",
                version,
                "--managed-python",
                "--no-python-downloads",
            ],
            env=env,
            check=True,
            capture_output=True,
        )
        lock_before = (project / "uv.lock").read_bytes()
    old = project / ".venv"
    (old / "bin").mkdir(parents=True)
    (old / "bin/python").symlink_to("/missing/miniforge/bin/python")
    (old / "pyvenv.cfg").write_text("home = /missing/miniforge/bin\n")
    inode = old.stat().st_ino
    result = run(legacy, "--python", requested_version, answers="s\n")
    assert result.returncode == 0, result.stdout + result.stderr
    backup = next((project / ".pyinit-backups").iterdir())
    assert (backup / "venv-before").stat().st_ino == inode
    for name, data in files.items():
        if kind not in ("poetry",) or name != "pyproject.toml":
            assert (project / name).read_text() == data
    if lock_before is not None:
        assert (project / "uv.lock").read_bytes() == lock_before
    code = "import sys; assert sys.version_info[:3] == " + repr(sys.version_info[:3])
    if kind in ("requirements", "pep621"):
        code += "; import demo_migration; assert demo_migration.VALUE == 42"
    subprocess.run(
        [
            real_uv,
            "--no-config",
            "run",
            "--project",
            str(project),
            "--no-sync",
            "python",
            "-c",
            code,
        ],
        env={**env, "UV_PROJECT_ENVIRONMENT": str(project / ".venv")},
        check=True,
        capture_output=True,
    )
    assert (project / ".envrc").read_text() == "use devshell_python\n"
    assert not (Path(env["XDG_DATA_HOME"]) / "direnv").exists()


@pytest.mark.parametrize(
    "files",
    [
        {
            "requirements.txt": "requests\n",
            "requirements-dev.txt": "pytest\n",
            "dev-requirements.txt": "ruff\n",
        },
        {
            "pyproject.toml": '[project]\nname="old"\nversion="1"\n'
            'dependencies=["requests"]\n'
            '[tool.poetry.group.dev.dependencies]\npytest="*"\n'
        },
        {
            "pyproject.toml": '[tool.poetry.dependencies]\nrequests="*"\n'
            '[tool.poetry.group.dev]\ninclude-groups=["test"]\n'
            "[tool.poetry.group.test]\noptional=true\n"
            '[tool.poetry.group.test.dependencies]\npytest="*"\n'
        },
        {
            "setup.py": "from setuptools import setup as _setup\n"
            "def setup(**kwargs):\n"
            "    kwargs['install_requires'].append('numpy')\n"
            "    _setup(**kwargs)\n"
            "setup(install_requires=['requests'])\n"
        },
        {
            "setup.py": "from setuptools import setup\n"
            "setup(install_requires=['requests'], setup_requires=['Cython'])\n"
        },
        {
            "setup.py": "from setuptools import setup\n"
            "if True:\n    setup(install_requires=['requests'])\n"
        },
    ],
)
def test_reviewed_ambiguous_semantics_block_before_any_write(
    legacy: tuple[Path, dict[str, str]], files: dict[str, str]
) -> None:
    project, env = legacy
    for name, data in files.items():
        (project / name).write_text(data)
    before = tree(Path(env["HOME"]))
    result = run(legacy, "--dry-run")
    assert result.returncode == 2
    assert json.loads(result.stdout)["blockers"]
    assert tree(Path(env["HOME"])) == before


def test_copy_failure_keeps_private_backup_ignored_and_originals_intact(
    legacy: tuple[Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    pyinit: Callable[[str], ModuleType],
) -> None:
    project, _ = legacy
    (project / "requirements.txt").write_text("requests\n")
    (project / ".envrc").write_text("export PRIVATE=artificial-test-value\n")
    old = project / ".venv"
    old.mkdir()
    inode = old.stat().st_ino
    module = pyinit("migrate")
    original_atomic = module.atomic

    def fail_copy(path: Path, data: bytes, mode: int = 0o600) -> None:
        if path.name == "requirements.txt" and path.parent.name == "files":
            raise OSError("artificial copy failure")
        original_atomic(path, data, mode)

    monkeypatch.setattr(module, "atomic", fail_copy)
    plan, originals, output = module.plan_migration(project, "3.13.11")
    with pytest.raises(OSError, match="artificial copy failure"):
        module.apply_migration(plan, originals, output, "/unused/uv")
    assert old.stat().st_ino == inode
    assert (project / ".envrc").read_text() == "export PRIVATE=artificial-test-value\n"
    assert (project / "requirements.txt").read_text() == "requests\n"
    assert not (project / "pyproject.toml").exists()
    assert (project / ".gitignore").read_text().endswith(".pyinit-backups/\n")
    backup = next((project / ".pyinit-backups").iterdir())
    assert json.loads((backup / "manifest.json").read_text())["status"] == "rolled-back"


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        (
            "pyproject.toml",
            '[tool.poetry]\nname="original-name"\nversion="2.4.0"\n'
            '[tool.poetry.dependencies]\nrequests="*"\n',
        ),
        (
            "setup.cfg",
            "[metadata]\nname = original-name\nversion = 2.4.0\n"
            "[options]\ninstall_requires = requests\n",
        ),
        (
            "setup.py",
            "from setuptools import setup\n"
            "setup(name='original-name', version='2.4.0', "
            "install_requires=['requests'])\n",
        ),
    ],
)
def test_preserves_static_project_name_and_version(
    legacy: tuple[Path, dict[str, str]], filename: str, content: str
) -> None:
    project, _ = legacy
    (project / filename).write_text(content)
    result = run(legacy, answers="s\n")
    assert result.returncode == 0, result.stderr
    metadata = tomllib.loads((project / "pyproject.toml").read_text())["project"]
    assert metadata["name"] == "original-name"
    assert metadata["version"] == "2.4.0"


def test_migrated_poetry_remains_usable_as_locked_uv_project(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    (project / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\nrequests="*"\n'
        '[tool.poetry.group.dev.dependencies]\npytest="*"\n'
    )
    assert run(legacy, answers="s\n").returncode == 0
    manifest = (project / "pyproject.toml").read_bytes()
    result = run(legacy, "--dry-run")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["format"] == "uv"
    assert plan["groups"] == {"dev": ["pytest"]}
    assert (project / "pyproject.toml").read_bytes() == manifest


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("pyproject.toml", '[tool.poetry]\ngroup="invalid-shape"\n'),
        ("Pipfile", 'source=["invalid-shape"]\n[packages]\n'),
    ],
)
def test_malformed_manager_schema_is_reported_without_state_or_traceback(
    legacy: tuple[Path, dict[str, str]], filename: str, content: str
) -> None:
    project, _ = legacy
    (project / filename).write_text(content)
    result = run(legacy, "--dry-run")
    assert result.returncode == 2
    assert json.loads(result.stdout)["blockers"]
    assert "Traceback" not in result.stderr
    assert not (project / ".pyinit-backups").exists()


def test_existing_uv_metadata_cannot_remain_group_writable_during_sync(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    contents = {
        "pyproject.toml": '[project]\nname="old"\nversion="1"\ndependencies=[]\n',
        "uv.lock": "version=1\n",
    }
    for name, data in contents.items():
        (project / name).write_text(data)
        (project / name).chmod(0o664)
    result = run(legacy, answers="s\n")
    assert result.returncode == 0, result.stderr
    for name, data in contents.items():
        assert (project / name).read_text() == data
        assert not (project / name).stat().st_mode & 0o022
    backup = next((project / ".pyinit-backups").iterdir())
    record = json.loads((backup / "manifest.json").read_text())
    assert record["plan"]["inputs"]["uv.lock"]["mode"] & 0o020


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("setup.cfg", "[options]\ninstall_requires = requests\n"),
        ("Pipfile", '[packages]\nrequests="*"\n'),
        (
            "pyproject.toml",
            '[project]\nname="old"\nversion="1"\ndependencies=["requests"]\n',
        ),
    ],
)
def test_competing_dev_requirements_are_not_silently_dropped(
    legacy: tuple[Path, dict[str, str]], filename: str, content: str
) -> None:
    project, env = legacy
    (project / filename).write_text(content)
    (project / "requirements-dev.txt").write_text("pytest>=8\n")
    before = tree(Path(env["HOME"]))
    result = run(legacy, "--dry-run")
    assert result.returncode == 2
    assert json.loads(result.stdout)["blockers"]
    assert tree(Path(env["HOME"])) == before


@pytest.mark.parametrize(
    ("requires", "python", "allowed"),
    [
        (">=3.12.1,<3.13", "3.12", True),
        ("==3.12.5", "3.12", True),
        (">=3.12.1,<3.12.1", "3.12", False),
        ("!=3.12.*", "3.12", False),
        (">=3.13", "3.12", False),
        (">=3.12.1,<3.13", "3.12.0", False),
        (">3.12", "3.12", True),
        ("!=3.12", "3.12", True),
        (">3.12,<=3.12.1", "3.12", True),
        (">3.12,<3.12.1", "3.12", False),
        ("!=3.12,<=3.12", "3.12", False),
        (">3.12,!=3.12.1,<3.12.2", "3.12", False),
        (">3.12", "3.12.0", False),
        ("!=3.12", "3.12.0", False),
        (">3.12", "3.12.1", True),
        ("!=3.12", "3.12.1", True),
    ],
)
def test_python_minor_request_checks_the_possible_patch_range(
    legacy: tuple[Path, dict[str, str]], requires: str, python: str, allowed: bool
) -> None:
    project, env = legacy
    (project / "pyproject.toml").write_text(
        '[project]\nname="old"\nversion="1"\ndependencies=[]\n'
        + "requires-python="
        + json.dumps(requires)
        + "\n"
    )
    before = tree(Path(env["HOME"]))
    result = run(legacy, "--dry-run", "--python", python)
    assert result.returncode == (0 if allowed else 2), result.stderr
    plan = json.loads(result.stdout)
    if allowed:
        assert plan["python"] == python
        assert not plan["blockers"]
    else:
        assert plan["blockers"]
    assert tree(Path(env["HOME"])) == before
    assert not Path(env["TEST_LOG"]).exists()


@pytest.mark.parametrize("extra", ["pytest", ["pytest"]])
def test_static_setuptools_extra_does_not_split_requirements_into_characters(
    legacy: tuple[Path, dict[str, str]], extra: str | list[str]
) -> None:
    project, _ = legacy
    (project / "setup.py").write_text(
        "from setuptools import setup\n"
        + "setup(name='demo', install_requires=[], "
        + f"extras_require={{'test': {extra!r}}})\n"
    )
    result = run(legacy, answers="s\n")
    assert result.returncode == 0, result.stderr
    data = tomllib.loads((project / "pyproject.toml").read_text())
    assert data["project"]["optional-dependencies"]["test"] == ["pytest"]


@pytest.mark.parametrize("lookup", ["override", "path"])
def test_relative_uv_lookup_is_bound_to_the_callers_directory(
    legacy: tuple[Path, dict[str, str]], monkeypatch: pytest.MonkeyPatch, lookup: str
) -> None:
    project, env = legacy
    (project / "requirements.txt").write_text("requests\n")
    caller = Path(env["UV_BIN"]).parent.parent
    monkeypatch.chdir(caller)
    if lookup == "override":
        env["UV_BIN"] = "./tools/uv"
    else:
        del env["UV_BIN"]
        env["PATH"] = "tools" + os.pathsep + os.defpath
    wrong_tool = project / "tools/uv"
    wrong_tool.parent.mkdir(mode=0o700)
    wrong_tool.write_text("#!/bin/sh\ntouch wrong-uv-executed\nexit 1\n")
    wrong_tool.chmod(0o700)
    result = run(legacy, answers="s\n")
    assert result.returncode == 0, result.stderr
    assert not (project / "wrong-uv-executed").exists()
    assert Path(env["TEST_LOG"]).is_file()


def run_mode(
    legacy: tuple[Path, dict[str, str]], *args: str, answers: str = ""
) -> subprocess.CompletedProcess[str]:
    project, env = legacy
    return subprocess.run(
        ["bash", str(SCRIPT), str(project), *args],
        env=env,
        input=answers,
        capture_output=True,
        text=True,
        timeout=30,
    )


def migrated(legacy: tuple[Path, dict[str, str]], with_venv: bool) -> str:
    project, _ = legacy
    (project / "requirements.txt").write_text("requests>=2\n")
    (project / ".gitignore").write_text("private-data/\n")
    (project / ".python-version").write_text("3.11\n")
    if with_venv:
        (project / ".venv").mkdir()
        (project / ".venv/old-file").write_text("preserve me\n")
    result = run(legacy, "--python", "3.13.11", answers="s\n")
    assert result.returncode == 0, result.stdout + result.stderr
    return next((project / ".pyinit-backups").iterdir()).name


@pytest.mark.parametrize("with_venv", [True, False])
def test_restore_returns_project_to_state_before_migration(
    legacy: tuple[Path, dict[str, str]], with_venv: bool
) -> None:
    project, _ = legacy
    ident = migrated(legacy, with_venv)
    backup = project / ".pyinit-backups" / ident
    migrated_manifest = (project / "pyproject.toml").read_bytes()
    (project / "pyproject.toml").write_bytes(migrated_manifest + b"# edited later\n")
    listed = json.loads(run_mode(legacy, "--list-backups").stdout)
    assert [(b["id"], b["status"], b["format"], b["python"]) for b in listed] == [
        (ident, "complete", "requirements", "3.13.11")
    ]
    before = tree(project)
    dry = run_mode(legacy, "--restore", ident, "--dry-run")
    assert dry.returncode == 0, dry.stderr
    plan = json.loads(dry.stdout)
    assert plan["operation"] == "restore"
    assert plan["files"] == {
        "pyproject.toml": "remover (ausente antes da migracao)",
        "uv.lock": "remover (ausente antes da migracao)",
        ".python-version": "restaurar do backup",
        ".envrc": "remover (ausente antes da migracao)",
        ".gitignore": "restaurar do backup",
    }
    assert tree(project) == before
    refused = run_mode(legacy, "--restore", ident, answers="n\n")
    assert refused.returncode == 1
    assert tree(project) == before

    result = run_mode(legacy, "--restore", ident, answers="s\n")
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("pyproject.toml", "uv.lock", ".envrc"):
        assert not (project / name).exists(), name
    assert (project / ".python-version").read_text() == "3.11\n"
    assert (project / "requirements.txt").read_text() == "requests>=2\n"
    assert (project / ".gitignore").read_text() == (
        "private-data/\n# pyinit: backups privados de migracao\n.pyinit-backups/\n"
    )
    after = backup / "after-restore"
    assert stat.S_IMODE(after.stat().st_mode) == 0o700
    assert (after / "files/pyproject.toml").read_bytes().endswith(b"# edited later\n")
    assert (after / "venv/pyvenv.cfg").is_file()
    if with_venv:
        assert (project / ".venv/old-file").read_text() == "preserve me\n"
        assert not (backup / "venv-before").exists()
    else:
        assert not (project / ".venv").exists()
    assert json.loads((backup / "manifest.json").read_text())["status"] == "restored"
    again = run_mode(legacy, "--restore", ident, answers="s\n")
    assert again.returncode == 2
    assert "'restored' nao pode ser restaurado" in again.stderr


@pytest.mark.parametrize(
    ("ident", "message"),
    [
        ("../../etc", "ID de backup invalido"),
        ("f" * 32, "Backup inexistente"),
    ],
)
def test_restore_refuses_unknown_or_unsafe_backups(
    legacy: tuple[Path, dict[str, str]], ident: str, message: str
) -> None:
    project, _ = legacy
    migrated(legacy, True)
    before = tree(project)
    result = run_mode(legacy, "--restore", ident, answers="s\n")
    assert result.returncode == 2
    assert message in result.stderr
    assert tree(project) == before


def test_restore_refuses_shared_backup_directory_and_changed_project(
    legacy: tuple[Path, dict[str, str]], pyinit: Callable[[str], ModuleType]
) -> None:
    project, _ = legacy
    ident = migrated(legacy, True)
    module = pyinit("migrate")
    plan, _ = module.plan_restore(project, ident)
    (project / ".python-version").write_text("3.12\n")
    with pytest.raises(module.Refused, match="mudou apos a revisao"):
        module.apply_restore(plan)
    assert not (project / ".pyinit-backups" / ident / "after-restore").exists()
    (project / ".pyinit-backups").chmod(0o755)
    result = run_mode(legacy, "--restore", ident, answers="s\n")
    assert result.returncode == 2
    assert "privado (0700)" in result.stderr
    assert run_mode(legacy, "--list-backups").returncode == 2


def test_list_backups_is_empty_without_migrations(
    legacy: tuple[Path, dict[str, str]],
) -> None:
    project, _ = legacy
    result = run_mode(legacy, "--list-backups")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []
    assert list(project.iterdir()) == []


@pytest.mark.parametrize("number", [signal.SIGTERM, signal.SIGHUP])
def test_termination_signals_roll_back_migration(
    legacy: tuple[Path, dict[str, str]], number: signal.Signals
) -> None:
    project, env = legacy
    (project / "requirements.txt").write_text("requests>=2\n")
    old = project / ".venv"
    old.mkdir()
    inode = old.stat().st_ino
    ready = project.parent / "sync-started"
    fake = Path(env["UV_BIN"])
    fake.write_text(
        f"#!{sys.executable}\n"
        "import sys, time\n"
        "from pathlib import Path\n"
        f"Path({str(ready)!r}).touch()\n"
        "time.sleep(60)\n"
    )
    process = subprocess.Popen(
        ["bash", str(SCRIPT), str(project), "--migrate", "--python", "3.13.11"],
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    assert process.stdin is not None
    process.stdin.write("s\n")
    process.stdin.flush()
    deadline = time.monotonic() + 20
    while not ready.exists():
        assert time.monotonic() < deadline and process.poll() is None
        time.sleep(0.05)
    os.killpg(process.pid, number)
    _, stderr = process.communicate(timeout=20)
    # O Bash que recebeu o mesmo sinal termina por ele apos o rollback do filho.
    assert process.returncode != 0, stderr
    assert "Migracao revertida" in stderr
    assert "Operacao interrompida por sinal" in stderr
    assert old.stat().st_ino == inode
    assert not (project / "pyproject.toml").exists()
    backup = next((project / ".pyinit-backups").iterdir())
    assert json.loads((backup / "manifest.json").read_text())["status"] == "rolled-back"
