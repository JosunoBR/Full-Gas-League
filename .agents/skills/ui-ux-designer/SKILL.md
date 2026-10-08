---
name: ui-ux-designer
description: >-
  Especialista em Experiência do Usuário (UX) e Design de Interface (UI) para o Sistema FullGas.
  Use esta skill sempre que for criar, revisar ou refatorar telas, templates HTML/Jinja2,
  folhas de estilo CSS, dashboards, tabelas de classificação, componentes de formulário,
  microinterações e responsividade mobile.
---

# 🎨 Skill: Especialista em UI / UX (FullGas League)

Esta skill guia o agente a projetar e implementar interfaces atraentes, modernas, acessíveis e focadas na melhor experiência do usuário, mantendo a identidade visual automobilística e esportiva da **FullGas League**.

---

## 🏎️ 1. Identidade Visual e Estética (Motorsport Theme)

* **Paleta de Cores & Atmosfera:**
  * Base escura elegante (dark mode premium com tons de grafite, cinza escuro e preto).
  * Cores de destaque vibrantes com inspiração automobilística: Vermelho de corrida (#E10600), amarelo bandeira (#FFD700), verde largada (#00D26A) e acentos ciano/neon para elementos interativos.
  * Badges e status com semântica visual clara: Punições (vermelho/laranja), Presença confirmada (verde), Ausente (cinza/vermelho), Sob análise (amarelo).
* **Tipografia:** Moderna e legível (ex: sans-serif esportiva como Inter, Montserrat ou Roboto), com hierarquia tipográfica evidente entre títulos, subtítulos, labels e valores numéricos.
* **Componentes Visuais:** Cards translúcidos ou com bordas sutis (glassmorphism/dark cards), cantos arredondados consistentes (`border-radius: 8px` a `12px`), sombras suaves em profundidade.

---

## 📱 2. Responsividade Mobile-First

* **Tabelas de Classificação & Grids:**
  * Em telas menores que 768px, evite que tabelas estourem a tela. Use scroll horizontal suave com indicação visual ou transformação inteligente em "Cards de Piloto".
  * Fixação da coluna de posição (`#`) ou nome do piloto caso haja rolagem horizontal de pontuações parciais.
* **Botões e Toque (Touch Targets):**
  * Áreas de clique mínimas de 44x44px em telas sensíveis ao toque.
  * Ações principais (Check-in, Salvar Resultado, Ver Classificação) sempre em destaque e fáceis de alcançar pelo polegar.

---

## ⚡ 3. Microinterações e Feedback ao Usuário

* **Estados de Ação:**
  * Todo botão deve ter estados visíveis para `:hover`, `:focus`, `:active` e `:disabled`.
  * Em submissões assíncronas ou carregamento, forneça spinners ou indicadores de "Salvando...".
* **Mensagens & Notificações (Flashes/Toasts):**
  * Notificações claras e temporizadas para sucesso, alerta e erro.
  * Formulários devem destacar campos inválidos com mensagens de erro inline descritivas ao lado do campo.

---

## 🛠️ 4. Diretrizes Técnicas de Implementação

* **Templates Jinja2:**
  * Mantenha a herança limpa estendendo `base.html` ou layouts apropriados.
  * Isole componentes reutilizáveis em `macros` ou `partials` quando houver repetição.
* **CSS Organizado:**
  * Evite estilos inline (`style="..."`). Centralize utilitários e regras nos arquivos CSS em `app/static/css/`.
  * Use variáveis CSS (`--var`) para cores de tema e espaçamentos quando aplicável.
