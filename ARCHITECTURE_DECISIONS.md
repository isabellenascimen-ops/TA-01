# ARCHITECTURE_DECISIONS.md — TA-01

Cada decisão segue o formato: contexto → decisão → alternativas consideradas → consequência.
Regra geral aplicada em toda ambiguidade da spec: escolher a solução tecnicamente mais simples que preserve a intenção original, e registrar aqui.

---

### ADR-001 — pgvector dentro do Postgres, não um vector DB separado
**Contexto**: a spec pede embeddings + pgvector, mas não é explícita sobre isolar isso em outro serviço.
**Decisão**: manter embeddings na mesma instância Postgres que o resto do estado.
**Alternativas**: Qdrant/Weaviate separado — mais escalável, mas quebra a transação única entre "salvar episódio" e "salvar embedding", arriscando inconsistência.
**Consequência**: menor throughput em escala muito grande, mas consistência transacional garantida — prioridade dada pela spec à integridade da trajetória sobre performance.

---

### ADR-002 — Redis é cache/fila, nunca fonte de verdade
**Contexto**: seção 7 do TA-01_2 exige que a trajetória sobreviva a reinicialização, crash, migração de máquina.
**Decisão**: nenhum dado que não possa ser reconstruído a partir do Postgres pode viver exclusivamente no Redis.
**Alternativas**: usar Redis também para armazenar estado de curto prazo do agente — mais rápido, mas violaria diretamente a seção 7.
**Consequência**: todo acesso ao Redis precisa ser tratado como opcional/best-effort no código.

---

### ADR-003 — APScheduler em vez de Celery para o ciclo autônomo (Fase inicial)
**Contexto**: a spec não define a tecnologia do ciclo autônomo, apenas o comportamento (seção 26/85).
**Decisão**: usar APScheduler com jobstore persistido, mantendo o scheduler no mesmo processo do backend na Fase 1.
**Alternativas**: Celery+Redis (mais robusto para múltiplos workers) ou Temporal (mais robusto para workflows de longa duração, mas adiciona um serviço inteiro).
**Consequência**: mais simples de operar localmente; a interface do ciclo autônomo (`autonomy/scheduler.py`) é isolada o suficiente para trocar por Celery/Temporal depois, sem alterar `evaluator.py`/`initiative.py`.

---

### ADR-004 — `LLMProvider` como Protocol, primeira implementação via Anthropic SDK
**Contexto**: seção 6 exige que o agente não fique acoplado a um fornecedor.
**Decisão**: interface `Protocol` tipada em `llm/base.py`; implementação concreta inicial usa o SDK da Anthropic; um `local_stub_provider.py` determinístico existe desde a Fase 1 para testes.
**Consequência**: testes de comportamento do agente não dependem de um LLM real nem de custo de API.

---

### ADR-005 — Deliberação como pipeline de estágios explícitos, nunca um único prompt
**Contexto**: seção 20/99 proíbe `entrada → resposta` direto.
**Decisão**: cada estágio (interpretar, recuperar, montar contexto, gerar candidatos, avaliar, decidir, registrar, executar) é uma função/módulo separado, testável isoladamente, com um `DeliberationTrace` obrigatório por execução.
**Alternativas**: delegar tudo a um único prompt "megaprompt" que já devolve a decisão final — mais simples de implementar, mas inviabiliza observabilidade (seção 11 do TA-01_2) e testes determinísticos.
**Consequência**: mais código de orquestração, mas testabilidade e auditabilidade completas.

---

### ADR-006 — Crenças/preferências/valores com tabela de histórico dedicada
**Contexto**: seções 15/16/79/80 exigem que crenças e preferências tenham trajetória, não apenas um valor atual.
**Decisão**: cada entidade (`Belief`, `Preference`, `Value`) tem uma tabela `*History` correspondente; a linha "atual" nunca é sobrescrita sem gravar a transição.
**Consequência**: mais tabelas, mas nenhuma mudança de identidade é destrutiva — satisfaz diretamente a seção 14/74 (reconstruir como mudou).

---

### ADR-007 — Toda mutação de identidade exige `source_memory_ids` não vazio
**Contexto**: seção 12 do TA-01_2 ("não inventar acontecimentos"); seção 54 ("princípio de não-fabricação").
**Decisão**: a nível de schema, `IdentityChange.source_memory_ids` e `GoalChange.source_memory_ids` são colunas `NOT NULL` com `CHECK (array_length(source_memory_ids, 1) > 0)`.
**Consequência**: é estruturalmente impossível o sistema registrar uma mudança de identidade "do nada" — a restrição está no banco, não apenas em código de aplicação (mais difícil de contornar por engano).

---

### ADR-008 — Enum de status epistêmico obrigatório em toda memória
**Contexto**: seções 55/56/179–182.
**Decisão**: toda linha de `Episode` e `Belief` carrega `status: observed | reported | inferred | hypothesized | unknown`, sem valor default além de `unknown` explícito — nunca inferido silenciosamente como `observed`.
**Consequência**: consultas de recuperação podem filtrar/ponderar por confiabilidade epistêmica.

---

### ADR-009 — Formato de exportação: manifest JSON + JSON Lines por tabela + checksum SHA-256
**Contexto**: seções 35/36/145–149.
**Decisão**: pacote legível por humanos (JSON), não binário proprietário, com `schema_version` para permitir migração na importação.
**Alternativas**: dump binário do Postgres (`pg_dump` custom format) — mais compacto, mas opaco e difícil de versionar/migrar entre schemas diferentes.
**Consequência**: exportação é maior em disco, mas auditável e portável entre versões do schema.

---

### ADR-010 — Verificação de permissão de ferramenta acontece no executor, nunca no LLM
**Contexto**: seção 190 é explícita: "o LLM nunca deverá possuir acesso direto às credenciais."
**Decisão**: `Tool.execute()` só é chamado depois que `tools/permissions.py` valida a `PermissionPolicy` vigente; o LLM apenas propõe `ToolCall`, que é um DTO sem nenhuma credencial embutida.
**Consequência**: mesmo que a deliberação "decida" usar uma ferramenta proibida, a execução é bloqueada e registrada como tentativa negada — nunca executada por confiança na saída do modelo.

---

### ADR-011 — Log de auditoria append-only com encadeamento de hash
**Contexto**: seção 151 ("log imutável").
**Decisão**: cada linha de `AuditLog` armazena `hash(prev_hash + payload)`; não há operação de `UPDATE`/`DELETE` exposta para essa tabela (revogada a nível de permissão de banco para o usuário da aplicação).
**Alternativas**: WORM storage externo (ex.: S3 Object Lock) — mais forte, mas desproporcional para a Fase 0/1 de um agente local.
**Consequência**: tamper-evidence suficiente para o estágio atual do projeto; pode evoluir para armazenamento WORM externo sem mudar o schema lógico.

---

### ADR-012 — Testes divididos em unit / integration / scenario, nunca dependentes de julgamento sobre texto do LLM real
**Contexto**: seções 42–50 e 161–174 descrevem testes comportamentais, mas um LLM real é não-determinístico.
**Decisão**: testes de CI usam um `local_stub_provider` determinístico; testes que precisam de um LLM real são marcados `manual` e avaliam apenas mudança de estado observável no banco (ex.: "uma preferência foi registrada com histórico", não "a resposta pareceu genuína").
**Consequência**: CI é 100% determinístico e reprodutível; avaliação qualitativa fica separada, como processo humano periódico (alinhado à seção 53, experimento longitudinal).

---

## Decisões acrescentadas durante a implementação da Fase 1

### ADR-013 — `EmbeddingProvider` é uma interface separada de `LLMProvider`
**Contexto**: a spec pede pgvector, mas nunca diz de onde vêm os vetores. Descoberto na implementação: a Anthropic não oferece API de embeddings.
**Decisão**: criar `app/memory/embeddings.py` com uma interface própria, independente de `LLMProvider`. Implementações: `LocalHashEmbeddingProvider` (determinístico, sem rede) e `VoyageEmbeddingProvider` (real).
**Consequência**: o fornecedor de LLM e o de embeddings podem ser trocados independentemente — aplicação do princípio da seção 6 a um segundo eixo que a spec não havia previsto.

### ADR-014 — Enum `Action` completo desde a Fase 1, com `PHASE_AVAILABLE_ACTIONS` limitando a execução
**Contexto**: a regra de implementação incremental diz para criar só o necessário, mas o enum de ações é um contrato persistido em banco.
**Decisão**: definir as 8 ações da seção 21 desde já (evita migração de dados depois), e controlar o que é executável via `PHASE_AVAILABLE_ACTIONS`. Escolher uma ação sem handler levanta `ActionNotAvailableInPhaseError`.
**Consequência**: o agente nunca "finge" executar algo sem suporte; a fronteira entre contrato e implementação fica explícita e testada.

### ADR-015 — Pedido explícito de memorização é detectado por regra determinística, não pelo prompt
**Contexto**: bug encontrado em teste — com `REMEMBER=0.65` e `RESPOND=0.75`, o agente respondia em vez de guardar o que o interlocutor pediu explicitamente para guardar.
**Decisão**: `has_explicit_memory_request()` vive em código (`deliberation.py`), e eleva `REMEMBER` para 0.85 quando há pedido explícito. O LLM propõe a ação; quem confirma o pedido é o avaliador determinístico.
**Consequência**: aplicação direta da seção 15 ("evitar esconder toda a lógica dentro de prompts") — a regra é inspecionável, versionada e coberta por testes de regressão.

### ADR-016 — Testes de integração rodam contra Postgres real, não SQLite nem mocks
**Contexto**: parte do que precisa ser validado é o schema em si (pgvector, enums nativos, JSONB, foreign keys) — nada disso existe igual em SQLite.
**Decisão**: banco `trajectory_test` real; cada teste roda dentro de uma transação com `join_transaction_mode="create_savepoint"` e sofre rollback ao final. O engine tem escopo por-teste com `NullPool`, porque conexões asyncpg não podem atravessar event loops do pytest-asyncio.
**Consequência**: testes mais lentos que com SQLite, mas validam o comportamento real do banco — inclusive o `numpy.ndarray` devolvido pelo pgvector, que causou um bug real de truthiness ambígua no ranking de memórias.
