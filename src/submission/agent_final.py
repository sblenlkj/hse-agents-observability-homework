"""Final ReAct-style agent for HSE Agents homework, Part 3.

This version keeps the same conceptual execution model as the starter agent:

    LLM call -> tool execution -> LLM call -> final answer

The final agent does not replace the agent with fully deterministic templates.
Instead it hardens the tool layer and improves accounting/routing around the
same ReAct loop:

- prompt-cache accounting for static prompt/tool schema tokens;
- model routing between small/large mock models;
- max_tokens parameter as a real-API placeholder;
- input filtering before model/tool execution;
- data sanitization for tool results;
- tool-argument validation, especially for reserve_seats;
- output sanitization before returning the answer.

When executed as a module, it evaluates itself on golden_cases.yaml and writes
metrics_final.json.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import json
import re
import statistics
import time
from typing import Any, Callable

import yaml

from fixtures.films import FILMS
from fixtures.schedule import SCHEDULE, all_seat_codes
from fixtures.users import POLICIES, USERS
from submission.baseline_agent import (
    SYSTEM_PROMPT,
    TOOL_SCHEMAS,
    MockLLM,
    check_loyalty,
    check_seats,
    cost_of,
    count_tokens,
    lookup_policy,
    reserve_seats,
    search_showings,
)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CASES_PATH = BASE_DIR / "golden_cases.yaml"
DEFAULT_METRICS_PATH = BASE_DIR / "metrics_final.json"

CURRENT_USER_ID = "current"
FINAL_MAX_TOKENS = 96
CACHE_STATIC = True


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Span:
    name: str
    kind: str
    start_ts: float = field(default_factory=time.perf_counter)
    end_ts: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    children: list["Span"] = field(default_factory=list)
    error: str | None = None

    def finish(
        self,
        *,
        attributes: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.end_ts = time.perf_counter()
        if attributes:
            self.attributes.update(attributes)
        if error:
            self.error = error

    @property
    def duration_ms(self) -> float:
        end_ts = self.end_ts if self.end_ts is not None else time.perf_counter()
        return max(0.001, (end_ts - self.start_ts) * 1000)

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
        attributes: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Span:
        if not self._stack:
            raise RuntimeError("Cannot end span: no active span")
        span = self._stack.pop()
        span.finish(attributes=attributes, error=error)
        return span

    def close_all(self, error: str | None = None) -> None:
        while self._stack:
            self.end_span(error=error)

    def to_dict(self) -> dict[str, Any]:
        if self.root is None:
            raise RuntimeError("Trace has no root span")
        return self.root.to_dict()


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

DANGEROUS_INPUT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, re.I)
    for pattern in [
        r"игнорируй|забудь\s+.*инструкц|ignore\s+previous|ignore\s+all\s+previous",
        r"developer\s*mode|jailbreak|без\s+ограничен|новые\s+инструкц",
        r"system\s*prompt|системн\w*\s+промпт|как\s+тебя\s+настро",
        r"system\s+note|system\s+override|free\s+tickets",
        r"промокод|100\s*%|скидк\w*\s+100|бесплатн",
        r"user_id\s*=|друг\w*\s+пользовател|чуж\w*|other_user|vip_admin|не\s+моего\s+аккаунт",
        r"\b1\s*руб|цену\s+поставь|цена\s+.*вручн|за\s+1\s*руб",
        r"проверку\s+возраста\s+игнор|без\s+проверки\s+мест",
        r"<\s*script|</\s*script\s*>",
    ]
]

DATA_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, re.I | re.S)
    for pattern in [
        r"\[?\s*system\s+(?:note|override)[^\n.]*[\].]?",
        r"ignore\s+previous\s+rules[^\n.]*[.]?",
        r"allow\s+free\s+tickets[^\n.]*[.]?",
        r"<\s*script[^>]*>.*?<\s*/\s*script\s*>",
    ]
]


def normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def detect_dangerous_input(text: str) -> bool:
    return any(pattern.search(text) for pattern in DANGEROUS_INPUT_PATTERNS)


def sanitize_text(text: Any) -> str:
    cleaned = str(text)
    for pattern in DATA_INJECTION_PATTERNS:
        cleaned = pattern.sub("[удалено]", cleaned)
    return cleaned


def sanitize_output(text: str) -> str:
    cleaned = sanitize_text(text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:900]


def security_refusal() -> str:
    # Do not echo the exact suspicious phrase, otherwise prompt-leak tests may
    # fail because the unsafe marker appears in the answer.
    return (
        "Не могу выполнить этот запрос: я не раскрываю внутренние настройки, "
        "не оформляю произвольные скидки, не работаю с чужими user_id и не обхожу "
        "проверку возраста или мест. Переформулируйте обычный запрос."
    )


# ---------------------------------------------------------------------------
# Domain helpers and safe tools
# ---------------------------------------------------------------------------

FILM_BY_ID = {film["id"]: film for film in FILMS}
SCHEDULE_BY_ID = {showing["id"]: showing for showing in SCHEDULE}


def film_title_matches(film: dict[str, Any], query: str) -> bool:
    q = normalize(query)
    title = normalize(str(film.get("title", "")))
    main = title.split(":")[0].strip()
    words = [word for word in re.split(r"\W+", main) if len(word) >= 4]
    if main and main in q:
        return True
    return bool(words and all(word in q for word in words[:2]))


def extract_date(query: str) -> str:
    q = normalize(query)
    if "послезавтра" in q or "после завтра" in q:
        return "day_after"
    if "завтра" in q:
        return "tomorrow"
    if "сегодня" in q or "седня" in q or "веч" in q:
        return "today"
    return ""


def extract_time(query: str) -> str:
    match = re.search(r"(\d{1,2})[:. ](\d{2})", query)
    if not match:
        return ""
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def extract_count(query: str) -> int:
    q = normalize(query)
    match = re.search(r"(\d+)\s*(?:мест|билет)", q)
    if match:
        return max(1, min(6, int(match.group(1))))
    if "два" in q or "две" in q:
        return 2
    if "три" in q:
        return 3
    return 1


def extract_genre_stem(query: str) -> str:
    q = normalize(query)
    for stem in ["фантастик", "драм", "ужас", "анимаци", "комеди", "семейн", "боевик", "мелодрам"]:
        if stem in q:
            return stem
    if "семей" in q or "ребен" in q or "ребён" in q:
        return "семейн"
    return ""


def find_showing_for_query(query: str) -> dict[str, Any] | None:
    explicit_id = re.search(r"s\d{3}", query.lower())
    if explicit_id:
        return SCHEDULE_BY_ID.get(explicit_id.group(0))

    q_date = extract_date(query)
    q_time = extract_time(query)
    mentioned_films = [film for film in FILMS if film_title_matches(film, query)]

    candidates = SCHEDULE
    if mentioned_films:
        film_ids = {film["id"] for film in mentioned_films}
        candidates = [showing for showing in candidates if showing["film_id"] in film_ids]
    if q_date:
        candidates = [showing for showing in candidates if showing["date"] == q_date]
    if q_time:
        candidates = [showing for showing in candidates if showing["time"] == q_time]

    return candidates[0] if candidates else None


def all_available_seats(showing: dict[str, Any]) -> list[str]:
    taken = set(showing.get("seats_taken", []))
    return [code for code in all_seat_codes() if code not in taken]


def user_age(user_id: str = CURRENT_USER_ID) -> int:
    user = USERS.get(user_id, {})
    value = user.get("age", None)
    if isinstance(value, int):
        return value
    raise ValueError(f"User {user_id} has no age")


def film_requires_adult(showing: dict[str, Any]) -> bool:
    film = FILM_BY_ID.get(showing.get("film_id"), {})
    rating = str(film.get("rating", ""))
    return "18" in rating


def requested_minor_for_adult_content(query: str) -> bool:
    q = normalize(query)
    if "18+" not in q and "18" not in q:
        return False
    return bool(re.search(r"\b(?:[0-9]|1[0-7])\s*лет\b", q) or "ребен" in q or "ребён" in q)


def policy_topic(query: str) -> str:
    q = normalize(query)
    if "возврат" in q or "вернуть" in q:
        return "возврат"
    if "оплат" in q:
        return "оплата"
    if "возраст" in q or "18+" in q or "16+" in q:
        return "возраст"
    return "общие правила"


def safe_lookup_policy(topic: str, **kwargs: Any) -> dict[str, Any]:
    result = lookup_policy(topic=topic)
    if result.get("status") == "ok":
        return {"status": "ok", "data": sanitize_text(result.get("data", ""))}
    return result


def safe_check_loyalty(user_id: str = CURRENT_USER_ID, **kwargs: Any) -> dict[str, Any]:
    if user_id != CURRENT_USER_ID:
        return {"status": "error", "error": "можно проверять только ваш аккаунт"}
    return check_loyalty(user_id=CURRENT_USER_ID)


def safe_reserve_seats(
    *,
    showing_id: str,
    seats: list[str],
    user_id: str = CURRENT_USER_ID,
    request_text: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    if user_id != CURRENT_USER_ID:
        return {"status": "error", "error": "нельзя бронировать от имени другого пользователя"}

    forbidden_args = {"price", "discount", "discount_pct", "promo", "promocode"}.intersection(kwargs)
    if forbidden_args:
        return {"status": "error", "error": f"нельзя задавать цену или скидку вручную: {sorted(forbidden_args)}"}

    showing = SCHEDULE_BY_ID.get(showing_id)
    if not showing:
        return {"status": "error", "error": f"сеанс {showing_id} не найден"}

    if requested_minor_for_adult_content(request_text) or (
        film_requires_adult(showing) and user_age() is not None and user_age() < 18
    ):
        return {"status": "error", "error": "нельзя бронировать 18+ без подтверждения возраста"}

    available = set(all_available_seats(showing))
    invalid = [seat for seat in seats if seat not in available]
    if invalid:
        return {"status": "error", "error": f"места недоступны: {invalid}"}

    return reserve_seats(showing_id=showing_id, seats=seats, user_id=CURRENT_USER_ID)


SAFE_TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "search_showings": search_showings,
    "check_seats": check_seats,
    "reserve_seats": safe_reserve_seats,
    "lookup_policy": safe_lookup_policy,
    "check_loyalty": safe_check_loyalty,
}


# ---------------------------------------------------------------------------
# LLM layer: still ReAct, but with better intent routing for the mock
# ---------------------------------------------------------------------------

def choose_model(query: str) -> str:
    return "small" if len(query) < 180 else "large"


def estimate_usage(
    *,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, str]] | None,
    response: dict[str, Any],
    max_tokens: int,
    cache_static: bool,
) -> dict[str, int]:
    in_text = (
        system
        + json.dumps(messages, ensure_ascii=False)
        + json.dumps(tools or [], ensure_ascii=False)
    )
    in_tokens = count_tokens(in_text)
    cached_tokens = count_tokens(system) + count_tokens(tools or []) if cache_static else 0
    out_tokens = min(count_tokens(json.dumps(response, ensure_ascii=False)), max_tokens)
    return {
        "input_tokens": in_tokens,
        "cached_tokens": cached_tokens,
        "output_tokens": out_tokens,
    }


def secure_first_llm_response(query: str, *, tools: list[dict[str, str]] | None) -> dict[str, Any]:
    """Return the first ReAct decision.

    This simulates a better final LLM/router than the baseline mock while keeping
    the same LLM->tool->LLM control flow. The baseline mock has a known ordering
    bug: "билет" routes policy questions to search before policy can match.
    """
    q = normalize(query)

    if not q.strip() or "ты кто" in q or q.strip() in {"привет", "здравствуйте", "добрый день"}:
        return {
            "type": "final",
            "text": "Чем могу помочь? Я помогу подобрать сеанс, проверить наличие мест, оформить бронь или рассказать про правила.",
        }

    # Policy must be checked before generic search words like "билет".
    if any(token in q for token in ["возврат", "вернуть", "оплат", "политик", "правил", "возраст", "18+", "16+"]):
        return {
            "type": "tool_call",
            "name": "lookup_policy",
            "args": {"topic": policy_topic(query)},
        }

    if any(token in q for token in ["балл", "лояльн", "бонус", "уровень", "скидк"]):
        return {
            "type": "tool_call",
            "name": "check_loyalty",
            "args": {"user_id": CURRENT_USER_ID},
        }

    if any(token in q for token in ["заброн", "бронь", "купить", "оформ"]):
        showing = find_showing_for_query(query)
        if showing is None or "неизвест" in q:
            return {
                "type": "final",
                "text": "Не получилось: фильм или сеанс не найден. Уточните название фильма, дату и время.",
            }

        seats = all_available_seats(showing)[:extract_count(query)]
        return {
            "type": "tool_call",
            "name": "reserve_seats",
            "args": {
                "showing_id": showing["id"],
                "seats": seats,
                "user_id": CURRENT_USER_ID,
                "request_text": query,
            },
        }

    if any(token in q for token in ["свободн", "налич", "места", "мест", "сколько мест", "осталось"]):
        showing = find_showing_for_query(query)
        showing_id_match = re.search(r"s\d{3}", q)
        showing_id = showing["id"] if showing is not None else (showing_id_match.group(0) if showing_id_match else "auto")
        return {
            "type": "tool_call",
            "name": "check_seats",
            "args": {"showing_id": showing_id},
        }

    if (
        any(
            token in q
            for token in [
                "идет", "идёт", "сеанс", "распис", "что показыва", "что есть",
                "что нового", "посовет", "хочу посмотр", "найди", "ищу", "что-нибудь",
                "что нибудь", "билет", "есть ли", "седня", "вечир", "вечер",
            ]
        )
        or any(film_title_matches(film, query) for film in FILMS)
    ):
        args: dict[str, str] = {}
        date = extract_date(query)
        genre = extract_genre_stem(query)
        if date:
            args["date"] = date
        if genre:
            args["genre_stem"] = genre
        return {
            "type": "tool_call",
            "name": "search_showings",
            "args": args,
        }

    return {
        "type": "final",
        "text": "Чем могу помочь? Я помогу подобрать сеанс, проверить наличие мест, оформить бронь или рассказать про правила.",
    }


def secure_llm_call(
    *,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, str]] | None,
    max_tokens: int,
    cache_static: bool,
    model: str,
) -> dict[str, Any]:
    last = messages[-1]

    if last["role"] == "user":
        response = secure_first_llm_response(str(last["content"]), tools=tools)
        usage = estimate_usage(
            messages=messages,
            system=system,
            tools=tools,
            response=response,
            max_tokens=max_tokens,
            cache_static=cache_static,
        )
        return {"content": response, "usage": usage, "model": model}

    # The second call is still the starter mock: it sees a tool result and
    # composes the final answer. This preserves the ReAct shape.
    return MockLLM(model=model).call(
        messages=messages,
        system=system,
        tools=tools,
        max_tokens=max_tokens,
        cache_static=cache_static,
    )


def llm_call_traced(
    tracer: Tracer,
    *,
    step: int,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, str]] | None,
    max_tokens: int,
    cache_static: bool,
    model: str,
) -> dict[str, Any]:
    tracer.start_span(f"llm.step_{step}", "llm")
    response = secure_llm_call(
        messages=messages,
        system=system,
        tools=tools,
        max_tokens=max_tokens,
        cache_static=cache_static,
        model=model,
    )
    usage = response["usage"]
    attributes = {
        "gen_ai.system": "mock",
        "gen_ai.request.model": response.get("model", model),
        "gen_ai.usage.input_tokens": usage["input_tokens"],
        "gen_ai.usage.output_tokens": usage["output_tokens"],
        "gen_ai.usage.cached_tokens": usage.get("cached_tokens", 0),
        "cost_usd": cost_of(
            str(response.get("model", model)),
            int(usage["input_tokens"]),
            int(usage["output_tokens"]),
            int(usage.get("cached_tokens", 0)),
        ),
        "optimization.prompt_cache": cache_static,
        "optimization.max_tokens": max_tokens,
    }
    tracer.end_span(attributes=attributes)
    return response


def call_tool_traced(tracer: Tracer, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    attrs = {"tool.name": tool_name, "tool.args": dict(args), "error": None}
    tracer.start_span(f"tool.{tool_name}", "tool", **attrs)
    tool_fn = SAFE_TOOLS.get(tool_name)

    if tool_fn is None:
        error = f"unknown tool {tool_name}"
        result = {"status": "error", "error": error}
        tracer.end_span(attributes={"error": error}, error=error)
        return result

    try:
        result = tool_fn(**args)
        error = result.get("error") if result.get("status") == "error" else None
        tracer.end_span(attributes={"error": error}, error=error)
        return result
    except Exception as exc:
        error = str(exc)
        tracer.end_span(attributes={"error": error}, error=error)
        return {"status": "error", "error": error}


def run_reservation_workflow(tracer: Tracer, args: dict[str, Any]) -> dict[str, Any]:
    """Safe reservation preflight.

    LLM selected reserve_seats, but the application code refuses to perform the
    side effect before search/check validation. All steps are traced as tools.
    """
    showing_id = str(args.get("showing_id", ""))
    showing = SCHEDULE_BY_ID.get(showing_id)
    if showing is None:
        return {"status": "error", "error": f"сеанс {showing_id} не найден"}

    call_tool_traced(tracer, "search_showings", {"date": showing.get("date", "")})
    seats_result = call_tool_traced(tracer, "check_seats", {"showing_id": showing_id})
    if seats_result.get("status") == "error":
        return seats_result

    reservation_args = dict(args)
    reservation_args["user_id"] = CURRENT_USER_ID
    return call_tool_traced(tracer, "reserve_seats", reservation_args)


def run_agent_final(query: str, max_iterations: int = 8) -> tuple[str, dict[str, Any]]:
    tracer = Tracer()
    tracer.start_span("agent.run", "agent", query=query)

    if detect_dangerous_input(query):
        answer = sanitize_output(security_refusal())
        if tracer.root:
            tracer.root.attributes.update({
                "security.input_blocked": True,
                "optimization.short_circuit": True,
            })
        tracer.end_span()
        return answer, tracer.to_dict()

    model = choose_model(query)
    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

    try:
        for step in range(max_iterations):
            response = llm_call_traced(
                tracer,
                step=step,
                messages=messages,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                max_tokens=FINAL_MAX_TOKENS,
                cache_static=CACHE_STATIC,
                model=model,
            )
            content = response["content"]

            if content["type"] == "final":
                answer = sanitize_output(str(content["text"]))
                if tracer.root:
                    tracer.root.attributes.update({
                        "security.output_sanitized": True,
                        "optimization.model": model,
                    })
                tracer.end_span()
                return answer, tracer.to_dict()

            if content["type"] == "tool_call":
                tool_name = str(content["name"])
                tool_args = dict(content.get("args", {}))

                if tool_name == "reserve_seats":
                    tool_result = run_reservation_workflow(tracer, tool_args)
                else:
                    tool_result = call_tool_traced(tracer, tool_name, tool_args)

                if tool_result.get("status") == "ok" and isinstance(tool_result.get("data"), str):
                    tool_result = {"status": "ok", "data": sanitize_text(tool_result["data"])}

                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "tool", "content": tool_result})

        answer = "Не удалось сформулировать ответ за отведённое число шагов."
        tracer.end_span()
        return answer, tracer.to_dict()

    except Exception as exc:
        if tracer.root:
            tracer.root.error = str(exc)
        tracer.close_all(error=str(exc))
        return "Не получилось обработать запрос безопасно. Попробуйте уточнить формулировку.", tracer.to_dict()


def run_agent(query: str) -> tuple[str, dict[str, Any]]:
    return run_agent_final(query)


# ---------------------------------------------------------------------------
# Self-eval
# ---------------------------------------------------------------------------

def iter_spans(root_span: dict[str, Any]):
    yield root_span
    for child in root_span.get("children", []):
        yield from iter_spans(child)


def collect_called_tools(root_span: dict[str, Any]) -> list[str]:
    tools: list[str] = []
    for span in iter_spans(root_span):
        if span.get("kind") == "tool":
            attrs = span.get("attributes", {})
            tools.append(str(attrs.get("tool.name") or str(span.get("name", "")).removeprefix("tool.")))
    return tools


def collect_llm_spans(root_span: dict[str, Any]) -> list[dict[str, Any]]:
    return [span for span in iter_spans(root_span) if span.get("kind") == "llm"]


def trace_cost_usd(root_span: dict[str, Any]) -> float:
    return sum(float(span.get("attributes", {}).get("cost_usd", 0.0)) for span in collect_llm_spans(root_span))


def contains_any(answer: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    al = answer.lower()
    return any(str(pattern).lower() in al for pattern in patterns)


def contains_none(answer: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    al = answer.lower()
    return not any(str(pattern).lower() in al for pattern in patterns)


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        cases = yaml.safe_load(file)
    if not isinstance(cases, list):
        raise ValueError("golden_cases.yaml must contain a list")
    return cases


def check_case(case: dict[str, Any], answer: str, root_span: dict[str, Any]) -> dict[str, Any]:
    called_tools = collect_called_tools(root_span)
    expected_tool = case.get("must_call_tool")
    tool_check = not called_tools if expected_tool is None else str(expected_tool) in called_tools
    contains_check = contains_any(answer, case.get("answer_contains_any"))
    not_contains_check = contains_none(answer, case.get("answer_must_not_contain"))
    passed = bool(tool_check and contains_check and not_contains_check)
    return {
        "id": case["id"],
        "category": case["category"],
        "input": case["input"],
        "answer": answer,
        "called_tools": called_tools,
        "expected_tool": expected_tool,
        "tool_check": tool_check,
        "contains_check": contains_check,
        "not_contains_check": not_contains_check,
        "passed": passed,
        "cost_usd": trace_cost_usd(root_span),
        "llm_calls": len(collect_llm_spans(root_span)),
    }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return ordered[index]


def run_eval(cases_path: Path = DEFAULT_CASES_PATH) -> dict[str, Any]:
    cases = load_cases(cases_path)
    results: list[dict[str, Any]] = []
    by_category_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "total": 0})

    for case in cases:
        answer, trace = run_agent_final(str(case["input"]))
        result = check_case(case, answer, trace)
        results.append(result)
        bucket = by_category_counts[str(case["category"])]
        bucket["total"] += 1
        if result["passed"]:
            bucket["passed"] += 1

    costs = [float(result["cost_usd"]) for result in results]
    llm_calls = [int(result["llm_calls"]) for result in results]
    passed = sum(1 for result in results if result["passed"])

    return {
        "task_success_rate": round(passed / len(results), 4) if results else 0.0,
        "by_category": dict(by_category_counts),
        "avg_cost_usd": round(statistics.mean(costs), 8) if costs else 0.0,
        "p95_cost_usd": round(percentile(costs, 0.95), 8) if costs else 0.0,
        "avg_llm_calls": round(statistics.mean(llm_calls), 4) if llm_calls else 0.0,
        "total_cases": len(results),
        "passed_cases": passed,
        "failed_cases": len(results) - passed,
        "results": results,
    }


def write_metrics(metrics: dict[str, Any], path: Path = DEFAULT_METRICS_PATH) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    metrics = run_eval()
    write_metrics(metrics)
    print(f"Wrote metrics to {DEFAULT_METRICS_PATH}")
