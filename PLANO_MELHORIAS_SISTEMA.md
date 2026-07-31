# Plano de Implantação e Evolução do Sistema FullGas

Este documento estabelece o roteiro detalhado para a implementação das melhorias arquiteturais, de desempenho e de experiência do usuário no **Sistema FullGas** (Web Flask + App Mobile React Native).

---

## 🎯 Objetivos Principais
1. **Flexibilidade de Regras**: Permitir que cada temporada/grid configure suas regras de pontuação (descartes, bonificações) via painel ADM sem alterar o código.
2. **Precisão Histórica**: Garantir 100% de consistência na pontuação dos construtores, mesmo em cenários de substituição ou troca de equipe durante o campeonato.
3. **Alta Performance**: Migrar para um sistema de cache granular em tempo real para carregamento instantâneo no App e na Web.
4. **Engajamento dos Pilotos**: Introduzir o comparador Head-to-Head e notificações push para o Tribunal de Penas.
5. **Robustez de Código**: Unificar as APIs e garantir cobertura de testes automatizados.

---

## 🗓️ Roteiro por Fases de Implantação

### 📦 FASE 1: Motor de Pontuação Centralizado (Scoring Engine)
> **Objetivo**: Unificar todas as fórmulas de pontos, descartes e penalidades em um único serviço extensível.

- [ ] **1.1. Refatoração do `ScoringService` para `ScoringEngine`**
  - Criar classe centralizadora que recebe `season_id` e `grid_id` e aplica a regra correspondente.
- [ ] **1.2. Regra de Descarte Automático (Piores Etapas)**
  - Adicionar configuração no `GridConfig` para definir a quantidade de descartes permitidos por temporada.
  - Implementar lógica de descarte dinâmico ao calcular os pontos acumulados do piloto.
- [ ] **1.3. Bonificações Dinâmicas**
  - Permitir configuração de pontos extras por Pole Position, Volta Mais Rápida e Maior Ganho de Posições (Gainer).

---

### 🏎️ FASE 2: Histórico de Vínculos de Piloto por Etapa
> **Objetivo**: Garantir que substituições e trocas de equipe no meio da temporada reflitam corretamente no campeonato de construtores.

- [ ] **2.1. Novo Modelo de Dados `PilotRaceContract`**
  - Registrar formalmente: `race_id`, `pilot_id`, `team_id`, `is_reserve`, `carro`.
- [ ] **2.2. Atualização Automática no Lançamento de Resultados**
  - Ao salvar o resultado de um GP, gravar o contrato exato do piloto naquela corrida.
- [ ] **2.3. Recálculo Histórico de Construtores**
  - Atualizar o `ScoringService.build_constructors` para computar os pontos da equipe com base no contrato da etapa.

---

### 🚀 FASE 3: API REST Unificada & Cache Granular
> **Objetivo**: Maximizar o desempenho da Home e sincronizar o App Mobile com a Web.

- [ ] **3.1. Unificação das Rotas da API (`/api/v2/`)**
  - Padronizar os retornos JSON para atender a Web e o App React Native com os mesmos endpoints.
- [ ] **3.2. Cache Granular por Grid/Season**
  - Quebrar o `HomeCache` em chaves específicas (`cache:standings:<grid_id>`, `cache:constructors:<grid_id>`).
  - Invalidação automática direcionada apenas ao grid alterado ao salvar um resultado ou protesto.
- [ ] **3.3. Endpoint de Evolução Corrigido (`/api/standings/<grid_id>/evolution`)**
  - Manter suporte ao parâmetro de temporada flexível.

---

### 📊 FASE 4: Experiência do Piloto (Head-to-Head & Notificações)
> **Objetivo**: Aumentar a interatividade e manter os pilotos engajados na plataforma.

- [ ] **4.1. Tela e Comparador Head-to-Head (Piloto vs Piloto)**
  - Criar aba/modal comparativa no App e na Web (Vitórias, Pódios, Pontos Médios, Posições de Largada).
  - Gráfico comparativo sobreposto da evolução de pontuação entre dois pilotos selecionados.
- [ ] **4.2. Central de Notificações do Tribunal (Push via FCM)**
  - Enviar notificação em tempo real quando um protesto for aberto contra o piloto.
  - Notificar o acusado e o acusador assim que o veredito final for publicado pelos comissários.

---

### 🧪 FASE 5: Suíte de Testes Automatizados (CI/CD)
> **Objetivo**: Garantir segurança total contra regressões ao fazer atualizações no sistema.

- [ ] **5.1. Testes de Integração de Fluxo Completo**
  - *Criar Etapa* ➔ *Lançar Resultados* ➔ *Processar Protestos* ➔ *Validar Tabela e CNH*.
- [ ] **5.2. Testes de Desempenho e Carga**
  - Garantir tempo de resposta da API abaixo de 100ms para requisições do App Mobile.

---

## 📌 Como iniciar a implantação
Quando o servidor sair do modo de manutenção e você quiser iniciar a execução:
1. Abra este arquivo (`PLANO_MELHORIAS_SISTEMA.md`).
2. Indique qual **Fase** você gostaria de executar primeiro (recomendado começar pela **Fase 1** ou **Fase 3**).
3. O assistente irá guiar a implementação passo a passo, executando e testando cada item de forma segura.
