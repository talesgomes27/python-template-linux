# Task Tracking: python-template-linux

Status dos Gates: `[ ] Pendente`, `[/] Em andamento`, `[x] Aprovado`

- [x] Gate 1: Contexto Inicial e Descoberta (Greenfield, sem fontes legadas)
- [x] Gate 2: Ideação, Escopo, Hipóteses e Especificação (`docs/02-PRD-and-specs.md`)
- [x] Gate 3: Arquitetura do Ambiente e Decisões Técnicas (`docs/03-architecture-and-schema.md`, `docs/adr/`)
- [x] Gate 4: Scaffolding, Estrutura de Pastas e Convenções (`docs/04-scaffolding-and-conventions.md`)
- [x] Gate 5: Plano de Implementação e Verificação Automatizada (`docs/05-implementation-plan.md`)

## Implementação Concluída
- [x] 1. Instalar runtime Python 3.12 hermético via uv
- [x] 2. Criar `.python-version`
- [x] 3. Criar `pyproject.toml` com hatchling, ruff e pytest
- [x] 4. Criar `.gitignore` com exclusão estrita de `.venv` e caches
- [x] 5. Criar `src/python_template_linux/` com core, cli e `__main__`
- [x] 6. Criar `tests/test_core.py` com cobertura completa
- [x] 7. Criar `.github/workflows/ci.yml` com matriz de Python (3.11, 3.12, 3.13)
- [x] 8. Criar `AGENTS.md` e `README.md`
- [x] 9. Executar `git init`, `uv sync`, `uv run ruff check .`, `uv run pytest`
