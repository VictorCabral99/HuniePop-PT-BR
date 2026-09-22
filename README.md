# HuniePop PT-BR

Tradução **não oficial** (feita por fãs) do jogo **HuniePop** (Steam) para **português do Brasil**.

- Traduz: textos da interface, menus, tutoriais e diálogos  
- **Não** traduz: voz / áudio (continua em inglês)  
- Você **precisa ter o jogo comprado** na Steam — este projeto só troca os arquivos de texto

> Versão atual: **alfa 0.0.1** (ainda em revisão — pode ter frases estranhas ou incompletas)

---

## Como baixar e instalar (passo a passo)

### 1. Baixe o patch

1. Abra a página da release:  
   **[v0.0.1 — Download](https://github.com/VictorCabral99/HuniePop-PT-BR/releases/tag/v0.0.1)**
2. Em **Assets**, baixe o arquivo:  
   `HuniePop_PT-BR-0.0.1.zip`  
   (~330 MB)
3. Extraia o zip em qualquer pasta (botão direito → Extrair tudo…).  
   Você deve ver algo assim:

```
HuniePop_PT-BR/
  LEIA-ME.txt
  VERSION
  HuniePop_Data/
    resources.assets
    sharedassets0.assets
```

### 2. Feche o jogo

Se o HuniePop estiver aberto, feche completamente.

### 3. Abra a pasta do jogo na Steam

1. Abra a **Steam**
2. Na biblioteca, clique com o **botão direito** em **HuniePop**
3. Vá em **Gerenciar** → **Procurar arquivos locais**

Vai abrir a pasta do jogo. O caminho costuma ser parecido com:

`C:\Program Files (x86)\Steam\steamapps\common\HuniePop`

Lá dentro existe uma pasta chamada **`HuniePop_Data`**.

### 4. (Recomendado) Faça um backup rápido

Dentro de `HuniePop_Data`, copie estes dois arquivos para outro lugar (ex.: área de trabalho → pasta `backup-huniepop`):

- `resources.assets`
- `sharedassets0.assets`

Assim você consegue voltar ao inglês sem precisar da Steam.

### 5. Cole o patch

1. Abra a pasta que você extraiu do zip (`HuniePop_PT-BR`)
2. **Copie** a pasta `HuniePop_Data` que está **dentro do zip**
3. **Cole** na pasta do jogo (a mesma que a Steam abriu), **em cima** da `HuniePop_Data` que já existe
4. Quando o Windows perguntar se deseja **substituir os arquivos**, confirme que **sim**

Pronto. Abra o HuniePop pela Steam — os textos devem aparecer em português.

---

## Problemas comuns

| O que aconteceu | O que fazer |
|-----------------|-------------|
| Tela preta / não abre | Steam → botão direito no HuniePop → **Propriedades** → **Arquivos instalados** → **Verificar integridade dos arquivos do jogo**. Depois instale o patch de novo (passos 3–5). |
| Continua em inglês | Você colou no lugar errado. A pasta `HuniePop_Data` do zip precisa ir **dentro** da pasta do HuniePop da Steam, substituindo os `.assets`. |
| Quero voltar ao inglês | Devolva o backup dos dois `.assets`, **ou** use “Verificar integridade” na Steam. |
| Antivírus bloqueou | Libere a pasta do jogo / o zip; são só arquivos de dados do Unity, sem executável novo. |

---

## O que esperar nesta alfa

- Menus e boa parte dos diálogos em PT-BR  
- Tom ainda está sendo melhorado (às vezes soa “traduzido no Google”)  
- Áudio das personagens permanece em inglês  
- Não é um patch oficial da desenvolvedora

Achou erro de português ou crash? Abra uma [Issue](https://github.com/VictorCabral99/HuniePop-PT-BR/issues) descrevendo **onde** no jogo apareceu.

---

## Aviso legal

Fan patch **não oficial**. Não redistribuímos o jogo completo — só os arquivos de texto/UI já patchados. Use apenas se você possui o HuniePop na Steam.

---

## Para quem for traduzir / desenvolver

Veja o guia técnico em [`docs/install.md`](docs/install.md) e o tom desejado em [`docs/tom-pt-br.md`](docs/tom-pt-br.md).

Resumo rápido:

```bash
python -m pip install -r requirements.txt
# editar locale/pt-BR/unique_texts_ascii.csv
python scripts/apply_patch_expand.py --install
python scripts/apply_ui_images.py --assets build/patch_expand/sharedassets0.assets --install
python scripts/build_dropin.py --zip
```
