Relatório de Auditoria Técnica — Voice XP Bot

1. Visão geral do projeto

Bot de Discord (Python 3.12, discord.py 2.7.1 instalado, requirements pedindo >=2.7,<3 — compatível e correto) que credita XP por tempo em call e por mensagens no chat, com níveis, recompensas automáticas de cargo, ranking com imagem, streak, multiplicadores, Double XP e um painel de configuração completo (/setup) construído em Components v2 (LayoutView/Container/TextDisplay/Separator/ActionRow), API correta para a versão do discord.py usada.

A arquitetura já está razoavelmente em camadas, não é um monólito de fato:

bot.py       → composição raiz (instancia repos/services e injeta como atributos do bot)
config/      → settings (.env) + constantes
UserPromptSubmit hook error
Failed with non-blocking status code: /usr/bin/bash: line 1: node: command not found

  Listed 1 directory

Vou iniciar a auditoria técnica completa do projeto. Primeiro vou mapear a estrutura, ler a documentação e usar o CodeGraph (já indexado neste repositório) para entender a arquitetura em profundidade.

  Searched for 6 patterns, read 19 files, called codegraph 6 times, ran 4 shell commands

Relatório de Auditoria Técnica — Voice XP Bot

1. Visão geral do projeto

Bot de Discord (Python 3.12, discord.py 2.7.1 instalado, requirements pedindo >=2.7,<3 — compatível e correto) que
credita XP por tempo em call e por mensagensnsas automáticas de cargo, ranking comimagem, streak, multiplicadores, Double XP e um painel de configuração completo (/setup) construído em Components v2 (LayoutView/Container/TextDisplay/Separator/ActionRow), API correta para a versão do discord.py usada.

A arquitetura já está razoavelmente em camad:

bot.py       → composição raiz (instancia repos/services e injeta como atributos do bot)
config/      → settings (.env) + constantes
models/      → dataclasses puras (GuildConfig, RoleReward, StreakBonus, MemberStats)
database/    → conexão sqlite (WAL) + repositórios (ConfigRepository com cache, StatsRepository)
services/    → regras de negócio (XpService, LevelCurve, RewardService, TwoFactorService, card/log)
systems/     → tracker de voz (sessões), ranking, scheduler (tasks periódicas)
commands/    → cogs de comando (xp, rank, xpadmin, setup)
events/      → cogs de evento (voice, messag
views/       → painel Components v2 (base, panel, modals, rewards_view, twofa)
utils/       → checks de permissão, formatação

Persistência: SQLite puro, conexão única compartilhada, WAL + synchronous=NORMAL, schema criado e migrado via lista idempotente de ALTER TABLE. Não há ORM — decisão consciente e documentada no próprio código (comentário em connection.py justificando I/O síncrono pelo volume de escrita esperado).

Não há testes automatizados, não há repositório git, não há .gitignore.

---
2. Problemas encontrados

#: 1
Onde: models/guild_config.py:26 + services/reward_service.py:69-78
Problema: O campo RoleReward.remove_previouse setado como True na criação
(views/rewards_view.py:154,258), mas nunca é lido em RewardService.check_member — a lógica remove incondicionalmente
todos os outros cargos de recompensa, independente do valor do campo. É um campo morto/inconsistente: hoje não existe
 forma de ter cargos de nível acumulativos mesmo que a UI sugira essa intenção pelo nome do campo.
────────────────────────────────────────
#: 2
Onde: database/stats_repo.py:44-64
Problema: Em StatsRepository.get(), a variável dirty é setada como True em dois pontos e nunca lida depois — resíduo
de
uma versão anterior. Inofensivo, mas indica refatoração incompleta.
────────────────────────────────────────
#: 3
Onde: services/xp_service.py:88,112 + database/stats_repo.py:107-124
Problema: O multiplicador de streak é calculado com stats.streak_current antes de register_streak_day() incrementá-lo
para o dia corrente. Resultado: ao bater 7/15/30/60 dias, o bônus só passa a valer no dia seguinte ao marco, não no
dia em que ele é atingido. Pode ser intencional, mas o README ("entrou em call todo dia, o multiplicador vai
crescendo (7, 15, 30 e 60 dias)") sugere quedia do marco — vale confirmar com o time se
é bug ou comportamento esperado.
────────────────────────────────────────
#: 4
Onde: services/card_service.py:31-41
Problema: Caminhos de fonte hardcoded, na ordem: fontes do Windows primeiro, com um único fallback DejaVu para Linux.
Em hospedagem Linux sem fonts-dejavu-core inker mínimas), cai silenciosamente em
ImageFont.load_default() — uma bitmap font minúscula — degradando visualmente todos os cartões /xp e /rank sem
qualquer erro ou log. Como não há testes nem verificação de ambiente, isso só seria percebido em produção.
────────────────────────────────────────
#: 5
Onde: database/connection.py:68-73
Problema: _migrate() executa cada ALTER TABLE em um try/except sqlite3.OperationalError: pass genérico. Correto para
"coluna já existe", mas também engole silenc operacional (disco cheio, banco bloqueado,
permissão) durante o boot, mascarando falhas reais de migração.
────────────────────────────────────────
#: 6
Onde: database/config_repo.py:15-25
Problema: ConfigRepository.get() não tem tratamento de erro ao redor de
GuildConfig.from_dict(json.loads(row["config"])). Um JSON corrompido na coluna config (edição manual, bug futuro em
serialização, migração malformada) derruba toda interação daquele servidor com uma exceção não tratada, sem fallback
para os defaults.
────────────────────────────────────────
#: 7
Onde: views/rewards_view.py:129-165,249-282 irements_modal.save)
Problema: Ao criar/editar um cargo de nível, o código itera bot.stats.top(cfg.guild_id, 500) e faz await
bot.rewards.check_member(...) sequencialmente, dentro do próprio callback da interação, para até 500 membros.  Cada
chamada pode disparar 1-2 requisições HTTP ao Discord (add/remove role). Em servidores grandes isso pode segurar a
resposta daquela interação por muito tempo (as por segundo) — ver  seção de gargalos de
performance abaixo.

---
3. Riscos

🔴 Alto — BYPASS_USER_IDS hardcoded (src/config/defaults.py:4)
Um ID de usuário do Discord fixo no código-fonte tem acesso administrativo total (ignora cargo, ignora dono, ignora 2FA) em qualquer servidor onde o bot estiver instalado. Isso é, na prática, um backdoor de fábrica:
- Se o repositório for compartilhado, publica descobre que existe um "usuário mestre" com acesso irrestrito a todos os servidores que rodam o bot.
- Donos de servidor não têm visibilidade nem deram consentimento explícito para esse acesso.
- Nenhuma ação feita via esse bypass é logadnd_log normal registra "quem fez o quê", masnão sinaliza que foi via bypass global).

🔴 Alto — Ausência total de controle de versão
O diretório não é um repositório git (Is a git repository: false) e não existe .gitignore. Consequências práticas:
- Nenhum histórico, nenhum rollback possível em caso de regressão em produção.
- Se o git for inicializado sem cuidado, .endados reais de XP de todos os servidores)seriam commitados por padrão — vazamento de credencial e de dados de usuários.

🟠 Médio — Zero cobertura de testes
Toda a lógica sensível (cálculo de XP/multiplicadores, curva de nível, streak, elegibilidade de recompensa, migração
de config legado JS→Python) roda sem qualque refatoração — inclusive as sugeridas nesterelatório — é feita "no escuro".

🟠 Médio — Config corrompida derruba o servidor (ver Problema #6): sem fallback, um guild com JSON inválido fica inutilizável até intervenção manual no banco.

🟡 Baixo/operacional — Múltiplas instâncias
O código já tem tratamento defensivo explícito para os erros HTTP 10062/40060 ("outra instância já respondeu"), em views/base.py, commands/setup.py. Isso é sinal de que o problema já aconteceu (mesmo token rodando local + hospedagem simultaneamente). Vale documentar operacionaa.

🟡 Baixo — Backup de banco manual
Existe uma pasta backup-db-local/ com cópias de clown.db, mas não há rotina automatizada no próprio bot (snapshot periódico, ou pelo menos um lembrete/checagem de idade do backup). Perda do arquivo único = perda de todo o histórico
de XP de todos os servidores atendidos.

Nenhum problema de integridade de schema encontrado: voice_stats tem PK composta (guild_id, user_id) correta, índices em (guild_id, period_xp DESC) e (guild_id, total_xp DESC) cobrem exatamente as queries de top()/rank_of() — não há query duplicada nem faltando índice. guild_config com PK simples e INSERT ... ON CONFLICT DO UPDATE está correto para upsert. Nenhuma sugestão deste relatório envolve apagar tabelas ou dados.

---
4. Melhorias recomendadas

- Testes automatizados (pytest + pytest-asyncio) cobrindo, no mínimo: LevelCurve (curva de XP), GuildConfig.from_dict (inclusive a migração do formato legado camelCase), XpService (stacking de multiplicadores),
RewardService.check_member (com um discord.My/ConfigRepository usandoDatabase(path=":memory:").
- Fallback defensivo em ConfigRepository.get(): try/except ao redor do parse, com log de erro e retorno de GuildConfig default em vez de propagar a exceção.
- Restringir o except de migração (connectioumn" na mensagem do erro, ou inspecionarPRAGMA table_info antes de tentar o ALTER TABLE, em vez de engolir qualquer OperationalError.
- Mover a sincronização em massa de cargos para background (asyncio.create_task) em vez de await sequencial dentro do callback de modal, para não segurar a resposta da interação em servidores grandes.
- Resolver o campo remove_previous morto: ou implementar de fato o comportamento acumulativo, ou remover o campo do modelo para não sugerir uma funcionalidade que não existe.
- Empacotar uma fonte TTF junto ao projeto (assets/fonts/) como primeira opção em _font(), eliminando a dependência de fontes do SO estarem presentes no host de produção.
- Mover BYPASS_USER_IDS para variável de ambiente e logar toda vez que o bypass for exercido (decisão de produto sobre
manter ou remover essa funcionalidade deve s).
- Handler global on_app_command_error no VoiceXPBot, como rede de segurança adicional além dos checks já existentes por cog.

---
5. Estrutura sugerida

A base já segue boa separação de responsabilidades; a recomendação é evolução incremental, não reescrita:

src/
├── bot.py
├── config/            (mantém)
├── models/            (mantém)
├── database/
│   ├── connection.py  (+ tabela schema_version explícita)
│   ├── config_repo.py (+ fallback em erro de parse)
│   └── stats_repo.py
├── services/          (mantém; considerar Protocol para repos se o projeto crescer)
├── systems/           (mantém)
├── commands/          (mantém)
├── events/            (mantém)
├── views/
│   └── panel/                 ← quebrar views/panel.py (483 linhas, 9 seções) em subpacote
│       ├── main.py
│       ├── voice.py
│       ├── messages.py
│       ├── multipliers.py
│       ├── events.py
│       ├── access.py
│       ├── channels.py
│       └── dispatcher.py      (render() + _SECTIONS)
├── utils/             (mantém)
└── assets/
    └── fonts/         ← fonte TTF embutida (novo)

tests/                 ← novo, espelhando a estrutura de src/

Não há necessidade de introduzir Dependency tecture "em camadas concêntricas" completa ou um Repository Pattern mais elaborado — o pro e a injeção atual via atributos do bot(bot.configs, bot.stats, bot.xp, bot.rewards, bot.tracker, bot.twofa) já cumpre o papel de composition root de forma simples e testável (dá pra instanciar cada service isoladamente nos testes). Adicionar camadas extras aqui seria over-engineering para o tamanho atual do bot.

---
6. Ordem ideal da refatoração

1. git init + .gitignore (excluir .env, clown.db*, .venv, backup-db-local/) — risco zero, pré-requisito para tudo o resto ser rastreável e reversível.
2. Suíte de testes cobrindo o core de regras de negócio (XP, curva de nível, streak, recompensas, migração legado) — rede de segurança antes de tocar em qualquer lógica existente.
3. Correções pontuais de baixo risco: campo remove_previous morto, variável dirty não usada, fonte embutida, except de migração mais específico — cada uma protegida pelos testes do passo 2.
4. Fallback de erro em ConfigRepository.get() para JSON corrompido.
5. Mover a sincronização em massa de cargos para background task (melhoria de performance, sem mudança de comportamento visível).
6. Decisão de produto + implementação sobre nv var, logging de uso) — feito com ousuário, não unilateralmente, por ser uma mudança de superfície de segurança.
7. Modularização de views/panel.py em subpacote — puramente estrutural, só depois de haver testes cobrindo a navegação/seções para garantir que nada quebrou.
8. (Opcional, futuro) Formalizar Protocol/AB o projeto crescer a ponto de precisar trocar o backend de sqlite ou mockar mais pesadamente em testes.

---
7. Checklist para o Desenvolvedor

Infraestrutura / operações
- [ ] Inicializar repositório git e criar .gitignore (.env, clown.db, clown.db-shm, clown.db-wal, .venv/, backup-db-local/)
- [ ] Definir rotina de backup automatizado do clown.db (script agendado ou lógica no próprio bot)
- [ ] Documentar no README o risco de rodar oken

Segurança
- [ ] Discutir com o usuário se BYPASS_USER_ se sim, mover para .env e adicionar logdedicado de uso
- [ ] Adicionar try/except com fallback em ConfigRepository.get() para JSON corrompido

Testes
- [ ] Configurar pytest + pytest-asyncio
- [ ] Testes de LevelCurve.progress/xp_for_l
- [ ] Testes de GuildConfig.from_dict, incluindo o caminho de migração legado (_migrate_legacy)
- [ ] Testes de XpService.total_multiplier/award_minutes/award_message_xp (stacking de multiplicadores, caps diários)
- [ ] Testes de RewardService.check_member/mde discord.Member)
- [ ] Testes de StatsRepository/ConfigRepository com Database(path=":memory:")

Bugs / dívida técnica
- [ ] Resolver o campo morto RoleReward.remove_previous (implementar ou remover)
- [ ] Remover a variável dirty não utilizada em StatsRepository.get()
- [ ] Confirmar se o lag de 1 dia no bônus de streak é intencional; ajustar se não for
- [ ] Restringir o except sqlite3.Operationajá existe"
- [ ] Embutir fonte TTF no projeto em vez de depender de fontes do SO

Performance
- [ ] Mover a sincronização em massa de cargos (on_create_level_role, _requirements_modal.save) para uma
asyncio.create_task em background

Arquitetura
- [ ] Quebrar views/panel.py em subpacote views/panel/ por seção (somente após testes cobrirem a navegação)
- [ ] Adicionar on_app_command_error global no VoiceXPBot como rede de segurança adicional
