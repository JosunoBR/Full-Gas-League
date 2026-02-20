# Sistema FullGas - Gerenciador de Liga F1

## Sobre o Projeto
Sistema de gerenciamento de campeonatos de F1 virtual, com controle de pilotos, equipes, pontuação, punições e estatísticas.
O sistema suporta múltiplos grids, temporadas, sistema de lastro invertido e cálculo automático de pontuação baseado no tamanho do grid.

## Instalação Local
1. Crie um ambiente virtual: `python -m venv venv`
2. Ative o ambiente:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
3. Instale as dependências: `pip install -r requirements.txt`
   - *Nota:* Caso tenha erro de módulo faltando, execute: `pip install flask-cors flask-migrate`
4. Execute o sistema: `python run.py`
   - O site rodará em: `http://127.0.0.1:5000`

### Acesso Externo (Ngrok)
Para testar o site em outros dispositivos ou enviar para amigos sem fazer deploy:
1. Baixe e instale o ngrok.
2. Com o site rodando, abra outro terminal e digite: `ngrok http 5000`
3. Copie o link `https://....ngrok-free.app` e envie.

## Regras de Negócio (Pontuação e Grids)
O sistema possui lógica automática para pontuação baseada no tamanho do grid configurado na Seletiva/Corrida:
- **Grid Padrão (20 Pilotos):** Pontuação de P1 (35) até P20 (1).
- **Grid Cheio (22 Pilotos):** Pontuação estendida de P1 (35) até P22 (1), com suavização do meio do pelotão.

**Lastro Invertido:**
A ordem de desempenho dos carros é fixa no código (`app/utils.py`):
Sauber (Líderes) -> Haas -> Alpine -> RB -> Williams -> Aston -> Ferrari -> Mercedes -> RBR -> McLaren (Últimos).

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

## 📱 Integração com Aplicativo Móvel (API)
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