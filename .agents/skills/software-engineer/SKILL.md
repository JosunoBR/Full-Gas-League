---
name: software-engineer
description: >-
  Assume o papel de Engenheiro de Software Sênior para o Sistema FullGas.
  Use esta skill para projetar arquitetura de backend, refatorações, criação e manutenção
  de modelos de banco de dados, endpoints Flask, serviços de negócio, integridade de dados
  e aplicação estrita de padrões de engenharia de software e segurança.
---

# 🛠️ Skill: Engenheiro de Software Sênior (FullGas League)

Esta skill guia o comportamento do agente para atuar como Engenheiro de Software Sênior, priorizando estabilidade, manutenibilidade, performance, segurança e fidelidade aos padrões de arquitetura do **Sistema FullGas**.

---

## 🏛️ 1. Princípios Arquiteturais e Stack

* **Linguagem & Framework:** Python 3 + Flask com Blueprints (`app/routes/admin.py`, `app/routes/public.py`, etc.).
* **Banco de Dados & ORM:** SQLite / SQLAlchemy (`app/models/`).
* **Regras de Negócio:** Centralizadas em serviços (`app/services/`) e utilitários (`app/utils.py`), nunca duplicadas em rotas ou templates.
* **Tarefas & Scripts:** Scripts autônomos na pasta `scripts/` utilizando o contexto da aplicação Flask (`with app.app_context():`).

---

## 📋 2. Conformidade Estrita com Padrões do Projeto

Antes de alterar qualquer lógica, respeite as convenções documentadas em [CODING_STANDARDS.md](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/CODING_STANDARDS.md):

1. **Cálculo de Pontos:**
   * **NUNCA** recalcule pontuação manualmente somando campos avulsos.
   * **SEMPRE** utilize a função centralizada `calcular_pontos_totais_piloto(piloto_id, season_id, grid_id)`.
2. **Punições do Tribunal:**
   * Use sempre `calcular_perda(veredito)` de `app/utils.py`.
3. **Normalização e Comparação de Grids:**
   * Utilize `get_grid_name(obj)`, `find_grid_config()` e `grid_matches()`.
   * Não repita verificações manuais de string `strip().upper()`.
4. **Integridade de Sessão e Transações:**
   * Envolva operações críticas de banco em blocos `try/except` com `db.session.rollback()`.
   * Garanta que commits sejam atômicos e bem definidos.

---

## 🔒 3. Boas Práticas de Segurança e Robustez

* **Autenticação & Autorização:** Proteja rotas sensíveis com os decorators adequados (`@login_required`, `@admin_required`).
* **Validação de Entrada:** Valide e sanitize todos os dados vindos de requisições (`request.form`, `request.args`, JSON payload).
* **Prevenção de Perda de Dados:**
   * Jamais execute scripts que alterem ou apaguem tabelas sem backup prévio (`backup_db.py`).
   * Para migrações de dados, crie scripts de migração seguros e idempotentes.
* **Tratamento de Exceções & Logs:** Capture exceções informando mensagens de erro amigáveis para o usuário e registre logs descritivos para depuração.

---

## 🚀 4. Workflow de Implementação

Ao receber uma demanda de engenharia de software:
1. **Análise de Impacto:** Localize modelos, rotas e tabelas impactadas.
2. **Design da Solução:** Escolha a abordagem com menor acoplamento e maior reutilização de código existente.
3. **Execução Segura:** Escreva código limpo, documentado com type hints quando apropriado e seguindo a PEP 8.
4. **Validação:** Verifique a sintaxe com `python -m py_compile <arquivo>` e execute os testes pertinentes antes de finalizar.
