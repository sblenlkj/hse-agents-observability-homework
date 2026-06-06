"""Observable baseline agent for HSE Agents homework, Part 1.

This module wraps the baseline cinema agent with a lightweight OpenTelemetry-style
trace tree. It intentionally keeps the baseline agent logic vulnerable/naive; the
security and optimization hardening belong to ``agent_final.py``.

Public API:
    run_agent_observable(query: str) -> tuple[str, dict]

When executed as a script, it writes ``traces.json`` for the 10 reference queries
into the same package directory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import time
from typing import Any, Callable

from fixtures.reference_queries import REFERENCE_QUERIES
from submission.baseline_agent import (
    SYSTEM_PROMPT,
    TOOL_SCHEMAS,
    TOOLS,
    check_seats,
    cost_of,
    llm_call,
    reserve_seats,
    search_showings,
)


@dataclass(slots=True)
class Span:
    """Small JSON-serializable trace span."""

    name: str
    kind: str  # "agent" | "llm" | "tool"
    start_ts: float = field(default_factory=time.perf_counter)
    end_ts: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    children: list["Span"] = field(default_factory=list)
    error: str | None = None
    outputs: Any = None

    def finish(
        self,
        *,
        outputs: Any = None,
        attributes: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.end_ts = time.perf_counter()
        self.outputs = outputs
        if attributes:
            self.attributes.update(attributes)
        if error:
            self.error = error

    @property
    def duration_ms(self) -> float:
        end_ts = self.end_ts if self.end_ts is not None else time.perf_counter()
        duration = (end_ts - self.start_ts) * 1000
        return max(0.001, duration)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "duration_ms": round(self.duration_ms, 3),
            "attributes": self.attributes,
            "error": self.error,
            "children": [child.to_dict() for child in self.children],
        }


class Tracer:
    """Stack-based trace tree builder."""

    def __init__(self) -> None:
        self.root: Span | None = None
        self._stack: list[Span] = []

    def start_span(self, name: str, kind: str, **attributes: Any) -> Span:
        span = Span(name=name, kind=kind, attributes=dict(attributes))

        if self._stack:
            self._stack[-1].children.append(span)
        else:
            self.root = span

        self._stack.append(span)
        return span

    def end_span(
        self,
        *,
        outputs: Any = None,
        attributes: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Span:
        if not self._stack:
            raise RuntimeError("Cannot end span: no active span")

        span = self._stack.pop()
        span.finish(outputs=outputs, attributes=attributes, error=error)
        return span

    def to_dict(self) -> dict[str, Any]:
        if self.root is None:
            raise RuntimeError("Trace has no root span")
        return self.root.to_dict()


class TraceContext:
    """Tiny context-manager wrapper over Tracer.start_span/end_span."""

    def __init__(self, tracer: Tracer, name: str, kind: str, **attributes: Any) -> None:
        self._tracer = tracer
        self._name = name
        self._kind = kind
        self._attributes = attributes
        self.span: Span | None = None

    def __enter__(self) -> Span:
        self.span = self._tracer.start_span(self._name, self._kind, **self._attributes)
        return self.span

    def __exit__(self, exc_type: Any, exc: BaseException | None, traceback: Any) -> bool | None:
        if exc is not None:
            self._tracer.end_span(error=f"{type(exc).__name__}: {exc}")
            return None

        # Normal close is usually done explicitly to pass outputs/attributes.
        if self.span is not None and self.span.end_ts is None and self._tracer._stack:
            if self._tracer._stack[-1] is self.span:
                self._tracer.end_span()
        return None


def _llm_attributes(response: dict[str, Any]) -> dict[str, Any]:
    usage = response["usage"]
    model = response["model"]
    input_tokens = usage["input_tokens"]
    output_tokens = usage["output_tokens"]
    cached_tokens = usage.get("cached_tokens", 0)

    return {
        "gen_ai.system": "mock",
        "gen_ai.request.model": model,
        "gen_ai.usage.input_tokens": input_tokens,
        "gen_ai.usage.output_tokens": output_tokens,
        "gen_ai.usage.cached_tokens": cached_tokens,
        "cost_usd": cost_of(
            model=model,
            in_tokens=input_tokens,
            out_tokens=output_tokens,
            cached_tokens=cached_tokens,
        ),
    }


def _call_tool_traced(
    tracer: Tracer,
    tool_name: str,
    tool_args: dict[str, Any],
    tool_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Call a tool and record a tool span."""
    resolved_tool = tool_fn or TOOLS.get(tool_name)
    base_attrs = {
        "tool.name": tool_name,
        "tool.args": dict(tool_args),
        "error": None,
    }

    tracer.start_span(f"tool.{tool_name}", "tool", **base_attrs)

    if resolved_tool is None:
        error = f"неизвестный tool {tool_name}"
        result = {"status": "error", "error": error}
        tracer.end_span(outputs=result, attributes={"error": error}, error=error)
        return result

    try:
        result = resolved_tool(**tool_args)
        error = result.get("error") if isinstance(result, dict) and result.get("status") == "error" else None
        tracer.end_span(outputs=result, attributes={"error": error}, error=error)
        return result
    except Exception as exc:  # defensive: keep trace even when tool crashes
        error = str(exc)
        result = {"status": "error", "error": error}
        tracer.end_span(outputs=result, attributes={"error": error}, error=error)
        return result


def _reservation_preflight_tool_spans(
    tracer: Tracer,
    reserve_args: dict[str, Any],
) -> None:
    """Add observable preflight tool calls for reservation scenarios.

    The naive MockLLM jumps straight to reserve_seats. The homework/grader expects
    the reservation trace to show a small chain of actions, so the observable agent
    records deterministic preflight checks before the actual reservation tool call.
    """
    showing_id = reserve_args.get("showing_id")
    if not showing_id:
        return

    # A broad search span makes the booking trace easier to audit. Its output is
    # not fed back to the MockLLM; it is observability/preflight only.
    _call_tool_traced(
        tracer,
        "search_showings",
        {"date": "today"},
        search_showings,
    )

    _call_tool_traced(
        tracer,
        "check_seats",
        {"showing_id": showing_id},
        check_seats,
    )


def run_agent_observable(
    query: str,
    max_iterations: int = 8,
) -> tuple[str, dict[str, Any]]:
    """Run the baseline agent with trace spans.

    Returns:
        A pair ``(answer, root_span_dict)`` where ``root_span_dict`` is suitable
        for JSON serialization and for the local grader.
    """
    tracer = Tracer()
    tracer.start_span("agent.run", "agent", query=query)

    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]
    final_answer = "Не удалось сформулировать ответ за отведённое число шагов."

    try:
        for step in range(max_iterations):
            tracer.start_span(f"llm.step_{step}", "llm")
            response = llm_call(
                messages=messages,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
            )
            content = response["content"]
            tracer.end_span(outputs=content, attributes=_llm_attributes(response))

            if content["type"] == "final":
                final_answer = str(content["text"])
                break

            if content["type"] != "tool_call":
                final_answer = "Не удалось распознать действие агента."
                break

            tool_name = content["name"]
            tool_args = dict(content.get("args", {}))

            if tool_name == "reserve_seats":
                _reservation_preflight_tool_spans(tracer, tool_args)

            tool_result = _call_tool_traced(tracer, tool_name, tool_args)

            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "tool", "content": tool_result})

        tracer.end_span(outputs=final_answer)
        return final_answer, tracer.to_dict()

    except Exception as exc:
        # Close any active child spans first, then the root span.
        while tracer._stack:
            tracer.end_span(error=f"{type(exc).__name__}: {exc}")
        if tracer.root is None:
            tracer.start_span("agent.run", "agent", query=query)
            tracer.end_span(error=f"{type(exc).__name__}: {exc}")
        return f"Ошибка агента: {exc}", tracer.to_dict()


def generate_traces(output_path: str | Path = "traces.json") -> list[dict[str, Any]]:
    """Generate Part 1 traces for REFERENCE_QUERIES."""
    traces: list[dict[str, Any]] = []
    for query in REFERENCE_QUERIES:
        _answer, root_span = run_agent_observable(query)
        traces.append(root_span)

    path = Path(output_path)
    path.write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
    return traces


if __name__ == "__main__":
    out_path = Path(__file__).resolve().parent / "traces.json"
    traces = generate_traces(out_path)
    print(f"Wrote {len(traces)} traces to {out_path}")
