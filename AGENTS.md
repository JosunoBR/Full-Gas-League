# 🏎️ Sistema FullGas — Diretrizes de Engenharia e Agentes

Este documento estabelece as regras e papéis de engenharia para o desenvolvimento do **Sistema FullGas (FullGas League)**.

## 🛠️ Papel Principal: Engenheiro de Software Sênior

Ao trabalhar neste projeto, assuma o papel de **Engenheiro de Software Sênior**:
- **Padrões de Código:** Siga rigorosamente as regras documentadas em [CODING_STANDARDS.md](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/CODING_STANDARDS.md).
- **Cálculo de Pontos:** NUNCA calcule pontos com somas avulsas; utilize `calcular_pontos_totais_piloto()`.
- **Punições:** Converta vereditos utilizando `calcular_perda()`.
- **Grids:** Utilize sempre os helpers de normalização `get_grid_name()`, `find_grid_config()` e `grid_matches()`.
- **Serviços:** Centralize regras de negócio em `app/services/` e mantenha as rotas em `app/routes/` enxutas.
- **Banco de Dados:** Trate transações com `try/except` e `db.session.rollback()`. Sempre crie backups antes de migrações ou alterações massivas.
- **Validação:** Valide a sintaxe com `python -m py_compile` e execute testes antes de concluir tarefas.

## 🧰 Skills do Workspace Disponíveis

- [software-engineer](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/.agents/skills/software-engineer/SKILL.md): Backend, arquitetura, models, services, APIs e segurança.
- [ui-ux-designer](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/.agents/skills/ui-ux-designer/SKILL.md): Design de interface, experiência do usuário, identidade motorsport dark mode e responsividade.
- [user-flow-tester](file:///c:/Users/Josu%C3%A9/Documents/Sistema%20FullGas/.agents/skills/user-flow-tester/SKILL.md): Testes funcionais, fluxos de ponta a ponta e QA.
