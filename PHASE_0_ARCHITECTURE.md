# TA-01 — Trajectory Agent — FASE 0: ARQUITETURA

Status: proposta para aprovação. Nenhum código de produção foi escrito ainda.
Escopo: apenas arquitetura, modelos de dados, tecnologias e estratégias. Implementação começa na Fase 1, após confirmação.

---

## 1. Árvore completa de diretórios

```
trajectory/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py                 # re-exporta os módulos abaixo
│   │   │
│   │   ├── agent/
│   │   │   ├── core.py               # orquestra o ciclo perceber→deliberar→agir
│   │   │   ├── state.py              # AgentState (singleton persistente por agente)
│   │   │   ├── identity.py           # SelfModel, IdentityChange
│   │   │   ├── beliefs.py            # Belief, BeliefHistory
│   │   │   ├── preferences.py        # Preference, PreferenceHistory
│   │   │   ├── goals.py              # Goal, GoalChange
│   │   │   ├── deliberation.py       # pipeline de deliberação
│   │   │   ├── actions.py            # enum Action + handlers
│   │   │   ├── autonomy.py           # ciclo autônomo / initiative
│   │   │   └── lifecycle.py          # init, restart, sleep, shutdown
│   │   │
│   │   ├── memory/
│   │   │   ├── episodic.py           # Episode
│   │   │   ├── semantic.py           # embeddings / pgvector queries
│   │   │   ├── autobiographical.py   # AutobiographicalEvent
│   │   │   ├── retrieval.py          # recuperação híbrida
│   │   │   └── consolidation.py      # job periódico de consolidação
│   │   │
│   │   ├── relationships/
│   │   │   ├── models.py             # Person, Relationship, RelationshipEvent
│   │   │   └── manager.py
│   │   │
│   │   ├── llm/
│   │   │   ├── base.py               # class LLMProvider (interface)
│   │   │   └── providers/
│   │   │       ├── anthropic_provider.py
│   │   │       └── local_stub_provider.py   # para testes determinísticos
│   │   │
│   │   ├── autonomy/
│   │   │   ├── scheduler.py          # ticks periódicos (APScheduler)
│   │   │   ├── evaluator.py          # relevância de eventos → agir/esperar
│   │   │   └── initiative.py         # geração de comunicação espontânea
│   │   │
│   │   ├── tools/
│   │   │   ├── base.py               # class Tool
│   │   │   ├── registry.py
│   │   │   ├── permissions.py        # PermissionPolicy, sandbox defaults
│   │   │   └── builtin/              # ex.: research_tool.py (internet=false por padrão)
│   │   │
│   │   ├── audit/
│   │   │   ├── observer.py           # componente externo, somente leitura
│   │   │   └── log.py                # AuditLog append-only, hash-chained
│   │   │
│   │   ├── export/
│   │   │   ├── exporter.py
│   │   │   └── importer.py
│   │   │
│   │   └── api/
│   │       ├── chat.py
│   │       ├── memories.py
│   │       ├── identity.py
│   │       ├── relationships.py
│   │       ├── agent.py
│   │       └── audit.py
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── scenarios/                # testes #43-#50, #161-#174 da spec
│   │
│   └── alembic/                      # migrations versionadas
│
├── frontend/
│   ├── src/
│   └── package.json
│
├── ops/
│   ├── backup.sh
│   └── restore.sh
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── ARCHITECTURE_DECISIONS.md
└── README.md
```

Diferenças em relação à sugestão original de diretórios (registradas como decisões em `ARCHITECTURE_DECISIONS.md`):
- `beliefs.py`, `preferences.py`, `goals.py` foram separados de `identity.py` porque cada um tem histórico próprio (Belief­History, PreferenceHistory, GoalChange) — misturar tudo em `identity.py` violaria a separação de responsabilidades exigida pelas seções 15–17.
- `tools/` foi promovido a pasta de primeiro nível (a spec original colocava permissões dentro de `agent/`), porque a seção 187/190 exige que a verificação de permissão seja **separada** da deliberação — logo não deve morar dentro do pacote `agent`.
- `audit/` também foi promovido a pasta própria, pelo mesmo motivo (seção 12: o observador não deve fazer parte do agente).
- `alembic/` foi adicionado porque nenhuma migração foi mencionada explicitamente na spec, mas ela é obrigatória para satisfazer a seção 149 (versionamento) e a sobrevivência a atualizações (seção 7).
- `ops/` foi adicionado para a estratégia de backup (não estava na árvore original, mas é exigida implicitamente pela seção 7 e pelo Teste 172).

---

## 2. Componentes principais

| Componente | Responsabilidade | Depende de |
|---|---|---|
| **AgentState** | Estado persistente singleton (nome, autodescrição, ponteiros para crenças/preferências/objetivos atuais) | Postgres |
| **Memory** (episodic/semantic/autobiographical) | Armazenar e recuperar experiências, com origem rastreável | Postgres + pgvector |
| **SelfModel** | Identidade, crenças, preferências, valores, objetivos — visão consolidada e dinâmica | Memory |
| **Deliberation** | Pipeline determinístico que orquestra chamadas ao LLM, nunca `entrada→resposta` direto | SelfModel, Memory, Relationships, Goals, LLMProvider |
| **Autonomy** (scheduler/evaluator/initiative) | Ciclo autônomo: percebe tempo/eventos, decide agir ou `WAIT` | Deliberation |
| **Tools** | Execução de ações no mundo, com permissão verificada fora do LLM | Permissions |
| **Observer/Audit** | Log imutável e externo de tudo que acontece | Todos os componentes (somente leitura) |
| **Export/Import** | Serialização completa da trajetória, com checksum | Todos os modelos de dados |
| **API** | Interface HTTP para chat, memórias, identidade, relações, agente, auditoria | Todos acima |
| **Frontend** | Visualização humana do estado e da trajetória | API |

Fluxo (mapeado 1:1 na seção 5 da spec):
`MUNDO → Percepção → Memória → Modelo de Si → Deliberação → Ação → Nova Experiência → Memória`

---

## 3. Tecnologias escolhidas e versões

| Camada | Tecnologia | Versão | Motivo |
|---|---|---|---|
| Linguagem | Python | 3.12 | conforme spec |
| API | FastAPI | 0.115.x | conforme spec; async nativo |
| Validação | Pydantic | 2.9.x | v2 (performance, `model_config`) |
| ORM | SQLAlchemy | 2.0.x (estilo `Mapped[...]`) | async support, maduro |
| Migrations | Alembic | 1.13.x | padrão para SQLAlchemy |
| Banco relacional | PostgreSQL | 16 | conforme spec |
| Extensão vetorial | pgvector | 0.7.x | conforme spec |
| Cache / fila leve | Redis | 7.2.x | conforme spec — **apenas cache/locks/fila, nunca fonte de verdade** (decisão crítica, ver ADR-002) |
| Agendador do ciclo autônomo | APScheduler | 3.10.x (com jobstore em Postgres) | mais simples que Celery para um único agente local; interface trocável (ver ADR-003) |
| Concorrência | asyncio | stdlib | conforme spec |
| Empacotamento | Docker / Docker Compose | Docker 26+, Compose v2 | conforme spec |
| Frontend | React | 18.x | conforme spec |
| Frontend | TypeScript | 5.5.x | conforme spec |
| Testes | pytest + pytest-asyncio | pytest 8.x | testes assíncronos |
| Testes de integração | testcontainers-python | 4.x | Postgres/Redis efêmeros e reais nos testes |
| Provedor de LLM inicial | Anthropic SDK (`anthropic`) | última estável | via `LLMProvider`, trocável sem tocar no núcleo |

`LLMProvider` (seção 6 da spec) é uma interface abstrata em `llm/base.py`:

```python
class LLMProvider(Protocol):
    async def generate(self, *, system: str, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse: ...
```

Toda a lógica de deliberação depende apenas dessa interface — nunca de um SDK específico.

---

## 4. Banco de dados

- **PostgreSQL 16** é a única fonte de verdade. Toda a trajetória (seção 7 e 17 do TA-01_2) deve sobreviver fora do modelo e fora do processo — logo, fora do Redis também.
- **pgvector** roda como extensão dentro do mesmo Postgres (não um vector DB separado), para que embeddings e estado estruturado fiquem na mesma transação/consistência (ver ADR-001).
- **Redis** guarda apenas: cache de recuperação de memória recente, locks de concorrência (ex.: evitar duas deliberações simultâneas), e a fila de jobs do scheduler (job store é redundante — o estado canônico do job também é persistido no Postgres, o job store do Redis é reconstruível).

---

## 5. Modelo de memória

Tabelas principais (todas com `source_type`, `source_id`, `confidence`, `status` conforme seções 179–182 e 55-56):

**Episode** (memória episódica, seção 9/64)
```
id, timestamp, event_type, content, context, interpretation,
importance (0-1), participants[], consequences, embedding (vector),
source_type, source_id, confidence,
status: observed | reported | inferred | hypothesized | unknown
```

**AutobiographicalEvent** (seção 11/66)
```
id, episode_ids[] (origem rastreável, nunca inventado),
what_happened, when, with_whom, interpretation, consequence,
importance, created_at
```

**ConsolidationRun** (seção 12/71)
```
id, started_at, finished_at, episodes_considered[], events_created[],
self_model_updates[]
```

**Recuperação híbrida** (`memory/retrieval.py`, seção 10/69, 176–178):
```
score = w1*similaridade_semantica + w2*recencia + w3*importancia + w4*relacao_com_contexto_atual
```
Pesos são configuráveis, nunca fixos em prompt; nenhuma memória é apagada automaticamente — apenas consolidada/compressa (seção 175).

---

## 6. Modelo de identidade

**AgentState** (singleton por agente):
```
agent_id, name (nullable — pode ser "inexistente"), self_description,
created_at, updated_at, version (para optimistic locking)
```

**SelfModel** (visão dinâmica, não um prompt estático — seção 13/72):
```
identity_description, belief_ids[], preference_ids[], value_ids[],
goal_ids[], important_memory_ids[], relationship_ids[],
current_questions[], identity_change_ids[]
```

**IdentityChange** (seção 14/74):
```
id, timestamp, previous_state, trigger, new_state, explanation,
source_memory_ids[] (obrigatório, nunca vazio — ADR-007)
```

**Belief** + **BeliefHistory** (seção 15/79/80):
```
Belief: id, proposition, confidence (0-1), origin, evidence[], created_at, updated_at
BeliefHistory: belief_id, timestamp, previous_confidence, new_confidence, trigger_episode_id
```

**Preference** + **PreferenceHistory** (seção 16/77/78): mesmo padrão de `Belief`, com `subject` e `strength` em vez de `proposition`/`confidence`.

**Value**: mesmo padrão, para os "valores" citados na seção 13 mas não detalhados — tratado como um caso particular de crença de alta estabilidade (decisão registrada em ADR).

---

## 7. Modelo de relações

**Person**
```
id, external_ref (não usar "user" genérico — seção 183), display_name, created_at
```

**Relationship** (seção 18/92)
```
id, person_id, familiarity, importance, trust,
interaction_count, recurring_topics[], last_interaction_at,
shared_memory_ids[]
```

**RelationshipEvent** (histórico, seção 19/93/94)
```
id, relationship_id, timestamp, episode_id, interpretation, change_description
```

Privacidade (seção 185): toda query de memória/relação é escopada por `person_id`; não existe consulta "global" que misture relações sem autorização explícita.

---

## 8. Modelo de objetivos e deliberação

**Goal** (seção 17/82/83)
```
id, kind: system_constraint | persistent | temporary | emergent,
description, status, created_at, parent_goal_id (para objetivos derivados)
```
`system_constraint` é **imutável pelo agente** — protegido a nível de aplicação (não exposto em nenhuma action de update) e a nível de banco (linha marcada `immutable=true`, trigger de banco rejeita UPDATE).

**GoalChange**: histórico análogo a `IdentityChange`.

**Pipeline de deliberação** (`agent/deliberation.py`, seção 20/99, nunca `entrada→resposta` direto):

```
1. interpretar(entrada, contexto)
2. recuperar_memorias(interpretação)         # memory/retrieval.py
3. montar_contexto()                          # estado + objetivos + preferências + relação
4. gerar_candidatos(contexto)                  # via LLMProvider, produz lista de Action candidatas
5. avaliar_candidatos(candidatos)              # regras determinísticas + heurísticas
6. decidir(avaliação)                          # pode escolher WAIT
7. registrar_traço_de_deliberação()            # DeliberationTrace, ver seção 11 de observabilidade
8. executar_ação()
```

**DeliberationTrace** (satisfaz seção 11 do TA-01_2 — reconstruir o que aconteceu):
```
id, timestamp, input_summary, state_snapshot_ref, memories_considered[],
candidates_considered[], chosen_action, evaluation_scores, result, resulting_state_ref
```

**Action** (enum, seção 21):
```
WAIT, RESPOND, START_CONVERSATION, RESEARCH, CREATE,
REMEMBER, UPDATE_SELF, UPDATE_RELATIONSHIP
```
`WAIT` é ação de primeira classe, com sua própria taxa de sucesso nas métricas — nunca penalizada como "não-resposta" (seção 22/86).

---

## 9. Ciclo autônomo

`autonomy/scheduler.py`: tick periódico (intervalo configurável, não fixo em "enviar mensagens regularmente" — seção 10 do TA-01_2 proíbe isso explicitamente). Cada tick:

```
evento (tempo passado | novo dado externo | fim de consolidação)
   ↓
autonomy/evaluator.py → relevância
   ↓
   relevância insuficiente → Action.WAIT (registrado, não silencioso)
   relevância suficiente    → deliberação completa → possivelmente START_CONVERSATION
```

**Fila de tarefas** (seção 118/119): tabela `Task` com estados `PENDING | RUNNING | DONE | FAILED | WAITING`, com prioridade (seção 117) e orçamento computacional (seção 116, ex.: nº máximo de chamadas ao LLM por hora).

**Lifecycle** (`agent/lifecycle.py`, seção 120–124): `initialize → running ⇄ sleep(consolidação) → restart → shutdown`, todos os estados persistidos, nenhum estado "só na RAM".

---

## 10. Sistema de ferramentas

`tools/base.py`:
```python
class Tool:
    name: str
    description: str
    permissions: list[str]
    async def execute(self, **kwargs) -> ToolResult: ...
```

`tools/permissions.py` — **PermissionPolicy**, padrão restritivo (seção 187):
```
internet = false
filesystem = restricted
messaging = restricted
shell = false
```
A deliberação pode *propor* o uso de uma ferramenta, mas **o executor (fora do LLM) verifica a permissão separadamente** (seção 190) — o LLM nunca tem acesso direto a credenciais. Toda execução gera um `ToolExecutionLog` (seção 189).

Ações irreversíveis ou financeiras (seções 195–196) passam por `ConfirmationRequest`: um registro que fica `PENDING` até aprovação humana explícita via API — nunca autoexecutado.

---

## 11. Sistema de auditoria

`audit/observer.py` é um processo/módulo logicamente separado do agente — **não controla a identidade**, apenas lê e registra (seção 12 do contexto, seção 150–153 da spec).

`audit/log.py` — **AuditLog** append-only:
```
id, timestamp, event_type, payload, prev_hash, hash
```
Cada registro inclui o hash do anterior (encadeamento simples), permitindo detectar adulteração retroativa sem exigir infraestrutura de blockchain.

---

## 12. Sistema de exportação/importação

`export/exporter.py` produz um pacote versionado:
```
manifest.json { schema_version, exported_at, agent_id, tables: [...], checksum_sha256 }
+ um arquivo por tabela (JSON Lines)
```
`export/importer.py`:
1. valida `checksum_sha256`;
2. valida `schema_version` (aplica migração se necessário, seção 148/149);
3. importa em transação única — tudo ou nada;
4. permite importar sob um **novo** `agent_id` para satisfazer o Teste de Bifurcação (seção 173) sem sobrescrever o original.

---

## 13. Estratégia de testes

Pirâmide de três camadas, mapeando diretamente os testes da spec:

1. **Unit** (`tests/unit`) — componentes determinísticos: cálculo de score de recuperação, verificação de permissões, transições de estado de `Task`, imutabilidade de `system_constraint`. Não usam LLM real.
2. **Integration** (`tests/integration`, com `testcontainers`) — Postgres+pgvector e Redis reais, sobem e derrubam containers: Teste de Reinicialização (#43/#171), Teste de Exportação (#172), Teste de Bifurcação (#173).
3. **Scenario** (`tests/scenarios`) — usam um `LLMProvider` stub determinístico (respostas fixas) para testar comportamento do agente sem depender de um LLM real: Teste de Silêncio (#46), Teste de Discordância (#47/#167), Teste de Iniciativa (#45/#164), Teste de Relação (#48/#163), Teste de Identidade (#49/#168), Teste de Nome (#50).

Testes que dependem de julgamento qualitativo sobre a saída do LLM real (ex.: "a resposta é coerente?") são marcados `@pytest.mark.manual` e não bloqueiam CI — eles avaliam trajetória observável (mudança de estado no banco), não o texto gerado.

---

## 14. Estratégia de execução local

`docker-compose.yml` com serviços:
```
postgres   (imagem com pgvector já compilado, ex. pgvector/pgvector:pg16)
redis
backend    (FastAPI + scheduler no mesmo processo na Fase 1; extraível para worker separado depois)
frontend   (vite dev server)
```
`.env.example` documenta todas as variáveis (chave do provedor LLM, DSN do Postgres, URL do Redis, flags de sandbox). `alembic upgrade head` roda automaticamente na inicialização do container backend.

---

## 15. Estratégia de backup

- `pg_dump` agendado (`ops/backup.sh`), independente do mecanismo de exportação da aplicação.
- Adicionalmente, um **export completo via `export/exporter.py`** é gerado periodicamente e versionado fora do banco — porque a spec exige que a trajetória sobreviva mesmo a uma migração completa de máquina (seção 7 do TA-01_2), não apenas a um crash do Postgres.
- Redis nunca precisa de backup — é sempre reconstruível a partir do Postgres.

---

## 16. Riscos técnicos conhecidos

1. **Deriva de embeddings**: se o modelo de embedding mudar, vetores antigos e novos ficam incomparáveis. Mitigação: armazenar `embedding_model_version` por vetor e ter um job de re-embedding.
2. **Alucinação tratada como fato** (seção 179): mitigado estruturalmente pelos campos `source_type`/`confidence`/`status` obrigatórios em toda memória — nunca opcionais no schema.
3. **Crescimento ilimitado de memória**: consolidação reduz volume de contexto, mas nunca apaga dados brutos (seção 175) — implica custo de armazenamento crescente ao longo de anos; aceito como trade-off deliberado.
4. **Concorrência em `AgentState`**: múltiplos ticks do ciclo autônomo ou requisições simultâneas podem gerar condição de corrida. Mitigação: locking otimista (coluna `version`) + lock distribuído no Redis para a fase de deliberação.
5. **Custo do ciclo autônomo**: sem orçamento computacional, ticks periódicos podem gerar chamadas ilimitadas ao LLM. Mitigação: seções 115–117 implementadas desde a Fase 1 (não deixadas para depois).
6. **Troca de provedor de LLM**: mudanças de comportamento/tom ao trocar de provedor podem ser confundidas com "evolução de identidade". Mitigação: `IdentityChange` sempre exige `source_memory_ids` rastreáveis a eventos, nunca a uma troca de infraestrutura.
7. **Escopo filosófico**: risco de o próprio código (comentários, nomes de variáveis, mensagens de log) implicitamente afirmar ou negar consciência. Mitigação: revisão de linguagem em code review — nada no sistema declara conclusão sobre subjetividade (seção 14 e 133 do TA-01_2/TA-01).

---

## Próximo passo

Aguardando confirmação para iniciar a **Fase 1**, que deverá conter apenas: `AgentState`, memória episódica básica, `LLMProvider` (stub + Anthropic), e o pipeline de deliberação mínimo — sem ciclo autônomo, sem ferramentas, sem export/import (essas entram em fases posteriores), conforme a regra de implementação incremental da spec.
