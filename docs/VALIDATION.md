# Validação do gerador

## Correções de revisão e endurecimento do CI — 2026-11-13

- `--archetype` desconhecido é recusado na leitura dos argumentos (código 2),
  antes de qualquer chamada uv; antes havia apenas um aviso.
- O bloco R do `.gitignore` usa `.Rproj.user/` como marcador e não é mais
  duplicado a cada execução.
- Projetos sem `tests/` recebem `tests/test_smoke.py`; um caminho existente
  é preservado.
- Na migração, `.venv/` é inserido antes do bloco final de backups, que
  deixa de ser duplicado e continua sendo a última regra.
- As integrações com uv real são puladas, em vez de falhar, quando o pytest
  não roda em CPython gerenciado pelo uv.
- O piso do template passa a `requires-python = ">=3.11"` (Python 3.10
  encerrou o suporte em outubro de 2026); a exceção
  `extra-standard-library = ["tomllib"]` foi removida. Os registros abaixo
  descrevem o estado anterior.
- CI: actions fixadas por SHA, uv fixado em 0.11.32, `permissions:
  contents: read`, `persist-credentials: false`, `timeout-minutes` e
  Dependabot semanal para actions e uv.

## Correção F1 — arquétipo ds e grupo notebook — 2026-11-06

Candidata isolada sobre `54458190e7f70c71a3c2a509f1cae4a709e258a9`, sem
aplicação ao checkout. Somente `scripts/init_project.sh`,
`tests/test_init_project.py`, `README.md` e este registro mudam. As guardas
A1–A6/A2-LF-01, a seleção de Python e a composição Ruff/pytest são mantidas.
O pré-requisito `/usr/bin/python3` >=3.11 continua igual.

`--archetype ds` passa a executar, pelo `creation_uv` existente:

```bash
uv add --python "$PYTHON_DEFAULT" --group notebook jupyterlab
```

Polars/DuckDB/PyArrow continuam nas dependências do projeto; ipykernel
continua no grupo `dev`. Os outros três arquétipos não recebem o grupo
`notebook`. Nenhum novo atalho, modo ou argumento posicional foi criado.
O comando compatível com o corpo atual do `jlab` do Data Lab é
`uv run --locked --group notebook jupyter lab`.
O sync final padrão não seleciona `notebook`; a inicialização com esse grupo
pode sincronizar a `.venv` e baixar dependências. O gerador não inicia servidor
ou navegador, nem instala JupyterLab globalmente.

Evidências locais atuais, com HOME/XDG/cache/TMPDIR temporários e uv offline:

- A base congelada passou **239 testes em 25,57 s**.
- As sete regressões novas cobrem os quatro arquétipos, encaminhamento de
  `--python`, preservação da stack anterior, grupo novo, grupo existente com
  inclusão de outro grupo e falha de resolução sem mensagem de sucesso.
  Antes da mudança no gerador, três casos falharam e quatro passaram:
  faltavam a chamada de adição e o grupo novo, e o pacote ausente não era
  sequer resolvido. Após a correção, os sete passaram.
- Nas integrações novas, `init` (quando necessário), `pin`,
  `add --group notebook` e `sync` são delegados ao uv real; a falha no pacote
  ausente interrompe antes do sync. A instalação de runtime e os demais `add` são
  simulados. O `sync` usa `--no-install-project`; no caso novo, o pacote gerado
  é instalado em modo editável na `.venv` temporária. Uma wheel artificial
  local chamada `jupyterlab` fornece o entry point `jupyter`, que apenas verifica
  `lab --version` e imprime uma sentinela. Isso verifica a composição do grupo,
  o lock, a seleção e o encaminhamento do comando; não verifica JupyterLab real.
  Os dois casos de sucesso executam `uv run --locked --group notebook jupyter
  lab --version` sem mudar bytes do manifesto ou do lock. O terceiro, sem
  wheel disponível, falha no novo `add` e não anuncia sucesso.
- Uma verificação adicional executou o corpo exato de `jlab` lido de
  `dotfiles/dot_config/devshell/env.sh` do Data Lab em Bash temporário, com
  `jlab --version`, uv real e o mesmo entry point artificial. Passou sem mudar
  manifesto/lock. Isso não carrega o devshell completo nem valida a troca de
  ambiente no terminal do usuário.
- A suíte completa da candidata passou **246 testes em 27,26 s**, sem skips,
  falhas ou avisos, incluindo as sete integrações de migração com as
  pré-condições originais de CPython gerenciado.
- Passaram Ruff check e format (20 arquivos Python), ShellCheck, shfmt,
  `bash -n` e ajuda. Após quebrar somente duas strings longas da fixture em
  literais adjacentes, Ruff foi conferido novamente e as sete regressões foram
  repetidas; o conteúdo do wrapper gerado não mudou.

Ferramentas: CPython 3.12.15 gerenciado, pytest 9.1.1, uv 0.13.5 e Ruff
0.17.1. O parser do gerador usou `/usr/bin/python3` 3.14.4. O ambiente de
desenvolvimento foi copiado, sem instalação de ferramentas ou download de
interpretadores. As wheels de teste são artificiais e locais; nenhuma
instalação completa da stack científica ou do JupyterLab real foi realizada.
Não foram executados CI da candidata, containers, servidor, navegador ou
notebook real. A CI e os resultados de A1–A6 registrados anteriormente são
históricos e não validam remotamente os novos bytes F1.

O patch incremental é conferido por reaplicação apenas em cópia da base,
comparando os 26 arquivos por bytes, tipo e bit executável. A candidata
preserva os modos POSIX dos arquivos originais; o patch Git transporta somente
o bit executável, sem garantir os demais metadados POSIX.

O checkout original, o `.envrc` pessoal e os demais arquivos não rastreados
são preservados e não fazem parte da candidata. Não houve stage, commit,
push, instalação de `pyinit`, atualização de submódulo, manifesto ou lançadores
do Data Lab. A versão instalada e a consumida pelo Data Lab continuam
anteriores. F2, R1 e demais melhorias permanecem fora deste recorte.

## Correção A6 — inferência do alvo Ruff — 2026-11-06

Candidata isolada sobre `c875362eca362ac0b97964e174bdaee1798a40dc`, sem
aplicação no checkout, instalação de `pyinit` ou atualização do Data Lab.
Removido `target-version = "py312"` do template e dos novos blocos Ruff do
gerador. Na descoberta automática, a escolha do alvo é delegada às regras de
inferência do Ruff a partir de `project.requires-python`, sem implementar um
resolvedor completo de restrições PEP 440. O requisito do pacote continua
`>=3.10`; seleção de runtime, pin, lock, dependências e configurações Ruff
preexistentes não foram alterados.

O ajuste P3 desta revisão é somente documental. Código, configuração e testes
permanecem idênticos aos da candidata A6 anterior; os resultados abaixo são
evidências anteriores reaproveitadas, sem nova execução neste ajuste.

Validação local com Ruff 0.17.1, uv 0.13.5, CPython gerenciado 3.12.15 para
pytest/integrações e Python do sistema 3.14.4 para o gerador, com HOME/XDG/cache
temporários:

- Baseline: **232 testes aprovados**, sem skips.
- Sete casos novos executam Ruff real por descoberta automática, sem
  `--config` nem `--target-version`. Cobrem o próprio template, projetos
  existentes com pisos 3.10/3.11/3.12/3.13, família Ruff parcial preservada e
  alvo explícito `py39` preservado. A regra UP036 distingue o piso esperado
  do minor seguinte por diagnósticos reais, sem analisar o texto de
  `--show-settings`. Os casos do gerador simulam uv; não instalam os runtimes
  desses pisos. O pedido de runtime 3.13 não substitui o piso dos metadados.
- Antes da correção, cinco dos sete novos casos falharam; os dois controles
  de Ruff existente passaram. Quatro casos anteriores, ajustados para o
  padrão sem alvo fixo, também falharam. Após a correção, os 16 casos
  direcionados passaram. Os testes conferem preservação do manifesto e da
  configuração existente.
- A inferência de `py310` expôs dois I001 na classificação de `tomllib` pelo
  isort. O template agora declara `extra-standard-library = ["tomllib"]`:
  seus testes exigem Python >=3.11. Isso mantém o piso 3.10, a regra I001 e
  os imports corretos, sem adicionar dependência ou propagar essa exceção
  aos novos blocos do gerador. Ruff check passou após o ajuste.
- Suíte completa: **239 testes aprovados, sem skips**, em 29,45 s, incluindo
  as regressões A1–A5/A2-LF-01 e as integrações offline anteriores.
- Oito cenários adicionais com Ruff real: reprodução UP046 no template
  anterior (`py312`, diagnóstico), candidata (`py310`, sem diagnóstico),
  piso 3.13, configurações explícitas, override CLI, `.ruff.toml` e um
  projeto novo com `uv init`, `python pin` e `sync` reais offline. Neste
  último, somente `python install` e `add` são simulados; o alvo inferido
  foi `py312`, coerente com o projeto criado com CPython 3.12.15.
- Nenhuma correção Ruff foi aplicada aos exemplos. Os diagnósticos UP046
  que sugerem sintaxe PEP 695 estão marcados como correções inseguras.
- Ruff check/format (20 arquivos), corpo Python da composição extraído e
  conferido separadamente, ShellCheck, `shfmt -i 4 -ci -d`, `bash -n`, ajuda
  e whitespace do patch aprovados.

Limites: alvo explícito e prioridades de configuração do Ruff continuam
valendo; projetos anteriores não são migrados automaticamente. No Ruff
0.17.1 ensaiado, `--config pyproject.toml` respeitou o requisito desse arquivo,
mas `--config ruff.toml` sem alvo deixou o alvo não resolvido e não buscou o
requisito vizinho. A descoberta automática é o caminho coberto pela correção;
outros modos devem ser conferidos com `--show-settings`. A documentação geral
de inferência não substitui essa verificação na versão em uso.

Na revisão independente anterior, Ruff 0.17.1 resolveu
`requires-python = ">=3.10,>=3.13"` como `py310`, apesar de a conjunção exigir
Python >=3.13. Esse limite do algoritmo upstream também é delegado por A6;
os testes de pisos simples não certificam resolução geral de requisitos
compostos. O README agora explicita esse limite e orienta conferir o alvo
efetivo com `--show-settings`.

O pré-requisito `/usr/bin/python3` >=3.11 permanece; a versão mínima declarada
de Ruff não foi aumentada. Somente Ruff 0.17.1 foi executado nesta validação,
sem certificar todas as versões admitidas por `ruff>=0.8.0`. Não foram
executados CI remota, containers, downloads ou instalação dos arquétipos.
O patch Git é conferido por bytes, tipos, destinos de symlink e bit executável;
os modos POSIX completos ficam no manifesto da candidata, pois o formato Git
não representa todas essas permissões.

## Correção A5 — pedidos minor na migração — 2026-11-06

Candidata isolada sobre `221c4a234517eaeafdfd074322489eb8afafa881`, sem
aplicação no checkout independente, instalação de `pyinit` ou atualização do
Data Lab. A alteração de comportamento limita-se a `python_allows` na migração:
os candidatos de um pedido major.minor incluem `.0` e `.1`, além dos vizinhos
dos limites de patch explícitos já considerados. Isso evita rejeitar `3.12`
para `>3.12` e `!=3.12` por testar apenas `.0`. Não muda a comparação de pedidos
com patch explícito nem as restrições declaradas pelo projeto.

Validação local desta candidata, com HOME/XDG/cache temporários:

- Baseline: 222 testes aprovados em CPython 3.12.15.
- Dez casos acrescentados à regressão existente. Antes da correção, os dois
  casos centrais falharam e 14 passaram. Depois, os 16 passaram: `>` e `!=`
  sem patch, limites explícitos, intervalos vazios, exclusão `!=3.12.*` e
  pedidos com patch explícito. Todos conferem dry-run sem alterações de
  arquivos nem chamadas uv e preservação do pedido no plano quando aceito.
- Suíte completa: **232 testes aprovados, sem skips**, em 25,22 s. Inclui as
  sete integrações anteriores de migração com CPython gerenciado e uv real
  offline, além das regressões de criação A1–A4/A2-LF-01.
- Dois experimentos adicionais com uv 0.13.5 real, offline, sem dependências
  nem downloads: `requires-python=">3.12"` e `"!=3.12"`, ambos com pedido
  `--python 3.12`. A base recusou os dry-runs com retorno 2; a candidata
  aceitou sem escrita/chamadas uv e, após confirmação em fixtures, realizou
  um sync por caso com CPython 3.12.15. Foram preservados o manifesto, o
  pedido minor em `.python-version` e o inode da antiga `.venv` no backup.
- Ruff check/format (20 arquivos), corpo Python da migração extraído e
  conferido separadamente com a configuração do projeto, ShellCheck,
  `shfmt -i 4 -ci -d`, `bash -n`, ajuda e whitespace do patch aprovados.

A correção não adiciona dependências; o requisito de `/usr/bin/python3`
>=3.11 permanece. Nesta máquina, o Python do sistema que executa a migração
é 3.14.4; 3.12.15 é o interpretador do pytest e das integrações gerenciadas.
A existência de um patch compatível no cálculo não comprova que esse runtime
esteja instalado: uv continua responsável por validar o interpretador real
após a confirmação. A sintaxe conservadora de restrições suportada não foi
ampliada. A6, a CI remota, containers e a distribuição pelo Data Lab não fazem
parte desta candidata.

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

## Correção A1 — preservação das configurações na criação — 2026-11-06

Candidata local baseada em `288a183022121526ce98d8fbd94ace14b518d28e`, em cópia
isolada, sem atualizar o submódulo, manifesto ou `pyinit` instalado no Data Lab.
A mudança limita-se a `.vscode/settings.json`, `.Renviron`, `.Rprofile`, à
validação de `.vscode` e às mensagens correspondentes da criação.

A suíte inicial de 125 testes passou. Antes da implementação, 25 casos novos
falharam contra o gerador anterior, confirmando sobrescrita, links atravessados,
chamadas uv anteriores ao bloqueio e ausência de recusa de conflitos tardios.
Os casos FIFO foram executados somente depois da correção, para evitar bloquear
a versão anterior ao abrir um pipe para escrita.

Na revisão independente, duas reproduções adicionais expuseram falta de busca
em diretórios e um symlink para FIFO surgido após a revalidação: `noclobber` do
Bash não recusa todos os tipos. As regressões foram observadas falhando antes
de corrigir esses casos e de adotar publicação exclusiva com `ln -T`.

Os novos testes usam uv simulado com registro de chamadas, HOME/XDG/cache
temporários e arquivos externos artificiais. Cobrem o diretório padrão, caminhos
com espaços, conteúdo padrão, preservação de bytes/modos/inodes e renv,
reexecução, vizinhos em `.vscode`, symlinks válidos/pendentes, hardlinks,
diretórios, FIFOs, diretórios sem busca e conflitos em `.vscode`. A recusa inicial
confere também que nenhuma chamada uv ocorreu e que os tipos, vínculos e conteúdos
permanecem intactos. Casos determinísticos fazem arquivos ou um symlink `.vscode` surgir
durante uv; outro faz um arquivo surgir entre a revalidação e a abertura de
escrita, incluindo symlink para FIFO externo com leitor não bloqueante,
exercitando a criação exclusiva sem escrever no alvo externo. Falha artificial
ao produzir conteúdo confirma ausência de publicação parcial e limpeza.
Nos testes de diretórios sem busca, os modos permanecem intactos durante as
asserções; somente o teardown os restaura para permitir a limpeza da fixture.

Passaram Ruff check/format, os 157 testes pytest (32 novos casos A1), ShellCheck,
shfmt em conferência, ajuda do gerador e `git diff --check`. O pytest final não
teve skips nem avisos. A suíte completa mantém os cenários de manutenção e
migração, incluindo suas integrações uv reais offline já existentes; os novos
casos A1 não executam uv real. Foi usada cópia do ambiente de desenvolvimento,
com Python 3.12.15 e uv 0.13.5, HOME/XDG/cache/TMPDIR temporários e
`uv run --no-sync --offline`, sem baixar dependências. A revisão independente
repetiu cinco casos focados e confirmou a recusa sem chamadas uv; após os
ajustes, não encontrou novos bloqueios no diff A1.

O preflight não grava estado. Arquivos regulares de vínculo único são mantidos;
novos conteúdos são preparados em temporários privados no mesmo diretório e
publicados com `ln -T` sem force, após revalidação. O destino final nunca é aberto
para escrita. A gravação em `.vscode` ocorre por seu diretório físico.
Essas guardas não constituem transação nem sandbox
contra processos com escrita concorrente: mudanças tardias podem interromper o
fluxo depois de etapas uv, e renomeações posteriores à última conferência ficam
fora da garantia.

A2–A6, R1, integração ds/jlab e ampliação de project doctor permanecem pendentes
e fora desta candidata. A criação inteira não deve ser declarada segura com
base nesta correção. Não houve instalação na HOME real, autorização direnv real,
stage, commit, push, PR ou alteração de projetos reais nesta validação.

## Candidata A2/A3 sobre A1 — 2026-11-06

A base desta etapa é a fotografia dos 26 arquivos rastreados do checkout em
`288a183022121526ce98d8fbd94ace14b518d28e`, incluindo o diff A1 aprovado e
aplicado sem commit. O `.envrc` pessoal não integra a fotografia nem a candidata.
As comparações iniciais confirmaram igualdade de bytes/tipos; o manifesto da
base registra hashes dos arquivos rastreados. A suíte inicial desta execução
passou os 157 testes, antes das mudanças A2/A3.

A3 normaliza o executável uv para caminho absoluto antes de `cd`; o resolver
compartilhado também tem regressão na manutenção. O migrador já fazia essa
normalização e não foi alterado. Os testes exercitam override relativo,
PATH relativo, vazio e `.`, espaços no caminho, executável absoluto, fallback,
ausência e propagação de falhas. Não há garantia nova de integridade imutável
do executável. A resolução relativa de direnv na manutenção é uma questão
separada identificada nesta revisão, sem mudança nesta etapa.

A2 restringe todas as chamadas uv da criação ao projeto e à `.venv` local,
limpando somente os overrides de localização/ativação pertinentes nas chamadas
filhas. Cache e instalação explícita de runtime continuam podendo usar os
diretórios do usuário. O uv falso registra executável, argumentos, diretório e
um conjunto limitado de variáveis artificiais; sentinelas e snapshots cobrem
também as operações intermediárias, manifests/locks/ambientes externos e pais.
A recusa de qualquer `pyproject.toml` ancestral é intencionalmente conservadora,
inclusive para pais sem workspace; não tenta interpretar TOML em Bash.

A revisão independente confirmou uma lacuna inicial em `include/site`: uma
wheel artificial de headers fez o sync uv real gravar fora da `.venv`. A
reprodução foi repetida antes da correção; novas regressões também falharam
para links internos de headers e de pacote. A guarda agora percorre a árvore
existente sem seguir aliases, recusa links que escapam do ambiente e mantém
os links dos interpretadores e os aliases internos. A reprodução real passou
a ser recusada antes das operações, com retorno 2, sem mensagem de sucesso
ou novos arquivos no destino externo. O resultado não representa sandbox
contra renomeações concorrentes ou código autorizado de builds.

O teste offline com uv real usa `init`, `python pin` e `sync` reais, com cache e
HOME descartáveis e sem dependências. Apenas `python install` e `add` são
simulados; o sync recebe `--no-install-project` e `--no-python-downloads` para
não instalar o pacote local nem baixar runtime/build backend. Todos os
overrides externos são combinados nessa execução, e as sentinelas externas
permanecem intactas. Não é evidência de download completo dos arquétipos.
O caminho pai contém espaços; o basename desse projeto real é um nome de
pacote válido. Basenames com espaços continuam sujeitos à recusa de `uv init
--name`, uma limitação anterior que não foi corrigida aqui.

Foram consultados a [CLI oficial do uv](https://docs.astral.sh/uv/reference/cli/),
as [variáveis de ambiente](https://docs.astral.sh/uv/configuration/environment/)
e a [fonte da CLI em 0.9.0](https://github.com/astral-sh/uv/blob/0.9.0/crates/uv-cli/src/lib.rs).
O `--no-workspace` de init e `--no-project` de pin existem nessa referência;
as opções de Python de add/sync também foram conferidas na ajuda instalada.
A execução real usa uv 0.13.5; não foi executado um binário uv 0.9.0.

Na execução final passaram Ruff check/format, os 191 testes pytest, ShellCheck,
shfmt em conferência e a ajuda do gerador. O runner de testes usou Python
3.12.15 com HOME/XDG/cache/TMPDIR temporários e `uv run --no-sync --offline`;
não houve skips. A revisão independente repetiu a suíte de 191 testes e a
reprodução de headers corrigida, além de verificar aliases internos e links
de interpretadores, e aprovou o código sem novos bloqueios confirmados.
Os testes novos de arquivos usam dados artificiais; nada lê ou autoriza o
`.envrc` pessoal. Matriz de containers, CI e instalações limpas completas não
foram executados nesta etapa.

Os contratos e o registro A1 permanecem preservados. A4–A6, R1, ds/jlab e
project doctor não integram esta candidata. Não houve alteração do checkout
original, `.envrc`, submódulo, manifesto, lançadores ou instalação do usuário.
O patch desta etapa deve ser aplicado sobre a fotografia com A1; o diff
acumulado contra HEAD inclui A1 e é um artefato distinto.

## Ajuste A2-LF-01 — 2026-11-06

Nova candidata derivada da A2/A3 anterior, sem sobrescrevê-la nem alterar a
fotografia A1 ou o checkout original. A revisão independente encontrou perda
de LFs finais nas capturas de `realpath` e `pwd -P`: ambas reduziam `project`
com LF real ao nome da pasta irmã, permitindo que a comparação aprovasse um
`UV_PROJECT_ENVIRONMENT` externo. O erro posterior da conferência IDE não
desfazia as escritas já concluídas.

A correção preserva a saída com sentinela e confere o status dos dois produtores.
Remove somente o delimitador emitido pelo comando; destinos físicos terminados
em LF são explicitamente recusados antes das chamadas uv mutáveis. A comparação
após `cd` também preserva os bytes. A política cobre caminhos absolutos,
relativos, múltiplos LFs finais, `.` e symlinks para o destino físico. Não
normaliza nomes nem amplia o suporte a nomes de pacote de `uv init`.

Antes da mudança, cinco regressões falharam por detectar `.venv`/marcadores na
pasta irmã, e outra demonstrou que uma saída válida de `pwd` com status de falha
era aceita. Casos comuns/com espaços e a falha de `realpath` já passavam.
Depois do ajuste, os nove casos passaram. A comparação das árvores artificiais
inclui bytes, tipos, inodes, modos e vínculos; o teste não usa apenas o retorno
de erro. A recusa também exige ausência de chamadas uv. O uv falso registra
somente o conjunto seletivo de variáveis já adotado pela suíte.

O harness do relatório foi repetido com uv 0.13.5 real offline, CPython gerenciado
já disponível e três wheels artificiais locais. Na candidata anterior, pin e
add foram reais, somente python install foi simulado; init não era necessário
e sync não foi alcançado. O gerador retornou 2, mas criou `.venv` na pasta irmã
e 47 caminhos externos novos, preservando apenas a sentinela original.
Na nova candidata, o gerador retorna 2 antes de qualquer chamada uv pelo script:
zero caminhos externos novos, nenhuma `.venv` na irmã e árvore externa idêntica.
O harness adaptado aceita registro de chamadas ausente e inclui vínculos nas
comparações; o relatório de origem não foi alterado.

Os resultados anteriores de 191 testes do autor e 184 aprovados mais sete
dependentes de CPython gerenciado na revisão externa são históricos. Esta
validação utiliza o ambiente do projeto com Python 3.12.15 gerenciado por uv,
sem remover a pré-condição dos sete testes de integração. Não houve download
de runtime, mudança de permissões do host ou instalação de ferramentas globais.

Nesta execução, a cópia congelada da candidata anterior passou 191 testes.
A nova passou 200 testes, sem skips ou avisos, incluindo os nove casos novos e
as integrações de migração com suas pré-condições originais. Também passaram
Ruff check/format, `bash -n`, ShellCheck, shfmt em conferência e ajuda. A
verificação de whitespace e a aplicação dos três patches usam cópias distintas
das respectivas bases; os resultados são conferidos por bytes, tipos e bit
executável. Patches Git não transportam UID/GID, inodes, timestamps, ACLs ou
todos os bits POSIX (por exemplo, escrita de grupo); não se afirma restauração
integral desses metadados pelo patch.

A revisão independente aprovou A2-LF-01, repetiu os 200 testes, os nove casos
focados e o harness real offline. Também conferiu alvo LF inexistente, alias
textual com LF para destino físico comum, LF intermediário e `pwd` emitindo LF
adicional com status zero. Não encontrou bloqueio nesta correção; isso não
constitui aprovação dos demais achados ou da distribuição instalada.

Não foram executados containers, CI, instalações completas de arquétipos ou o
binário uv 0.9.0. Mantêm-se os limites documentados de concorrência e de builds
autorizados; a evidência nova trata somente a perda de LF no caminho.

Os contratos A1/A3, isolamento A2, preservação de `.envrc`, guarda de pais e
inspeção de links da `.venv` permanecem. Os demais achados e funcionalidades
continuam fora do escopo. Os novos patches distinguem o ajuste sobre a candidata
anterior, A2/A3 corrigida sobre a mesma A1 e o acumulado sobre `288a183`.

## Candidata A4 — composição Ruff/pytest — 2026-11-06

Base integrada: `a912bb1f5580a2e732f4bbe0789168eaf6c141a9`, árvore
`cb7c4790ddcae9e8a2d3e27cd7a8a453244ac955`, contendo A1, A2, A3 e A2-LF-01.
A candidata parte de uma fotografia dos 26 arquivos versionados, sem `.git`,
`.envrc` pessoal, caches ou ambiente de desenvolvimento. Somente gerador,
testes do gerador, README e este registro foram alterados.

A4 substitui a decisão textual única sobre `[tool.ruff]` por leitura TOML
semântica e composição independente das famílias Ruff e pytest. Uma família
existente permanece inteira, sem completar chaves/subtabelas ou substituir
valores. Só a família ausente recebe os padrões anteriores. O documento
resultante completo precisa ser TOML válido antes de acrescentar os blocos;
o prefixo original não é reescrito e, sem inclusão, a etapa não grava.
Tabelas inline fechadas que exigiriam reescrita recusam com orientação para
composição manual. Tipos incompatíveis e TOML malformado também recusam.

O usuário aceitou o novo pré-requisito `/usr/bin/python3` >=3.11 com `tomllib`.
O script continua standalone, sem pacote Python adicional. Esse Python roda
com `-I -B`, sem importar código do projeto; não é instalado nem alterado.
A leitura inicial antecede mkdir e todas as chamadas uv; o arquivo é lido
novamente depois dessas chamadas e antes da inclusão. Isso não cria transação
contra alterações concorrentes nem rollback de etapas uv anteriores.

Regressões observadas nesta execução:

- A fotografia de base passou os 200 testes originais; a coleta também foi
  conferida separadamente, sem alterar seleção ou pré-condições.
- A matriz nova de 19 casos teve 17 falhas e dois controles aprovados no
  código anterior; depois da correção, os 19 passaram. As falhas incluem
  pytest ausente quando Ruff existe, tabelas duplicadas, falsos cabeçalhos,
  tipos incompatíveis, recusa inicial e revalidação após mudança durante uv.
- Os testes conferem ausência/uma/ambas as famílias, Ruff só com subtabela,
  chaves citadas/pontuadas/inline, comentários e strings com cabeçalhos,
  bytes originais, CRLF, ausência de LF final e reexecução sem nova gravação.
- A integração offline passou nos quatro estados novo/Ruff/pytest/ambos.
  Com os testes novos sobre a base congelada, os dois estados intermediários
  falharam: pytest ausente ou TOML duplicado recusado pelo uv real. `pin` e
  `sync` são reais; `init` é real quando necessário. `python install` e `add`
  são simulados. O sync não instala o projeto, dependências ou runtime;
  sentinelas de projeto/ambiente externos artificiais permanecem intactas.
- A suíte final completa passou **222 testes em 28,48 s**, sem skips, falhas
  ou avisos, incluindo manutenção, A1/A2/A3/LF-01 e as sete integrações de
  migração com suas pré-condições originais de CPython gerenciado.

O runner usou CPython 3.12.15 gerenciado, pytest 9.1.1, Ruff 0.17.1 e uv
0.13.5. O parser chamado pelo gerador foi o Python do sistema 3.14.4. Uma
verificação adicional do mesmo helper extraído passou oito fixtures em cada
um dos CPython 3.11.17, 3.12.15, 3.13.11 e 3.14.4 já disponíveis: 32 casos,
distintos dos 222 pytest e sem download de interpretadores. Essa verificação
isolada do helper não é matriz completa do gerador nem CI.

Passaram Ruff check/format dos 20 arquivos Python e do novo helper embutido
extraído, ShellCheck, shfmt em conferência, sintaxe Bash e ajuda. O ambiente
de desenvolvimento foi copiado; os comandos usam uv offline/no-sync/no-cache,
com HOME/XDG/cache/TMPDIR descartáveis e bytecode desabilitado. Não houve
instalação de ferramentas nem acesso a índices de pacotes nesta validação.
As integrações antigas de migração continuam usando wheels artificiais locais.

A revisão independente leu o diff, os chamadores, as regressões e a
documentação, sem repetir a suíte ou os lints. O único apontamento documental
(uma frase antiga negando a necessidade de Python do sistema) foi corrigido;
não confirmou bloqueios no recorte A4. O patch incremental é conferido por
bytes, tipos, links e bit executável sobre uma cópia nova da base; ele não
transporta todos os metadados POSIX.

Não foram executados CI, containers, instalações completas dos arquétipos,
uv 0.9.0, falhas físicas de disco ou testes de concorrência. A validade das
opções existentes de Ruff/pytest não é auditada por este compositor. A5/A6,
R1, ds/jlab e project doctor ficam fora do recorte; seleção de versões e
`target-version = "py312"` permanecem como antes.

O checkout original e seu `.envrc` pessoal não recebem o patch. A candidata
não contém os particulares. Não houve stage, commit, push, instalação de
`pyinit`, mudança de gitlink/manifesto/lançadores ou atualização do Data Lab.
As evidências de CI descritas em etapas anteriores são históricas e não
validam remotamente os novos bytes A4.

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
