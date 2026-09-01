# Setup de Emojis Customizados

## O que foi feito

Todas as 14 imagens do painel foram adicionadas ao projeto em `assets/emojis/` e integradas aos botões:

### Mapeamento de Emojis

| Nome | Arquivo | Usado em |
|------|---------|---------|
| `voltar` | voltar.png | Botões "Voltar" em todas as seções |
| `settings` | settings.png | Botão "Settings" no painel principal |
| `eventos` | eventos.png | Botão "Eventos" |
| `permissões` | permissões.png | Botão "Permissões" |
| `cargo` | cargo.png | Botão "Cargos" (em recompensas) |
| `canais` | canais.png | Botão "Canais" |
| `xp_call` | xp_call.png | Botão "XP de Voz" |
| `multiplicador` | multiplicador.png | Botão "Multiplicadores" |
| `sistema_toggle` | sistema_toggle.png | Botão "Ativar/Desativar Sistema" |
| `mutado` | mutado.png | Botão "Mutado" (em XP de Voz) |
| `ensurdecido` | ensurdecido.png | Botão "Ensurdecido" (em XP de Voz) |
| `edit_role` | edit_role.png | Imagem armazenada (em uso futuro) |
| `reset_time` | reset_time.png | Imagem armazenada |
| `confirm` | confirm.png | Imagem armazenada |
| `denied` | denied.png | Imagem de recusa |

## Como ativar no seu servidor

### Passo 1: Executar comando de upload

No seu servidor Discord, execute:
```
/emoji_upload
```

**Requisitos:**
- Você precisa ter permissão de **Administrador** no servidor
- O bot precisa ter permissão de gerenciar emojis no servidor

### Passo 2: Resultado

O bot fará upload de todas as imagens como emojis customizados e retornará:
- ✅ Confirmação de cada emoji criado
- ⚠️ Alertas de falhas (se servidor tiver limite de emojis)

### Passo 3: Pronto!

Os emojis vão aparecer automaticamente nos botões do painel na próxima vez que abrir.

## Troubleshooting

### "Nenhuma imagem encontrada"
Verifique que `assets/emojis/` existe e tem imagens.

### "Erro ao criar emoji"
Possíveis razões:
- Servidor atingiu limite de emojis (máx ~50-200 por plano)
- Arquivo corrompido
- Permissões do bot insuficientes

### Emojis não aparecem nos botões
Verifique que:
- `.emoji_map.json` foi criado no raiz do projeto
- Botões estão usando `emoji=get_emoji("name")`
- Pode ser cache do Discord — reabra o painel

## Desativar emojis

Para remover os emojis dos botões, edite os arquivos em `src/views/` e remova o parâmetro `emoji=` dos botões.

## Adicionar novos emojis

1. Adicione a imagem em `assets/emojis/`
2. No arquivo de view, use `emoji=get_emoji("nome_do_arquivo")`
3. Execute `/emoji_upload` novamente
