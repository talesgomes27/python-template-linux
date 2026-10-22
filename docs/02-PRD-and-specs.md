# PRD e Especificação Técnica: python-template-linux

## 1. Contexto e Problema

Ambientes Python em Linux tradicionalmente sofriam com acoplamento ao interpretador da distribuição. Atualizações de sistema em Debian, Ubuntu ou Fedora frequentemente quebravam ambientes virtuais ou forçavam versões defasadas de pacotes via gerenciador de pacotes do sistema operacional.

O objetivo deste repositório é definir uma estrutura base 100% reproduzível entre distribuições Linux, máquinas locais e esteiras de CI. Cada projeto derivado deste modelo deve ser capaz de selecionar sua própria versão de Python (3.10 a 3.13) de forma isolada, sem compilar código fonte na máquina host e sem depender de privilégios de superusuário.

## 2. Requisitos Funcionais (RF)

- **RF01 (Runtimes Herméticos):** Instalação e gestão de versões do Python via binários manylinux pré-compilados pelo `uv`.
- **RF02 (Pinagem por Projeto):** Fixação declarativa da versão do interpretador no arquivo `.python-version`.
- **RF03 (Configuração Centralizada):** Especificação de metadados, dependências e ferramentas exclusivamente em `pyproject.toml` (PEP 621).
- **RF04 (Resolução Determinística):** Travamento de árvore de dependências com hashes criptográficos no arquivo `uv.lock`.
- **RF05 (Execução Transparente):** Execução de rotinas e testes através de `uv run`, eliminando a necessidade de ativação manual de ambientes virtuais.
- **RF06 (Qualidade de Código):** Linting e formatação unificados com `ruff` (regras E, F, I, B, UP).
- **RF07 (Testes Automatizados):** Execução de testes unitários com `pytest` e configuração de cobertura.
- **RF08 (Integração Contínua):** Workflow de GitHub Actions que testa o repositório em matriz de versões do Python sobre Linux.

## 3. Requisitos Não Funcionais (RNF)

- **RNF01 (Portabilidade entre Distribuições):** O projeto deve funcionar sem alterações em Ubuntu, Debian, Fedora, Arch Linux, openSUSE ou Alpine (musl), desde que o binário do `uv` esteja presente.
- **RNF02 (Tempo de Inicialização):** Resolução e criação do ambiente virtual inicial em menos de 5 segundos.
- **RNF03 (Isolamento de Estado):** O diretório `.venv` é descartável e efêmero. O estado de verdade reside unicamente em `pyproject.toml` e `uv.lock`.

## 4. Non-Goals (O que não faz parte do escopo)

- Não utilizar Conda/Mamba para gerenciamento de dependências puras do PyPI.
- Não adotar ferramentas legadas ou concorrentes com lockfiles redundantes (`pipenv`, `poetry`, `pip-tools`).
- Não instalar pacotes no ambiente Python do sistema via `sudo pip install`.
- Não versionar o diretório `.venv` no Git.
