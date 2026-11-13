# Política de segurança

## Versões com suporte

Somente a versão mais recente do branch `main` recebe correções de segurança.
O `pyinit` instalado pelo Data Lab Dotfiles é uma cópia fixada por checksum;
correções chegam a ele por uma atualização aprovada dessa versão fixada.

## Como relatar uma vulnerabilidade

Não abra uma issue pública para falhas de segurança. Use o relato privado
do GitHub:

1. Acesse a aba **Security** deste repositório.
2. Escolha **Report a vulnerability**
   (<https://github.com/talesgomes27/python-template-linux/security/advisories/new>).

Inclua, se possível, a versão (`pyinit --version` ou o commit), o comando
executado, o comportamento esperado e o observado, e um exemplo mínimo que
reproduza o problema. Não inclua credenciais nem dados reais.

## O que está no escopo

- `scripts/init_project.sh` e os módulos em `scripts/pyinit/`: criação de
  projetos, migração, restauração e manutenção, incluindo tratamento de
  symlinks, hardlinks, permissões e variáveis de ambiente.
- O workflow de CI deste repositório e os arquivos gerados para novos
  projetos.

Ficam fora do escopo falhas em dependências de terceiros (uv, Ruff, pytest,
mypy, direnv, Data Lab Dotfiles), que devem ser relatadas aos respectivos
projetos, e os limites já documentados em
[docs/generator.md](docs/generator.md) e [docs/VALIDATION.md](docs/VALIDATION.md),
como a ausência de garantia contra alterações concorrentes por processos com
acesso de escrita ao projeto.
