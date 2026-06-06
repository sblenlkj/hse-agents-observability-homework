"""Baseline agent logic for HSE Agents homework.

This module is a plain-Python version of the naive agent from ``starter.ipynb``.
It intentionally keeps the baseline vulnerabilities and limitations because Part 1
and Part 2 need a faithful baseline before we add tracing, evals, optimizations,
and security hardening.
"""

from __future__ import annotations

import json
import re
from typing import Any

from fixtures.films import FILMS
from fixtures.schedule import SCHEDULE, all_seat_codes
from fixtures.users import POLICIES, USERS


USE_REAL_API = False


PRICING: dict[str, dict[str, float]] = {
    "small": {"input": 0.25, "output": 1.25, "cache_read": 0.03},
    "large": {"input": 3.00, "output": 15.00, "cache_read": 0.30},
}


def count_tokens(text: Any) -> int:
    """Very rough token estimate: 1 token ≈ 4 characters.

    This mirrors the starter/seminar approach. In production, use the provider's
    tokenizer; for this homework, deterministic approximate accounting is enough.
    """
    if isinstance(text, str):
        return max(1, len(text) // 4)
    if isinstance(text, list):
        return sum(count_tokens(item) for item in text)
    if isinstance(text, dict):
        return count_tokens(json.dumps(text, ensure_ascii=False))
    return 1


def cost_of(
    model: str,
    in_tokens: int,
    out_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Calculate approximate LLM cost in USD."""
    prices = PRICING[model]
    paid_in = max(0, in_tokens - cached_tokens)

    return (
        paid_in * prices["input"] / 1_000_000
        + cached_tokens * prices["cache_read"] / 1_000_000
        + out_tokens * prices["output"] / 1_000_000
    )


class MockLLM:
    """Deterministic mock model for the cinema domain."""

    def __init__(self, model: str = "large") -> None:
        self.model = model

    def _intent(self, query: str) -> str:
        q = query.lower()

        film_mentioned = any(
            film["title"].lower().split(":")[0].strip() in q
            for film in FILMS
        )

        if any(
            word in q
            for word in ["заброн", "купить", "оформ", "хочу место", "забери", "возьм"]
        ):
            return "reserve"

        if any(
            word in q
            for word in ["свободн", "налич", "места", "сколько мест", "осталось"]
        ):
            return "check_seats"

        if (
            any(
                word in q
                for word in [
                    "идёт",
                    "сеанс",
                    "расписан",
                    "что показыва",
                    "что есть",
                    "что нового",
                    "посовет",
                    "хочу посмотр",
                    "найди",
                    "ищу",
                    "что-нибудь",
                    "что нибудь",
                    "билет",
                    "есть ли",
                ]
            )
            or film_mentioned
        ):
            return "search"

        if any(
            word in q
            for word in [
                "возврат",
                "оплат",
                "политик",
                "правил",
                "возраст",
                "0+",
                "6+",
                "12+",
                "16+",
                "18+",
            ]
        ):
            return "policy"

        if any(word in q for word in ["балл", "лояльн", "скидк", "бонус", "тир", "уровень"]):
            return "loyalty"

        return "chat"

    def _extract_search_filters(self, query: str) -> dict[str, str]:
        q = query.lower()
        filters: dict[str, str] = {}

        for genre_stem in [
            "фантастик",
            "драм",
            "ужас",
            "анимаци",
            "комеди",
            "семейн",
            "боевик",
            "мелодрам",
        ]:
            if genre_stem in q:
                filters["genre_stem"] = genre_stem
                break

        if "сегодня" in q or "вечер" in q:
            filters["date"] = "today"
        elif "завтра" in q:
            filters["date"] = "tomorrow"
        elif "послезавтра" in q or "после завтра" in q:
            filters["date"] = "day_after"

        return filters

    def _extract_showing(self, query: str) -> dict[str, Any]:
        """Extract film/time/date/seats from a free-form Russian query."""
        q = query.lower()
        result: dict[str, Any] = {}

        for film in FILMS:
            title_stem = film["title"].lower().split(":")[0].strip()
            if title_stem in q:
                result["film_id"] = film["id"]
                break

        time_match = re.search(r"(\d{1,2}):(\d{2})", q)
        if time_match:
            result["time"] = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"

        if "сегодня" in q:
            result["date"] = "today"
        elif "завтра" in q:
            result["date"] = "tomorrow"

        count_match = re.search(r"(\d+)\s*(мест|билет)", q)
        if count_match:
            result["count"] = int(count_match.group(1))
        elif "два" in q or "две" in q:
            result["count"] = 2
        elif "три" in q:
            result["count"] = 3

        return result

    def call(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, str]] | None = None,
        max_tokens: int = 1000,
        cache_static: bool = False,
    ) -> dict[str, Any]:
        last = messages[-1]

        in_text = (
            system
            + json.dumps(messages, ensure_ascii=False)
            + json.dumps(tools or [], ensure_ascii=False)
        )
        in_tokens = count_tokens(in_text)
        cached_tokens = count_tokens(system) + count_tokens(tools or []) if cache_static else 0

        if last["role"] == "user":
            response = self._handle_user_message(
                content=str(last["content"]),
                tools=tools,
            )
        elif last["role"] == "tool":
            response = self._handle_tool_message(last["content"])
        else:
            response = {
                "type": "final",
                "text": "Чем могу помочь?",
            }

        out_text = json.dumps(response, ensure_ascii=False)
        out_tokens = min(count_tokens(out_text), max_tokens)

        return {
            "content": response,
            "usage": {
                "input_tokens": in_tokens,
                "cached_tokens": cached_tokens,
                "output_tokens": out_tokens,
            },
            "model": self.model,
        }

    def _handle_user_message(
        self,
        *,
        content: str,
        tools: list[dict[str, str]] | None,
    ) -> dict[str, Any]:
        intent = self._intent(content)

        if intent == "search" and tools:
            filters = self._extract_search_filters(content)
            return {
                "type": "tool_call",
                "name": "search_showings",
                "args": filters,
            }

        if intent == "check_seats" and tools:
            showing = self._extract_showing(content)
            showing_id_match = re.search(r"s\d{3}", content.lower())
            showing_id = showing_id_match.group(0) if showing_id_match else showing.get("film_id", "auto")
            return {
                "type": "tool_call",
                "name": "check_seats",
                "args": {"showing_id": showing_id},
            }

        if intent == "reserve" and tools:
            showing = self._extract_showing(content)
            target = None

            for item in SCHEDULE:
                if item.get("film_id") != showing.get("film_id"):
                    continue
                if showing.get("time") and item["time"] != showing["time"]:
                    continue
                if showing.get("date") and item["date"] != showing["date"]:
                    continue

                target = item
                break

            showing_id = target["id"] if target else "s001"
            count = showing.get("count", 1)
            taken = set(target["seats_taken"]) if target else set()
            seats = [code for code in all_seat_codes() if code not in taken][:count]

            return {
                "type": "tool_call",
                "name": "reserve_seats",
                "args": {
                    "showing_id": showing_id,
                    "seats": seats,
                    "user_id": "current",
                },
            }

        if intent == "policy" and tools:
            topic = "общие правила"
            q = content.lower()

            for key in ["возврат", "оплат", "возраст", "лояльн"]:
                if key in q:
                    topic = next(policy_key for policy_key in POLICIES if key in policy_key)
                    break

            return {
                "type": "tool_call",
                "name": "lookup_policy",
                "args": {"topic": topic},
            }

        if intent == "loyalty" and tools:
            return {
                "type": "tool_call",
                "name": "check_loyalty",
                "args": {"user_id": "current"},
            }

        return {
            "type": "final",
            "text": (
                "Чем могу помочь? Я помогу подобрать сеанс, проверить наличие мест, "
                "оформить бронь или рассказать про правила."
            ),
        }

    def _handle_tool_message(self, tool_result: Any) -> dict[str, str]:
        if isinstance(tool_result, dict) and tool_result.get("status") == "ok":
            data = tool_result.get("data")

            if isinstance(data, list) and data:
                parts = []
                for item in data[:5]:
                    if "title" in item and "time" in item:
                        parts.append(
                            f"«{item['title']}» {item.get('date', '')} "
                            f"в {item['time']} ({item.get('price', '?')}₽)"
                        )
                    else:
                        parts.append(str(item))

                text = "Нашёл: " + "; ".join(parts)

            elif isinstance(data, dict):
                if "seats" in data and "showing_id" in data:
                    text = (
                        f"Готово. Забронировано: {data['seats']} "
                        f"на сеанс {data['showing_id']}. "
                        f"Итого: {data.get('total_price', '?')}₽."
                    )
                elif "tier" in data:
                    text = (
                        f"Уровень: {data.get('tier')}, "
                        f"баллов: {data.get('points')}, "
                        f"скидка: {data.get('discount_pct')}%."
                    )
                elif "available" in data:
                    seats = data.get("available", [])
                    seats_left = data.get("seats_left", len(seats))
                    text = f"Свободно мест: {seats_left}. Примеры мест: {seats[:6]}"
                else:
                    text = str(data)

            else:
                text = str(data)

            return {
                "type": "final",
                "text": text,
            }

        if isinstance(tool_result, dict) and tool_result.get("status") == "error":
            return {
                "type": "final",
                "text": f"Не получилось: {tool_result.get('error', 'ошибка')}.",
            }

        return {
            "type": "final",
            "text": str(tool_result),
        }


def real_llm_call(
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, str]] | None,
    max_tokens: int,
    cache_static: bool,
    model: str = "large",
) -> dict[str, Any]:
    raise NotImplementedError("Подключите свой API-провайдер здесь.")


def llm_call(
    messages: list[dict[str, Any]],
    system: str = "",
    tools: list[dict[str, str]] | None = None,
    max_tokens: int = 1000,
    cache_static: bool = False,
    model: str = "large",
) -> dict[str, Any]:
    if USE_REAL_API:
        return real_llm_call(messages, system, tools, max_tokens, cache_static, model)

    return MockLLM(model=model).call(
        messages=messages,
        system=system,
        tools=tools,
        max_tokens=max_tokens,
        cache_static=cache_static,
    )


def search_showings(
    genre_stem: str = "",
    date: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Search showings by genre and/or date.

    With no filters, returns today's showings.
    """
    if not date and not genre_stem:
        date = "today"

    film_by_id = {film["id"]: film for film in FILMS}
    hits = []

    for showing in SCHEDULE:
        if date and showing["date"] != date:
            continue

        film = film_by_id.get(showing["film_id"])
        if not film:
            continue

        if genre_stem and genre_stem not in film["genre"]:
            continue

        hits.append(
            {
                "showing_id": showing["id"],
                "film_id": film["id"],
                "title": film["title"],
                "rating": film["rating"],
                "genre": film["genre"],
                "date": showing["date"],
                "time": showing["time"],
                "hall": showing["hall"],
                "price": showing["price"],
                "seats_left": showing["seats_left"],
            }
        )

    return {"status": "ok", "data": hits}


def check_seats(showing_id: str, **kwargs: Any) -> dict[str, Any]:
    """Return available seats for a showing."""
    for showing in SCHEDULE:
        if showing["id"] == showing_id:
            taken = set(showing["seats_taken"])
            available = [code for code in all_seat_codes() if code not in taken]

            return {
                "status": "ok",
                "data": {
                    "showing_id": showing["id"],
                    "seats_left": showing["seats_left"],
                    "available": available[:10],
                    "total_available": len(available),
                },
            }

    return {"status": "error", "error": f"сеанс {showing_id} не найден"}


def reserve_seats(
    showing_id: str,
    seats: list[str],
    user_id: str = "current",
    **kwargs: Any,
) -> dict[str, Any]:
    """Reserve seats.

    Intentionally vulnerable baseline:
    - arbitrary ``user_id`` is accepted;
    - age restrictions are not checked;
    - arbitrary ``price`` can be passed through ``kwargs``.
    """
    for showing in SCHEDULE:
        if showing["id"] == showing_id:
            taken = set(showing["seats_taken"])
            conflicts = [seat for seat in seats if seat in taken]

            if conflicts:
                return {
                    "status": "error",
                    "error": f"места уже заняты: {conflicts}",
                }

            override_price = kwargs.get("price")
            unit_price = override_price if override_price is not None else showing["price"]
            total = unit_price * len(seats)

            order_id = f"ord-{showing_id}-{len(showing['seats_taken']) + len(seats):03d}"

            return {
                "status": "ok",
                "data": {
                    "order_id": order_id,
                    "showing_id": showing["id"],
                    "seats": seats,
                    "user_id": user_id,
                    "total_price": total,
                },
            }

    return {"status": "error", "error": f"сеанс {showing_id} не найден"}


def lookup_policy(topic: str, **kwargs: Any) -> dict[str, Any]:
    """Return cinema policy text.

    Intentionally vulnerable baseline: some policy text may contain prompt
    injection artifacts and must be sanitized only in the final agent.
    """
    for key, value in POLICIES.items():
        if key in topic.lower():
            return {"status": "ok", "data": value}

    return {"status": "ok", "data": POLICIES["общие правила"]}


def check_loyalty(user_id: str = "current", **kwargs: Any) -> dict[str, Any]:
    """Return loyalty profile for a user."""
    info = USERS.get(user_id)

    if not info:
        return {"status": "error", "error": f"пользователь {user_id} не найден"}

    return {
        "status": "ok",
        "data": {
            "user_id": user_id,
            "tier": info["tier"],
            "points": info["points"],
            "discount_pct": info["discount_pct"],
        },
    }


TOOLS = {
    "search_showings": search_showings,
    "check_seats": check_seats,
    "reserve_seats": reserve_seats,
    "lookup_policy": lookup_policy,
    "check_loyalty": check_loyalty,
}


TOOL_SCHEMAS = [
    {"name": "search_showings", "description": "Поиск сеансов по жанру и/или дате"},
    {"name": "check_seats", "description": "Свободные места на сеансе"},
    {"name": "reserve_seats", "description": "Бронирование мест"},
    {"name": "lookup_policy", "description": "Политики кинотеатра"},
    {"name": "check_loyalty", "description": "Статус лояльности пользователя"},
]


SYSTEM_PROMPT = """Ты консультант сети кинотеатров «Кадр».
Помогаешь подбирать сеансы, проверять наличие мест, бронировать билеты, рассказывать про правила и лояльность.

Используй tools для получения актуальной информации:
- search_showings — поиск сеансов
- check_seats — проверка свободных мест
- reserve_seats — бронирование
- lookup_policy — политики кинотеатра
- check_loyalty — статус лояльности

Отвечай по-русски, по делу, дружелюбно."""


def run_agent_naive(user_query: str, max_iterations: int = 8) -> str:
    """Run the naive baseline agent."""
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_query}]

    for _ in range(max_iterations):
        response = llm_call(
            messages=messages,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
        )
        content = response["content"]

        if content["type"] == "final":
            return str(content["text"])

        if content["type"] == "tool_call":
            tool_name = content["name"]
            tool_args = content["args"]

            tool_fn = TOOLS.get(tool_name)
            if not tool_fn:
                tool_result = {
                    "status": "error",
                    "error": f"неизвестный tool {tool_name}",
                }
            else:
                try:
                    tool_result = tool_fn(**tool_args)
                except TypeError as exc:
                    tool_result = {"status": "error", "error": str(exc)}

            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "tool", "content": tool_result})

    return "Не удалось сформулировать ответ за отведённое число шагов."


if __name__ == "__main__":
    demo_queries = [
        "Что идёт сегодня вечером?",
        "Есть ли свободные места на s001?",
        "Забронируй два места на «Дюну» на 21:00 сегодня",
        "Какая политика возврата?",
        "Сколько у меня баллов лояльности?",
        "Привет, ты кто?",
    ]

    for query in demo_queries:
        print(f"👤 {query}")
        print(f"🤖 {run_agent_naive(query)}")
        print()
