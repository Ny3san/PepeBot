# Voice XP

Bot que dá XP pra quem fica em call. Quanto mais tempo de voz, mais nível,
e o bot vai entregando cargos sozinho conforme a pessoa sobe. Tem ranking
com imagem, cartão de perfil, sequência de dias (streak), Double XP,
multiplicadores por cargo e um painel de configuração inteiro dentro do
Discord: não precisa mexer em arquivo nenhum depois que o bot está no ar.

Feito em Python 3.12 com discord.py 2.7+. As mensagens do bot usam o
Components v2 do Discord (aqueles blocos nativos com botão dentro), então
nada aqui é embed antigo.

## Como rodar

```bash
python -m pip install -r requirements.txt
python src/bot.py
```

Antes disso, crie um `.env` na raiz:

```
BOT_TOKEN=cole_o_token_aqui
DEV_GUILD_ID=            # opcional: id do servidor de testes, sync na hora
CLOWN_DB_PATH=           # opcional: onde salvar o banco (padrão: raiz)
BYPASS_USER_IDS=         # opcional: IDs (separados por vírgula) com acesso admin total, em todo servidor
```

`CLOWN_TOKEN` e `CLOWN_GUILD_ID` também funcionam como nomes alternativos.

`BYPASS_USER_IDS` é um bypass administrativo global (ignora dono, cargo
autorizado e 2FA). Cada uso é logado (`utils/checks.py`, `views/twofa.py`).
Deixe vazio se não precisar disso.

No Developer Portal, liga o **Server Members Intent** e o **Message Content
Intent**, senão o bot não enxerga os membros nem as mensagens.

Sem `DEV_GUILD_ID` os slash commands são registrados globalmente, o que pode
demorar um pouco pra aparecer (coisa do Discord, não do bot).

## Comandos

| Comando | Também funciona como | O que faz |
|---|---|---|
| `/xp [membro]` | `-xp [@membro]` | Cartão de perfil em imagem: nível, barra de progresso, XP, horas, posição |
| `/rank` | `-rank` | Top 10 do servidor, também em imagem |
| `/xpadmin add/remove/reset` | `-xpadmin add @membro 100` | Ajustes manuais de XP |
| `/resetall` | `-resetall` | Zera o XP do servidor inteiro |
| `/setup` | — | Painel de configuração (só você vê) |

Se a geração da imagem falhar por qualquer motivo, o `/xp` e o `/rank` caem
num fallback de texto com as mesmas informações.

## Como o XP funciona

- Ficou em call num canal permitido → ganha XP por minuto (configurável).
- Tem um tempo mínimo de call pra começar a contar, pra ninguém farmar
  entrando e saindo.
- Mutado/ensurdecido contar ou não é escolha sua no painel.
- Mensagem no chat também pode dar XP, com cooldown pra não virar spam.
- **Multiplicadores por cargo**: cargo X ganha 1.5x, cargo Y ganha 2x. Se a
  pessoa tem vários, vale só o maior.
- **Bônus de call cheia**: call com N+ pessoas rende mais pra todo mundo.
- **Streak**: entrou em call todo dia, o multiplicador vai crescendo
  (7, 15, 30 e 60 dias).
- **Double XP**: evento temporário que você liga no painel com duração em
  horas.
- Os cargos de nível são entregues automaticamente quando a pessoa cumpre o
  requisito (nível, XP total ou horas), e o bot mantém a hierarquia deles
  organizada no servidor.

## Painel /setup

Tudo se configura por aqui, navegando com botões:

```
Voice XP (menu principal)
├── XP de Voz       — canais, XP/min, tempo mínimo, mutado/ensurdecido
├── XP de Chat      — XP por mensagem, cooldown, canais
├── Multiplicadores — XP extra por cargo
├── Settings
│   ├── Cargos      — cargos de nível (criar/editar) e reset do ranking
│   └── Canais      — canal de logs e canal de ranking automático
├── Eventos         — bônus de call cheia, Double XP
├── Permissões      — quem pode configurar o bot (protegida por 2FA)
└── Ativar/Desativar sistema
```

Na seção Cargos dá pra criar um cargo de nível do zero: você digita o nome
e o nível, o bot cria o cargo, vincula e posiciona na hierarquia sozinho.

Se você definir um canal de ranking, o bot mantém uma mensagem com o top 10
sempre atualizada lá (a cada 5 minutos). O ranking pode resetar a cada 7 ou
30 dias, anunciando o vencedor do período no canal de logs.

O painel sobrevive a restart do bot: se alguém clicar num painel antigo, ele
se reconstrói na mesma mensagem em vez de morrer com "interação falhou".

## Quem pode mexer

Só o dono do servidor e quem tiver o cargo definido em **Permissões →
Acesso**. Sem cargo definido, só o dono mesmo.

E tem uma camada extra: as ações mais sensíveis (abrir/alterar o Acesso e
ligar/desligar o sistema) pedem confirmação do dono. O bot manda uma DM pro
dono dizendo quem quer fazer o quê, com botões de **Confirmar** e
**Recusar**. O pedido vale pra uma ação só e expira em 3 minutos. O dono,
claro, faz tudo direto sem passar por isso.

## Estrutura do código

```
src/
├── bot.py          # entrada: cria o bot, carrega as extensões, sync
├── config/         # leitura do .env e constantes
├── models/         # dataclasses: GuildConfig, RoleReward, MemberStats...
├── database/       # sqlite3 (WAL) + repositórios com cache
├── services/       # regras de negócio: XP, níveis, recompensas, cartão, logs, 2FA
├── systems/        # tracker de voz, ranking, scheduler
├── commands/       # cogs: xp, rank, xpadmin, setup
├── events/         # entrada/saída de call, mensagens, on_ready
├── views/          # painel em Components v2: seções, botões, selects, modais, 2FA
└── utils/          # formatação e checagem de permissão
```

## Testes

Suíte de testes com `pytest` cobrindo o core de regras de negócio (curva de
nível, `GuildConfig` e migração do formato legado, `XpService`,
`RewardService`, repositórios). Roda contra um banco SQLite em memória, sem
tocar no `clown.db` real.

```bash
uv sync                # instala dependências (produção + dev) num .venv
uv run pytest -q
```

Sem `uv`, dá pra usar `pip install -r requirements.txt pytest pytest-asyncio`
e rodar `pytest` normalmente a partir da raiz do projeto.

## Banco de dados

SQLite puro, num arquivo `clown.db` na raiz (o modo WAL gera os arquivos
`-shm` e `-wal` do lado, é normal). O schema é criado e migrado sozinho no
boot. Pra mudar de máquina, é só copiar o `clown.db` junto. Se na
hospedagem o arquivo ficar em outro lugar, aponte com o `CLOWN_DB_PATH`.
