# Tradução de texto em imagem / fontes bitmap

Escopo: **todo texto visível** (strings + sprites + fontes). Áudio/dublagem fora.

| Tipo | Como traduzir | Status |
|------|----------------|--------|
| Strings em MonoBehaviour | `apply_patch_expand.py` (**binário**, sem typetree) | Em uso |
| Texto de menu (labelText/appName) | expand / inplace | Em uso |
| **Botões save/title** (`loadscreen_button_*`) | Redesenhar sprite no atlas | **23 PT instalados** |
| Fontes bitmap tk2d (`Exo*`) | Sem acentos → `fold_ascii_pt.py` (`nao`/`faco`) | Em uso |
| tk2d `_text` nos TextMeshes | Campos vazios no asset (texto setado em runtime/DLL) | — |
| Áudio / voz | **Fora de escopo** | — |

## Achado: title/save = word-sprites

Continue / Start as Male|Female / NO DATA / Cancel / Credits / Erase / Gallery /
Settings **não** são strings no `.assets`. São sprites na collection tk2d
(atlas `Texture2D`), ex.:

- `loadscreen_button_continuegame` (+ `_over`)
- `loadscreen_button_startmale` / `startfemale`
- `loadscreen_nodata_background`
- `ui_transition_screen_gamesaved`

Cortes em `export/ui_sprites/` (+ `manifest.json` com UVs para reimport).

Fontes Exo: cada `*Fontdata` tem `chars[127]` (ASCII). PT-BR com acento exige
novos glifos no PNG da fonte **e** entradas extras em `chars` (ou remap).

## Pipeline

1. `python scripts/extract_ui_images.py` → `export/ui_images/` + `export/ui_sprites/`
2. `python scripts/generate_ui_pt.py` → `export/ui_sprites/pt/`
3. `python scripts/apply_ui_images.py` (usa `build/patch_expand/sharedassets0.assets`)
4. `--install` copia sharedassets; reinstalar `resources.assets` do expand se necessário
5. (depois) acentos nas fontes Exo se diálogos usarem Latin-1

Ordem correta: **expand de strings primeiro**, depois UI no sharedassets já patchado.

## Comandos

```bash
python scripts/extract_ui_images.py
python scripts/generate_ui_pt.py
python scripts/apply_ui_images.py --install
```
