# 📧 Guia de Configuração de DNS para Envio de E-mails (Resend)

Este documento detalha o passo a passo para autenticar o domínio **`fullgasleague.com.br`** no **Resend**, permitindo que os e-mails transacionais (convocação de corrida, lembretes de 48h, alertas de ban e notificações do tribunal) sejam disparados com reputação máxima, caindo na caixa de entrada dos pilotos sem cair no SPAM.

---

## 1. ⚙️ Como o Sistema está Configurado

O envio de e-mails é gerenciado pelo serviço `app/services/email_service.py` e integrado através da API do **Resend**.

As variáveis de ambiente ativas no arquivo [`.env`](.env) (baseadas no modelo [`.env.example`](.env.example)) são:

```env
# Chave de API gerada no painel do Resend
RESEND_API_KEY=re_sua_chave_de_api_aqui

# Remetente Oficial configurado:
MAIL_DEFAULT_SENDER=FullGas League <contato@fullgasleague.com.br>

# E-mail de resposta:
MAIL_REPLY_TO=fullgasracingf1@gmail.com

# Domínio base para links nos e-mails:
BASE_URL=https://www.fullgasleague.com.br
```

---

## 2. 🌐 Etapas de Validação no Resend

1. Acesse o painel do Resend: [https://resend.com/domains](https://resend.com/domains)
2. Clique no botão **"Add Domain"**.
3. Insira o domínio: `fullgasleague.com.br`.
4. Escolha a região: **São Paulo (South America - sa-east-1)** ou a região padrão indicada pelo Resend.
5. O Resend fornecerá uma tabela com os registros DNS que devem ser inseridos na sua zona de DNS (no **Registro.br**, **Cloudflare**, **HostGator**, etc.).

---

## 3. 📋 Entradas DNS Necessárias

No painel do seu provedor de DNS (onde o domínio `fullgasleague.com.br` está hospedado), adicione as seguintes entradas fornecidas pelo Resend:

### A. Registro DKIM (Autenticação Criptográfica)
* **Tipo:** `TXT`
* **Nome / Host:** `resend._domainkey` (ou `resend._domainkey.fullgasleague.com.br`)
* **Valor:** *(Valor exclusivo gerado na tela do seu domínio no Resend, ex: `p=MIGfMA0GCSqGSIb3DQE...`)*
* **TTL:** `Auto` ou `3600` (1 hora)

### B. Registro SPF / Return-Path (Subdomínio de Bounces)
* **Tipo:** `MX`
* **Nome / Host:** `bounces` (ou `bounces.fullgasleague.com.br`)
* **Prioridade:** `10`
* **Valor / Destino:** `feedback-smtp.us-east-1.amazonses.com` (ou o host MX indicado no seu painel Resend)

---

* **Tipo:** `TXT`
* **Nome / Host:** `bounces` (ou `bounces.fullgasleague.com.br`)
* **Valor:** `v=spf1 include:amazonses.com ~all` (ou o valor fornecido no painel do Resend)
* **TTL:** `Auto` ou `3600`

### C. Registro DMARC (Proteção contra Phishing / SPAM)
Se você ainda não tiver uma entrada DMARC criada para o seu domínio:
* **Tipo:** `TXT`
* **Nome / Host:** `_dmarc` (ou `_dmarc.fullgasleague.com.br`)
* **Valor:** `v=DMARC1; p=none; rua=mailto:fullgasracingf1@gmail.com`
* **TTL:** `Auto` ou `3600`

---

## 4. ✅ Verificação e Ativação

1. Após inserir as entradas no provedor de DNS, retorne à página do domínio no **Resend**.
2. Clique em **"Verify DNS Records"** (ou **"Verify"**).
3. A propagação de DNS costuma levar de **5 minutos a 2 horas** (no Registro.br pode levar um pouco mais).
4. Assim que o status mudar para **"Verified"** (verde):
   - Os disparos feitos pelo remetente `contato@fullgasleague.com.br` passam a ser entregues diretamente na caixa de entrada dos pilotos.
   - O painel `/admin/communication` exibirá o badge de **Resend Ativo (Disparo Real)**.

---

## 5. 🧪 Modo de Teste Temporário (Antes de Validar o DNS)

Caso precise testar disparos antes de o DNS estar validado:
- Altere temporariamente no arquivo [`.env`](.env):
  ```env
  MAIL_DEFAULT_SENDER=onboarding@resend.dev
  ```
  *(Nota: no modo `onboarding@resend.dev`, o Resend permite enviar e-mails apenas para o endereço cadastrado na sua própria conta do Resend).*
