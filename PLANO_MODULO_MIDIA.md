# 🎬 Planejamento e Especificação Técnica: Módulo Mídia & Broadcast

**Projeto:** Sistema FullGas League  
**Data:** 01/10/2026  
**Status:** Planejado / Pronto para Execução  
**Arquivo de Referência:** `PLANO_MODULO_MIDIA.md`

---

## 1. 📌 Contexto & Alinhamentos Recentes

1. **Formatação de Nomes no CSV (Concluído & Mergeado):**
   * Padrão oficial adotado: **Opção B (Abordagem 1)**: `Primeiro Nome + Inicial do Último Sobrenome` (ex: `Lucas V.`, `Marcello B.`, `João B.`).
   * Casos de borda tratados: nomes únicos (`Leandro`), nicks (`Doctor_Killer`) e tags de clã/equipe (`SMX | João Shura` $\rightarrow$ `João S.`).
   * Código sincronizado no Git (commit `fa053714`) após sanitização de credenciais de e-mail bloqueadas pela proteção do GitHub.

2. **A Ideia do Novo Módulo:**
   * Centralizar todas as ferramentas de geração de CSV e imagens (PNG 4K) em uma única tela focada: **Mídia** (`/admin/media`).
   * Evitar que narradores, produtores de GC/overlay e designers de redes sociais tenham que navegar pela tela cheia de controles de administração da temporada (`overview.html`) apenas para extrair tabelas.

---

## 2. 💡 Diagnóstico de Engenharia & Reaproveitamento de Código

Em vez de criar novos motores do zero, o sistema **já possui** toda a base pronta e homologada dentro de `overview.html`:

| Componente | Onde está hoje | Como será no Módulo Mídia |
| :--- | :--- | :--- |
| **Geração de CSV** | `app/routes/admin.py` (`export_classification`, `export_constructors`) | Reaproveitado diretamente como endpoints de download |
| **Geração de PNG** | Script inline com `html2canvas` em `overview.html` renderizando em 4K (3840px) | Extraído para um módulo JavaScript reutilizável: `static/js/media_exporter.js` |
| **Layout dos Cards** | Embutido no HTML de `app/templates/admin/overview.html` | Extraído para *partials* Jinja2 (`_card_classificacao.html`, `_card_construtores.html`) |

---

## 3. 🖥️ Especificação da Interface (UX/UI)

### Rota: `/admin/media`

```
+---------------------------------------------------------------------------------------------------+
| 🎬 Central de Mídia & Broadcast                                                                  |
+---------------------------------------------------------------------------------------------------+
| [ Temporada: Season 8 ▼ ]   [ Grid: Grid 1 ▼ ]   [ Tipo: Pilotos Titulares ▼ ]                   |
+---------------------------------------------------------------------------------------------------+
| Ações Disponíveis:                                                                                |
| [ 📥 Baixar CSV (vMix / Excel) ]        [ 🖼️ Baixar Imagem PNG (Alta Resolução 4K) ]              |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
| PREVIEW EM TEMPO REAL:                                                                            |
| +-----------------------------------------------------------------------------------------------+ |
| | 🏆 Tabela de Classificação - Grid 1 (Season 8)                                                 | |
| +-----+------------------------+-----------------+----------+--------+--------+                  | |
| | POS | PILOTO                 | EQUIPE          | VITÓRIAS | PÓDIOS | PONTOS |                  | |
| +-----+------------------------+-----------------+----------+--------+--------+                  | |
| |  1  | Lucas V.               | Red Bull        |    3     |   5    |   85   |                  | |
| |  2  | Marcello B.            | Ferrari         |    2     |   4    |   72   |                  | |
| |  3  | João B.                | McLaren         |    1     |   3    |   60   |                  | |
| +-----+------------------------+-----------------+----------+--------+--------+                  | |
| +-----------------------------------------------------------------------------------------------+ |
+---------------------------------------------------------------------------------------------------+
```

### Tipos de Consulta Suportados:
1. **Pilotos (Titulares):** Tabela principal de pilotos com classificação, vitórias, pódios e pontuação.
2. **Pilotos (Reservas):** Tabela de pilotos reservas que pontuaram no grid selecionado.
3. **Construtores / Equipes:** Pontuação acumulada por equipe no grid.
4. **Disciplina / Advertências:** Tabela disciplinar de advertências e punições da temporada.

---

## 4. 🧱 Arquitetura Técnica Proposta

### 4.1. Backend (`app/routes/admin.py`)
* **Rota Principal:**
  ```python
  @admin_bp.route('/media')
  @login_required
  def media_hub():
      # Parâmetros: season_id (int), grid_id (int), tipo (str: 'titulares', 'reservas', 'construtores', 'disciplina')
      # Coleta o contexto da temporada ativa e grids cadastrados
      # Retorna o template 'admin/media.html' com os dados prontos para exibição
  ```

### 4.2. Frontend & Componentização (DRY)
1. **`static/js/media_exporter.js`**:
   * Função genérica `exportElementToPng(elementId, filename)`
   * Responsável por configurar `html2canvas`, escala 4K (`targetWidth = 3840`), aplicar fundo escuro `#0b0d11`, tratar estado de loading do botão e disparar download via Blob/URL.
   * Utilizável tanto em `overview.html` quanto em `media.html`.
2. **Template `app/templates/admin/media.html`**:
   * Barra de filtros reativa (ao alterar os selects, atualiza a consulta).
   * Painel de botões de ação fixo.
   * Renderização do card com o design system da FullGas League.

---

## 5. 📋 Próximos Passos para a Execução

- [ ] **Etapa 1:** Criar `static/js/media_exporter.js` com a lógica unificada do `html2canvas`.
- [ ] **Etapa 2:** Modularizar os cards de tabela em templates parciais (para reaproveitar em `overview.html` e `media.html`).
- [ ] **Etapa 3:** Criar a rota `admin.media_hub` em `app/routes/admin.py` com suporte aos filtros.
- [ ] **Etapa 4:** Criar o template `app/templates/admin/media.html` com preview limpo e responsivo.
- [ ] **Etapa 5:** Adicionar o botão/link "Mídia" no menu de navegação da barra administrativa.
- [ ] **Etapa 6:** Rodar suite de testes e validar geração de CSV e PNG.
