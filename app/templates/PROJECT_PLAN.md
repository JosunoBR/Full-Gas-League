# 📱 Projeto App Mobile - Full Gas League

## 🎯 Objetivo
Aplicativo Android para pilotos da liga, focado em facilidade de acesso, check-in rápido e notificações push para eventos críticos (punições e lembretes).

## 🛠️ Stack Tecnológico
- **Framework:** React Native (via Expo SDK 50+)
- **Linguagem:** JavaScript / TypeScript
- **Backend:** Flask (API existente extendida)
- **Notificações:** Firebase Cloud Messaging (FCM)
- **Distribuição:** APK direto no site (Side-loading)

---

## 📅 Etapas de Desenvolvimento

### FASE 1: Preparação do Backend (Python/Flask)
O backend precisa "falar" com o App. Precisamos transformar o site em uma API segura.

1. **Banco de Dados:**
   - Adicionar campo `fcm_token` na tabela `PilotProfile` ou `User`.
   - *Motivo:* Esse token é o identificador único do celular do piloto para enviarmos notificações (Push).

2. **Segurança (Auth):**
   - O App não usa cookies de sessão igual o navegador.
   - Implementar rota `/api/login` que retorna um **JWT (JSON Web Token)**.
   - O App guardará esse token para manter o piloto logado.

3. **Endpoints da API (JSON):**
   - `GET /api/profile`: Dados idênticos ao perfil do site (Foto, Equipe, CNH, Licença), exceto punições.
   - `GET /api/next-race`: Dados da próxima corrida para o Check-in.
   - `POST /api/checkin`: Realizar o check-in/out.

### FASE 2: Estrutura do App (Frontend)
Criação das telas no React Native.

1. **Tela de Login:**
   - Inputs: Email/Senha.
   - Ação: Bate na API, salva o Token e o Token de Notificação (FCM).

2. **Tela Home (Dashboard):**
   - **Visual de Perfil:** Foto do piloto, Equipe atual, Status da CNH (Pontos), Licença.
   - **Card de Ação:** Se houver check-in aberto, exibe o botão em destaque.
   - *Obs:* Não mostrará histórico de punições nesta versão.

### FASE 3: Sistema de Notificações (Alertas)
A parte mais importante para o engajamento.

1. **Configurar Firebase:**
   - Criar projeto no Console do Firebase (Google).
   - Baixar `google-services.json`.

2. **Gatilhos no Backend (Python):**
   - **Alerta de Protesto:** Ao ser acusado, o piloto recebe um push: "Você foi citado em um protesto. Acesse o site para defender-se".
   - **Lembrete Check-in:** Script agendado (Cron) que envia Push para todos que não fizeram check-in 24h antes da corrida.

### FASE 4: Build e Distribuição

1. **Gerar APK:**
   - Comando: `eas build -p android --profile preview`.
2. **Hospedagem:**
   - Colocar o arquivo `.apk` na pasta `app/static/downloads/`.
   - Criar link de download no rodapé do site.

---

## 📝 Checklist de Arquivos Backend Necessários

- [x] `app/models.py`: Adicionar coluna `fcm_token`.
- [x] `app/routes/api.py`: Criar rota de Login (JWT) e endpoints de perfil/check-in.
- [ ] `app/services/notification_service.py`: Serviço para enviar msg p/ Firebase.

## 📱 Checklist FASE 2 (Frontend React Native)

- [x] Inicializar projeto (`create-expo-app`)
- [x] Instalar bibliotecas essenciais (axios, navigation, secure-store)
- [x] Configurar `src/services/api.js` (Conexão com Flask)
- [x] Criar `src/context/AuthContext.js` (Gerenciamento de Login/Token)
- [x] Criar Tela de Login
- [ ] Criar Tela Home (Perfil + Check-in)

## � Como Iniciar o App (Comandos)

Dentro desta pasta `APP FGL`, executaremos:

```bash
# 1. Instalar dependências globais (se não tiver)
npm install -g eas-cli expo-cli

# 2. Criar o projeto
npx create-expo-app .
```