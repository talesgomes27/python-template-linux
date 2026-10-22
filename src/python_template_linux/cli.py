"""Interface de linha de comando para python-template-linux."""

from python_template_linux.core import format_environment_info


def main() -> None:
    """Ponto de entrada para execução direta."""
    print(format_environment_info())


if __name__ == "__main__":
    main()
