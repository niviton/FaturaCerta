# FaturaCerta

SaaS para integradoras de energia solar: monitoramento de usinas de vários fabricantes e auditoria da fatura da
concessionária, cruzando três fontes na janela de leitura de cada conta:

1. **Inversor** (API do fabricante): quanto a usina gerou.
2. **Medidor próprio** (ESP32 com sensores de corrente): o que entrou e saiu da rede.
3. **Concessionária** (fatura): o que foi medido e cobrado.

Região inicial: Natal-RN (Neoenergia Cosern). Outras concessionárias entram por configuração.

## Perfis

| Perfil | O que faz |
|---|---|
| Administrador geral | Vê toda a plataforma; cadastra integradoras e usuários; gerencia APIs dos inversores e dispositivos ESP; logs; "entrar como" qualquer integradora. |
| Integradora (gestor / técnico) | Carteira de clientes, cadastro completo (UC, usina, equipamentos), monitoramento, faturas e análise. |
| Cliente final | Portal com a marca da integradora: usinas, geração, conta conferida e economia. |

## Como rodar

### Local (sem Docker)

Requer Python 3.12. Sem `DATABASE_URL` usa SQLite; sem `REDIS_URL` as tarefas do Celery rodam na hora.

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Linux/macOS: .venv/bin/pip
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py seed_demo           # dados de demonstração
.venv/Scripts/python manage.py runserver
```

Acesse http://127.0.0.1:8000.

### Docker Compose

```bash
cp .env.example .env    # ajuste as variáveis
docker compose up --build
docker compose exec web python manage.py seed_demo
```

Sobe web, worker e beat do Celery, PostgreSQL e Redis.

## Usuários de demonstração

Senha de todos: `FaturaCerta@2026` (só para demonstração; troque em qualquer ambiente real).

| Usuário | Perfil |
|---|---|
| `admin` | Administrador geral |
| `gestor`, `tecnico` | Integradora Exemplo |
| `gestor2` | Sol do Seridó (outra integradora, para mostrar o isolamento) |
| `cliente` | Cliente final (Padaria Sol Nascente) |
| `lima` | Cliente final (Residência Lima) |

## Integrações: fictício × real

Toda integração tem uma interface, uma implementação fictícia (determinística) e uma real. A real só é usada
quando as credenciais estão completas; senão a tela mostra o selo "dados de demonstração".

| Integração | Situação |
|---|---|
| Inversores: Growatt, Huawei, SolarEdge, Fronius, GoodWe, Deye/Solarman | Conectores prontos (`apps/integracoes/inversores_reais.py`), ainda não validados com conta real. Preencha credenciais e ID no cadastro do inversor. |
| Medidor próprio ESP32 | API real: `POST /api/medidores/medicoes` com token por dispositivo. Firmware de exemplo em `docs/esp32/`. |
| Medidor HTTP / MQTT | Estrutura pronta, mapeamento por fabricante a ajustar. |
| Faturas | Lançamento manual. Leitor de PDF (pdfplumber + IA) e leitura do Gmail/IMAP nas próximas fases. |
| Notificações (e-mail, WhatsApp) | Fictício por padrão; `NOTIFY_EMAIL_PROVIDER=smtp` e `NOTIFY_WHATSAPP_PROVIDER=cloud` ativam os reais. |

Tarifas e percentuais regulatórios nunca são fixos no código; decisões e interpretações em
[docs/decisoes.md](docs/decisoes.md).

## Testes e lint

```bash
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check .
```

## Estrutura

```
apps/
  core/          integradora (tenant), criptografia de campos, log de auditoria, gráficos
  accounts/      usuários e perfis, equipe da integradora
  cadastro/      cliente, UC, usina, arranjos, inversor, medidor próprio, créditos
  integracoes/   interfaces + Fake + conectores reais
  monitoramento/ coleta, curva do dia, API do ESP, painel "Usinas agora"
  faturas/       fatura da concessionária
  analise/       cruzamento das três fontes e indícios
  plataforma/    painel do administrador geral
  portal/        portal do cliente final
```
