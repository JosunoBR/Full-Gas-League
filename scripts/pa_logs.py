"""
Utilitário para consulta de logs e status no PythonAnywhere via API oficial.
Usa as credenciais definidas no arquivo .env:
  PYTHONANYWHERE_USERNAME
  PYTHONANYWHERE_TOKEN
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path


def load_env(env_path=None):
    """Lê variáveis do .env manualmente para não depender de pacotes externos."""
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / '.env'
    else:
        env_path = Path(env_path)

    env_vars = {}
    if not env_path.exists():
        return env_vars

    with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            env_vars[k] = v
            if k not in os.environ:
                os.environ[k] = v
    return env_vars


def get_api_host(username, token):
    """Testa se o host é www ou eu."""
    for host in ["www.pythonanywhere.com", "eu.pythonanywhere.com"]:
        url = f"https://{host}/api/v0/user/{username}/cpu/"
        req = urllib.request.Request(url, headers={"Authorization": f"Token {token}"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return host
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(f"[ERRO] Token inválido ou não autorizado no host {host}.", file=sys.stderr)
                return None
            continue
        except Exception:
            continue
    # Fallback padrão
    return "www.pythonanywhere.com"


def fetch_pa_api(host, endpoint, token, method='GET'):
    url = f"https://{host}{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": f"Token {token}"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            content_type = resp.headers.get('Content-Type', '')
            data = resp.read()
            if 'application/json' in content_type:
                return json.loads(data.decode('utf-8'))
            return data.decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"[ERRO API] Código {e.code} ao acessar {url}: {body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[ERRO CONEXÃO] {e}", file=sys.stderr)
        return None


def main():
    load_env()
    username = (os.environ.get('PYTHONANYWHERE_USERNAME') or '').strip()
    token = (os.environ.get('PYTHONANYWHERE_TOKEN') or '').strip()

    if not username or not token:
        print("[AVISO] Preencha PYTHONANYWHERE_USERNAME e PYTHONANYWHERE_TOKEN no arquivo .env antes de executar.")
        sys.exit(1)

    print(f"[*] Conectando ao PythonAnywhere para o usuário '{username}'...")
    host = get_api_host(username, token)
    if not host:
        sys.exit(1)

    print(f"[+] Autenticado com sucesso em {host}.")

    # 1. Busca webapps configuradas
    webapps = fetch_pa_api(host, f"/api/v0/user/{username}/webapps/", token)
    if not webapps:
        print("[!] Nenhuma aplicação web encontrada ou falha ao listar webapps.")
        sys.exit(1)

    num_lines = 100
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        num_lines = int(sys.argv[1])

    for app in webapps:
        domain = app.get('domain_name')
        error_log = app.get('error_log') or f"/var/log/{domain}.error.log"
        server_log = app.get('server_log') or f"/var/log/{domain}.server.log"
        access_log = app.get('access_log') or f"/var/log/{domain}.access.log"
        print(f"\n========================================================")
        print(f" App Web: {domain}")
        print(f" Error Log Path: {error_log}")
        print(f"========================================================")

        if error_log:
            print(f"[*] Baixando as últimas {num_lines} linhas do Error Log...")
            raw_log = fetch_pa_api(host, f"/api/v0/user/{username}/files/path{error_log}", token)
            if raw_log:
                lines = raw_log.splitlines()
                last_lines = lines[-num_lines:]
                print(f"--- [ÚLTIMAS {len(last_lines)} LINHAS DE {error_log}] ---")
                print("\n".join(last_lines))
                print(f"--- [FIM DO LOG] ---\n")
            else:
                print(f"[!] Log de erro está vazio ou não pôde ser lido.")


if __name__ == '__main__':
    main()
