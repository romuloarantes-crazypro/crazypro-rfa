#!/usr/bin/env python3
"""Baixa a lista OFICIAL de categorias do Perfil da Empresa no Google (pt-BR, Brasil)
e salva em static/categorias_gbp.json. O CrazyPro passa a usá-la automaticamente.

Roda no SEU computador, com o SEU login Google. Nada é enviado a terceiros e nenhuma
credencial precisa ser compartilhada com ninguém.

Preparação (uma vez):
 1. No Google Cloud Console (console.cloud.google.com), crie ou escolha um projeto.
 2. Ative a API "My Business Business Information API".
    ATENÇÃO: as APIs do Perfil da Empresa exigem aprovação do Google para o projeto
    (formulário de solicitação de acesso na documentação do Google). Sem aprovação a
    cota é zero e a chamada falha com erro 429/403.
 3. Configure a tela de consentimento OAuth e crie uma credencial do tipo
    "App para computador". Baixe o JSON e salve como client_secret.json na pasta do projeto.
    (client_secret*.json e token_gbp.json estão no .gitignore: nunca os envie ao GitHub.)
 4. pip3 install google-auth-oauthlib requests

Uso:
    python3 tools/baixar_categorias_gbp.py

Abre o navegador para você entrar com a conta que administra o Perfil. Escopo usado:
https://www.googleapis.com/auth/business.manage
"""
import json, os, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRET = os.path.join(ROOT, 'client_secret.json')
TOKEN_FILE = os.path.join(ROOT, 'token_gbp.json')
OUT_FILE = os.path.join(ROOT, 'static', 'categorias_gbp.json')
SCOPES = ['https://www.googleapis.com/auth/business.manage']
URL = 'https://mybusinessbusinessinformation.googleapis.com/v1/categories'
REGION, LANGUAGE = 'BR', 'pt-BR'


def fetch_all(get):
    """get(params) -> dict da resposta JSON. Percorre todas as páginas."""
    categorias, token = [], None
    while True:
        params = {'regionCode': REGION, 'languageCode': LANGUAGE, 'view': 'BASIC', 'pageSize': 100}
        if token: params['pageToken'] = token
        data = get(params)
        for c in data.get('categories', []):
            if c.get('name') and c.get('displayName'):
                categorias.append({'id': c['name'], 'nome': c['displayName']})
        token = data.get('nextPageToken')
        if not token: break
    return categorias


def build_output(categorias):
    return {
        'fonte': 'Google Business Profile API - Business Information v1 categories.list',
        'regionCode': REGION, 'languageCode': LANGUAGE,
        'gerado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'categorias': sorted(categorias, key=lambda c: c['nome'].casefold()),
    }


def credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES) if os.path.exists(TOKEN_FILE) else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not os.path.exists(CLIENT_SECRET):
            sys.exit('Arquivo client_secret.json não encontrado. Veja as instruções no topo deste script.')
        creds = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES).run_local_server(port=0)
    with open(TOKEN_FILE, 'w') as f: f.write(creds.to_json())
    return creds


def main():
    import requests
    creds = credentials()
    headers = {'Authorization': f'Bearer {creds.token}'}

    def get(params):
        r = requests.get(URL, params=params, headers=headers, timeout=30)
        if r.status_code != 200:
            sys.exit(f'Erro {r.status_code} da API: {r.text[:400]}\n'
                     'Se for 403/429, o projeto ainda não tem acesso aprovado às APIs do Perfil da Empresa.')
        return r.json()

    categorias = fetch_all(get)
    if not categorias: sys.exit('A API não devolveu categorias.')
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(build_output(categorias), f, ensure_ascii=False, indent=1)
    print(f'{len(categorias)} categorias salvas em {OUT_FILE}. Recarregue o CrazyPro (CMD+R).')


if __name__ == '__main__':
    main()
