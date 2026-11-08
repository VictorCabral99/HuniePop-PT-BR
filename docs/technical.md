# Notas técnicas — HuniePop texto PT-BR

## Engine

- Unity **4.2.2f1** (Mono)
- Texto em MonoBehaviours dentro de:
  - `HuniePop_Data/resources.assets`
  - `HuniePop_Data/sharedassets0.assets`
- Sem sistema i18n nativo; patch reescreve strings nos assets.

## Extração

Unity 4 não embute TypeTree completo nos `.assets`. Usamos:

1. `UnityPy` para abrir os arquivos
2. `TypeTreeGenerator` + `TypeTreeGeneratorAPI` lendo `Managed/*.dll`
3. `env.typetree_generator = gen` antes de `read_typetree()`

Parte dos MonoBehaviours falha (EOF / tamanho) — esperado; a maioria dos textos de UI/diálogo passa.

## Escopo

**Somente texto.** Áudio/voz permanece em inglês.

## Repack

**Expand binário** ([`scripts/apply_patch_expand.py`](../scripts/apply_patch_expand.py)): troca strings
`<u32 len><utf8><align4>` e reassenta objetos — **sem** `save_typetree` (typetree = tela preta).

Locale usual: `locale/pt-BR/unique_texts_ascii.csv` (após `fold_ascii_pt.py`).

`apply_patch_unitypy.py` / typetree rewrite **quebram** o jogo. Não usar.

## Tradução contextual (diálogos)

Diálogos no asset têm `object_name` de cena (`IntroAiko`, `DateGreeting`, …). Pipeline:

1. `python scripts/build_dialogue_groups.py` → grupos EN ordenados por step
2. `python scripts/retranslate_contextual.py` — traduz em blocos com vizinhos EN + meta (girl/kind); **EN é a fonte**
3. `fold_ascii_pt.py` → expand `--install`

## Fonte / acentos

Fontes Exo bitmap = ASCII. `fold_ascii_pt.py` mantém a letra (`não`→`nao`). Ver [image-text.md](image-text.md).

## Curadoria

`python scripts/curate.py` sobe uma mesa local (só em `127.0.0.1`).

- Leitura **No jogo**: as falas já entram em PT-BR, na ordem da cena, com a variante jogador/jogadora.
- Aba **Frases**: inglês e tradução lado a lado, com filtros (tom de Portugal, pausa perdida, rótulo interno, sem tradução).
- A correção grava `locale/pt-BR/unique_texts.csv`. O status (aprovada / revisar) fica em `locale/pt-BR/review.json` e não entra no patch.
- Cada gravação regenera `unique_texts_ascii.csv` via `fold_ascii_pt.export_game_csv`. Esse é o arquivo do `apply_patch_expand.py`.

## Instalação pública

Ver [install.md](install.md). Drop-in = copiar `HuniePop_Data`.

