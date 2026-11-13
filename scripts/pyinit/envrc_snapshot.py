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
