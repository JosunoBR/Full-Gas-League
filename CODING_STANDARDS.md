# 📋 PADRÕES DE CÓDIGO - SISTEMA FULLGAS

## 1. CÁLCULO DE PONTOS

### ✅ **Sempre use a função centralizada**

Ao calcular pontos de um piloto em um grid/temporada específico:

```python
from app.utils import calcular_perda
from app.routes.public import calcular_pontos_totais_piloto

# CORRETO:
pontos = calcular_pontos_totais_piloto(piloto_id=123, season_id=1, grid_id=5)

# ❌ ERRADO: Implementar cálculo manual em vários lugares
pts = sum(r.pontos_ganhos for r in resultados) - manual_penalty
```

### Função: `calcular_pontos_totais_piloto(piloto_id, season_id, grid_id)`
- **Retorna:** Float com pontos líquidos
- **Desconta:** Punições do tribunal + penalidade manual
- **Localização:** [app/routes/public.py](app/routes/public.py#L13)

---

## 2. PUNIÇÕES DO TRIBUNAL

### ✅ **Use a função centralizada de cálculo**

```python
from app.utils import calcular_perda

# Calcula pontos descontados por uma punição
pontos_perdidos = calcular_perda(veredito='MEDIA')  # Retorna 5
```

### Mapeamento de Vereditos:
- `'LEVE'` → 3 pontos descontados
- `'MEDIA'` → 5 pontos descontados  
- `'GRAVE'` → 10 pontos descontados
- Outro → 0 pontos

**Localização:** [app/utils.py](app/utils.py#L92)

---

## 3. NORMALIZAÇÃO DE GRIDS

### ✅ **Use os novos helpers de Grid**

```python
from app.utils import get_grid_name, find_grid_config, grid_matches

# Obter nome normalizado de um grid
grid_nome = get_grid_name(race_object)
# Retorna: 'F1', 'STOCK', etc (uppercase, stripped)

# Encontrar GridConfig em uma lista
all_grids = GridConfig.query.filter_by(season_id=1).all()
target_grid = find_grid_config('f1', all_grids)

# Verificar se um objeto pertence a um grid
matches = grid_matches(race_obj, grid_id=5)
matches = grid_matches(race_obj, grid_ref_config_obj)
```

### ❌ **NUNCA faça assim:**

```python
# Ruim - Repetido em 20+ lugares
r_grid = (r.race.grid_config.nome if r.race.grid_config else r.race.grid).strip().upper()

# Use grid_name() em vez disso:
r_grid = get_grid_name(r.race)
```

**Localização:** [app/utils.py](app/utils.py#L115-L180)

---

## 4. COMPARAÇÃO DE GRIDS

### ✅ **Use padrão consistente**

```python
from app.utils import get_grid_name

# Comparar grids de duas entidades
if get_grid_name(race) == get_grid_name(team):
    # São do mesmo grid
    pass

# Em loops, normalize uma vez:
race_grid = get_grid_name(race)
team_grid = get_grid_name(team)

for r in resultados:
    if get_grid_name(r.race) == target_grid:
        process(r)
```

---

## 5. BUSCA DE GRIDCONFIG

### ✅ **Use helper para busca consistente**

```python
from app.utils import find_grid_config

# Buscar um GridConfig pelo nome (case-insensitive)
all_grids = GridConfig.query.filter_by(season_id=season_id).all()
cfg = find_grid_config('F1', all_grids)

if cfg:
    # Usar cfg.id para queries
    ranking = get_ranking_by_grid(cfg.id)
```

### ❌ **NUNCA faça assim:**

```python
# Ruim - Repetido em múltiplos lugares
cfg = next((c for c in grids if c.nome.upper() == 'F1'), None)
```

---

## 6. ESTRUTURA DE ARQUIVOS - IMPORTS

### Public Routes
```python
from app.routes.public import calcular_pontos_totais_piloto, gerar_evolucao_pontos
from app.utils import calcular_perda, get_grid_name, find_grid_config, grid_matches
```

### Admin Routes
```python
from app.utils import calcular_perda, get_grid_name, find_grid_config
from app.routes.public import gerar_evolucao_pontos, calcular_pontos_totais_piloto
```

### API Routes
```python
from app.utils import calcular_perda
from app.routes.public import calcular_pontos_totais_piloto
```

---

## 7. REFATORAÇÃO RECOMENDADA (Próxima Sprint)

### Movimento de Funções (Prioridade Alta)
- [ ] Mover `gerar_evolucao_pontos()` para `utils.py`
- [ ] Mover `converter_standings_para_json()` para `utils.py`
- [ ] Mover `calcular_pontos_totais_piloto()` para `utils.py`

### Consolidação de Queries (Prioridade Média)
- [ ] Criar helper `get_pilot_results_for_grid(pilot_id, grid_id, season_id)`
- [ ] Criar helper `get_team_by_grid(team_id, grid_id, grid_name)`
- [ ] Criar helper `get_grid_config_for_season(season_id, grid_name)`

---

## 8. TESTES OBRIGATÓRIOS

Ao adicionar nova funcionalidade:

```python
# 1. Testar cálculo de pontos desconta tribunal
assert calcular_pontos_totais_piloto(piloto_id, season_id, grid_id) in [0, 100, 200]  # Valores esperados

# 2. Testar normalização de grid
r = Race.query.first()
assert get_grid_name(r).islower() == False  # Deve ser uppercase
assert get_grid_name(r).strip() == get_grid_name(r)  # Sem espaços extras

# 3. Testar busca de GridConfig
cfg = find_grid_config('f1', grids)
assert cfg.nome.upper() == 'F1' or cfg is None
```

---

## 9. CHECKLIST DE CODE REVIEW

Quando revisar PRs:

- [ ] Função `calcular_perda()` é usada para ALL punições?
- [ ] Grid names são normalizados com `get_grid_name()`?
- [ ] Não há cálculos duplicados de pontos em múltiplos lugares?
- [ ] GridConfigs são buscados com `find_grid_config()`?
- [ ] Imports incluem novos helpers de utils?
- [ ] Nenhum `.strip().upper()` aplicado diretamente sem usar helper?

---

## 10. REFERÊNCIA RÁPIDA DE FUNÇÕES

| Função | Localização | Uso |
|--------|-----------|-----|
| `calcular_perda(veredito)` | utils.py:92 | Calcular pontos de punição tribunal |
| `calcular_pontos_totais_piloto()` | public.py:13 | Pontos líquidos de piloto em grid |
| `get_grid_name(obj)` | utils.py:115 | Normalizar nome de grid |
| `find_grid_config()` | utils.py:160 | Buscar GridConfig por nome |
| `grid_matches()` | utils.py:138 | Verificar if objeto é de um grid |

---

*Documento criado após Code Audit (2025-03-02)*
*Última atualização: 2025-03-02*
