# Benchmark de acurácia do Auditor NBR 9050 — injeção controlada de erros

## Método

1. **Modelo-base:** `BENCHMARK_00_3.ifc` (IFC4, Revit). Ele atende 100% aos 12 itens auditados.
2. **Variantes:** `gerar_variantes.py` cria 30 IFCs a partir da base. Cada um recebe erros conhecidos, alterados por script (ifcopenshell) sem mudar os GlobalIds:
   - 17 erros grosseiros e 4 limítrofes (logo fora do limite);
   - 4 quase-erros (logo **dentro** do limite, que devem continuar Conforme e servem para medir alarme falso);
   - 1 omissão de dado e 2 variantes com vários erros;
   - a base sem alteração;
   - 1 caso **real** do Revit: `BENCHMARK_00_2`, com o corrimão de parede reto.
3. **Pré-registro:** o `gabarito.csv` (status esperado de cada item em cada variante) foi gravado e enviado ao repositório **antes** de o auditor rodar (commit `acaa304`, 2026-10-03 17:26).
4. **Validação das variantes:** cada IFC foi reaberto e a grandeza alterada foi medida. As 30 variantes conferem com o valor planejado.
5. **Execução:** `rodar_benchmark.py` registra três camadas por par (variante × item):
   - `python`: verificação determinística;
   - `llm`: veredito do LLM;
   - `final`: o que o relatório mostra, com o Python sobrescrevendo o LLM nos itens que ele mede.
6. **Métricas:** `calcular_metricas.py` calcula, por item e no total:
   - VP, FP, FN, VN;
   - acurácia, precisão, recall e F1;
   - acurácia de status exato.

### Definições

| Termo | Definição |
|---|---|
| Unidade de análise | par variante × item NBR (30 × 12 = 360) |
| Positivo real | status esperado ≠ Conforme e ≠ N/A |
| Previsto positivo, **estrito** | Não Conforme ou Parcial. Pares cujo gabarito espera "Indeterminado" ficam fora deste critério. |
| Previsto positivo, **amplo** | Não Conforme, Parcial ou Indeterminado ("sinalizou para revisão humana") |
| Não avaliado ("—") | a camada não mede o item (o Python não mede o 7.7.1). O par fica fora da conta daquela camada. |

As métricas, em termos de alarme de incêndio:
- **Precisão:** "quando acusa, acerta?";
- **Recall:** "dos problemas reais, quantos pegou?".

### Errata do gabarito (transparência)

O gabarito anotou o status do **elemento** alterado. O relatório, porém, dá um status por **item**, agregando os elementos pela regra "X de Y". Essa regra já existia antes do benchmark: no `nbr9050_rules.json` e no `status_item_python` (commit `8fd71d5`, 15:21).

Por exemplo, uma porta de 0,75 m entre 2 portas leva o item a **Parcial**, não a "Não Conforme".

Essa diferença só foi percebida depois da primeira execução. Para não ajustar o gabarito ao resultado, foram tomadas três medidas:
- O `gabarito.csv` original **não foi alterado**.
- O `gerar_errata.py` deriva o status por item **só por regra**: elementos do item no modelo-base (Y), elementos alterados pela mutação (X) e a mesma função de agregação do auditor. Ele **não lê resultados**. As 14 linhas que ele gera são idênticas a uma errata montada à mão.
- A errata afeta **só** a acurácia de status exato, reportada com e sem ela. Precisão, recall, F1 e acurácia usam o gabarito **original**.

Uma conferência independente recalculou todas as métricas a partir dos CSVs e encontrou os mesmos valores.

## Resultados — rodada v2 (referência, 03/10/2026)

Ambiente: computador do projeto (Windows, Python 3.12, ifcopenshell 0.9.0), LLM `claude-sonnet-4-5` com temperatura 0. Os números abaixo estão em `metricas.csv` e são recalculados por fórmula em `benchmark_resultados.xlsx`.

| Camada | Critério | n | VP | FP | FN | VN | Acurácia | Precisão | Recall | F1 |
|---|---|---|---|---|---|---|---|---|---|---|
| Python | Estrito | 328 | 27 | 0 | 2 | 299 | 0,994 | **1,000** | 0,931 | 0,964 |
| Python | Amplo | 330 | 30 | 0 | 1 | 299 | 0,997 | **1,000** | 0,968 | 0,984 |
| LLM sozinho | Estrito | 358 | 26 | 64 | 3 | 265 | 0,813 | 0,289 | 0,897 | 0,437 |
| LLM sozinho | Amplo | 360 | 31 | 107 | 0 | 222 | 0,703 | 0,225 | 1,000 | 0,367 |
| **Final (relatório)** | Estrito | 358 | 27 | 1 | 2 | 328 | 0,992 | **0,964** | 0,931 | 0,947 |
| **Final (relatório)** | Amplo | 360 | 30 | 1 | 1 | 328 | 0,994 | **0,968** | 0,968 | 0,968 |

- **Acurácia de status exato** (com a errata): Python 0,994 · LLM 0,675 · final 0,992.
- **Ganho da arquitetura híbrida** ("LLM traduz, Python julga"): no critério estrito, a precisão sobe de 0,289 (LLM sozinho) para 0,964 e os alarmes falsos caem de 64 para 1.
- **Python sem nenhum alarme falso.** Os 4 quase-erros (porta 0,81 m, peitoril 1,21 m, rampa 8,0%, desnível 3 mm) e a base saíram Conforme.
- **Alarmes falsos do LLM** (critério amplo, 107) concentram-se em 4.6.6 (27), 7.7.2.1 (28), 7.6-7.8 (19), 6.3.4 (17) e 6.6 (14). Quase todos são "Indeterminado" ou "Parcial" em itens que dependem de cotas 3D ou de Psets do tipo da porta, que o texto enviado ao LLM não traz. O Python corrige todos eles na camada final.

### Erros que restam na camada final

| Variante | Item | Esperado | Obtido | Causa |
|---|---|---|---|---|
| S01 | 7.7.2.1 | Não Conforme | Indeterminado | Regra de projeto: borda da bacia fora de 0,41–0,47 m vira "verificar in loco", nunca Não Conforme. É FN no critério estrito e acerto no amplo. |
| S02 | 7.6-7.8 | Parcial | Conforme | Barra de fundo a 3,2 cm da tampa (mínimo 4 cm) aceita pela tolerância de modelagem de 1 cm (`TOL_BARRA_CONF`). É FN nos dois critérios. |
| W01 | 7.7.1 | Conforme | Não Conforme | O Python não mede o 7.7.1, então vale o LLM. A mutação reduziu o ambiente (giro ⌀1,50 m) e o LLM ligou isso à área de transferência. O caso é ambíguo. |

Os dois FN do Python vêm de **decisões de tolerância**, não de erros de medição: os valores medidos (0,495 m e 0,032 m) estão corretos.

**Sensibilidade.** Sem o par W01/7.7.1, a camada final fica com precisão 1,000 nos dois critérios (recall 0,931 estrito / 0,968 amplo).

### Repetibilidade (v1 × v2)

- **LLM:** respondeu igual em 331 de 360 pares (**91,9%**), mesmo com temperatura 0. As divergências concentram-se em 6.3.4 (12) e 6.6 (9).
- **Python:** igual em 359 de 360 pares. A única mudança (S02/7.7.2.1) é a correção do código descrita abaixo, não variação aleatória.

Arquivos: `resultados.csv`, `metricas.csv` (inclui as métricas por item), `erros_auditor.csv` e `benchmark_resultados.xlsx` (gerada por `montar_planilha.py`).

## Bug encontrado pelo próprio benchmark (rodada v1 → v2)

Na primeira rodada completa no computador do projeto (ifcopenshell 0.9.0, 03/10/2026), a variante **S02** (bacia 2 cm mais alta) saiu "Indeterminado" no item 7.7.2.1, em vez de "Parcial". Na S01 o motivo era o mesmo.

**Causa.** Quando o ponto de inserção da família (o Z do placement) era ≥ 1 cm, o auditor o usava como **altura** da bacia. Só que esse ponto fica no **piso**, então a bacia era lida como tendo 0,02 m. Isso afetaria também modelos reais com a bacia inserida acima do nível.

**Correção** (`extracao.py` e `verificacoes._v_bacias`): a altura agora segue esta prioridade:
1. propriedade `MountingHeight`;
2. topo da geometria (sólido "Body");
3. só então os demais indicadores.

Na rodada v2, a S02 sai Parcial e a S01 sai Indeterminado pela regra de tolerância.

**Registro.** Os arquivos da rodada v1 ficam em `benchmark/rodada_v1/`, como evidência do bug encontrado. Este é um resultado do próprio método: a injeção de erros revelou uma falha que os testes com o modelo-base não mostravam.

## Limitações

- **O LLM não é determinístico**, mesmo com temperatura 0 (91,9% de repetição entre as rodadas). As métricas da camada LLM variam um pouco a cada execução; as da camada final, quase nada.
- **O prompt do LLM não inclui os Psets do TIPO da porta.** Por isso o LLM sozinho marca o 4.6.6 (maçaneta) como Indeterminado; o Python lê esses Psets e corrige.
- **W01:** a mutação alterou só o contorno do ambiente. O alarme do LLM no 7.7.1 é ambíguo (ver sensibilidade).
- **Um único modelo-base**, pequeno (3 ambientes e 31 pares positivos). As métricas valem para estes tipos de erro, não para qualquer projeto.
- **Erros injetados por script não passam pela exportação do Revit.** Por isso o caso real C02 entra junto.
- Na porta, a mutação altera o atributo `OverallWidth`, que é o que o item 6.11.2 lê, mas não a geometria da folha.
- **Mutações interdependentes**, declaradas no gabarito:
  - subir a bacia aproxima a tampa da barra de fundo (S01, S02);
  - subir a barra lateral tira a referência da barra vertical (G01).

## Como reproduzir (na raiz do repositório)

```powershell
# 1. gerar as variantes (IFCs ficam em benchmark/variantes/, fora do git)
python benchmark/gerar_variantes.py --base C:\caminho\BENCHMARK_00_3.ifc --real-corrimao C:\caminho\BENCHMARK_00_2.ifc

# 2. camada Python
python benchmark/rodar_benchmark.py

# 3. (opcional) + camada LLM
$env:ANTHROPIC_API_KEY = "sua-chave"
python benchmark/rodar_benchmark.py --llm anthropic --modelo <id-do-modelo-usado-no-app>

# 4. métricas (errata é regenerada por regra antes)
python benchmark/gerar_errata.py
python benchmark/calcular_metricas.py

# 5. planilha consolidada (lê também benchmark/rodada_v1/)
python benchmark/montar_planilha.py
```

O passo 2 ou o passo 3 sobrescreve o `resultados.csv`. A rodada no computador do projeto é a de referência para a dissertação.
