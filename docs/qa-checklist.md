# Checklist QA in-game (PT-BR texto)

Use depois de `python scripts/apply_patch.py --pilot --install` (ou instalar o conteúdo de `build/patch`).

## Antes de abrir o jogo

- [ ] Backup existe em `assets/original/backup_YYYYMMDD_HHMMSS/`
- [ ] `python scripts/verify_patch.py --pilot` reporta `missing=0`
- [ ] Steam: verificar integridade dos arquivos **só se** precisar restaurar o inglês (isso apaga o patch)

## Menu / opções

- [ ] **Tela cheia** / **Janela** aparecem traduzidos
- [ ] Dificuldade: **Fácil** / **Normal** / **Difícil**
- [ ] Volume/qualidade: **Alto** / **Médio** / **Baixo** (se aplicável)
- [ ] Gênero: **Masculino** / **Feminino**
- [ ] Acentos legíveis (á, ã, ç, é…) — se virarem □ ou ?, falta fonte

## Celular / ações com a garota

- [ ] **Busca de Garotas**
- [ ] **Convidar para encontro**
- [ ] **Conversar com ela**
- [ ] **Comprar presentes**
- [ ] **Ver perfil**
- [ ] **Ver inventário**

## Estabilidade

- [ ] Jogo abre sem crash na splash
- [ ] Entrar num encontro / conversa curta sem crash
- [ ] Sem texto cortado demais nos botões (PT costuma ser mais longo)

## Se algo quebrar

1. Feche o jogo  
2. Restaure os `.assets` do backup para `HuniePop_Data\`  
3. Abra um issue/nota com: tela, string EN esperada, o que apareceu

## Fora de escopo deste QA

- Áudio / voz (permanece em inglês)
- Diálogos longos (ainda não traduzidos no lote UI)
