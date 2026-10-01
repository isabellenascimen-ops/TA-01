<<<<<<< HEAD
# TA-01 — Trajectory Agent

Entidade computacional persistente cujo comportamento emerge de uma trajetória
armazenada, não de uma personalidade escrita à mão.

**Estado atual: Fase 1 concluída.** Ver `PHASE_0_ARCHITECTURE.md` para a
arquitetura completa e `ARCHITECTURE_DECISIONS.md` para as decisões tomadas.

---

## O que existe nesta fase

| Componente | Estado |
|---|---|
| `AgentState` (identidade mínima: sem nome, sem autodescrição) 
| Memória episódica (`Episode`) com embeddings pgvector 
| Recuperação híbrida (semântica + recência + importância)
| `LLMProvider` — interface + stub determinístico + Anthropic
| `EmbeddingProvider` — interface + local determinístico + Voyage
| Pipeline de deliberação em 8 estágios + `DeliberationTrace`
| Ações `WAIT` / `RESPOND` / `REMEMBER`
| API HTTP (`/agent`, `/chat`)
| Migrations Alembic

**Deliberadamente ausente nesta fase** (entra nas fases seguintes): ciclo
autônomo, comunicação espontânea, ferramentas e permissões, modelo de
relações, crenças/preferências/objetivos, consolidação de memória,
auditoria com hash encadeado, exportação/importação, frontend.

O enum `Action` já contém as 8 ações da especificação (é contrato, mudá-lo
depois exigiria migrar dados), mas `PHASE_AVAILABLE_ACTIONS` limita quais
têm handler real. Escolher uma ação sem handler levanta
`ActionNotAvailableInPhaseError` — nunca falha em silêncio.

---

## Executar com Docker (recomendado)

```bash
cp .env.example .env
docker compose up --build
```

A API sobe em `http://localhost:8000` (docs interativas em `/docs`).
As migrations rodam automaticamente antes do servidor.

## Executar localmente sem Docker

Requer PostgreSQL 16 com a extensão `pgvector`.

```bash
# banco
sudo apt-get install -y postgresql postgresql-16-pgvector
sudo service postgresql start
sudo -u postgres psql -c "CREATE USER trajectory WITH PASSWORD 'trajectory_dev_pw' SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE trajectory_dev OWNER trajectory;"
sudo -u postgres psql -c "CREATE DATABASE trajectory_test OWNER trajectory;"
sudo -u postgres psql -d trajectory_dev  -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -d trajectory_test -c "CREATE EXTENSION IF NOT EXISTS vector;"

# aplicação
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Testes

```bash
cd backend
pytest -v          # 26 testes, contra Postgres real (banco trajectory_test)
```

Os testes usam o `LocalStubProvider` determinístico — não fazem chamadas a
nenhum LLM real, não custam nada e não dependem de rede (ADR-012).

---

## Experimentar pela API

```bash
# criar um agente (nasce sem nome e sem autodescrição)
AGENT=$(curl -s -X POST http://localhost:8000/agent | python3 -c "import sys,json;print(json.load(sys.stdin)['agent_id'])")

# conversar
curl -X POST "http://localhost:8000/chat/$AGENT/message" \
  -H "Content-Type: application/json" -d '{"text":"Olá, quem é você?"}'

# pedido explícito de memória → ação REMEMBER
curl -X POST "http://localhost:8000/chat/$AGENT/message" \
  -H "Content-Type: application/json" -d '{"text":"lembre-se que eu moro em Jaraguá do Sul"}'

# entrada vazia → ação WAIT (esperar é um resultado válido, não uma falha)
curl -X POST "http://localhost:8000/chat/$AGENT/message" \
  -H "Content-Type: application/json" -d '{"text":"   "}'
```

Para inspecionar a trajetória registrada:

```sql
SELECT event_type, content, importance FROM episode ORDER BY timestamp;
SELECT input_summary, chosen_action, evaluation_scores FROM deliberation_trace ORDER BY timestamp;
```

---

## Usar um LLM real

No `.env`:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

Nenhuma outra mudança é necessária: `app/llm/providers/anthropic_provider.py`
é o único arquivo do projeto que importa o SDK da Anthropic (seção 6 da spec —
o modelo pode ser substituído sem destruir a trajetória do agente).

O mesmo vale para embeddings, que têm um provedor **separado** do LLM: a
Anthropic não oferece API de embeddings, então acoplar os dois criaria uma
dependência que a spec proíbe.
=======
# TA-01
>>>>>>> 2be1f82592404a842cbbd77536f91be1fc1b4217
