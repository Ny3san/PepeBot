# Voice XP — Instruções do projeto

Bot de Discord (Python 3.12, discord.py 2.7+) que dá XP por tempo em call e
por mensagens, com níveis, recompensas de cargo, ranking, streak, Double XP
e painel `/setup` em Components v2. Arquitetura em camadas: `config/` →
`models/` → `database/` (sqlite WAL + repositórios com cache) → `services/`
(regras de negócio) → `systems/` (tracker, ranking, scheduler) →
`commands/`/`events/`/`views/` (interface Discord).

Estas regras vêm de uma auditoria técnica completa do projeto (2026-07-19) e
existem para não repetir os problemas encontrados nela. Elas valem para
qualquer sessão futura que mexer neste repositório.

## Regras obrigatórias

### Log de toda sessão de trabalho
Sempre que você (Claude) alterar qualquer arquivo deste projeto:
1. Ao final da sessão (ou a cada mudança relevante), grave um arquivo de log
   em `.claude/logs/`, nomeado `AAAA-MM-DD_HH-mm-ss-resumo-curto.md`, contendo:
   data/hora, o que foi alterado (arquivos), por que, e qualquer decisão ou
   risco relevante tomado durante a sessão.
2. Antes de terminar, apague em `.claude/logs/` qualquer arquivo cuja data no
   nome seja **anterior à data de hoje** (1 dia ou mais atrás) — mantenha
   apenas os logs do dia corrente. Não apague logs do próprio dia.
3. Nunca pule este passo, mesmo em alterações pequenas (ex.: só documentação).

### Git e segredos
- O projeto deve ter `.gitignore` cobrindo `.env`, `clown.db`, `clown.db-shm`,
  `clown.db-wal`, `.venv/`, `backup-db-local/`. Nunca remova essas entradas.
- Nunca commitar `.env` ou qualquer arquivo com token/credencial.
- Nunca use `git push --force`, `reset --hard`, `clean -f` sem confirmação
  explícita do usuário nesta sessão.

### Banco de dados
- **Nunca** proponha ou execute `DROP TABLE`, `DELETE` em massa fora de um
  fluxo de reset já existente (`reset_guild`/`reset_user`), ou qualquer
  operação que apague dados de XP sem o usuário pedir explicitamente.
- Migrações de schema devem ser idempotentes e o `except` em volta de um
  `ALTER TABLE` deve checar especificamente "coluna já existe" — nunca um
  `except Exception: pass` genérico que engole outros erros.
- `ConfigRepository.get()` (e qualquer parse de JSON vindo do banco) precisa
  de fallback seguro para dado corrompido: nunca deixar uma guild travada
  por uma exceção não tratada em `from_dict`/`json.loads`.

### Testes antes de refatorar
- Antes de alterar lógica de negócio (`XpService`, `LevelCurve`,
  `RewardService`, streak, migração legado de `GuildConfig.from_dict`),
  garanta que existe teste cobrindo o comportamento atual. Se não existir,
  escreva o teste primeiro, depois refatore.
- Não faça refatorações estruturais grandes (ex.: quebrar `views/panel.py`
  em subpacote) sem testes de regressão cobrindo o fluxo afetado.

### Performance / chamadas à API do Discord
- Nunca faça loops sequenciais de `add_roles`/`remove_roles`/`send` para mais
  de ~10 membros dentro do callback síncrono de uma interação (modal/botão).
  Use `asyncio.create_task` para rodar em background e responder rápido ao
  usuário.

### Consistência de código
- Todo campo de dataclass/model precisa ser efetivamente lido em algum lugar.
  Não deixe campos "decorativos" (ex.: um campo de config que a UI seta mas
  nenhum service consulta) — implemente de verdade ou remova.
- Não deixe variáveis calculadas e nunca usadas (dead code tipo flags `dirty`
  que não disparam nenhuma ação).

### Compatibilidade multiplataforma
- Qualquer asset carregado por caminho de sistema operacional (fontes,
  etc.) precisa ter uma cópia embutida no repo (`assets/`) como primeira
  opção — não depender só de fontes/arquivos que só existem no Windows de
  desenvolvimento e podem faltar no host Linux de produção.

### Segurança / permissões
- `BYPASS_USER_IDS` (`src/config/defaults.py`) é um bypass administrativo
  global hardcoded. Não adicione novos IDs a essa lista nem crie bypasses
  equivalentes em outro lugar sem aprovação explícita do usuário nesta
  sessão. Se for alterado, mova para variável de ambiente e adicione log
  dedicado de uso.

## Como validar antes de finalizar uma tarefa
- Rodar os testes (quando existirem) antes de considerar a tarefa concluída.
- Conferir que nenhuma mudança introduziu `DROP`/perda de dados não pedida.
- Escrever o log da sessão em `.claude/logs/` e limpar logs de dias
  anteriores, conforme a regra acima.
