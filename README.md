# Sistema FullGas - Gerenciador de Liga F1

## Sobre o Projeto
Sistema de gerenciamento de campeonatos de F1 virtual, com controle de pilotos, equipes, pontuação, punições e estatísticas.
O sistema suporta múltiplos grids, temporadas, sistema de lastro invertido e cálculo automático de pontuação baseado no tamanho do grid.

**Contato:** [Instagram](https://www.instagram.com/fullgasleagueofficial/) | [YouTube](https://www.youtube.com/@FullGasLeagueF1Oficial) | [E-mail](mailto:fullgasracingf1@gmail.com)
**Desenvolvedor:** Josué Nogueira

## Instalação Local
1. Crie um ambiente virtual: `python -m venv venv`
2. Ative o ambiente:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
3. Instale as dependências: `pip install -r requirements.txt`
   - *Nota:* Caso tenha erro de módulo faltando, execute: `pip install flask-cors flask-migrate flask-jwt-extended firebase-admin`
4. Execute o sistema: `python run.py`
   - O site rodará em: `http://127.0.0.1:5000`

### Acesso Externo (Ngrok)
Para testar o site em outros dispositivos ou enviar para amigos sem fazer deploy:
1. Baixe e instale o ngrok.
2. Com o site rodando, abra outro terminal e digite: `ngrok http 5000`
3. Copie o link `https://....ngrok-free.app` e envie.

## Regras de Negócio (Pontuação e Grids)
### Pontuação do Campeonato
O sistema utiliza um cálculo **dinâmico** de pontuação. Os pontos salvos no banco de dados (`RaceResult`) representam o desempenho bruto na pista. As deduções são aplicadas em tempo real na visualização:
- **Pontos de Corrida:** Baseados no tamanho do grid (20 ou 22 pilotos).
- **Grid Padrão (20 Pilotos):** Pontuação de P1 (35) até P20 (1).
- **Grid Cheio (22 Pilotos):** Pontuação estendida de P1 (35) até P22 (1), com suavização do meio do pelotão.
- **Punições do Tribunal:** Subtraídas automaticamente do total do piloto no grid específico onde ocorreu o protesto (Leve: -3, Média: -5, Grave: -10).
- **Penalidades Administrativas:** Subtraídas do total global do piloto na temporada (definidas no perfil do piloto).

### Gestão de Equipes e Reservas
- **Composição**:
  - **Campeonato de Equipes**: Cada equipe suporta até **3 pilotos titulares** e **4 pilotos reservas** oficiais. As equipes usam seus próprios nomes e o desempenho dos carros é idêntico.
  - **Campeonato de Pilotos**: O formato de equipes é opcional ou secundário, focando no desempenho individual.
- **Visualização**: As tabelas de classificação separam automaticamente Titulares de Reservas. A aba de Reservas não possui limitação de vagas, permitindo listar todos os pilotos vinculados.
- **Fotos por Grid**: Pilotos podem ter fotos de perfil diferentes para cada grid que participam (ex: macacões diferentes).

### CNH (Carteira Nacional de Habilitação)
Sistema global de conduta com base de **25 pontos**:
- **Protestos**: Descontos de 3, 5 ou 10 pontos conforme o veredito.
- **Advertências**: A cada 3 advertências acumuladas, o piloto perde 3 pontos na CNH.
- **FNJ (Falta Não Justificada)**: Cada W.O. sem justificativa desconta 2 pontos automaticamente.

### Arquitetura de Grids
O sistema utiliza `GridConfig` vinculados a cada temporada. Isso permite que grids com o mesmo nome (ex: ELITE) tenham configurações de vagas e de tipo de campeonato (Campeonato de Equipes ou Campeonato de Pilotos) independentes entre temporadas.

### Lastro Invertido
Aplicado apenas em **Campeonatos de Pilotos** para equilibrar a disparidade de desempenho dos veículos. A ordem de atribuição de carros para 2026 (baseada na classificação invertida de construtores) é: Cadillac (Líderes) -> Aston Martin -> Audi -> Haas -> Alpine -> Racing Bulls -> Williams -> Red Bull -> Ferrari -> McLaren -> Mercedes (Últimos). Em **Campeonatos de Equipes**, todos correm com desempenho de carro igual, e a coluna de lastro é omitida da visualização.

## Deploy (Hospedagem)
Este projeto está configurado para o **PythonAnywhere**.

### Passos para Produção:
1. No PythonAnywhere, use **Manual Configuration**.
2. Aponte o **WSGI file** para o objeto `app` no arquivo `run.py`.
3. Mapeie `/static/` para `app/static/` na aba Web.
4. Certifique-se de que a variável `UPLOAD_FOLDER` no `config.py` use caminhos absolutos baseados em `/home/fullgasleague/`.

### Domínio Personalizado (.com.br)
Para configurar `www.fullgasleague.com.br`:
1. No PythonAnywhere (Web tab), renomeie o app para `www.fullgasleague.com.br`.
2. Copie o CNAME gerado (ex: `webapp-123.pythonanywhere.com`).
3. No registro do domínio (ex: Registro.br), crie uma entrada CNAME para `www` apontando para o endereço copiado.
4. Configure um redirecionamento web do domínio raiz (sem www) para o domínio com www.

### Atualizando o Site
1. No computador local: `git push origin main`
2. No console do PythonAnywhere:
   - `cd ~/Full-Gas-League` (ou nome da pasta)
   - `git pull origin main`
3. Na aba **Web** do PythonAnywhere: Clicar em **Reload**.

## Banco de Dados
- **Migrações:** Use `flask db migrate` e `flask db upgrade` ao alterar `models.py`.
- **Backup:** O arquivo `f1_league.db` contém todos os dados. Faça download regular dele pelo painel do PythonAnywhere.

## 🛠️ Scripts de Manutenção
Localizados na raiz, devem ser usados para auditoria e migração:
- `verificar_pontos.py`: Audita a CNH de todos os pilotos e aponta divergências.
- `corrigir_pontos.py`: Sincroniza o saldo da CNH baseado no histórico de protestos e faltas.
- `estornar_punicoes.py`: Reverte punições fixas no banco para o novo modelo de cálculo dinâmico.
- `estornar_penalidades_manuais.py`: Zera penalidades administrativas aplicadas nos perfis.
- `vincular_grids_temporadas.py`: Migra dados da arquitetura antiga (texto) para a nova (IDs).
- `migrar_fotos_grid.py`: Converte o endereçamento de fotos de grid de nomes para IDs.
- `reparar_fotos_grid.py`: Corrige vínculos de fotos baseando-se na temporada ativa.

## 📜 Padrões de Código (Bíblia)
Para manter a consistência e segurança do sistema, siga este padrão em todas as rotas de busca:

### 1. Busca de Registros com Blindagem
```python
protesto = db.session.get(Protesto, protest_id) or abort(404)
```

## � Integração com Aplicativo Móvel (API)
O sistema foi preparado para suportar um aplicativo nativo (Android/iOS) através de uma arquitetura de API REST.

### Estado Atual
- **CORS:** Habilitado no `run.py` para permitir requisições de origens externas.
- **Serialização:** Os modelos em `app/models.py` possuem o método `to_dict()` para conversão em JSON.
- **Endpoints:** Localizados em `app/routes/api.py` sob o prefixo `/api`.

### Endpoints Disponíveis (GET)
- `/api/news`: Últimas notícias do carrossel.
- `/api/standings/<grid>`: Classificação de pilotos por categoria.
- `/api/calendar/<grid>`: Calendário de corridas.
- `/api/race/<id>/results`: Súmula detalhada de uma corrida.
- `/api/pilots`: Lista de todos os pilotos ativos.
- `/api/teams`: Lista de equipes ativas.

## Estrutura de Pastas
- `app/routes`: Lógica das páginas (Admin, Público, API).
- `app/templates`: Arquivos HTML (Jinja2).
- `app/static`: CSS, JS e Imagens (Uploads).
- `app/models.py`: Tabelas do Banco de Dados.
- `app/utils.py`: Funções auxiliares e Tabelas de Pontuação.
## Servicos de Dominio
- `app/services`: regras de dominio e consultas canonicas (team context, scoring, diagnostics).

## Testes
- `python -m unittest tests/test_home_consistency.py`
- `python -m unittest tests/test_constructor_scoring.py`

## Auditoria e Migracao de Dados
- Painel administrativo: `/admin/data-health`
- Script idempotente para normalizacao de aliases de equipe:
  - Simulacao: `python scripts/normalize_team_aliases.py`
  - Aplicar: `python scripts/normalize_team_aliases.py --apply`
