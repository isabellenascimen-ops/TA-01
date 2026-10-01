"""
Import central de todos os modelos ORM.

Alembic (e qualquer código que precise de Base.metadata completo, como
`create_all` em testes) deve importar ESTE módulo, não os módulos
individuais — garante que nenhuma tabela fique de fora por falta de
import em algum ponto do código.
"""
from app.agent.deliberation import DeliberationTrace  # noqa: F401
from app.agent.state import AgentState  # noqa: F401
from app.database import Base  # noqa: F401
from app.memory.episodic import Episode  # noqa: F401

__all__ = ["Base", "AgentState", "Episode", "DeliberationTrace"]
