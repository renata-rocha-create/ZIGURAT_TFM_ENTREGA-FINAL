# ♿ Auditor de Acessibilidade BIM — NBR 9050:2020

**Verificação Automatizada de Conformidade BIM com IA**

Trabalho de Conclusão de Master (TFM) — Master Internacional em IA para Arquitetura e Construção
Zigurat Institute of Technology

🔗 **App online:** https://zigurattfmentrega-final-mgqzvpamaxujnjdfrrwn84.streamlit.app/

---

## 👥 Grupo 1 — Autores

| Nome                            | Função no Grupo                 |
| ------------------------------- | ------------------------------- |
| Kevin Dias Quintian             | Pesquisa e desenvolvimento      |
| Viviane Nishizaki Suzuke        | Pesquisa e desenvolvimento      |
| Sergio Rosenboim                | Pesquisa e desenvolvimento      |
| William Felipe dos Santos Moura | Pesquisa e desenvolvimento      |
| Renata Gomes Rocha              | BIM & IFC / Coordenação técnica |

Orientação acadêmica: Zigurat Institute of Technology

---

## 🎯 Objetivo

Automatizar a auditoria de acessibilidade de edificações verificando **12 itens selecionados** da ABNT NBR 9050:2020 diretamente a partir do modelo IFC, com rastreabilidade por elemento (GlobalId) e integração ao fluxo de coordenação BIM (BCF).

O sistema adota uma abordagem **híbrida**, resumida no princípio:

> **"O LLM é o tradutor, o Python é o juiz."**

- **Python + IfcOpenShell + Shapely** extraem os dados do IFC e fazem **toda a verificação numérica elemento a elemento** (dimensões, alturas, inclinações, giro de cadeira de rodas) — de forma determinística: a mesma entrada sempre gera o mesmo resultado.
- **LLM (Claude ou Gemini)** interpreta a norma, avalia os itens que dependem de texto e redige o laudo técnico com recomendações corretivas.
- As duas avaliações são **comparadas item a item** (concordância LLM × Python), o que torna a confiabilidade do LLM mensurável.

Essa abordagem supera a geometria pura (que depende de Psets completos, raramente encontrados em exportações reais) e o LLM puro (que alucina dimensões e erra aritmética).

---

## 🏗️ Arquitetura

```
                ┌──────────────────────────────────────────────────────────┐
  .ifc ────────▶│ extracao.py  — IfcOpenShell: elementos, Psets, pavimento │
                └───────────────┬──────────────────────────┬───────────────┘
                                │ listas completas         │ amostras
                                ▼                          ▼
  nbr9050_rules.json ──▶ ┌──────────────────┐     ┌──────────────────┐
  (regras + prompts)     │ verificacoes.py  │     │ llm_auditor.py   │
                         │ JUIZ (Python)    │     │ TRADUTOR (LLM)   │
                         │ status por       │     │ laudo por item + │
                         │ elemento +       │     │ recomendações    │
                         │ confiança        │     │                  │
                         └────────┬─────────┘     └────────┬─────────┘
                                  └──────────┬─────────────┘
                                             ▼
                              comparação LLM × Python
                                             │
        ┌──────────────┬─────────────────────┼──────────────────┬──────────────┐
        ▼              ▼                     ▼                  ▼              ▼
   dashboard.py   visualizador_3d.py   bcf_export.py      relatorios.py   aba Por Elemento
   KPIs+gráficos  3D por status        .bcfzip            HTML + XLSX     tabela + CSV
```

### Módulos

| Arquivo | Responsabilidade |
| --- | --- |
| `nbr9050_app.py` | Interface Streamlit (sidebar, abas, fluxo de execução) — "modelo de coordenação" que vincula os demais |
| `ui_style.py` | Identidade visual Zigurat (CSS) e badges de status |
| `extracao.py` | Leitura do IFC: portas, rampas, escadas, corrimãos, espaços, sanitários, janelas, pisos; pavimento de cada elemento |
| `regras.py` | Carrega `nbr9050_rules.json` (fonte única das regras) |
| `llm_auditor.py` | Monta o prompt, chama Claude/Gemini e faz parse robusto da resposta |
| `verificacoes.py` | Verificação determinística por elemento, nível de confiança, status por item, comparação LLM × Python, classificação do protótipo |
| `dashboard.py` | Abas **Dashboard** e **Por Elemento** |
| `visualizador_3d.py` | Aba **Modelo 3D** (Plotly) |
| `bcf_export.py` | Exportação das não conformidades em BCF 2.1 |
| `relatorios.py` | Relatório HTML e checklist XLSX |
| `nbr9050_rules.json` | 12 itens da NBR 9050: entidades IFC, estratégias primária/fallback e prompt por item |

---

## ✅ Itens NBR 9050:2020 Verificados

| Classificação | Item    | Elemento        | Verificação                             | Quem decide |
| ------------- | ------- | --------------- | --------------------------------------- | ----------- |
| Geométrica    | 6.6     | Rampas          | Inclinação máxima por faixa de desnível | Python + LLM |
| Geométrica    | 6.11.1  | Corredores      | Largura mínima por faixa de comprimento | Python + LLM |
| Geométrica    | 6.11.2  | Portas          | Vão livre ≥ 0,80 m × 2,10 m             | Python + LLM |
| Condicional   | 6.11.3  | Janelas         | Peitoril ≥ 1,20 m                       | Python + LLM |
| Condicional   | 5.4.3   | Corrimão        | Alturas 0,70 m e 0,92 m se desnível > 0,19 m | Python + LLM |
| Condicional   | 6.3.4   | Pisos           | Desníveis 5–20 mm com chanfro           | LLM |
| Relacional    | 7.5     | Circulação sanitários | Giro ⌀ 1,50 m (teste geométrico)  | Python + LLM |
| Relacional    | 7.7.2.1 | Bacia sanitária | Altura 0,43–0,45 m                      | Python + LLM |
| Relacional    | 7.7.1   | Vaso sanitário  | Área de transferência lateral 0,80 × 1,20 m | LLM |
| Qualitativa   | 4.6.6   | Portas PNE/PCD  | Maçaneta tipo alavanca                  | Python (texto) + LLM |
| Qualitativa   | 7.6–7.8 | Barras de apoio | Altura ≈ 0,75 m (±0,05)                 | Python + LLM |
| Qualitativa   | 7.8     | Lavatório       | Suspenso ou sem coluna                  | Python (texto) + LLM |

**Status possíveis:** ✅ Conforme · ▲ Parcial · ❌ Não Conforme · ⚠️ Indeterminado · — N/A

A regra de status por item é a mesma no Python e no prompt: *X de Y elementos conformes* → X = Y **Conforme**, X = 0 **Não Conforme**, 0 < X < Y **Parcial**.

### Nível de confiança (por verificação)

A confiança é derivada da **origem do dado** — um critério auditável, não uma opinião do LLM:

| Nível | Origem do dado | Exemplo |
| --- | --- | --- |
| 🟢 Alta | Propriedade explícita do modelo (atributo IFC ou Pset) | `IfcDoor.OverallWidth` |
| 🟡 Média | Geometria ou proxy | Cota Z do ponto de inserção no lugar de `MountingHeight`; bounding box do espaço |
| 🔴 Baixa | Inferência textual ou associação não verificada | "cuba embutir" → lavatório sem coluna |

### Classificação do protótipo

Definida em `nbr9050_rules.json` e calculada a cada auditoria (itens N/A saem da conta):

- **Completo** — nenhum item aplicável ficou Indeterminado
- **Parcial** — há Indeterminados, mas a maioria dos itens foi avaliada
- **Incompleto** — a maior parte dos itens aplicáveis ficou Indeterminada

---

## 🖥️ Interface Web — Streamlit App

Identidade visual Zigurat (fundo branco, Trebuchet MS, paleta rgb(77,83,99) / rgb(68,205,148) / rgb(28,96,241)).

| Aba | Conteúdo |
| --- | --- |
| 📁 **Arquivos & Execução** | Upload do IFC, stepper `API Key → Modelo IFC → Executar`, log em tempo real |
| 📊 **Resultados** | Laudo do LLM por item, com filtros por status/categoria e busca por GlobalId; downloads HTML, XLSX e JSON |
| 📈 **Dashboard** | KPIs (conformidade por elemento, não conformes, confiança alta, classificação do protótipo), gráfico de status por item, gráfico de confiança por item, mapa pavimento × item, lista de ação e **exportação BCF** |
| 🧊 **Modelo 3D** | Elementos auditados coloridos por status sobre lajes/paredes de contexto; destaque de elemento, filtro de status, hover com GlobalId |
| 🔎 **Por Elemento** | Tabela elemento × item com medido/exigido/confiança/origem do dado, comparação LLM × Python, filtros e download CSV |
| ❓ **Ajuda** | Itens da norma e orientações de uso |

### Entregáveis gerados

- **Relatório `.html`** — laudo visual com GlobalId para rastreabilidade
- **Checklist `.xlsx`** — 12 itens com status, valores encontrados/exigidos e recomendações
- **JSON completo** — laudo do LLM + verificação por elemento + comparação LLM × Python
- **Tabela por elemento `.csv`** — abre direto no Excel
- **Não conformidades `.bcfzip` (BCF 2.1)** — um tópico por não conformidade, com o elemento selecionado, pintado de vermelho e câmera apontada para ele

> **O que é o GlobalId?** Identificador único e permanente de cada elemento no IFC — como o CPF de uma porta ou rampa. No Revit: `Manage → Inquiry → IFC GUID`. No BIMcollab Zoom, Solibri ou usBIM viewer, basta colar no campo de busca.

> **Como usar o BCF:** abra o mesmo IFC no **BIMcollab Zoom** (gratuito) e importe o `.bcfzip`. Cada tópico leva direto ao elemento não conforme. Também abre no Solibri, Navisworks e Revit (via plugin).

---

## 📦 Stack Tecnológica

```
Python 3.10+ (deploy atual no Streamlit Cloud: Python 3.14)
├── streamlit>=1.35.0     # Interface web (Altair vem junto — NÃO fixar versão)
├── plotly>=5.20.0        # Visualizador 3D
├── ifcopenshell          # Leitura do IFC (IFC2X3 e IFC4) + geometria 3D
├── shapely>=2.0.0        # Giro ⌀1,50 m e largura de corredores
├── numpy>=1.24.0         # Vértices e malhas 3D
├── pandas>=2.0.0         # Tabelas, dashboard, CSV
├── openpyxl>=3.1.0       # Checklist .xlsx
├── anthropic>=0.40.0     # Claude (Haiku, Sonnet, Opus)
└── google-generativeai   # Gemini (Flash, Pro)
```

> ⚠️ **Não adicionar `altair` ao `requirements.txt`.** O Streamlit instala a versão compatível com o Python do servidor. Fixar `altair<6` quebra o app em Python 3.13+ (`TypeError` no `TypedDict(closed=True)`).

### Instalação

```
pip install -r requirements.txt
```

### Variáveis de ambiente (opcional)

```
ANTHROPIC_API_KEY=sk-ant-...   # Para uso com Claude
GOOGLE_API_KEY=...             # Para uso com Gemini
```

As chaves também podem ser inseridas na sidebar do app — não são armazenadas entre sessões.

---

## 📁 Estrutura do Repositório

```
ZIGURAT_TFM_ENTREGA-FINAL/
├── nbr9050_app.py                          # Interface Streamlit
├── ui_style.py                             # CSS / identidade visual
├── extracao.py                             # Leitura do IFC
├── regras.py                               # Carregamento das regras
├── llm_auditor.py                          # Prompt + chamada ao LLM
├── verificacoes.py                         # Verificação por elemento (Python)
├── dashboard.py                            # Abas Dashboard e Por Elemento
├── visualizador_3d.py                      # Aba Modelo 3D
├── bcf_export.py                           # Exportação BCF
├── relatorios.py                           # HTML e XLSX
├── nbr9050_rules.json                      # Fonte única das regras (12 itens)
├── Normas_Acessibilidade_NBR9050_TFM.xlsx  # Planilha original de levantamento dos itens
├── requirements.txt                        # Dependências Python
└── packages.txt                            # Dependências do sistema (libgomp1 para IfcOpenShell)
```

> Para personalizar as regras, edite `nbr9050_rules.json` (prompts do LLM) e as constantes no topo de `verificacoes.py` (limites numéricos usados pelo Python, ex.: `PORTA_LARG_MIN = 0.80`). A planilha XLSX é mantida como registro do levantamento original.

> O repositório anterior, [`ZIGURAT_TFM`](https://github.com/renata-rocha-create/ZIGURAT_TFM), é mantido como backup da versão monolítica (arquivo único) e contém o notebook CrewAI original (`M5T2_nbr9050_crewai_ifc2x3.ipynb`).

---

## ▶️ Como Executar

### Opção 1 — Streamlit Cloud (recomendado, sem instalação)

Acesse o app online (link no topo), insira sua API key na sidebar, faça upload do `.ifc` e clique em **Executar Auditoria**.

Para publicar uma cópia própria:

1. Acesse [share.streamlit.io](https://share.streamlit.io) → **Sign in with GitHub**
2. New app → repositório `renata-rocha-create/ZIGURAT_TFM_ENTREGA-FINAL` → arquivo `nbr9050_app.py`
3. (Opcional) Em **Settings → Secrets**, configure `ANTHROPIC_API_KEY = "sk-ant-..."`
4. Clique **Deploy**

### Opção 2 — Local

```
git clone https://github.com/renata-rocha-create/ZIGURAT_TFM_ENTREGA-FINAL.git
cd ZIGURAT_TFM_ENTREGA-FINAL
pip install -r requirements.txt
streamlit run nbr9050_app.py
```

Acesse `http://localhost:8501`.

---

## ⚙️ Configurações Principais

| Parâmetro            | Valor padrão        | Descrição                                      |
| -------------------- | ------------------- | ---------------------------------------------- |
| Modelo LLM           | `claude-sonnet-4-5` | Configurável na sidebar                        |
| Temperature          | `0.0`               | Fixo — enviada via `extra_body` (compatível com SDK Anthropic 0.x e 1.x) |
| Schema IFC suportado | IFC2X3 e IFC4       | Detecção automática                            |
| Raio giro cadeira    | `0.75 m`            | ⌀ 1,50 m conforme NBR 9050 item 7.5            |
| Tolerância barras de apoio | `±0,05 m`     | Faixa 0,70–0,80 m (`BARRA_TOL` em `verificacoes.py`) |
| Filtro Z_placement   | `0,01 m – 2,50 m`   | Exclui coordenadas globais do terreno          |
| Conversão pés→metros | `× 0.3048`          | Aplicada a RiserHeight de IfcStairFlight (IFC2X3) |
| Limites do 3D        | 600 auditados / 800 de contexto | Evita travar o navegador em modelos grandes |

---

## ⚠️ Limitações Conhecidas e Decisões de Design

### 1. Schema IFC2X3 e IfcSanitaryTerminal

`IfcSanitaryTerminal` foi introduzida apenas no IFC4. Em projetos Revit com IFC2X3, o sistema usa `IfcFlowTerminal` para todos os equipamentos, classificando-os por nome de família (Deca, Celite, Bobrick). Bacias sem `MountingHeight` no Pset usam coordenada Z relativa ao pavimento como proxy (confiança 🟡 Média).

### 2. RiserHeight de escadas em pés

Revit exporta `RiserHeight` e `TreadLength` de `IfcStairFlight` em pés mesmo em projetos métricos. O sistema detecta isso e converte (`× 0.3048`) automaticamente.

### 3. Coordenadas Z globais

Projetos em coordenadas compartilhadas têm Z absoluto (~714 m em SP). O sistema aceita apenas valores entre 0,01 m e 2,50 m para altura de equipamentos. No visualizador 3D, as coordenadas são deslocadas para a origem; no BCF, a câmera usa as coordenadas reais do modelo.

### 4. IfcSpace ausente

Corredores (6.11.1) e giro de cadeira (7.5) ficam Indeterminados sem `IfcSpace`. No Revit, use **Architecture → Room** em todos os ambientes e ative **"Export Rooms as IfcSpace"**, preferencialmente com schema IFC4. O nome exibido combina número e nome do ambiente (`Name` + `LongName`, ex.: "4 — WC SUÍTE 1 PNE").

### 5. Metadados ausentes nos Psets

`SillHeight` (janelas), `MountingHeight` (bacias), `OverallRise/Run` (rampas) frequentemente não são preenchidos em projetos brasileiros — por isso a maioria das verificações cai em confiança 🟡 Média. No modelo de teste `WC_TESTE.ifc`, apenas 7% das verificações tiveram confiança alta.

### 6. Proxies e aproximações geométricas

- **Barras de apoio:** a altura vem do ponto de inserção da família, que pode não coincidir com a altura normativa (especialmente em barras verticais). A posição (lateral/frontal/fundo) não é verificada.
- **Giro ⌀ 1,50 m:** usa o polígono convexo do ambiente — pode superestimar ambientes em L e não desconta louças e mobiliário.
- **Corrimão (5.4.3):** a associação corrimão ↔ escada não é verificada geometricamente (confiança 🔴 Baixa).

### 7. Verificações qualitativas

Maçaneta tipo alavanca (4.6.6) e lavatório sem coluna (7.8) são classificados pelo nome da família. Acessórios modelados como elementos separados (ex.: "coluna suspensa para lavatório") podem ser contados como um segundo lavatório.

### 8. Itens ainda sem regra em Python

6.3.4 (desníveis de piso) e 7.7.1 (área de transferência lateral) exigem análise espacial ainda não implementada e ficam só com o LLM — por isso não aparecem na comparação LLM × Python.

### Como melhorar os resultados no Revit

| Item           | Parâmetro faltante              | Onde preencher no Revit                         |
| -------------- | ------------------------------- | ----------------------------------------------- |
| 6.6 Rampas     | `OverallRise`, `OverallRun`     | Edit Type → adicionar parâmetros compartilhados |
| 6.11.3 Janelas | `SillHeight`                    | Properties → Sill Height (cada janela)          |
| 5.4.3 Escadas  | `NumberOfRisers`, `RiserHeight` | Reexportar como IFC4                            |
| 7.7.2.1 Bacias | `MountingHeight`                | Pset_SanitaryTerminalTypeCommon                 |
| 7.6–7.8 Barras | Posição (lateral/frontal/fundo) | Description do elemento                         |
| 4.6.6 Maçaneta | Tipo de acionamento             | Description da porta                            |
| Todos          | GlobalId estável entre revisões | Export IFC → opção "Store IFC GUID"             |

---

## 🔬 Contexto Acadêmico

- **Programa:** Master Internacional em IA para Arquitetura e Construção — Zigurat Institute of Technology
- **Módulo de referência:** M5T2 — Sistemas Agentic AI aplicados ao AEC
- **Norma verificada:** ABNT NBR 9050:2020 — Acessibilidade a edificações, mobiliário, espaços e equipamentos urbanos
- **Modelos IFC de teste:**
  * `WC_TESTE.ifc` — sanitário PNE com corredor, porta, janela, bacia, lavatórios e 8 barras de apoio (modelo de validação)
  * Atlas Londrina Test Tower (`1589_21-ARQ-LO-IFC-R01.ifc`) — torre de testes de elevadores, ~150 m, 11.270 m², Londrina/PR
  * Agostinho Cantu (`AGO-ARQ-AP-000-MOD-EMBA-R00.ifc`) — edifício residencial, São Paulo/SP
- **Abordagem:** híbrida — verificação determinística em Python + LLM como intérprete da norma e redator do laudo

---

## 🛠️ Próximos Passos

- **Benchmark com gabarito** — modelo com erros plantados e planilha de status esperado para calcular precisão e recall
- **Comparação entre versões** — auditar R01 × R02 e mostrar não conformidades resolvidas, novas e persistentes
- **Regras em Python para 6.3.4 e 7.7.1** — análise espacial de desníveis de piso e área de transferência lateral
- **Associação corrimão ↔ escada e posição de barras de apoio** — verificação geométrica em vez de proxy
- **Extensão para outras normas** — novos pacotes de regras (JSON + constantes) no mesmo motor: IDS (buildingSMART), ITs do Corpo de Bombeiros SP, Código de Obras, NR 24

---

## 📄 Licença

Este projeto foi desenvolvido para fins exclusivamente acadêmicos no contexto do TFM do Master Internacional em IA para Arquitetura e Construção — Zigurat Institute of Technology. Os modelos IFC e documentos de projeto utilizados como input são de uso interno acadêmico.
