# Migrar projetos legados com pyinit

O modo `--migrate` prepara o ambiente de um projeto existente para uv,
`pyproject.toml`, `uv.lock`, `.python-version` e `.venv` local. Preserva código,
notebooks, dados, configuração de IDEs e os manifestos legados. Não executa
refatoração, formatação, testes do projeto, comandos Git ou autorização direnv.

## Revisar antes de executar

A partir do checkout:

```bash
bash scripts/init_project.sh /caminho/absoluto/projeto --migrate --dry-run
bash scripts/init_project.sh /caminho/absoluto/projeto --migrate --python 3.13.11
```

Com esta versão instalada como `pyinit`, os mesmos argumentos funcionam sem
indicar o script. O Data Lab fixa o artefato/submódulo por commit e checksum;
confira `pyinit --help` antes de usar as novas opções. Atualizar o checkout ou
aplicar dotfiles não atualiza o executável instalado.

O diagnóstico exige `/usr/bin/python3` >=3.11. Emite JSON com formato, versão,
dependências, grupos, hashes/identidades, mudanças e avisos. Bloqueios retornam
código 2 e um JSON com `blockers`. `--dry-run` não chama uv, executa código do
projeto, cria cache, arquivo, backup ou diretório de estado. URLs são ocultadas
na saída do plano, pois podem conter credenciais; revise o manifesto original.

Sem `--python`, lê somente a versão em `pyvenv.cfg` do ambiente `geral` em
`$XDG_DATA_HOME/devshell/venvs/geral` (fallback `~/.local/share`); sem essa
informação, usa 3.12. Não importa nem executa o ambiente geral. Um pedido como
`--python 3.13` representa a faixa de patches desse minor, e o uv verifica o
runtime gerenciado disponível após a confirmação. A versão precisa
respeitar as restrições declaradas pelo projeto: incompatibilidades não são
corrigidas alterando silenciosamente o requisito de Python.

## Formatos reconhecidos e limites

| Formato | Conversão automática conservadora |
|---|---|
| pip/pip-tools | `requirements.in` tem prioridade sobre `requirements.txt`; reconhece um arquivo dev (`requirements-dev.in`, `requirements-dev.txt` ou `dev-requirements.txt`), permitindo o par pip-tools `.in`/`.txt` e recusando nomes concorrentes, includes locais `-r`, constraints `-c`, marcadores e hashes. Não leva hashes do pip ao TOML; uv gera seu próprio lock. Opções de índice, editáveis, includes externos/circulares e sintaxes não suportadas bloqueiam. |
| Conda/Anaconda/Miniforge | `environment.yml` ou `.yaml`, listas YAML simples em bloco, requisito de Python, lista revisada de pacotes Python e seção `pip`. Dependências nativas/desconhecidas, canais/builds por pacote e YAML avançado exigem revisão. Canais Conda não são transportados para PyPI. Um inventário `conda-meta` sem manifesto solicita exportação/revisão; não infere dependências diretas a partir de tudo que foi instalado. |
| Poetry | `[tool.poetry.dependencies]`, restrições simples/exatas/caret/tilde, extras, marcadores, dependências opcionais associadas a extras, dev antigo e grupos. Grupos não opcionais são mantidos como grupos padrão do uv. Fontes, caminhos/Git, restrições Python por dependência, alternativas complexas e `include-groups`, formatos híbridos PEP 621/Poetry com dependências sem uv.lock e declarações dinâmicas exigem revisão. A configuração original permanece no arquivo. |
| Pipenv | `Pipfile` com produção/dev e restrição Python; ou `Pipfile.lock` isolado com versões/marcadores/extras simples. Fontes além do PyPI padrão e dependências especiais bloqueiam. O lock original é preservado. |
| Setuptools | `setup.cfg` com dependências estáticas/extras/Python, ou um wrapper literal reconhecido de `setuptools.setup` em `setup.py`, lido com AST sem execução. Declarações dinâmicas, `file:`, `attr:` e combinações ambíguas bloqueiam. É migração de ambiente: distribuição, entry points e metadados de publicação exigem revisão própria. |
| PEP 621/uv | Preserva `pyproject.toml` estático. Quando há `uv.lock`, usa `--locked` e exige bytes idênticos ao final. Ambiente ausente, antigo ou quebrado pode ser substituído com backup. |

Formatos concorrentes, inclusive arquivos requirements dev junto de outro
gerenciador, exigem escolher/revisar a fonte principal antes de prosseguir. Em projetos uv já fixados, PEP 621 e grupos uv são a fonte principal; exports
`requirements` e metadados Poetry remanescentes ficam preservados, com aviso.
Nomes/versões estáticos de projetos Poetry/setuptools são mantidos. Workspaces uv são recusados para evitar alterar locks externos.
A existência de `.venv`, `venv/` ou um ambiente Conda global, sozinha, não basta
para reconstruir as dependências do projeto.

Versões instaladas podem mudar ao resolver um novo lock de outro gerenciador;
restrições declaradas são preservadas e os locks originais não são apagados.
Revise o novo `uv.lock` e valide o comportamento científico/operacional.
O migrador não instala Ruff/pytest nem substitui ferramentas declaradas por
conta própria: essas decisões pertencem à revisão do projeto.

## Confirmação, segurança e backup

A aplicação mostra o plano e pede uma resposta explícita `s`/`sim` com Enter.
EOF, resposta incompleta ou recusa cancelam sem escrita. Conteúdo, identidade,
modo e propriedade dos arquivos e diretórios são conferidos de novo; mudanças
após a revisão cancelam antes do backup. Um lock na raiz serializa migrações.

Symlinks/hardlinks nos manifestos e destinos, diretórios de outro proprietário
e ancestrais graváveis por grupo/outros bloqueiam. A raiz própria do projeto
pode ter somente os bits de escrita compartilhada removidos, por descritor,
após confirmação; esse reparo seguro não é desfeito em caso de falha. Quando `pyproject.toml` ou
`uv.lock` existentes permitem escrita compartilhada, o plano também anuncia
cópias privadas dos mesmos bytes antes do uv; os modos anteriores ficam no
backup. Permissões seguras desses metadados permanecem após falha.
Não há chmod recursivo nem alteração das permissões de ancestrais.

Cada execução cria `.pyinit-backups/ID` com modo 0700, manifesto privado e
cópias dos arquivos inspecionados, com os modos anteriores registrados.
A `.venv` anterior é renomeada para `venv-before`, preservando inode e conteúdo.
Ambientes `venv/`, `env/`, globais ou Conda externos não são modificados.
Antes do primeiro conteúdo privado, acrescenta a proteção de backup ao `.gitignore`, preservando suas linhas anteriores. Essa preparação também é tratada em caso de falha. Novos arquivos são privados (umask 077). Não remova os backups antes de validar.

O uv é encontrado por `UV_BIN`/PATH. O sync força a `.venv` local, remove
ativações herdadas e overrides uv de destino/configuração e exige CPython
**gerenciado já instalado**, com `--no-python-downloads`. Instale previamente o
runtime escolhido pelo processo aprovado da sua máquina. Pacotes podem ser
baixados e builds executados após a confirmação. O migrador não instala
ferramentas do sistema, não desinstala Conda nem muda o Python do sistema.

## Falha e recuperação

Falha no sync ou na validação estrutural restaura os arquivos gerenciados e a
`.venv` anterior. A tentativa malsucedida fica em `failed-venv`, quando criada;
`manifest.json` registra `rolled-back`. O reparo seguro da raiz e a regra final
que ignora `.pyinit-backups/` no `.gitignore` permanecem, para proteger o backup.
O `.gitignore` original está em `files/.gitignore` no registro privado.
Backups não são apagados automaticamente e cada execução usa um ID diferente.

Ctrl+C, SIGTERM e SIGHUP (terminal fechado) disparam o mesmo rollback. Para
desfazer uma migração concluída, ou recuperar uma execução que ficou `pending`,
use `--list-backups` e `--restore ID` (com `--dry-run` para apenas revisar):
os arquivos gerenciados e a `.venv` voltam ao estado anterior, e o estado
substituído é guardado em `after-restore` dentro do mesmo backup.

Ctrl+C, SIGTERM e SIGHUP (terminal fechado) disparam o mesmo rollback. Para
desfazer uma migração concluída, ou recuperar uma execução que ficou `pending`,
use `--list-backups` e `--restore ID` (com `--dry-run` para apenas revisar):
os arquivos gerenciados e a `.venv` voltam ao estado anterior, e o estado
substituído é guardado em `after-restore` dentro do mesmo backup.

Após uma interrupção abrupta (SIGKILL, falta de energia/disco), confira o
`manifest.json` e os caminhos antes de repetir. Se o estado estiver `pending`,
não sobrescreva a `.venv`: preserve uma tentativa incompleta, restaure
`venv-before` ao caminho original e use as cópias em `files/` e os modos do plano
para recuperar os arquivos. Nunca remova um ambiente para contornar um conflito.
O registro não é uma sandbox contra builds autorizados ou processos do mesmo UID.

## Validar e autorizar a troca

Depois da migração:

```bash
cd /caminho/absoluto/projeto
uv run --no-sync python --version
# Execute a suíte apropriada; não rode uma pipeline científica sem autorização.
# Se o Data Lab estiver instalado:
devshell project doctor --path "$PWD"
# Revise todo o .envrc e suas permissões, inclusive conteúdo preexistente:
direnv allow .
```

O migrador cria somente `use devshell_python` quando `.envrc` não existe;
arquivo preexistente é preservado. O comando não chama `direnv allow`, não
configura whitelist e recusa `--allow-direnv` junto de `--migrate`. A troca de
ambiente depende da integração Data Lab/direnv instalada na shell.

`--fix-permissions [--sync] [--allow-direnv]` continua sendo manutenção de uma
`.venv` válida, com suas confirmações próprias. Não combine esses argumentos ou
`--archetype` com `--migrate`. Para uma nova migração de runtime, cada execução
preserva a `.venv` atual em um novo backup; para manutenção habitual, use o modo
de manutenção existente.

As verificações e limitações estão em [validação local](VALIDATION.md).
