# HuniePop PT-BR (fan translation — texto apenas)

Tradução feita por fãs do **HuniePop** (Steam) para português brasileiro.  
Escopo: **somente texto** (UI, tutoriais, diálogos, mensagens). Sem dublagem/áudio.

> Você precisa ter o jogo na Steam. Este patch **não** inclui o executável do jogo.

## Download (alfa)

**[Release v0.0.1](https://github.com/VictorCabral99/HuniePop-PT-BR/releases/tag/v0.0.1)** — baixe o zip, leia o `LEIA-ME.txt` e copie `HuniePop_Data` para a pasta do jogo.

## Status

| Item | Estado |
|------|--------|
| Versão | **alfa 0.0.1** |
| Diálogos + UI em PT-BR | sim (rascunho; tom em revisão) |
| Áudio | inglês (fora do escopo) |
| QA completo | pendente |

## Instalar o zip (jogadores)

1. Feche o HuniePop.
2. Steam → HuniePop → Gerenciar → Procurar arquivos locais.
3. (Opcional) Backup de `HuniePop_Data\resources.assets` e `sharedassets0.assets`.
4. Extraia o zip e **copie** a pasta `HuniePop_Data` por cima da pasta do jogo (substituir).

Se der tela preta: Steam → Verificar integridade dos arquivos.

## Desenvolvimento (tradutores)

```bash
python -m pip install -r requirements.txt
python scripts/extract_strings.py
# editar locale/pt-BR/unique_texts_ascii.csv  (sep=$ ; delim $)
python scripts/apply_patch_expand.py --source assets/original/backup_... --install
python scripts/apply_ui_images.py --assets build/patch_expand/sharedassets0.assets --install
python scripts/build_dropin.py --zip
```

Caminho Steam (Windows):  
`C:\Program Files (x86)\Steam\steamapps\common\HuniePop`

## Princípios

1. Markup do jogo (`[[Passion]heart]`, pausas `·····`) preservado.
2. Nomes das garotas em inglês (salvo glossário).
3. Tom: casual BR (**você/vocês**), adulto — ver `docs/tom-pt-br.md`.
4. No git: scripts + CSV + docs. O zip da release leva os `.assets` patchados.
