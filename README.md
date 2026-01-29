# Sistema FullGas - Gerenciador de Liga F1

## Sobre o Projeto
Sistema de gerenciamento de campeonatos de F1 virtual, com controle de pilotos, equipes, pontuação, punições e estatísticas.

## Instalação Local
1. Crie um ambiente virtual: `python -m venv venv`
2. Ative o ambiente:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
3. Instale as dependências: `pip install -r requirements.txt`
   - *Nota:* Caso tenha erro de módulo faltando, execute: `pip install flask-cors flask-migrate`
4. Execute o sistema: `python run.py`

### Configuração do Git (Primeiro Push)
Se for a primeira vez subindo o projeto para o GitHub:
1. `git init`
2. `git add .`
3. `git commit -m "Initial commit"`
4. `git branch -M main`
5. `git remote add origin https://github.com/JosunoBR/Full-Gas-League.git`
6. `git push -u origin main`

### Atualizando o Banco de Dados (Migrações)
Sempre que alterar o arquivo `models.py`, você deve atualizar a estrutura do banco:
1. **Windows:** `$env:FLASK_APP = "run.py"` | **Linux:** `export FLASK_APP=run.py`
2. Garanta que está na raiz do projeto: `cd caminho/do/projeto`
3. `python -m flask db migrate -m "Descrição da mudança"`
4. `python -m flask db upgrade`

## Deploy (Hospedagem)
Este projeto está configurado para o **PythonAnywhere**.

### Passos para Produção:
1. No PythonAnywhere, use **Manual Configuration**.
2. Aponte o **WSGI file** para o objeto `app` no arquivo `run.py`.
3. Mapeie `/static/` para `app/static/` na aba Web.
4. Certifique-se de que a variável `UPLOAD_FOLDER` no `config.py` use caminhos absolutos baseados em `/home/fullgasleague/`.

### Como atualizar o site (Deploy)
1. No computador local: `git push origin main`
2. No console do PythonAnywhere:
   - `cd ~/Sistema-FullGas`
   - `git pull origin main`
3. Na aba **Web** do PythonAnywhere: Clicar em **Reload**.

### Persistência de Dados
O banco de dados SQLite (`f1_league.db`) e a pasta `app/static/uploads/` estão no `.gitignore`. 
Isso significa que:
1. Eles **não** são enviados para o GitHub (segurança e performance).
2. No primeiro deploy no PythonAnywhere, o banco será criado vazio e você deverá cadastrar os dados ou subir o arquivo `.db` manualmente via FTP/Painel de Arquivos apenas uma vez.

### Usuário Admin Inicial
O sistema cria automaticamente um usuário `Admin` (senha: `admin123`) na primeira execução se não houver nenhum cadastrado.

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

### Guia para o Próximo Programador
Para implementar funcionalidades de escrita (Check-in, Defesa, Protesto) no App:
1. Implementar autenticação via **JWT (JSON Web Token)**, pois o sistema atual utiliza sessões baseadas em Cookies/Session (Flask-Login).
2. Criar rotas de `POST` no `api.py` protegidas pelo token JWT.