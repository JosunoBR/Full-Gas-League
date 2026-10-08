---
name: user-flow-tester
description: >-
  Especialista em Testes de Fluxo de Usuário (User Flow Testing), QA e Validação Funcional
  Ponta a Ponta para o Sistema FullGas. Use esta skill para simular e validar jornadas completas
  de pilotos, administradores e visitantes, testar formulários, autenticação, check-in de corridas,
  cálculo de classificações e executar testes funcionais e de regressão.
---

# 🧪 Skill: Testador de Fluxo de Usuário & QA (FullGas League)

Esta skill orienta o agente na validação de qualidade, testes de usabilidade de ponta a ponta e auditoria de fluxos funcionais do **Sistema FullGas**, garantindo que as jornadas de cada tipo de usuário ocorram sem falhas.

---

## 🚦 1. Jornadas Críticas do Usuário (User Journeys)

Ao avaliar ou criar funcionalidades, valide o fluxo completo de acordo com o perfil:

### A. Jornada do Piloto
1. **Autenticação:** Login com credenciais válidas e recuperação de senha.
2. **Dashboard do Piloto:** Acesso ao painel pessoal e visualização do status da próxima corrida.
3. **Confirmação de Presença (Check-in):**
   * Confirmar presença para uma etapa aberta.
   * Marcar ausência / justificativa se aplicável.
   * Validação de bloqueio quando o prazo de check-in estiver expirado.
4. **Consulta de Posição:** Visualização de pontos líquidos (com penalidades descontadas) e posição no seu grid.
5. **Tribunal / Punições:** Verificação das advertências recebidas e status de recursos.

### B. Jornada do Administrador
1. **Controle de Acesso:** Garantir que rotas administrativas estejam protegidas contra acessos de pilotos comuns (`@admin_required`).
2. **Ciclo de Corrida:**
   * Criação de Temporada e configuração de Grids.
   * Agendamento de Corrida (data, pista, horários).
   * Verificação da lista de presenças/check-ins dos pilotos.
3. **Lançamento de Resultados:**
   * Registro de posições de chegada, pole position, volta rápida.
   * Validação de recálculo da tabela geral após salvar.
4. **Tribunal & Penalidades:**
   * Cadastro de punição com veredito (Leve, Média, Grave).
   * Verificação do desconto correto de pontos na tabela pública.
5. **Notificações:** Disparo de lembretes e e-mails de alerta sem quebras no serviço de envio (`email_service.py`).

### C. Jornada Pública / Visitante
1. **Página Inicial:** Navegação limpa e tempos de resposta rápidos.
2. **Tabela de Classificação:** Alternância entre grids de diferentes categorias sem erros 500 ou desconfiguração de layout.
3. **Calendário:** Exibição clara de etapas passadas e futuras.

---

## 🎯 2. Matriz de Casos de Borda (Edge Cases)

Sempre teste cenários que fogem do caminho feliz (happy path):
* **Dados Vazios:** Grid sem nenhuma corrida realizada, ou temporada recém-criada sem resultados.
* **Critérios de Desempate:** Dois pilotos com a mesma pontuação (verificar desempate por melhores colocações).
* **Piloto sem Equipe / Substituto:** Comportamento da pontuação de construtores/equipes.
* **Corridas Canceladas:** Exclusão da contagem na classificação geral.
* **Inputs Maliciosos ou Inválidos:** Caracteres especiais, datas invertidas, números negativos em posições.

---

## 💻 3. Como Executar e Validar os Testes

1. **Testes Automatizados do Projeto:**
   * Executar a suíte de testes: `python run_tests.py` ou `pytest tests/` no ambiente virtual ativo.
2. **Testes de Sintaxe e Imports:**
   * `python -m py_compile run.py app/routes/*.py app/models/*.py`
3. **Testes Funcionais com Test Client Flask:**
   * Utilize `app.test_client()` em scripts de teste para simular requisições HTTP (`GET`, `POST`), testar redirecionamentos (302) e códigos de status (200, 403, 404).
4. **Inspeção de Integridade no Banco:**
   * Verificar se registros associados no SQLite mantêm consistência referencial (chaves estrangeiras e integridade de temporadas/grids).
