# Validação do gerador

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
