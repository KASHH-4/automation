"""Enterprise proposal supervisor for the AI Proposal Intelligence prototype.

This module is the orchestration layer for the system. It does not train a model
and it does not generate quotes directly. Instead, it:

1. Interprets the user request.
2. Uses a LangChain router to decide which tools are needed.
3. Calls only the selected tools.
4. Builds a structured context bundle.
5. Sends the combined context to Gemini for the final proposal draft.

The supervisor is intentionally dependency-injected so it stays decoupled from
the internal implementation of the other modules.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence

from pydantic import BaseModel, Field

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import StructuredTool

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


ToolName = Literal["company_data", "market_data", "similar_quotes"]


def _ensure_rag_module_on_path() -> Path:
    """Add the RAG module directory to sys.path so retriever.py can be imported."""

    current_dir = Path(__file__).resolve().parent
    rag_module_dir = current_dir / "RAG_Module" / "RAG" / "rag_module"

    if rag_module_dir.exists() and str(rag_module_dir) not in sys.path:
        sys.path.insert(0, str(rag_module_dir))

    return rag_module_dir


_RAG_MODULE_DIR = _ensure_rag_module_on_path()

try:
    from retriever import retrieve_similar_quotes as default_retrieve_similar_quotes
except Exception:  # pragma: no cover - import is environment dependent
    default_retrieve_similar_quotes = None

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except Exception:  # pragma: no cover - optional dependency
    ChatGoogleGenerativeAI = None


class EmptyArgs(BaseModel):
    """Args schema for tools that do not require user input."""


class RetrievalArgs(BaseModel):
    """Args schema for quotation retrieval."""

    query: str = Field(..., description="Natural-language search query.")
    k: int = Field(default=3, ge=1, le=10, description="Number of results to return.")


class MarketArgs(BaseModel):
    """Args schema for market data retrieval."""

    country: str = Field(..., description="Target country for market lookup.")
    laptop_query: str = Field(..., description="Laptop model or query phrase for market lookup.")


class MarketInputs(BaseModel):
    """Structured market extraction payload from routing."""

    country: str = Field(default="India")
    laptop_query: str = Field(default="Laptop")


class ProposalRoute(BaseModel):
    """Structured routing decision returned by the planner."""

    selected_tools: List[ToolName] = Field(default_factory=list)
    retrieval_query: Optional[str] = Field(
        default=None,
        description="Query to send to the retrieval tool when similar quotes are needed.",
    )
    retrieval_k: int = Field(default=3, ge=1, le=10)
    market_inputs: Optional[MarketInputs] = Field(
        default=None,
        description="Country and laptop query extracted when market_data is selected.",
    )
    clarification_needed: bool = Field(default=False)
    clarification_question: Optional[str] = None
    routing_summary: str = Field(
        default="",
        description="Short explanation of why the selected tools are sufficient.",
    )


class SupervisorDependencyError(RuntimeError):
    """Raised when the supervisor needs a tool that was not supplied."""


@dataclass(frozen=True)
class SupervisorDependencies:
    """Injected tool implementations used by the supervisor."""

    load_company_data: Optional[Callable[[], Any]] = None
    get_live_market_data: Optional[Callable[..., Any]] = None
    retrieve_similar_quotes: Optional[Callable[[str, int], Any]] = None


@dataclass
class ToolExecutionResult:
    """Normalised result of a tool call."""

    name: str
    ok: bool
    data: Any = None
    error: Optional[str] = None


@dataclass
class ProposalSupervisorResult:
    """Full orchestration output for tracing and downstream use."""

    user_request: str
    route: ProposalRoute
    tool_results: Dict[str, ToolExecutionResult]
    assembled_context: str
    final_proposal: str
    warnings: List[str] = field(default_factory=list)


def _safe_json(data: Any, max_chars: int = 12000) -> str:
    """Serialise tool output to compact JSON for prompt assembly."""

    try:
        text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    except TypeError:
        text = repr(data)

    if len(text) > max_chars:
        return text[:max_chars] + "\n... [truncated]"

    return text


def _model_dump_compat(model: Any) -> Dict[str, Any]:
    """Support both Pydantic v2 model_dump() and v1 dict()."""

    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)


def _format_similar_quotes(quotes: Any, max_quotes: int = 5) -> str:
    """Convert retrieval output into a compact, readable context block."""

    if not quotes:
        return "No similar quotations were retrieved."

    if not isinstance(quotes, list):
        return _safe_json(quotes)

    lines: List[str] = []
    for index, quote in enumerate(quotes[:max_quotes], start=1):
        if not isinstance(quote, dict):
            lines.append(f"[{index}] {quote}")
            continue

        content = str(quote.get("content", "")).strip()
        if len(content) > 1400:
            content = content[:1400] + "\n... [truncated]"

        lines.append(
            f"[{index}] quotation_id={quote.get('quotation_id', '')} | "
            f"customer={quote.get('customer', '')} | "
            f"supplier={quote.get('supplier', '')} | "
            f"currency={quote.get('currency', '')} | "
            f"similarity_score={quote.get('similarity_score', '')}\n"
            f"{content}"
        )

    return "\n\n".join(lines)


def _heuristic_route(user_request: str) -> ProposalRoute:
    """Fallback router used when Gemini is unavailable."""

    text = user_request.lower().strip()
    selected_tools: List[ToolName] = []
    retrieval_query: Optional[str] = None
    market_inputs: Optional[MarketInputs] = None
    clarification_needed = False
    clarification_question: Optional[str] = None

    market_keywords = ["exchange rate", "usd", "inr", "steel price", "copper price", "market price", "commodity"]
    retrieval_keywords = ["previous quotation", "previous quotations", "similar quotation", "historical quote", "show quotes"]
    quotation_keywords = ["quotation", "quote", "proposal", "generate a quotation", "prepare a quotation"]

    if any(keyword in text for keyword in retrieval_keywords):
        selected_tools = ["similar_quotes"]
        retrieval_query = user_request
    elif any(keyword in text for keyword in market_keywords):
        selected_tools = ["market_data"]
        market_inputs = _extract_market_inputs_from_text(user_request)
    elif any(keyword in text for keyword in quotation_keywords):
        selected_tools = ["company_data", "similar_quotes", "market_data"]
        retrieval_query = user_request
        market_inputs = _extract_market_inputs_from_text(user_request)
    else:
        clarification_needed = True
        clarification_question = (
            "Please clarify whether you need live market data, historical quotations, "
            "or a full quotation draft."
        )

    summary = "Heuristic router selected tools based on keyword intent detection."
    return ProposalRoute(
        selected_tools=selected_tools,
        retrieval_query=retrieval_query,
        retrieval_k=3,
        market_inputs=market_inputs,
        clarification_needed=clarification_needed,
        clarification_question=clarification_question,
        routing_summary=summary,
    )


def _extract_market_inputs_from_text(user_request: str) -> MarketInputs:
    """Best-effort extractor used when router output does not include market inputs."""

    cleaned = user_request.strip().replace("\n", " ")

    country_match = re.search(r"\bin\s+([A-Za-z][A-Za-z\s]{1,40})(?:[.?!]|$)", cleaned, re.IGNORECASE)
    country = country_match.group(1).strip() if country_match else "India"

    query_match = re.search(
        r"\bfor\s+(.+?)(?:\s+in\s+[A-Za-z][A-Za-z\s]{1,40})?(?:[.?!]|$)",
        cleaned,
        re.IGNORECASE,
    )
    laptop_query = query_match.group(1).strip() if query_match else cleaned

    if not laptop_query:
        laptop_query = "Laptop"

    return MarketInputs(country=country, laptop_query=laptop_query)


class ProposalSupervisor:
    """LangChain-based AI supervisor for proposal intelligence orchestration."""

    def __init__(
        self,
        dependencies: Optional[SupervisorDependencies] = None,
        llm: Any = None,
        model_name: Optional[str] = None,
        temperature: float = 0.0,
    ) -> None:
        if load_dotenv is not None:
            load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

        self._llm_config_error: Optional[str] = None
        self.dependencies = dependencies or SupervisorDependencies()
        self._tool_registry = self._build_tool_registry()
        self.llm = llm or self._build_llm(model_name=model_name, temperature=temperature)
        self._router_chain = self._build_router_chain() if self.llm is not None else None
        self._generator_chain = self._build_generator_chain() if self.llm is not None else None

    @property
    def tools(self) -> Sequence[StructuredTool]:
        """Expose the registered LangChain tools for external composition."""

        return self._tool_registry

    def _build_llm(self, model_name: Optional[str], temperature: float) -> Any:
        """Create the Gemini chat model if the optional dependency is installed."""

        if ChatGoogleGenerativeAI is None:
            self._llm_config_error = (
                "Gemini dependency is missing. Install 'langchain-google-genai' to enable LLM routing and generation."
            )
            return None

        gemini_model = model_name or os.environ.get("GEMINI_MODEL_NAME", "gemini-1.5-flash")
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

        if not api_key:
            self._llm_config_error = (
                "Gemini API key is missing. Set GOOGLE_API_KEY in a .env file at the project root."
            )
            return None

        self._llm_config_error = None

        return ChatGoogleGenerativeAI(
            model=gemini_model,
            temperature=temperature,
            google_api_key=api_key,
        )

    def _build_router_chain(self) -> Any:
        """Planner chain that decides which tools are needed."""

        router_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a routing supervisor for an enterprise proposal intelligence system. "
                    "Select only the tools that are actually needed. Never choose every tool by default. "
                    "If the user wants a live price or exchange rate, choose market_data only. "
                    "If the user wants previous quotations or similar historical references, choose similar_quotes only. "
                    "If the user wants a quotation draft, choose company_data, similar_quotes, and market_data when relevant. "
                    "When similar_quotes is needed, provide a short retrieval_query derived from the user request. "
                    "When market_data is selected, always fill market_inputs.country and market_inputs.laptop_query from the user request. "
                    "If country is not explicit, infer the most likely country from wording; default to India only when no signal exists. "
                    "If the request is too vague, mark clarification_needed=true and provide one concise clarification_question."
                ),
                ("human", "User request: {user_request}"),
            ]
        )

        structured_llm = self.llm.with_structured_output(ProposalRoute)
        return router_prompt | structured_llm

    def _build_generator_chain(self) -> Any:
        """Final proposal generation chain powered by Gemini."""

        generator_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an enterprise proposal writing engine for a sales and marketing team. "
                    "Use only the supplied context. Do not invent prices, rates, or company details. "
                    "If data is missing, state the gap and make the minimum necessary assumptions. "
                    "Do not reveal internal tool routing or chain-of-thought. "
                    "Return a professional quotation draft in markdown with clear sections for requirement understanding, "
                    "pricing basis, historical references, market inputs, assumptions, and next steps."
                ),
                (
                    "human",
                    "User request:\n{user_request}\n\nStructured context:\n{context}\n\nWrite the final proposal draft.",
                ),
            ]
        )

        return generator_prompt | self.llm | StrOutputParser()

    def _build_tool_registry(self) -> List[StructuredTool]:
        """Create the LangChain tool registry for the supervisor."""

        return [
            StructuredTool.from_function(
                name="load_company_data",
                description=(
                    "Load structured company pricing information from the ingestion module. "
                    "This tool does not need the user request; it simply returns the internal company dataset."
                ),
                func=self._load_company_data_tool,
                args_schema=EmptyArgs,
            ),
            StructuredTool.from_function(
                name="get_live_market_data",
                description=(
                    "Run the market module adapter using country and laptop query. "
                    "This executes the standalone market pipeline and returns captured terminal output."
                ),
                func=self._get_live_market_data_tool,
                args_schema=MarketArgs,
            ),
            StructuredTool.from_function(
                name="retrieve_similar_quotes",
                description=(
                    "Retrieve semantically similar historical quotations. "
                    "This tool only needs a search query and an optional top-k value."
                ),
                func=self._retrieve_similar_quotes_tool,
                args_schema=RetrievalArgs,
            ),
        ]

    def _require_dependency(self, name: str, value: Optional[Callable[..., Any]]) -> Callable[..., Any]:
        if value is None:
            raise SupervisorDependencyError(
                f"Missing dependency for '{name}'. Pass the callable into SupervisorDependencies."
            )
        return value

    def _load_company_data_tool(self) -> str:
        loader = self._require_dependency("load_company_data", self.dependencies.load_company_data)
        data = loader()
        return _safe_json(data)

    def _run_market_module_adapter(self, country: str, laptop_query: str) -> str:
        """Adapter for the standalone market module without changing its internals."""

        module_dir = Path(__file__).resolve().parent / "Scraping and Converstion module"
        config_path = module_dir / "config.py"

        if not module_dir.exists() or not config_path.exists():
            raise SupervisorDependencyError(
                "Market module not found. Expected 'Scraping and Converstion module/config.py'."
            )

        original_config = config_path.read_text(encoding="utf-8")
        safe_country = country.replace("\\", "\\\\").replace('"', '\\"')
        safe_laptop_query = laptop_query.replace("\\", "\\\\").replace('"', '\\"')

        updated_config, country_replacements = re.subn(
            r"^TARGET_COUNTRY\s*=\s*.*$",
            f'TARGET_COUNTRY = "{safe_country}"',
            original_config,
            flags=re.MULTILINE,
        )
        updated_config, model_replacements = re.subn(
            r"^LAPTOP_MODEL\s*=\s*.*$",
            f'LAPTOP_MODEL = "{safe_laptop_query}"',
            updated_config,
            flags=re.MULTILINE,
        )

        if country_replacements != 1 or model_replacements != 1:
            raise RuntimeError("Market module config format is unexpected; could not update TARGET_COUNTRY/LAPTOP_MODEL.")

        config_path.write_text(updated_config, encoding="utf-8")

        try:
            run_env = os.environ.copy()
            run_env.setdefault("PYTHONIOENCODING", "utf-8")
            run_env.setdefault("PYTHONUTF8", "1")

            process = subprocess.run(
                [sys.executable, "main.py"],
                cwd=str(module_dir),
                capture_output=True,
                text=True,
                env=run_env,
                timeout=240,
            )
        finally:
            config_path.write_text(original_config, encoding="utf-8")

        captured = "\n".join(part for part in [process.stdout, process.stderr] if part).strip()
        if process.returncode != 0:
            raise RuntimeError(
                "Market module execution failed. "
                f"Exit code: {process.returncode}. Output:\n{captured or 'No output captured.'}"
            )

        return captured or "Market module executed successfully with no terminal output."

    def _get_live_market_data_tool(self, country: str, laptop_query: str) -> str:
        loader = self.dependencies.get_live_market_data

        if loader is not None:
            try:
                data = loader(country=country, laptop_query=laptop_query)
            except TypeError:
                data = loader()
            return _safe_json(data)

        return self._run_market_module_adapter(country=country, laptop_query=laptop_query)

    def _retrieve_similar_quotes_tool(self, query: str, k: int = 3) -> str:
        retriever = self.dependencies.retrieve_similar_quotes or default_retrieve_similar_quotes
        retriever = self._require_dependency("retrieve_similar_quotes", retriever)
        data = retriever(query=query, k=k)
        return _format_similar_quotes(data)

    def _route_request(self, user_request: str) -> ProposalRoute:
        """Use Gemini when available, otherwise fall back to the heuristic router."""

        if self._router_chain is None:
            return _heuristic_route(user_request)

        try:
            return self._router_chain.invoke({"user_request": user_request})
        except Exception:
            return _heuristic_route(user_request)

    def _execute_route(self, user_request: str, route: ProposalRoute) -> Dict[str, ToolExecutionResult]:
        """Execute only the tools selected by the router."""

        results: Dict[str, ToolExecutionResult] = {}

        for tool_name in route.selected_tools:
            try:
                if tool_name == "company_data":
                    output = self._load_company_data_tool()
                elif tool_name == "market_data":
                    market_inputs = route.market_inputs or _extract_market_inputs_from_text(user_request)
                    output = self._get_live_market_data_tool(
                        country=market_inputs.country,
                        laptop_query=market_inputs.laptop_query,
                    )
                elif tool_name == "similar_quotes":
                    query = route.retrieval_query or user_request
                    output = self._retrieve_similar_quotes_tool(query=query, k=route.retrieval_k)
                else:
                    raise SupervisorDependencyError(f"Unknown tool selected by router: {tool_name}")

                results[tool_name] = ToolExecutionResult(name=tool_name, ok=True, data=output)

            except Exception as exc:
                results[tool_name] = ToolExecutionResult(name=tool_name, ok=False, error=str(exc))

        return results

    def _assemble_context(
        self,
        user_request: str,
        route: ProposalRoute,
        tool_results: Dict[str, ToolExecutionResult],
    ) -> str:
        """Build the structured prompt context that will be sent to Gemini."""

        sections: List[str] = [
            "## User Request\n" + user_request,
            "## Routing Decision\n" + _safe_json(_model_dump_compat(route)),
        ]

        if "company_data" in tool_results:
            result = tool_results["company_data"]
            section = result.data if result.ok else result.error
            sections.append("## Company Data\n" + str(section))

        if "market_data" in tool_results:
            result = tool_results["market_data"]
            section = result.data if result.ok else result.error
            sections.append("## Market Data\n" + str(section))

        if "similar_quotes" in tool_results:
            result = tool_results["similar_quotes"]
            section = result.data if result.ok else result.error
            sections.append("## Similar Quotations\n" + str(section))

        errors = [
            f"{name}: {result.error}"
            for name, result in tool_results.items()
            if not result.ok and result.error
        ]

        if errors:
            sections.append("## Tool Errors\n" + "\n".join(errors))

        context = "\n\n".join(sections)
        return context

    def _generate_final_proposal(self, user_request: str, context: str) -> str:
        """Generate the final proposal draft with Gemini."""

        if self._generator_chain is None:
            reason = self._llm_config_error or "Gemini is not configured."
            return (
                f"{reason}\n\n"
                "Structured context:\n\n"
                f"{context}"
            )

        try:
            return self._generator_chain.invoke(
                {
                    "user_request": user_request,
                    "context": context,
                }
            )
        except Exception as exc:
            return (
                "Gemini generation failed. Returning the assembled context for review.\n\n"
                f"Error: {exc}\n\n"
                f"{context}"
            )

    def invoke(self, user_request: str) -> ProposalSupervisorResult:
        """Run the full orchestration flow and return a structured result."""

        route = self._route_request(user_request)

        if route.clarification_needed:
            final_message = route.clarification_question or (
                "Please provide more detail so I can determine which data sources to consult."
            )
            return ProposalSupervisorResult(
                user_request=user_request,
                route=route,
                tool_results={},
                assembled_context="",
                final_proposal=final_message,
            )

        tool_results = self._execute_route(user_request, route)
        context = self._assemble_context(user_request, route, tool_results)
        final_proposal = self._generate_final_proposal(user_request, context)

        warnings = [
            f"{name}: {result.error}"
            for name, result in tool_results.items()
            if not result.ok and result.error
        ]

        return ProposalSupervisorResult(
            user_request=user_request,
            route=route,
            tool_results=tool_results,
            assembled_context=context,
            final_proposal=final_proposal,
            warnings=warnings,
        )

    def run(self, user_request: str) -> str:
        """Convenience wrapper that returns only the final proposal text."""

        return self.invoke(user_request).final_proposal


def build_default_supervisor(
    load_company_data: Optional[Callable[[], Any]] = None,
    get_live_market_data: Optional[Callable[[], Any]] = None,
    retrieve_similar_quotes: Optional[Callable[[str, int], Any]] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
) -> ProposalSupervisor:
    """Convenience factory for the common wiring pattern."""

    if load_company_data is None:
        try:
            from company_loader import load_company_data as default_company_loader

            load_company_data = default_company_loader
        except Exception:
            # Keep dependency optional; supervisor will surface a clean error at tool execution time.
            load_company_data = None

    dependencies = SupervisorDependencies(
        load_company_data=load_company_data,
        get_live_market_data=get_live_market_data,
        retrieve_similar_quotes=retrieve_similar_quotes,
    )
    return ProposalSupervisor(
        dependencies=dependencies,
        model_name=model_name,
        temperature=temperature,
    )


__all__ = [
    "build_default_supervisor",
    "EmptyArgs",
    "ProposalRoute",
    "ProposalSupervisor",
    "ProposalSupervisorResult",
    "RetrievalArgs",
    "SupervisorDependencies",
    "SupervisorDependencyError",
    "ToolExecutionResult",
]


if __name__ == "__main__":
    demo_supervisor = build_default_supervisor()
    print(
        demo_supervisor.run(
            "Generate a quotation for 20 stainless steel pressure vessels."
        )
    )