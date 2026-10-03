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

## Resultados: camada Python (2026-10-03)

| Critério | n | VP | FP | FN | VN | Acurácia | Precisão | Recall | F1 |
|---|---|---|---|---|---|---|---|---|---|
| Estrito | 328 | 27 | 0 | 2 | 299 | 0,994 | **1,000** | 0,931 | 0,964 |
| Amplo | 330 | 30 | 0 | 1 | 299 | 0,997 | **1,000** | 0,968 | 0,984 |

- Acurácia de status exato: 0,952 com o gabarito original e 0,994 com a errata.
- **Nenhum alarme falso.** Os 4 quase-erros (porta 0,81 m, peitoril 1,21 m, rampa 8,0%, desnível 3 mm) e a base saíram Conforme.
- Recall 1,000 em 9 dos 11 itens medidos pelo Python. As exceções:

| Variante | Item | Esperado | Obtido | Causa |
|---|---|---|---|---|
| S01 | 7.7.2.1 | Não Conforme | Indeterminado | Regra de projeto: borda da bacia fora de 0,41–0,47 m vira "verificar in loco", nunca Não Conforme. É FN no critério estrito e acerto no amplo. |
| S02 | 7.6-7.8 | Parcial | Conforme | Barra de fundo a 3,2 cm da tampa (mínimo 4 cm) aceita pela tolerância de modelagem de 1 cm (`TOL_BARRA_CONF`). É FN nos dois critérios. |

Os dois falsos negativos vêm de **decisões de tolerância**, não de erros de medição. Os valores medidos (0,495 m e 0,032 m) estão corretos.

Arquivos: `resultados.csv`, `metricas.csv` (inclui as métricas por item) e `erros_auditor.csv`.

## Limitações

- **Camada LLM ainda não medida.** O comando está abaixo e precisa da chave de API.
- **Ambiente de teste.** Os resultados acima foram gerados em um ambiente com ifcopenshell 0.8.0 e sem a biblioteca shapely. Os itens 6.11.1 e 7.5 usaram um substituto mínimo dela (casco convexo e círculo). Rode de novo no computador do projeto para confirmar com as bibliotecas reais.
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
```

O passo 2 ou o passo 3 sobrescreve o `resultados.csv`. A rodada no computador do projeto é a de referência para a dissertação.
