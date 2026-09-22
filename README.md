# ♿ Auditor de Acessibilidade BIM — NBR 9050:2020

**Verificação Automatizada de Conformidade BIM com IA**

Trabalho de Conclusão de Master (TFM) — Master Internacional em IA para Arquitetura e Construção  
Zigurat Institute of Technology

---

## 👥 Grupo 1 — Autores

| Nome | Função no Grupo |
|---|---|
| Kevin Dias Quintian | Pesquisa e desenvolvimento |
| Viviane Nishizaki Suzuke | Pesquisa e desenvolvimento |
| Sergio Rosenboim | Pesquisa e desenvolvimento |
| William Felipe dos Santos Moura | Pesquisa e desenvolvimento |
| Renata Gomes Rocha | BIM & IFC / Coordenação técnica |

Orientação acadêmica: Zigurat Institute of Technology

---

## 🎯 Objetivo

Automatizar a auditoria de acessibilidade de edificações verificando **12 itens selecionados** da ABNT NBR 9050:2020 diretamente a partir do modelo IFC, sem necessidade de inspeção manual completa.

O sistema adota uma abordagem **híbrida LLM-cêntrica + geometria computacional**:

- **Python + IfcOpenShell** extrai e pré-processa os dados do modelo IFC — calculando desníveis de escada, testando giro de cadeira de rodas com Shapely, classificando equipamentos sanitários por nome, e filtrando coordenadas inválidas.
- **LLM (Claude ou Gemini)** atua como motor de raciocínio — interpreta a norma, analisa as evidências extraídas e redige o laudo técnico com recomendações corretivas.

Essa abordagem supera a geometria pura (que depende de Psets completos, raramente encontrados em exportações reais) e o LLM puro (que alucina dimensões), aproveitando o melhor dos dois paradigmas.

### Entregáveis gerados

- **Checklist `.xlsx`** — 12 itens com status, valores encontrados, valores exigidos e recomendações
- **Relatório `.html`** — versão visual interativa com GlobalId para rastreabilidade no Revit/BIMcollab
- **JSON bruto** — dados completos para integração com outros sistemas (BCF, Solibri, BIMcollab)

---

## 🏗️ Arquitetura: Pipeline Híbrido

```
┌─────────────────────────────────────────────────────────────────┐
│                        PIPELINE DE AUDITORIA                    │
│                                                                  │
│  .ifc ──▶ [1. Extração Python]  ──▶ [2. Análise Geométrica]    │
│                                           │                      │
│  .xlsx ──▶ [Regras NBR 9050]              ▼                     │
│  (estratégias + prompts)          [3. Resumo Estruturado]       │
│                                           │                      │
│                                           ▼                      │
│                                    [4. LLM Auditor]             │
│                                           │                      │
│                                           ▼                      │
│                               [5. Relatório + Checklist]        │
└─────────────────────────────────────────────────────────────────┘
```

### Etapa 1 — Extração (Python + IfcOpenShell)

Para cada categoria, aplica estratégia primária e fallback:

| Categoria | Estratégia primária | Fallback |
|---|---|---|
| Portas | `IfcDoor.OverallWidth/Height` | Psets (`width`, `height`) |
| Escadas | `IfcStairFlight` (RiserHeight × 0,3048 pés→m) | Psets |
| Rampas | `IfcRampFlight.OverallRise/Run` | `IfcSlab` com nome "rampa" |
| Corrimões | `IfcRailing` | `IfcBuildingElementProxy` "corrimão" |
| Sanitários | `IfcFlowTerminal` classificado por nome | `IfcBuildingElementProxy` |
| Espaços | `IfcSpace` + geometria Shapely | Paredes para estimativa |
| Janelas | `IfcWindow.SillHeight` via Psets | — |

> ⚠️ **IFC2X3 (Revit):** `RiserHeight` de escadas é exportado em **pés** — o sistema converte automaticamente (`× 0.3048`). Coordenadas Z globais de equipamentos sanitários são filtradas (aceita apenas 0,01m–2,50m para evitar cotas absolutas do terreno).

### Etapa 2 — Análise Geométrica (Shapely)

Quando `IfcSpace` está presente, o sistema executa verificação geométrica real:

```python
# Teste de giro ⌀ 1,50m — NBR 9050 item 7.5
shape = ifcopenshell.geom.create_shape(settings, space)
verts = np.array(shape.geometry.verts).reshape(-1, 3)
floor_pts = verts[np.abs(verts[:,2] - verts[:,2].min()) < 0.02]
hull = MultiPoint(floor_pts[:,:2]).convex_hull
circle = Point(hull.centroid).buffer(0.75, resolution=64)
conforme = hull.contains(circle)
```

Para corredores (item 6.11.1), calcula largura via bounding box e aplica a regra condicional por faixa de comprimento diretamente em Python — sem depender do LLM para a aritmética.

### Etapa 3 — Resumo Estruturado

Em vez de enviar JSON bruto ao LLM, o sistema gera um resumo legível por seção:

```
## BACIAS SANITÁRIAS (IfcFlowTerminal) — 30 elementos
  [2CJnZwS...] Deca_Bacia Vogue Plus P.505.17
    MountingHeight=N/D | Z_placement=0.43m | altura_estimada=0.43m

## ESCADAS — 27 IfcStair, 41 IfcStairFlight
  ⚠️ RiserHeight já convertido de pés→metros (×0.3048)
  [0juK2FV...] Escada Run 1 | Risers=16 | RiserHeight=0.18m | desnivel_m=2.88m
  Todos os 41 lances com desnível > 0,19m REQUEREM corrimão.
```

### Etapa 4 — LLM Auditor

O LLM recebe dados estruturados + instruções específicas por item (da planilha XLSX). Regras explícitas evitam erros comuns:

- Nunca retornar "Indeterminado" por não encontrar `IfcSanitaryTerminal` — modelo IFC2X3 usa `IfcFlowTerminal`
- Usar `desnivel_m` já calculado para escadas
- Reconhecer "cuba embutir" e "semiencaixe" como lavatório sem coluna → Conforme
- Coordenadas Z já filtradas — sem valores absurdos de coordenadas globais

---

## ✅ Itens NBR 9050:2020 Verificados

| Classificação | Item | Elemento | Verificação |
|---|---|---|---|
| Geométrica | 6.6 | Rampas | Inclinação máxima por faixa de desnível |
| Geométrica | 6.11.1 | Corredores | Largura mínima (Shapely + bounding box) |
| Geométrica | 6.11.2 | Portas | Vão livre ≥ 0,80m × 2,10m |
| Condicional | 6.11.3 | Janelas | Peitoril ≥ 1,20m |
| Condicional | 5.4.3 | Corrimão | Alturas 0,70m e 0,92m; bilateral |
| Condicional | 6.3.4 | Pisos | Desníveis 5–20mm com chanfro |
| Relacional | 7.5 | Circulação | Giro ⌀ 1,50m (teste geométrico real) |
| Relacional | 7.7.2.1 | Bacia sanitária | Altura 0,43–0,45m |
| Relacional | 7.7.1 | Vaso sanitário | Área livre lateral 0,80m × 1,20m |
| Qualitativa | 4.6.6 | Portas | Maçaneta tipo alavanca |
| Qualitativa | 7.6–7.8 | Barras de apoio | Posição e altura ~0,75m |
| Qualitativa | 7.8 | Lavatório | Suspenso ou sem coluna |

**Status possíveis:** ✅ Conforme · ❌ Não Conforme · ⚠️ Indeterminado · N/A

---

## 🖥️ Interface Web — Streamlit App

Interface construída com identidade visual Zigurat (fundo branco, Trebuchet MS, paleta rgb(77,83,99) / rgb(68,205,148) / rgb(28,96,241)).

### Funcionalidades

- **Stepper de fluxo** — indicador visual `① API Key → ② IFC → ③ Checklist → ④ Executar` com estados dinâmicos
- **Upload hierárquico** — card IFC (obrigatório, destaque maior) + card XLSX (opcional, discreto)
- **Configuração de LLM** — Anthropic (Claude) ou Google (Gemini), com campo de API key seguro ("não armazenada · apenas nesta sessão")
- **Seleção de modelo** — Haiku / Sonnet / Opus (Claude) ou Flash / Pro (Gemini)
- **Log em tempo real** — terminal verde com progresso da extração e chamada ao LLM
- **Aba Resultados** — tabela com filtros por status, categoria e busca por GlobalId
- **Rastreabilidade por GlobalId** — cada elemento exibe seu identificador IFC para localização direta no Revit, BIMcollab Zoom, Solibri e usBIM
- **Download em 3 formatos** — checklist `.xlsx`, relatório `.html` e JSON bruto

> **O que é o GlobalId?** Identificador único e permanente de cada elemento no IFC — como o CPF de uma porta ou rampa. Cole no campo `Manage → Inquiry → IFC GUID` do Revit para selecionar o elemento diretamente.

---

## 📦 Stack Tecnológica

```
Python 3.10+
├── streamlit>=1.32.0        # Interface web
├── ifcopenshell             # Leitura e extração de dados IFC (IFC2X3 e IFC4)
├── shapely>=2.0.0           # Análise geométrica (giro cadeira, largura corredores)
├── numpy>=1.24.0            # Processamento de vértices 3D
├── anthropic>=0.25.0        # LLM Claude (Haiku, Sonnet, Opus)
├── google-generativeai      # LLM Gemini (Flash, Pro)
├── openpyxl>=3.1.0          # Geração do checklist .xlsx
├── pandas>=2.0.0            # Leitura da planilha de normas
└── python-docx>=1.1.0       # Geração de relatórios .docx
```

### Instalação

```bash
pip install -r requirements.txt
```

### Variáveis de ambiente (opcional)

```bash
ANTHROPIC_API_KEY=sk-ant-...   # Para uso com Claude
GOOGLE_API_KEY=...             # Para uso com Gemini
```

As chaves também podem ser inseridas diretamente na sidebar do app — não são armazenadas entre sessões.

---

## 📁 Estrutura do Repositório

```
ZIGURAT_TFM/
├── nbr9050_app.py                          # App Streamlit (interface + pipeline completo)
├── requirements.txt                        # Dependências Python
├── packages.txt                            # Dependências do sistema (libgomp1 para IfcOpenShell)
├── Normas_Acessibilidade_NBR9050_TFM.xlsx  # Planilha com os 12 itens verificáveis
│                                           # (estratégias primária/fallback + prompts por item)
└── notebooks/
    └── M5T2_nbr9050_crewai_ifc2x3.ipynb   # Versão CrewAI para Google Colab
```

> A planilha XLSX é o único arquivo a editar para personalizar as regras de verificação — cada linha define entidade IFC, estratégia de busca, fallback e prompt específico para o LLM.

---

## ▶️ Como Executar

### Opção 1 — Streamlit Cloud (recomendado, sem instalação)

1. Acesse [share.streamlit.io](https://share.streamlit.io) → **Sign in with GitHub**
2. New app → repositório `renata-rocha-create/ZIGURAT_TFM` → arquivo `nbr9050_app.py`
3. Em **Settings → Secrets**, configure sua API key:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. Clique **Deploy** — o app estará disponível em URL pública em ~5 minutos

### Opção 2 — Local

```bash
git clone https://github.com/renata-rocha-create/ZIGURAT_TFM.git
cd ZIGURAT_TFM
pip install -r requirements.txt
streamlit run nbr9050_app.py
```

Acesse `http://localhost:8501`. Faça upload do `.ifc` e da planilha, insira sua API key e clique em **Executar Auditoria**.

### Opção 3 — Google Colab (versão acadêmica original)

Abra `notebooks/M5T2_nbr9050_crewai_ifc2x3.ipynb` no Colab. A execução completa leva ~9–15 minutos, incluindo pausas de rate limit entre agentes CrewAI.

---

## ⚙️ Configurações Principais

| Parâmetro | Valor padrão | Descrição |
|---|---|---|
| Modelo LLM | `claude-sonnet-4-5` | Configurável na sidebar |
| Temperature | `0.0` | Fixo — determinístico para auditoria normativa |
| Schema IFC suportado | IFC2X3 e IFC4 | Detecção automática |
| Raio giro cadeira | `0.75m` | ⌀ 1,50m conforme NBR 9050 item 7.5 |
| Filtro Z_placement | `0,01m – 2,50m` | Exclui coordenadas globais do terreno |
| Conversão pés→metros | `× 0.3048` | Aplicada a RiserHeight de IfcStairFlight |

---

## ⚠️ Limitações Conhecidas e Decisões de Design

### 1. Schema IFC2X3 e IfcSanitaryTerminal
`IfcSanitaryTerminal` foi introduzida apenas no IFC4. Em projetos Revit com IFC2X3, o sistema usa `IfcFlowTerminal` para todos os equipamentos, classificando-os por nome de família (Deca, Celite, Bobrick). Bacias sem `MountingHeight` no Pset usam coordenada Z relativa ao pavimento como proxy.

### 2. RiserHeight de escadas em pés
Revit exporta `RiserHeight` e `TreadLength` de `IfcStairFlight` em pés mesmo em projetos métricos. O sistema detecta isso e converte (`× 0.3048`) automaticamente. O campo `desnivel_m` já vem calculado para o LLM.

### 3. Coordenadas Z globais
Projetos em coordenadas compartilhadas têm Z absoluto (~714m em SP). O sistema filtra aceitando apenas valores entre 0,01m e 2,50m para altura de equipamentos, descartando a cota do terreno.

### 4. IfcSpace ausente
Corredores (6.11.1) e giro de cadeira (7.5) ficam Indeterminados sem `IfcSpace`. Para habilitar: no Revit, use **Architecture → Room** em todos os ambientes e ative **"Export Rooms as IfcSpace"** no export IFC, preferencialmente com schema IFC4.

### 5. Metadados ausentes nos Psets
`SillHeight` (janelas), `MountingHeight` (bacias), `OverallRise/Run` (rampas) frequentemente não são preenchidos em projetos brasileiros. Ver tabela de ações no Revit abaixo.

### 6. Verificações qualitativas
Maçaneta tipo alavanca (4.6.6) e posição de barras de apoio (7.6–7.8) dependem de atributos textuais raramente preenchidos. Requerem inspeção manual complementar ou enriquecimento do modelo.

### Como melhorar os resultados no Revit

| Item | Parâmetro faltante | Onde preencher no Revit |
|---|---|---|
| 6.6 Rampas | `OverallRise`, `OverallRun` | Edit Type → adicionar parâmetros compartilhados |
| 6.11.3 Janelas | `SillHeight` | Properties → Sill Height (cada janela) |
| 5.4.3 Escadas | `NumberOfRisers`, `RiserHeight` | Reexportar como IFC4 |
| 7.7.2.1 Bacias | `MountingHeight` | Pset_SanitaryTerminalTypeCommon |
| 7.6–7.8 Barras | Posição (lateral/frontal/fundo) | Description do elemento |
| 4.6.6 Maçaneta | Tipo de acionamento | Description da porta |

---

## 🔬 Contexto Acadêmico

- **Programa:** Master Internacional em IA para Arquitetura e Construção — Zigurat Institute of Technology
- **Módulo de referência:** M5T2 — Sistemas Agentic AI aplicados ao AEC
- **Norma verificada:** ABNT NBR 9050:2020 — Acessibilidade a edificações, mobiliário, espaços e equipamentos urbanos
- **Modelos IFC de teste:**
  - Atlas Londrina Test Tower (`1589_21-ARQ-LO-IFC-R01.ifc`) — torre de testes de elevadores, ~150m, 11.270 m², Londrina/PR
  - Agostinho Cantu (`AGO-ARQ-AP-000-MOD-EMBA-R00.ifc`) — edifício residencial, São Paulo/SP
- **Abordagem:** LLM-cêntrica com pré-processamento geométrico em Python

---

## 🛠️ Extensões Futuras

- **Análise geométrica 3D completa** — `ifcopenshell.geom` para rampas sem `OverallRise/Run`, chanfros (item 6.3.4) e área de transferência lateral (item 7.7.1)
- **Exportação para BCF** — envio direto de não conformidades ao Solibri, BIMcollab Zoom ou BIMcollab Cloud, usando o GlobalId já presente no relatório
- **Agente de priorização** — ordena não conformidades por criticidade e custo estimado de correção
- **Extensão para outras normas** — a planilha XLSX é o único arquivo a editar para suportar Decreto 5.296/2004, normas municipais ou requisitos LEED
- **Suporte a IFC4** — mapeamento completo de `IfcSanitaryTerminal` e `IfcStairFlight` com dados dimensionais nativos
- **Interface para BEP e Memorial Descritivo** — upload de documentos de contexto para enriquecer as recomendações do LLM

---

## 📄 Licença

Este projeto foi desenvolvido para fins exclusivamente acadêmicos no contexto do TFM do Master Internacional em IA para Arquitetura e Construção — Zigurat Institute of Technology. Os modelos IFC e documentos de projeto utilizados como input são de uso interno acadêmico.


📄 Licença
Este projeto foi desenvolvido para fins exclusivamente acadêmicos no contexto do TFM do Master Internacional em IA para Arquitetura e Construção — Zigurat Institute of Technology. Os documentos de projeto utilizados como input (BEP e Memorial Descritivo) são de uso interno acadêmico.
