"""
REVA AI Assistant — core assistant engine.

Based on the SingleAssistant pattern from ai_engine, simplified for the REVA platform.
Creates a LangGraph agent with tools, system prompt, and memory management.
"""

import datetime
import json
import logging
from contextvars import copy_context
from pathlib import Path

from django.conf import settings
from langchain.agents import AgentState, create_agent
from langchain_core.messages import HumanMessage, SystemMessage

from ai_assistant.core.utils import (
    default_temperature,
    get_memory_saver,
    initialize_model,
)

logger = logging.getLogger("ai_assistant")


class RevaAssistant:
    """The REVA AI Assistant — a LangGraph-based conversational agent.

    Initialized with a provider (Azure OpenAI by default), model, and system prompt
    tailored for the REVA fitness/training platform.
    """

    def __init__(
        self,
        provider: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        system_prompt: str | None = None,
        user_id: int | None = None,
        assistant_session_id: int | None = None,
        screen_context: str = "default",
    ):
        """Initialize the REVA assistant.

        Args:
            provider: LLM provider (defaults to settings.AI_PROVIDER).
            model_name: Model identifier (defaults to settings.AI_MODEL).
            temperature: Model temperature (defaults to model-specific value).
            system_prompt: Custom system prompt (defaults to prompt.md).
            user_id: The pk of the authenticated user (trainer). Used to scope ORM tools.
        """
        self.provider = provider or getattr(settings, "AI_PROVIDER", "openai")
        self.model_name = model_name or getattr(settings, "AI_MODEL", "gpt-4o-mini")
        self.temperature = (
            temperature if temperature is not None else default_temperature(self.model_name)
        )
        self.user_id = user_id
        self.assistant_session_id = assistant_session_id
        self.screen_context = screen_context

        # Setup system prompt
        self.system_prompt = self._setup_system_prompt(system_prompt)

        # Initialize model
        self.model = self._initialize_model()

        # Setup tools (Django ORM tools scoped to the trainer)
        self.tools = self._setup_tools()

        logger.info(
            "RevaAssistant initialized: provider=%s, model=%s, tools=%d",
            self.provider,
            self.model_name,
            len(self.tools),
        )

    def _setup_system_prompt(self, custom_prompt: str | None) -> str:
        """Load system prompt from file or use custom prompt.

        Args:
            custom_prompt: Optional custom prompt override.

        Returns:
            Complete system prompt with current timestamp.
        """
        if custom_prompt is not None:
            prompt = custom_prompt
        else:
            prompt_path = Path(__file__).parent.parent / "prompt.md"
            prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

        # Append current timestamp for temporal awareness
        if prompt:
            current_dt = datetime.datetime.now(
                datetime.timezone(datetime.timedelta(hours=-3))
            ).strftime("%d/%m/%Y %H:%M")
            prompt = f"{prompt}\n\nData e hora atual: {current_dt}"

        return prompt

    def _initialize_model(self):
        """Initialize the LLM model based on provider settings.

        Returns:
            Initialized LangChain chat model.
        """
        if self.provider == "openai":
            api_key = getattr(settings, "AZURE_OPENAI_API_KEY", "")
            base_url = getattr(settings, "AZURE_OPENAI_ENDPOINT", "")
            return initialize_model(
                provider="openai",
                api_key=api_key,
                model_name=self.model_name,
                base_url=base_url,
                temperature=self.temperature,
            )

        if self.provider == "anthropic":
            api_key = getattr(settings, "AZURE_AI_FOUNDRY_API_KEY", "")
            base_url = getattr(settings, "AZURE_AI_FOUNDRY_ENDPOINT", "")
            return initialize_model(
                provider="anthropic",
                api_key=api_key,
                model_name=self.model_name,
                base_url=base_url,
                temperature=self.temperature,
            )

        if self.provider == "deepseek":
            api_key = getattr(settings, "AZURE_AI_FOUNDRY_API_KEY", "")
            base_url = getattr(settings, "AZURE_AI_FOUNDRY_ENDPOINT", "")
            return initialize_model(
                provider="deepseek",
                api_key=api_key,
                model_name=self.model_name,
                base_url=base_url,
                temperature=self.temperature,
            )

        if self.provider == "google":
            api_key = getattr(settings, "GOOGLE_API_KEY", "")
            return initialize_model(
                provider="google",
                api_key=api_key,
                model_name=self.model_name,
                temperature=self.temperature,
            )

        raise ValueError(f"Unsupported provider: {self.provider}")

    def _setup_tools(self) -> list:
        """Configure Django ORM tools scoped to the current user.

        Returns:
            List of LangChain tool callables.
        """
        if not self.user_id:
            logger.warning("No user_id provided — tools will not be available")
            return []

        from ai_assistant.core.tools import set_tools_context

        return set_tools_context(
            self.user_id,
            session_id=self.assistant_session_id,
            screen_context=self.screen_context,
        )

    def create_agent(self, checkpointer=None, name: str = "reva_assistant"):
        """Create a LangGraph agent with this assistant's configuration.

        Args:
            checkpointer: Optional checkpointer for state persistence.
            name: Name for the agent.

        Returns:
            Compiled LangGraph agent graph.
        """
        return create_agent(
            self.model,
            self.tools,
            checkpointer=checkpointer,
            system_prompt=self.system_prompt,
            state_schema=AgentState,
            name=name,
        )


class AssistantOrchestrator:
    """Orchestrator that manages the REVA assistant lifecycle.

    Handles agent creation, streaming, and token tracking.
    Based on OrchestratorAssistant from ai_engine.
    """

    def __init__(
        self,
        provider: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        screen_context: str = "default",
        user_id: int | None = None,
        assistant_session_id: int | None = None,
    ):
        """Initialize the orchestrator.

        Args:
            provider: LLM provider.
            model_name: Model to use.
            temperature: Model temperature.
            screen_context: Current screen context for context-aware responses.
            user_id: The pk of the authenticated user (trainer). Passed to tools.
        """
        self.provider = provider
        self.model_name = model_name
        self.temperature = temperature
        self.screen_context = screen_context
        self.user_id = user_id
        self.assistant_session_id = assistant_session_id
        self.delegate = None
        self.agent_graph = None

        # Token tracking
        self.last_input_tokens = 0
        self.last_output_tokens = 0
        self._first_reasoning_id_seen = False

    def _build_context_prompt(self, page_context: dict | None = None) -> str:
        """Build additional context based on the current screen and page data.

        Args:
            page_context: Dict from the frontend with URL, forms, fields, tables, etc.

        Returns:
            Context string to prepend to user messages.
        """
        parts = []

        # Static screen description
        screen_contexts = {
            "trainer-dashboard": "O usuário está na tela Hoje do treinador, com aulas do dia, alertas operacionais, perfis incompletos, saltos de carga e proximos passos.",
            "student-dashboard": "O usuário está no Painel do Aluno, onde pode ver seus treinos e progresso.",
            "student-list": "O usuário está na Lista de Alunos, gerenciando seus alunos.",
            "student-create": "O usuário está no formulário de vínculo de um aluno existente por e-mail.",
            "student-edit": "O usuário está editando os dados de um aluno.",
            "student-detail": "O usuário está vendo o perfil detalhado de um aluno.",
            "student-progress": "O usuário está vendo o progresso de um aluno.",
            "student-delete": "O usuário está na página de confirmação de exclusão de um aluno.",
            "student-set-password": "O usuário está em uma rota legada de senha de aluno, hoje substituída pelo auto-cadastro do próprio aluno.",
            "workout-list": "O usuário está na Lista de Treinos, visualizando planos de treino.",
            "workout-form": "O usuário está no formulário de criação/edição de treino.",
            "workout-detail": "O usuário está vendo os detalhes de um treino com todos os exercícios.",
            "workout-delete": "O usuário está na página de confirmação de exclusão de um treino.",
            "workout-session": "O usuário está em uma sessão de treino ativa, executando exercícios.",
            "plan-list": "O usuário está na Lista de Planos de Treino.",
            "plan-form": "O usuário está no formulário de criação/edição de plano de treino.",
            "plan-detail": "O usuário está vendo os detalhes de um plano de treino.",
            "plan-delete": "O usuário está na página de confirmação de exclusão de um plano.",
            "exercise-catalog": "O usuário está no Catálogo de Exercícios, explorando exercícios disponíveis.",
            "exercise-form": "O usuário está no formulário de criação/edição de exercício.",
            "exercise-detail": "O usuário está vendo os detalhes de um exercício do catálogo.",
            "exercise-delete": "O usuário está na página de confirmação de exclusão de um exercício.",
            "my-progress": "O usuário está na página Meu Progresso, acompanhando sua evolução.",
        }
        static_desc = screen_contexts.get(self.screen_context, "")
        if static_desc:
            parts.append(static_desc)

        # Dynamic page context from frontend
        if page_context:
            ctx_parts = []
            url = page_context.get("url", "")
            heading = page_context.get("heading", "")
            if url:
                ctx_parts.append(f"URL da página: {url}")
            if heading:
                ctx_parts.append(f"Título visível: {heading}")

            # Stats (dashboard cards)
            stats = page_context.get("stats", [])
            if stats:
                stat_lines = [f"  - {s['label']}: {s['value']}" for s in stats if s.get("label")]
                if stat_lines:
                    ctx_parts.append("Estatísticas na tela:\n" + "\n".join(stat_lines))

            # Forms with field values
            forms = page_context.get("forms", [])
            for form in forms:
                fields = form.get("fields", [])
                if not fields:
                    continue
                field_lines = []
                for f in fields:
                    label = f.get("label") or f.get("name", "?")
                    val = f.get("value", "")
                    if isinstance(val, dict):
                        val = val.get("text", val.get("value", ""))
                    required = " (obrigatório)" if f.get("required") else ""
                    ftype = f.get("type", "text")

                    line = f"  - {label} [{ftype}]{required}"
                    if val:
                        line += f" = \"{val}\""
                    elif f.get("placeholder"):
                        line += f" (placeholder: \"{f['placeholder']}\")"

                    # Include select options
                    options = f.get("options", [])
                    if options:
                        opt_texts = [o.get("text", o.get("value", "")) for o in options[:15]]
                        line += f" | opções: {', '.join(opt_texts)}"

                    field_lines.append(line)

                form_label = f"Formulário ({form.get('method', 'POST')} {form.get('action', '')}):"
                ctx_parts.append(form_label + "\n" + "\n".join(field_lines))

            # Tables
            tables = page_context.get("tables", [])
            for tbl in tables:
                headers = tbl.get("headers", [])
                rows = tbl.get("rows", [])
                if headers or rows:
                    table_text = f"Tabela: {' | '.join(headers)}\n"
                    for row in rows[:10]:
                        table_text += f"  {' | '.join(str(c) for c in row)}\n"
                    ctx_parts.append(table_text.strip())

            # Cards / visible data
            visible = page_context.get("visible_data", {})
            cards = visible.get("cards", [])
            if cards:
                card_lines = []
                for c in cards[:15]:
                    line = c.get("title", "")
                    if c.get("detail"):
                        line += f" — {c['detail']}"
                    if c.get("badges"):
                        line += f" [{', '.join(c['badges'])}]"
                    card_lines.append(f"  - {line}")
                ctx_parts.append("Itens visíveis:\n" + "\n".join(card_lines))

            # Standalone fields
            standalone = visible.get("standalone_fields", [])
            if standalone:
                sf_lines = []
                for f in standalone:
                    label = f.get("label") or f.get("name", "?")
                    val = f.get("value", "")
                    sf_lines.append(f"  - {label}: {val}")
                ctx_parts.append("Campos na página:\n" + "\n".join(sf_lines))

            if ctx_parts:
                parts.append("Contexto detalhado da página:\n" + "\n".join(ctx_parts))

        return "\n\n".join(parts)

    def ensure_delegate_and_graph(self):
        """Ensure the assistant delegate and agent graph are initialized."""
        if self.delegate is None:
            self.delegate = RevaAssistant(
                provider=self.provider,
                model_name=self.model_name,
                temperature=self.temperature,
                user_id=self.user_id,
                assistant_session_id=self.assistant_session_id,
                screen_context=self.screen_context,
            )
            self.agent_graph = None

        if self.agent_graph is None:
            memory = get_memory_saver()
            self.agent_graph = self.delegate.create_agent(
                checkpointer=memory,
                name="reva_assistant",
            )
            logger.info("RevaAssistant agent graph initialized")

    def _prepare_execution_context(self):
        """Capture a context where tool calls are scoped to this user."""
        if self.user_id:
            from ai_assistant.core.tools import set_tools_context

            set_tools_context(
                self.user_id,
                session_id=self.assistant_session_id,
                screen_context=self.screen_context,
            )
        return copy_context()

    def stream_chat(
        self,
        user_message: str,
        thread_id: str = "default",
        system_prompt: str | None = None,
        page_context: dict | None = None,
    ):
        """Yield response chunks from the assistant.

        Uses LangGraph's synchronous stream_events for SSE-compatible streaming.

        Args:
            user_message: The user's text message.
            thread_id: Thread identifier for conversation memory.
            system_prompt: Optional additional system prompt.
            page_context: JSON dict with current page context (URL, forms, fields, etc.).

        Yields:
            dict: Chunks with 'type' and 'content' keys.
                - 'response': Regular text response
                - 'reasoning': Model's reasoning/thinking
                - 'tool_call': Tool invocation notification
                - 'tool_result': Tool result notification
        """
        self.ensure_delegate_and_graph()

        # Build messages
        messages_list = []
        context_note = self._build_context_prompt(page_context)
        if context_note:
            messages_list.append(SystemMessage(content=context_note))
        if system_prompt:
            messages_list.append(SystemMessage(content=system_prompt))
        messages_list.append(HumanMessage(content=user_message))

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 30,
        }

        # Reset token counters
        self.last_input_tokens = 0
        self.last_output_tokens = 0
        self._first_reasoning_id_seen = False

        logger.info("Streaming chat for thread=%s", thread_id)

        execution_context = self._prepare_execution_context()
        event_iterator = execution_context.run(
            lambda: self.agent_graph.stream(
                {"messages": messages_list},
                config=config,
                stream_mode="messages",
            )
        )

        while True:
            try:
                event = execution_context.run(next, event_iterator)
            except StopIteration:
                break

            msg, metadata = event

            # Only process AI message chunks
            if not hasattr(msg, "content"):
                continue

            # Detect tool calls
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    name = tc.get("name", "")
                    if name:
                        yield {"type": "tool_call", "content": name}

            # Detect tool responses
            msg_type = getattr(msg, "type", "")
            if msg_type == "tool":
                tool_name = getattr(msg, "name", "")
                yield {"type": "tool_result", "content": tool_name}
                continue

            text, reasoning = self._extract_text_and_reasoning(msg)
            if text:
                yield {"type": "response", "content": text}
            if reasoning:
                yield {"type": "reasoning", "content": reasoning}

            # Track token usage
            usage = getattr(msg, "usage_metadata", None)
            if usage:
                inp = usage.get("input_tokens", 0)
                out = usage.get("output_tokens", 0)
                if inp > 0:
                    self.last_input_tokens += inp
                if out > 0:
                    self.last_output_tokens += out

    def invoke_chat(
        self,
        user_message: str,
        thread_id: str = "default",
        system_prompt: str | None = None,
        page_context: dict | None = None,
    ) -> dict:
        """Send a message and get the full response (non-streaming).

        Args:
            user_message: The user's text message.
            thread_id: Thread identifier for conversation memory.
            system_prompt: Optional additional system prompt.
            page_context: JSON dict with current page context.

        Returns:
            dict with 'content', 'input_tokens', 'output_tokens'.
        """
        self.ensure_delegate_and_graph()

        messages_list = []
        context_note = self._build_context_prompt(page_context)
        if context_note:
            messages_list.append(SystemMessage(content=context_note))
        if system_prompt:
            messages_list.append(SystemMessage(content=system_prompt))
        messages_list.append(HumanMessage(content=user_message))

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 30,
        }

        execution_context = self._prepare_execution_context()
        result = execution_context.run(
            lambda: self.agent_graph.invoke(
                {"messages": messages_list},
                config=config,
            )
        )

        # Extract the last AI message
        ai_messages = [m for m in result["messages"] if hasattr(m, "type") and m.type == "ai"]
        if not ai_messages:
            return {"content": "", "input_tokens": 0, "output_tokens": 0}

        last_msg = ai_messages[-1]
        content = last_msg.content
        if isinstance(content, list):
            from ai_assistant.core.utils import extract_content_and_reasoning

            content, _ = extract_content_and_reasoning(content)

        usage = getattr(last_msg, "usage_metadata", None) or {}
        return {
            "content": content,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        }

    def _extract_text_and_reasoning(self, message_chunk) -> tuple[str, str]:
        """Extract response text and reasoning from a stream chunk."""
        from ai_assistant.core.utils import extract_content_and_reasoning

        content = getattr(message_chunk, "content", "")
        if not content:
            return "", ""

        text, reasoning = extract_content_and_reasoning(content)
        return text, reasoning

    def _extract_reasoning_from_blocks(self, blocks) -> str:
        """Parse reasoning from content blocks."""
        if not blocks:
            return ""

        reasoning_parts = []
        for block in blocks:
            if block.get("type") != "reasoning":
                continue
            if block.get("id"):
                if self._first_reasoning_id_seen:
                    reasoning_parts.append("\n\n")
                else:
                    self._first_reasoning_id_seen = True
            reasoning_text = block.get("reasoning", "")
            if reasoning_text:
                reasoning_parts.append(reasoning_text)
        return "".join(reasoning_parts)
