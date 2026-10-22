# Arquitetura Técnica do Ambiente: python-template-linux

## 1. Topologia do Ambiente de Execução

```
+-------------------------------------------------------------+
| Linux Host (Qualquer distribuição: Ubuntu / Debian / Arch) |
+-------------------------------------------------------------+
                              |
                              v
                  /home/tales/.local/bin/uv
                              |
      +-----------------------+-----------------------+
      |                                               |
      v                                               v
Runtimes Herméticos                      Repositório do Projeto
(~/.local/share/uv/python/)              (/path/to/project)
  - cpython-3.10-x86_64                    - .python-version (3.12)
  - cpython-3.11-x86_64                    - pyproject.toml (PEP 621)
  - cpython-3.12-x86_64                    - uv.lock (Multi-OS)
  - cpython-3.13-x86_64                    - .venv/ (Efêmero, gerenciado pelo uv)
                                           - src/ e tests/
```

## 2. Ciclo de Vida e Fluxo de Trabalho

1. **Seleção de Runtime:** O `uv` inspeciona o arquivo `.python-version` no diretório raiz do projeto. Caso a versão declarada não esteja instalada na máquina, o `uv` faz o download automático de um binário oficial manylinux pré-compilado e o aloca em `~/.local/share/uv/python/`.
2. **Resolução de Dependências:** O comando `uv sync` lê `pyproject.toml`, resolve o grafo universal de dependências e gera ou atualiza o lockfile `uv.lock`.
3. **Execução Isolada:** Todas as chamadas de aplicação, scripts ou ferramentas acontecem via `uv run <comando>`. O `uv` assegura que o ambiente virtual local (`.venv`) reflita o estado exato do `uv.lock` antes de iniciar o processo.
4. **Verificação de Qualidade:**
   - Linting e correção automática: `uv run ruff check . --fix`
   - Formatação consistente: `uv run ruff format .`
   - Suíte de testes automatizados: `uv run pytest`

## 3. Estratégia de CI/CD (GitHub Actions)

O pipeline de integração contínua executa em contêineres Linux oficiais utilizando a action oficial `astral-sh/setup-uv`.
A esteira valida:
- Resolução e instalação estrita via `uv sync --frozen`
- Formatação de código via `uv run ruff format --check .`
- Análise estática via `uv run ruff check .`
- Execução de testes unitários em matriz de versões do interpretador.
