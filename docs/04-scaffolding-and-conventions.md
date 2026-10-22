# Estrutura de Pastas e Convenções: python-template-linux

## 1. Árvore de Diretórios

```text
python-template-linux/
├── .github/
│   └── workflows/
│       └── ci.yml               # Pipeline de testes e linting no GitHub Actions
├── docs/                        # Documentação técnica e governança pré-código
│   ├── adr/
│   │   └── 0001-adocao-do-uv.md
│   ├── 00_archetype.md
│   ├── 02-PRD-and-specs.md
│   ├── 03-architecture-and-schema.md
│   ├── 04-scaffolding-and-conventions.md
│   ├── 05-implementation-plan.md
│   └── task.md
├── src/
│   └── python_template_linux/   # Código fonte seguindo o padrão src-layout
│       ├── __init__.py
│       └── core.py
├── tests/                       # Suíte de testes com pytest
│   ├── __init__.py
│   └── test_core.py
├── .gitignore                   # Exclusão estrita de artefatos efêmeros
├── .python-version              # Declaração do runtime padrão (ex: 3.12)
├── AGENTS.md                    # Diretrizes operacionais e comandos para IAs
├── pyproject.toml               # Configuração canônica de dependências e tooling
└── README.md                    # Documentação de uso e reprodução
```

## 2. Convenções Adotadas

- **Padrão `src-layout`:** Todo código produtivo reside sob `src/<nome_do_pacote>`. Isso impede que módulos locais sejam importados acidentalmente sem que o pacote esteja devidamente instalado no ambiente virtual.
- **Tipagem Estática:** Todo código Python novo deve incluir anotações de tipo (`type hints`).
- **Nomenclatura Semântica:** Módulos em `snake_case`, classes em `PascalCase`, constantes em `UPPER_CASE`.
- **Formatação de Commits:** Padrão Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`).
