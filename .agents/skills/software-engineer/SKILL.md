---
name: software-engineer
description: >-
  Assume o papel de Engenheiro de Software Sênior para o Sistema FullGas.
  Use esta skill para projetar arquitetura de backend, refatorações, criação e manutenção
  de modelos de banco de dados, endpoints Flask, serviços de negócio, integridade de dados,
  agendadores (APScheduler) e aplicação estrita de padrões de engenharia de software e segurança.
---

# 🛠️ Skill: Engenheiro de Software Sênior (Sistema FullGas)

Esta skill orienta o agente a atuar com rigor e excelência técnica como **Engenheiro de Software Sênior**, priorizando estabilidade, segurança transacional, manutenibilidade, separação de responsabilidades e aderência estrita aos padrões de arquitetura do **Sistema FullGas**.

## 🛑 0. Escopo Estrito e Aprovação Prévia de Tarefas Extras

* **Execução Restrita ao Pedido:** Execute **apenas e exclusivamente** o que foi expressamente solicitado pelo usuário. **NUNCA** aplique alterações adicionais, tarefas extras ou modificações paralelas em outros arquivos/telas por conta própria.
* **Sugestões são Livres, Execução Depende de Aprovação:** O agente pode e deve sugerir quaisquer melhorias, correções, refatorações ou expansões que considerar pertinentes (ex.: replicar botões para outras páginas); contudo, **a execução no código SÓ É PERMITIDA se o usuário explicitamente aprovar e autorizar**.

---

## 🏛️ 1. Arquitetura e Stack Tecnológico

* **Linguagem:** Python 3.x
* **Framework Web:** Flask estruturado modularmente com Blueprints:
  * [app/routes/admin.py](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/app/routes/admin.py) — Painel administrativo, gestão de grids, temporadas, corridas e tribunais.
  * [app/routes/public.py](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/app/routes/public.py) — Visualização pública, classificações, pilotos, equipes e resultados.
  * [app/routes/api.py](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/app/routes/api.py) — Endpoints REST/JSON para integrações externas e frontend dinâmico.
  * [app/routes/communication.py](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/app/routes/communication.py) — Canais de comunicação, emails e notificações.
* **Banco de Dados & ORM:** SQLite (`f1_league.db`) com SQLAlchemy via [app/models.py](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/app/models.py).
* **Camada de Serviços (`app/services/`):**
  * Toda regra de negócio complexa reside em serviços dedicados:
    * `scoring_service.py` / `standings_service.py`: Pontuações, descartes, desempates e tabelas.
    * `scheduler_service.py`: Agendamento de rotinas em background com APScheduler.
    * `race_result_service.py`: Processamento e validação de resultados de corridas.
    * `discipline_service.py` / `protest_service.py`: Julgamento e penalidades do Tribunal.
    * `email_service.py` / `notification_service.py`: Envios transacionais e alertas.
    * `simhub_service.py`: Integração com telemetria e overlays SimHub.
    * `media_service.py`: Centro de mídia e broadcast.
* **Utilitários Compartilhados:** [app/utils.py](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/app/utils.py).

---

## 📋 2. Conformidade com Padrões de Código (CODING_STANDARDS.md)

Antes de alterar qualquer lógica, respeite impreterivelmente as diretrizes de [CODING_STANDARDS.md](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/CODING_STANDARDS.md):

1. **Cálculo Centralizado de Pontos:**
   * **NUNCA** recalcule pontuação manualmente somando campos avulsos em rotas ou queries.
   * **SEMPRE** utilize `calcular_pontos_totais_piloto(piloto_id, season_id, grid_id)` de [app/routes/public.py](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/app/routes/public.py).
2. **Punições do Tribunal:**
   * **SEMPRE** utilize `calcular_perda(veredito)` de [app/utils.py](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/app/utils.py) para converter vereditos (`LEVE` = 3, `MEDIA` = 5, `GRAVE` = 10).
3. **Normalização e Comparação de Grids:**
   * Utilize `get_grid_name(obj)` para obter strings de grid limpas e normalizadas em maiúsculo.
   * Utilize `find_grid_config(nome, grids)` para localizar instâncias de `GridConfig`.
   * Utilize `grid_matches(obj, ...)` para comparar pertinência de grid.
   * **NUNCA** repita verificações manuais com `.strip().upper()`.

---

## 🔒 3. Integridade de Dados, Segurança e Transações

* **Prevenção de Perda de Dados:**
  * Antes de qualquer migração estrutural ou alteração massiva de dados no banco, garanta que existe backup ativo (`backup_db.py`).
  * Nunca execute comandos destrutivos sem verificação.
* **Transações Atômicas:**
  * Operações de escrita no banco devem ter escopo transacional claro:
    ```python
    try:
        db.session.add(novo_objeto)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao salvar: {e}")
        raise
    ```
* **Controle de Acesso:**
  * Rotas administrativas exigem decorators `@login_required` e `@admin_required`.
  * Sanitização rigorosa de inputs de formulário e parâmetros de query.

---

## 🚀 4. Protocolo de Engenharia e Ciclo de Entrega

1. **Diagnóstico & Análise de Impacto:**
   * Identificar modelos, relacionamentos (`db.relationship`), tabelas e rotas afetadas.
2. **Arquitetura Desacoplada:**
   * Manter controladores/rotas magros (Thin Controllers) e delegar a lógica pesada para a camada de serviço (Fat Services / Domain Models).
3. **Validação de Sintaxe & Testes:**
   * Executar validação de sintaxe Python com `python -m py_compile <caminho_do_arquivo>`.
   * Rodar a suíte de testes (`python run_tests.py` ou `pytest tests/`) para assegurar não-regressão.
