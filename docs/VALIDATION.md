# Validação do gerador

## Migração de legados — 2026-11-06

A implementação de `--migrate [--dry-run] [--python VERSAO]` passou nas
verificações locais:

- 125 testes pytest em CPython 3.12.15, sem skips: 41 anteriores e 84 de migração.
- Sete integrações com uv real offline: requirements, Conda, Poetry, Pipenv,
  setuptools, PEP 621 e uv já fixado. HOME/XDG/cache e projetos são temporários;
  o runtime uv previamente instalado é usado somente para leitura, sem download.
- Wheel Python artificial instalada/importada por requirements e por
  `tool.uv.sources`, verificando a conversão e a resolução real sem PyPI.
- Preservação do inode da `.venv` antiga ligada a um Miniforge inexistente,
  manifestos legados, configuração customizada e bytes de `uv.lock` existente.
- Diagnóstico sem uv/escritas, versão padrão lida dos metadados de `geral`,
  constraints/includes locais, grupos/extras, EOF/recusa, falha de sync,
  isolamento de overrides herdados, repetição e backup privado em cada execução.
- Bloqueios para symlinks/hardlinks, ancestrais inseguros, fontes/formatos
  concorrentes, alteração após revisão e metadados dinâmicos não suportados.
- Preservação de nomes/versões estáticos e diagnóstico posterior de projetos
  Poetry já convertidos em uv; esquemas inválidos não produzem traceback.
- Metadados uv graváveis por grupo/outros são copiados para modos privados
  depois do backup e antes do sync, sem alterar os bytes. O plano anuncia os
  reparos e o registro conserva os modos anteriores.
- ShellCheck, shfmt, `bash -n`, Ruff check/format, ajuda e `git diff --check`.
  O corpo Python incorporado também foi extraído e conferido com Ruff.

A revisão independente encontrou cinco problemas materiais. Sete novas
reproduções falharam antes das correções e passaram depois: falha intermediária
na cópia do backup; mistura de dependências PEP 621/Poetry; Poetry include-groups;
setup.py condicional, wrapper dinâmico e setup_requires; manifestos dev
concorrentes. O preparo do backup agora participa do tratamento de falhas e sua
proteção no `.gitignore` precede qualquer cópia privada. As semânticas de
manifestos ainda não suportadas bloqueiam sem escrita.

A revisão para publicação acrescentou 13 casos de regressão para quatro
achados: requirements dev concorrentes com outro gerenciador, extras setuptools
em string, pedido de Python major.minor tratado como patch zero e resolução
relativa de `UV_BIN`/PATH. As reproduções falharam antes das correções; a suíte
completa passou depois. O cenário PEP 621 com uv real também usa pedido sem
patch e um piso de patch compatível com o runtime instalado. O uv continua
responsável por validar o interpretador gerenciado disponível após confirmação.

O registro de falha preserva os originais e a `.venv` anterior; a regra de backup
no `.gitignore` e o reparo seguro da raiz permanecem. Foi injetada uma falha de
cópia depois de um `.envrc` artificial, confirmando proteção do backup e estado
`rolled-back` sem executar uv nem tocar o ambiente antigo.

Estas verificações usam fixtures artificiais e não aplicam configuração na
HOME nem migram repositórios reais. A instalação do `pyinit` é uma etapa
separada. Esta evidência local não certifica conversão de todo YAML/Poetry/Pipenv
nem equivalência científica; os [formatos suportados e recuperação](migration-recipe-for-agents.md)
delimitam os casos aceitos. Os resultados remotos da matriz Python 3.11/3.12/3.13
devem ser conferidos no workflow do PR correspondente; containers não foram
repetidos nesta validação.

## Manutenção guiada — 2026-11-06

As opções `--fix-permissions [--sync] [--allow-direnv]` foram exercitadas com
HOME, XDG e cache temporários, sem usar projetos reais como fixtures.
Passaram os 41 testes pytest do repositório (38 do gerador), Ruff check/format,
ShellCheck, shfmt, ajuda e `git diff --check`, após as correções da revisão.
Os testes pytest usam uv real offline para criar as `.venv`; resolução,
sincronização, backend e autorização são simulados nos testes de orquestração.
Cobrem preservação do projeto, separação de confirmações, EOF/recusa,
propagação de falhas, lock opcional, destino local, argumentos inválidos e
recusa de `.envrc` inseguro ou alterado após a revisão.
O cenário de membro de workspace usa uv real offline e comprova recusa antes
do reparo, sem alterar o lock ancestral. O sync exige `uv workspace dir`.

Uma integração adicional usou uv, direnv e o backend real do checkout local
do Data Lab Dotfiles em um projeto artificial sem dependências
(uv 0.13.5, direnv 2.37.1).

O fluxo foi repetido após instalar o novo lançador do Data Lab em HOME
temporária. A CLI foi descoberta pelo PATH sem `DEVSHELL_BIN`, tanto no teste
unitário de orquestração quanto na integração com backend real. O lançador
ficou `755` e seu registro privado `600`; nada foi aplicado na HOME do usuário.

Essa integração confirmou:

- Retirada de escrita de grupo/outros somente dos diretórios diagnosticados;
  filhos com modos `777`/`666` permaneceram intactos e os registros ficaram `600`.
- Confirmações de reparo, sync e autorização independentes; recusar sync impediu
  a autorização e preservou o lock.
- `uv sync --locked` com o Python existente preservou inode da `.venv`, symlink
  do interpretador, bytes de `pyvenv.cfg` e `uv.lock`.
- Overrides herdados de destino/projeto/ambiente ativo não atingiram um caminho
  externo artificial. Lock desatualizado interrompeu o fluxo sem reescrevê-lo
  nem autorizar o `.envrc`.
- Exportação real do direnv confirmou `geral → .venv → geral`, incluindo PATH.
  Esse cenário usou `direnv export bash`; não é evidência de novo teste em PTY
  nem de inicialização de todas as shells.

O backend real também foi corrigido para não consumir respostas de etapas
posteriores por buffering de stdin. Essa correção é necessária para orquestrar
confirmações por pipe e tem regressão Bats no Data Lab Dotfiles. EOF após `s`
sem Enter também é recusado, com regressão específica.

## Reproduzir os checks locais

```bash
UV_CACHE_DIR=/tmp/pyinit-check-cache uv run --no-sync --offline ruff check .
UV_CACHE_DIR=/tmp/pyinit-check-cache uv run --no-sync --offline ruff format --check .
UV_CACHE_DIR=/tmp/pyinit-check-cache uv run --no-sync --offline pytest
shellcheck scripts/init_project.sh
shfmt -d -i 4 -ci scripts/init_project.sh
bash scripts/init_project.sh --help
```

Os exemplos acima pressupõem dependências de desenvolvimento já presentes.
Escolha cache temporário próprio; os testes substituem HOME/XDG/cache dos
subprocessos. O backend de reparo é opcional para a criação normal e deve estar
disponível via `DEVSHELL_BIN` ou PATH para a manutenção. A integração adicional
exige a correção de stdin do Data Lab descrita acima.

## Limites

A validação local não aplicou configuração na HOME real nem recriou ambientes
existentes do usuário. Os resultados remotos de cada commit ficam no PR e no
[workflow CI](https://github.com/talesgomes27/python-template-linux/actions/workflows/ci.yml);
os checks locais não são evidência de execução desse workflow.
A versão instalada de `pyinit` exige atualização aprovada pelo instalador do
Data Lab; publicar um commit não altera os ambientes existentes.
O sync real cobriu projeto sem dependências e lock desatualizado;
não ampliou a evidência histórica de downloads dos arquétipos ds/api/cli.
Não há sandbox para builds nem para código de `.envrc` autorizado; mudanças
concorrentes pelo mesmo UID após a última validação permanecem fora da garantia.
