# ADR 0001: Adoção do uv como Ferramenta Unificada

## Status
Aceito

## Contexto
O ecossistema Python tradicionalmente fragmentava o gerenciamento em múltiplas ferramentas: `pyenv` para versões do interpretador, `virtualenv` ou `venv` para ambientes, `pip` ou `poetry` para pacotes e resolução de dependências, além de `pip-tools` para lockfiles. No Linux, essa fragmentação gerava atrito com dependências do sistema e inconsistências entre distribuições.

## Decisão
Adotar o `uv` (desenvolvido pela Astral) como motor único para:
1. Instalação e troca de runtimes de Python independentes da distribuição do sistema.
2. Resolução de dependências em alta performance escrita em Rust.
3. Criação e sincronização determinística do `.venv`.
4. Execução encapsulada de comandos via `uv run`.

## Consequências
- Elimina a necessidade de instalar pacotes de desenvolvimento (`gcc`, `libssl-dev`) apenas para compilar versões do Python.
- Reduz o tempo de resolução de dependências e instalação em até 10 a 100 vezes em relação ao `pip`.
- Garante que qualquer membro da equipe ou servidor de CI replique o ambiente exato apenas clonando o repositório e executando `uv sync`.
