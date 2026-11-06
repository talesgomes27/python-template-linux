"""Executa o gerador sem downloads, autorização direnv ou commits reais."""

import os
import shutil
import stat
import subprocess
import sys
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
    }
    # Simular somente instalação/resolução; a .venv é criada pelo uv real offline.
    (tools / "uv").write_text(
        f"#!{sys.executable}\n"
        "import json, os, subprocess, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['TEST_COMMAND_LOG'], 'a') as log:\n"
        "    log.write(json.dumps(['uv', *args]) + '\\n')\n"
        "if args[:2] == ['python', 'install']:\n"
        "    pass\n"
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
        "    if not Path('.venv/pyvenv.cfg').exists():\n"
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
    target: Path,
    *args: str,
    answers: str = "",
) -> subprocess.CompletedProcess[str]:
    workspace, env = scaffold
    return subprocess.run(
        ["bash", str(SCRIPT), str(target), *args],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        input=answers,
        preexec_fn=lambda: os.umask(0o002),
        timeout=30,
    )


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
