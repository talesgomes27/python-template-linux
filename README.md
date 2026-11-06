# python-template-linux

Template universal e reprodutivo para projetos Python em qualquer distribuição Linux (Ubuntu, Debian, Fedora, Arch Linux, openSUSE, Alpine).

Baseado no ecossistema moderno da Astral: **`uv` + `pyproject.toml` (PEP 621) + `ruff` + `pytest`**.

## Por que esta abordagem?

Sistemas Linux frequentemente vinculam o Python do sistema a utilitários da distribuição (`apt`, `dnf`, `pacman`). Tentar modificar esses pacotes ou compilar versões com `pyenv` costuma quebrar dependências do sistema operacional ou exigir bibliotecas C ausentes (`libssl-dev`, `zlib1g-dev`).

Com o `uv`, os runtimes do Python são binários portáveis (*standalone builds* manylinux) baixados sob demanda para `~/.local/share/uv/python/`. Cada projeto declara sua versão exata no `.python-version` e suas dependências no `pyproject.toml`, gerando um lockfile multiplataforma determinístico (`uv.lock`).

## Pré-requisitos

Apenas o binário do `uv` precisa estar instalado na máquina. Se ainda não possuir o `uv`, instale-o com um comando (sem sudo):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

O instalador coloca o executável em `~/.local/bin/uv`.

## Início Rápido

### 1. Clonar e sincronizar o ambiente

```bash
git clone <url-do-seu-repositorio>
cd python-template-linux
uv sync
```

O `uv sync` realiza três ações automaticamente:
1. Lê o `.python-version` (padrão: 3.12). Se essa versão não estiver instalada na máquina, baixa o binário imediatamente.
2. Cria o ambiente virtual isolado em `.venv/`.
3. Instala as dependências travadas no `uv.lock`.

### 2. Executar o código

Não é necessário ativar o ambiente virtual (`source .venv/bin/activate`). O comando `uv run` executa qualquer comando dentro do contexto correto:

```bash
uv run python -m python_template_linux.core
```

### 3. Executar testes e checagem de qualidade

```bash
# Rodar suíte de testes com pytest
uv run pytest

# Verificar conformidade de linter (Ruff)
uv run ruff check .

# Formatar o código automaticamente
uv run ruff format .
```

## Criar um novo projeto pelo gerador

Na raiz deste template, execute com Bash e uv instalados:

```bash
bash scripts/init_project.sh ../meu-projeto --python 3.12
```

O gerador prepara o projeto, instala o runtime necessário, adiciona as
dependências do arquétipo e sincroniza a `.venv`. Essas etapas podem baixar
arquivos. Consulte `bash scripts/init_project.sh --help` para os arquétipos.

Ele define `umask 077`: novas criações usam permissões privadas por padrão
(diretórios `700`, arquivos `600`). Diretórios e permissões preexistentes são
preservados; não há chmod recursivo. Se o caminho já tiver um ancestral
gravável por grupo/outros, como `775`, a integração do Data Lab Dotfiles ainda
poderá recusá-lo. Revise somente os caminhos apontados pela guarda antes de
alterar suas permissões.

Depois da sincronização, o gerador cria `.envrc` com:

```bash
use devshell_python
```

Esse conteúdo é uma integração opcional com
[Data Lab Dotfiles](https://github.com/talesgomes27/data-lab-dotfiles) e direnv,
que precisam estar configurados no terminal do usuário. `uv run` continua
disponível independentemente dessa integração. Um `.envrc` já existente,
inclusive um link simbólico, é preservado. Revise o arquivo completo e, se
necessário, acrescente a linha acima ao conteúdo existente.

Para habilitar a troca no projeto recém-criado, entre nele e autorize
explicitamente após a revisão:

```bash
cd ../meu-projeto
direnv allow .
```

A troca ocorre no próximo prompt: o terminal usa a `.venv` do projeto e
restaura o ambiente anterior ao sair. Cada novo diretório precisa dessa
autorização; a criação normal não executa `direnv allow` nem configura whitelist.

Se Git estiver disponível e o projeto ainda não tiver `.git`, ele será
inicializado. Não há stage, commit ou push automático; a escolha dos arquivos
e o primeiro commit ficam com o usuário.

O Data Lab Dotfiles prepara o terminal, o uv e o ambiente pessoal `geral`.
Este gerador prepara os arquivos e a `.venv` de cada projeto. Siga o
[preparo do ambiente pessoal e da troca por projeto](https://github.com/talesgomes27/data-lab-dotfiles/blob/main/docs/SCIENCE.md#ambiente-pessoal-e-troca-automática-por-projeto)
para conectar os dois fluxos; a autorização de cada `.envrc` continua manual.

### Reparar e preparar um projeto existente

O modo `--fix-permissions` delega ao comando `project fix-permissions` do
Data Lab Dotfiles. Ele apresenta os diretórios e modos a corrigir, pede
confirmação própria e registra os modos anteriores. Não usa chmod recursivo.
O backend exige uma `.venv` existente: ambiente ausente ou inválido, symlinks
nos diretórios, proprietários incorretos e problemas no caminho dos registros
bloqueiam o reparo. Prepare ambientes ausentes pelo processo do projeto antes
de usar esse modo.

Disponibilize primeiro `devshell` no PATH pela
[instalação do lançador no Data Lab](https://github.com/talesgomes27/data-lab-dotfiles/blob/main/docs/INSTALLATION.md#disponibilizar-devshell-no-path).
Exemplo a partir deste template, após instalar o lançador:

```bash
# Somente diagnóstico/reparo de permissões, seguido de validação:
bash scripts/init_project.sh /caminho/absoluto/projeto --fix-permissions

# Acrescentar sincronização e autorização guiadas:
bash scripts/init_project.sh /caminho/absoluto/projeto \
    --fix-permissions --sync --allow-direnv
```

Se esta versão do gerador estiver instalada como `pyinit`, o mesmo exemplo
funciona substituindo `bash scripts/init_project.sh` por `pyinit`.
O gerador encontra a CLI pelo PATH. `DEVSHELL_BIN` permanece como override
opcional, por exemplo `DEVSHELL_BIN=/caminho/data-lab-dotfiles/bin/devshell`,
para indicar diretamente outro checkout. Os comandos de manutenção não
instalam o lançador nem alteram a configuração da shell.

| Opção | Comportamento |
|---|---|
| `--fix-permissions` | Repara somente diretórios elegíveis após a revisão do backend e valida a `.venv`. Não exige uv nem direnv. |
| `--sync` | Exige `--fix-permissions` e `pyproject.toml`; mostra o comando e pede confirmação independente. Havendo `uv.lock`, executa `uv sync --locked`; lock desatualizado interrompe a operação. Sem lock, `uv sync` pode criá-lo. |
| `--allow-direnv` | Exige `--fix-permissions`, direnv e `/usr/bin/python3`. Mostra o `.envrc` completo com controles escapados, pede uma confirmação específica, confere novamente conteúdo/metadados e só então executa `direnv allow .`. |

As duas opções adicionais podem ser usadas juntas ou individualmente com
`--fix-permissions`. `--python` também pode ser usado com `--migrate`;
`--archetype` pertence somente à criação. Ambos são recusados com
`--fix-permissions`. O diretório padrão é o atual; para outro,
use caminho sem componentes `..`, conforme a guarda do Data Lab.

O sync usa o interpretador existente, sem download de Python, e fixa o destino
local `.venv` do projeto, ignorando `VIRTUAL_ENV`, `UV_PROJECT`, `UV_WORKING_DIR`
e um `UV_PROJECT_ENVIRONMENT` herdado que poderia apontar para `geral`.
Pode instalar/remover pacotes e executar builds; revise manifesto e dependências
antes de confirmar. A `.venv` é validada novamente após a sincronização.
Antes de reparar, `--sync` usa `uv workspace dir` em modo offline e sem cache
para conferir o escopo. Exige uma versão do uv com esse subcomando e recusa
membros cujo workspace esteja em uma pasta ancestral: o lock desse workspace
deve ser administrado explicitamente, sem alteração indireta pelo reparo local.

Esse modo não repete `uv init`, `uv add`, pin de Python, configuração de IDEs ou
inicialização Git. Preserva o `.envrc` e não cria um arquivo ausente: nesse caso,
prepare a integração manualmente. Na autorização guiada, symlinks, hardlinks,
arquivo de outro proprietário ou gravável por grupo/outros são recusados.
O reparo de diretórios não altera permissões do `.envrc`.

Recusa, EOF ou falha interrompem as etapas seguintes. Reparos/sync já concluídos
continuam aplicados; não há rollback de pacotes ou restauração automática de
permissões inseguras. Depois, `direnv reload` repete a seleção; a ativação ocorre
na shell, antes do próximo prompt. Autorizar `.envrc` permite executar seu
conteúdo, por isso a confirmação não reutiliza a resposta do reparo.

Esse preparo é explícito: abrir o terminal ou navegar entre pastas nunca
executa reparos, sync ou autorização. Veja os testes e limites em
[docs/VALIDATION.md](docs/VALIDATION.md).

No Data Lab Dotfiles, o perfil `science` oferece a instalação do gerador como
`pyinit`. O submódulo fixa o commit de origem e o instalador confere o checksum
do script correspondente antes de publicá-lo no diretório de binários do
usuário. Depois dessa instalação aprovada, também é possível executar:

```bash
pyinit meu-projeto --archetype ds
```

## Migrar um projeto legado

O modo `--migrate` reconhece requirements/pip-tools, Conda, Poetry, Pipenv,
setuptools estático e PEP 621/uv. Ele mostra o plano, preserva os manifestos e
prepara uma nova `.venv` com backup da anterior; não altera código, dados ou IDEs.

```bash
bash scripts/init_project.sh /caminho/absoluto/projeto --migrate --dry-run
bash scripts/init_project.sh /caminho/absoluto/projeto --migrate --python 3.13.11
```

`--dry-run` não escreve estado nem chama uv. A aplicação pede confirmação,
exige CPython gerenciado já instalado e restaura o ambiente/arquivos gerenciados
se o sync falhar. Backups privados ficam em `.pyinit-backups/ID`, protegidos
por uma regra no `.gitignore` que permanece mesmo após rollback.
O `direnv allow .` continua manual. Formatos ambíguos, metadados dinâmicos e
pacotes Conda sem equivalência revisada bloqueiam a migração.
Consulte os [formatos, limites e recuperação](docs/migration-recipe-for-agents.md).

A versão do Python vem do ambiente `geral` quando disponível, com fallback
3.12; `--python` permite escolher outra versão compatível. Quando esta versão
estiver instalada como `pyinit`, os argumentos são os mesmos. Confira
`pyinit --help`: o script instalado é independente do checkout e sua atualização
exige a instalação aprovada do componente no Data Lab.

## Como alternar a versão do Python no projeto

Se outro projeto precisar de uma versão específica (exemplo: Python 3.11 ou 3.13), execute na raiz do repositório:

```bash
# 1. Instalar o runtime desejado (se ainda não baixado)
uv python install 3.13

# 2. Fixar no projeto local (atualiza o arquivo .python-version)
uv python pin 3.13

# 3. Recriar/sincronizar o ambiente virtual para a nova versão
uv sync
```

Para listar todos os interpretadores Python disponíveis e instalados na sua máquina:

```bash
uv python list
```

## Gerenciamento de Dependências

```bash
# Adicionar pacote de produção
uv add httpx pydantic

# Adicionar pacote de desenvolvimento
uv add --dev ipykernel mypy

# Remover pacote
uv remove httpx

# Atualizar todas as dependências respeitando os limites do pyproject.toml
uv lock --upgrade
```

## Estrutura do Repositório

```text
python-template-linux/
├── .github/workflows/ci.yml       # Esteira de CI testando Python 3.11, 3.12 e 3.13
├── docs/                          # Documentação técnica e ADRs de arquitetura
│   └── migration-recipe-for-agents.md # Receita detalhada para migração de repositórios legados
├── scripts/
│   └── init_project.sh            # Script utilitário pyinit para novos projetos
├── src/python_template_linux/     # Código fonte (src-layout)
├── tests/                         # Testes unitários com pytest
├── .gitignore                     # Filtro de arquivos efêmeros
├── .python-version                # Versão ativa do interpretador (ex: 3.12)
├── AGENTS.md                      # Regras operacionais para agentes e LLMs
├── MIGRATION_RECIPE_FOR_AGENTS.md # Atalho para o playbook de migração para IAs
├── pyproject.toml                 # Metadados e configurações (Ruff, Pytest)
└── README.md
```
