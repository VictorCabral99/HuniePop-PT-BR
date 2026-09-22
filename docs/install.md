# Instalar o patch PT-BR (texto)

## Jogadores (zip da release)

1. Baixe `HuniePop_PT-BR-0.0.1.zip` na [release](https://github.com/VictorCabral99/HuniePop-PT-BR/releases).
2. Feche o jogo → Steam → Procurar arquivos locais.
3. Copie a pasta `HuniePop_Data` do zip **por cima** da pasta do jogo (substituir).
4. Detalhes: `LEIA-ME.txt` dentro do zip.

## Desenvolvedores

```bash
python scripts/apply_patch_expand.py --source assets/original/backup_... --locale locale/pt-BR/unique_texts_ascii.csv --install
python scripts/apply_ui_images.py --assets build/patch_expand/sharedassets0.assets --install
python scripts/build_dropin.py --zip
```

Se a tela ficar preta: Steam → Verificar integridade, ou restaure `assets/original/backup_*/*.assets`.
