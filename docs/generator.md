# Gerador de projetos (`pyinit`): referência

Referência completa de `scripts/init_project.sh`: garantias, limites e
detalhes de cada modo. Para um resumo de uso, veja o [README](../README.md).

## Criar um novo projeto pelo gerador

Na raiz deste template, execute com Bash, uv, `/usr/bin/python3` >=3.11 e os utilitários básicos Linux
(incluindo `stat -c %h`, `mktemp`, `ln -T` e `realpath -m`, do coreutils) disponíveis:

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

### Composição de Ruff e pytest

As famílias `tool.ruff` e `tool.pytest` são tratadas independentemente. Se uma
delas já existe como tabela, seu conteúdo inteiro é preservado: não há merge
de chaves nem preenchimento de subopções. Isso inclui configurações Ruff
somente em subtabelas e configurações pytest em `ini_options` ou diretamente
em `tool.pytest`; a validade das opções de cada ferramenta continua sendo
responsabilidade do projeto. Somente famílias ausentes recebem os padrões
do gerador.

O template e os novos blocos Ruff não fixam `target-version`. Na descoberta
automática da configuração, a escolha do alvo é delegada às regras de
inferência do Ruff a partir de `project.requires-python` no `pyproject.toml`
do mesmo diretório. Nos casos simples verificados, o template com
`requires-python = ">=3.11"` usa `py311` e um projeto com
`requires-python = ">=3.13"` usa `py313`, mesmo quando o runtime selecionado
é mais recente. O gerador não altera o requisito do projeto nem escolhe outro
interpretador para esse fim.

Essa delegação não garante a resolução completa de restrições PEP 440
compostas. Por exemplo, no Ruff 0.17.1, `requires-python = ">=3.10,>=3.13"`
resulta em `py310`, embora as duas cláusulas juntas exijam Python >=3.13.
Esse resultado vem do [algoritmo de inferência do Ruff](https://github.com/astral-sh/ruff/blob/0.17.1/crates/ruff_workspace/src/pyproject.rs#L216-L243).
Confira o alvo efetivo ao usar requisitos compostos, como indicado abaixo.

Um `target-version` já existente é preservado integralmente e prevalece sobre
a inferência. Projetos gerados anteriormente não têm esse valor removido
automaticamente. As prioridades do Ruff também continuam valendo: por exemplo,
`.ruff.toml`/`ruff.toml`, opções na linha de comando e `--target-version` podem
mudar a configuração efetiva. `--config` e `--isolated` alteram a descoberta;
não presuma o mesmo resultado nesses modos. Confira o alvo com
`ruff check --show-settings arquivo.py` usando os mesmos argumentos da sua
execução. Sem alvo explícito e sem `requires-python`, valem os padrões do Ruff.
Consulte a [inferência e descoberta oficiais do Ruff](https://docs.astral.sh/ruff/configuration/#inferring-the-python-version).

O Python do sistema roda com `-I -B`, sem importar código do projeto. `tomllib`
lê o TOML de verdade, incluindo chaves citadas, pontuadas e tabelas inline;
comentários e strings contendo nomes de tabelas não contam como configuração.
O documento completo resultante é validado antes de acrescentar qualquer
bloco, mantendo os bytes preexistentes, inclusive comentários e quebras de
linha. Quando ambas as famílias já existem, essa etapa não grava o arquivo.

Se uma tabela inline fechada impedir a inclusão de uma família ausente sem
reescrever a configuração, a criação recusa e pede composição manual. TOML
inválido ou `tool`, `tool.ruff` e `tool.pytest` com tipos incompatíveis também
bloqueiam. A conferência inicial ocorre antes de criar diretórios ou chamar
uv; depois das operações uv, o arquivo é lido e validado novamente antes da
inclusão. Essa revalidação não é uma transação contra alterações concorrentes,
e uma falha posterior pode deixar etapas uv já concluídas.

### Preservação de configurações e isolamento

Antes de criar diretórios ou chamar uv para instalar/fixar Python, inicializar,
adicionar dependências ou sincronizar, o gerador inspeciona
`.vscode/settings.json`, `.Renviron`, `.Rprofile` e o diretório `.vscode`:

- Arquivos regulares com um único vínculo são preservados integralmente,
  incluindo permissões e personalizações de renv; não há merge ou substituição.
- Destinos ausentes recebem a configuração padrão com criação exclusiva.
- Symlinks, inclusive pendentes, hardlinks com múltiplos vínculos, diretórios
  ou outros tipos nos três destinos bloqueiam a criação antes dessas chamadas uv.
- `.vscode` existente precisa ser diretório sem symlink; seus outros arquivos
  permanecem intactos. Um arquivo ou symlink nesse caminho também bloqueia.
  Diretórios do projeto e `.vscode` sem permissão de busca são recusados, pois
  seus destinos não podem ser inspecionados com segurança.

As condições são conferidas novamente antes das gravações. Se um arquivo
ausente surgir durante o preparo, a execução recusa substituí-lo. A gravação de
`settings.json` usa o diretório físico conferido. Cada conteúdo padrão é
preparado em um temporário privado no mesmo diretório e publicado com `ln -T`
sem force, que recusa qualquer destino já existente sem abri-lo para escrita.
O temporário é limpo também em caso de falha; conteúdo parcial não é publicado.
Ao final, cada configuração é identificada como criada ou preservada; conteúdo
preservado não significa integração validada. Arquivos R continuam sendo criados quando
ausentes, em todos os arquétipos.

Isso protege contra os conflitos inspecionados e não é uma transação de toda a
criação. Um conflito surgido após o início pode deixar etapas uv já concluídas;
não há reversão automática delas. Não há garantia contra toda troca concorrente
por processos com acesso de escrita ao projeto, especialmente renomeações de
diretórios após a última conferência. Use um diretório sob seu controle.

O uv escolhido por `UV_BIN` ou PATH é fixado como caminho absoluto antes de
entrar no projeto. Entradas relativas, vazias ou com espaços não passam a
selecionar outro executável após o `cd`. O fallback para uv no PATH permanece;
isso não fixa checksum nem impede substituição concorrente do executável.

Na criação, cada chamada filha neutraliza `UV_PROJECT`, `UV_WORKING_DIR`,
`UV_WORKING_DIRECTORY`, `UV_ACTIVE`, `UV_PYTHON`, ativações de ambiente virtual
e Conda, `PYTHONHOME` e `PYTHONPATH`. O destino de ambiente é sempre a `.venv`
local; índices, credenciais, certificados, cache e diretório de runtimes do
usuário permanecem disponíveis. Instalar explicitamente o runtime gerenciado
e usar cache fora do projeto continuam sendo efeitos previstos.

Antes das mutações, a criação recusa qualquer `pyproject.toml` ancestral,
inclusive um projeto pai sem workspace. Essa política conservadora evita
descoberta e alterações implícitas no pai; o TOML dos ancestrais não é
interpretado. Escolha um destino independente
ou administre explicitamente o projeto/workspace com uv. `init` usa
`--no-workspace` e `python pin` usa `--no-project`; `add` e `sync` recebem o
Python solicitado. Essas opções foram conferidas na fonte oficial do uv 0.9.0
e na ajuda do uv 0.13.5; a criação não exige o subcomando `uv workspace dir`.

Destinos cujo caminho físico termina em LF (quebra de linha real) não são
suportados e são recusados antes de criar diretórios ou chamar uv. Isso inclui
o destino padrão `.` e aliases que resolvam para esse caminho. Os caracteres
do nome não são removidos nem substituídos para selecionar outra pasta.
Caminhos comuns e com espaços mantêm o comportamento anterior; as regras
independentes de nome de pacote de `uv init --name` permanecem aplicáveis.

Uma `.venv` preexistente precisa ter estrutura mínima regular, `pyvenv.cfg`
sem symlink/hardlink e interpretadores executáveis. A árvore existente é
inspecionada sem percorrer aliases: links para fora da `.venv`, inclusive em
destinos internos de headers ou pacotes, são recusados. Links internos como
`lib64 -> lib` e symlinks legítimos dos interpretadores são preservados.
A estrutura é conferida novamente após sync, sem executar
o Python do projeto; ausência ou irregularidade impede a mensagem de sucesso.
Isso não audita pacotes instalados nem cria sandbox para builds autorizados.
Falhas propagam o código do uv; etapas anteriores podem permanecer aplicadas,
sem um novo mecanismo de rollback.

Depois da sincronização e validação da `.venv`, o gerador cria `.envrc` com:

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

Quando o projeto ainda não tem `tests/`, o gerador cria `tests/test_smoke.py`
para que `uv run pytest` funcione de imediato; um `tests/` existente é
preservado. Um arquétipo desconhecido é recusado antes de qualquer alteração.

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
[docs/VALIDATION.md](VALIDATION.md).

No Data Lab Dotfiles, o perfil `science` oferece a instalação do gerador como
`pyinit`. O submódulo fixa o commit de origem e o instalador confere o checksum
do script correspondente antes de publicá-lo no diretório de binários do
usuário. Depois dessa instalação aprovada, também é possível executar:

```bash
pyinit meu-projeto --archetype ds
```

O arquétipo `ds` deste gerador mantém Polars, DuckDB e PyArrow nas dependências
do projeto e ipykernel no grupo `dev`. JupyterLab é declarado no grupo
`notebook` de `[dependency-groups]`, pelo
[`uv add --group`](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-groups).
Os arquétipos `universal`, `api` e `cli` não recebem esse grupo.

Para iniciar JupyterLab no projeto criado:

```bash
cd meu-projeto
uv run --locked --group notebook jupyter lab
# Com o atalho python-tools do Data Lab disponível, o equivalente é:
jlab
```

O grupo `notebook` deve ser selecionado explicitamente: o `uv sync` final
padrão não o inclui. O comando de inicialização pode sincronizar a `.venv`
local e baixar dependências; `--locked` exige um lock atualizado. JupyterLab
pode abrir o navegador; use `jlab --no-browser` ou acrescente `--no-browser`
ao comando completo para evitar isso. Veja a
[documentação do JupyterLab](https://jupyterlab.readthedocs.io/en/stable/getting_started/starting.html).
O gerador apenas prepara o projeto; não inicia servidor ou navegador nem
instala JupyterLab globalmente. Projetos anteriores precisam de preparo
explícito (`uv add --group notebook jupyterlab`); esta mudança não os atualiza.
O `pyinit` distribuído pelo Data Lab só recebe a mudança após atualização
aprovada de sua versão fixada e do instalador.

### Automação gerada: CI e pre-commit

Quando ausentes, o gerador cria dois arquivos de automação:

- `.github/workflows/ci.yml`: em push para `main` e em pull requests, executa
  `uv sync --locked`, `ruff format --check`, `ruff check` e `pytest`. As
  actions vêm fixadas por SHA, o token tem somente `contents: read` e o
  checkout não persiste credenciais.
- `.pre-commit-config.yaml`: hooks locais que chamam `uv run ruff check --fix`
  e `uv run ruff format`, usando o Ruff travado no `uv.lock` do projeto. O
  gerador não instala o pre-commit; ative com `uvx pre-commit install`.

Arquivos existentes são preservados. Se `.github` ou `.github/workflows` for
symlink ou não for diretório, o workflow não é criado e nada é gravado
através desse caminho. Use `--no-ci` e `--no-pre-commit` para dispensá-los.

### Planejar a criação e dispensar integrações

`--dry-run` executa as mesmas conferências iniciais e mostra o plano — as
chamadas uv em ordem e cada arquivo a criar ou preservar — sem criar
diretórios nem chamar uv:

```bash
bash scripts/init_project.sh ../api-pedidos --archetype api --no-r --dry-run
```

| Opção | Efeito na criação |
|---|---|
| `--no-ide` | Não cria `.vscode/settings.json` nem inspeciona `.vscode`. |
| `--no-r` | Não cria `.Renviron`/`.Rprofile` nem acrescenta as regras R ao `.gitignore`. |
| `--no-ci` | Não cria `.github/workflows/ci.yml`. |
| `--no-pre-commit` | Não cria `.pre-commit-config.yaml`. |
| `--no-git` | Não inicializa o repositório Git, nem pelo gerador nem pelo `uv init` (`--vcs none`); nesse caso o `uv init` também não cria `.gitignore`. |
| `--version` | Mostra a versão do gerador, igual à do `pyproject.toml` deste template. |

As três opções `--no-*` pertencem somente à criação e são recusadas nos
demais modos. `UV_BIN` e o fallback no PATH consideram apenas arquivos
executáveis; nomes de funções ou builtins da shell não são aceitos.

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
Consulte os [formatos, limites e recuperação](migration-recipe-for-agents.md).

Para desfazer uma migração concluída, liste os backups e restaure pelo ID:

```bash
bash scripts/init_project.sh /caminho/absoluto/projeto --list-backups
bash scripts/init_project.sh /caminho/absoluto/projeto --restore ID --dry-run
bash scripts/init_project.sh /caminho/absoluto/projeto --restore ID
```

A restauração mostra o plano, pede confirmação e devolve os arquivos
gerenciados (`pyproject.toml`, `uv.lock`, `.python-version`, `.envrc`,
`.gitignore`) e a `.venv` ao estado anterior; arquivos criados pela migração
são removidos. Antes de substituir qualquer coisa, o estado atual desses
arquivos e da `.venv` é copiado para `.pyinit-backups/ID/after-restore`,
de modo que edições posteriores à migração não se perdem. Não usa uv, não
afrouxa novamente as permissões da raiz e mantém a regra do `.gitignore`
que protege os backups. Uma restauração interrompida no meio não é
revertida automaticamente; confira `after-restore`. Durante a migração,
SIGTERM e SIGHUP (terminal fechado) disparam o mesmo rollback do Ctrl+C.

A versão do Python vem do ambiente `geral` quando disponível, com fallback
3.12; `--python` permite escolher outra versão compatível. Na migração, um
pedido minor, como `--python 3.12`, representa a faixa de patches: `>3.12` e
`!=3.12` permitem patches posteriores a `.0`, enquanto `!=3.12.*` exclui todo
esse minor. Um pedido explícito `--python 3.12.0` continua sujeito à comparação
exata. O dry-run verifica se há um patch possível; isso não garante sua
disponibilidade. Após confirmação, uv valida o interpretador gerenciado já
instalado, sem download nem alteração silenciosa de `requires-python`.
Quando esta versão do gerador estiver instalada como `pyinit`, os argumentos
são os mesmos. Confira
`pyinit --help`: o script instalado é independente do checkout e sua atualização
exige a instalação aprovada do componente no Data Lab.
