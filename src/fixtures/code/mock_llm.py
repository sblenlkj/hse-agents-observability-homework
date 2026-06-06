import json
import re

from fixtures.films import FILMS
from fixtures.schedule import SCHEDULE, hall_capacity, all_seat_codes
from fixtures.users import USERS, POLICIES

from .pricing import count_tokens

USE_REAL_API = False

class MockLLM:
    """Детерминированный двойник модели для домена кино."""

    def __init__(self, model: str = "large"):
        self.model = model

    def _intent(self, query: str) -> str:
        q = query.lower()
        # упоминание конкретного фильма → почти всегда поиск или бронирование
        film_mentioned = any(f["title"].lower().split(":")[0].strip() in q for f in FILMS)

        if any(w in q for w in ["заброн", "купить", "оформ", "хочу место", "забери", "возьм"]):
            return "reserve"
        if any(w in q for w in ["свободн", "налич", "места", "сколько мест", "осталось"]):
            return "check_seats"
        if any(w in q for w in ["идёт", "сеанс", "расписан", "что показыва", "что есть", "что нового",
                                  "посовет", "хочу посмотр", "найди", "ищу", "что-нибудь", "что нибудь",
                                  "билет", "есть ли"]) or film_mentioned:
            return "search"
        if any(w in q for w in ["возврат", "оплат", "политик", "правил", "возраст", "0+", "6+", "12+", "16+", "18+"]):
            return "policy"
        if any(w in q for w in ["балл", "лояльн", "скидк", "бонус", "тир", "уровень"]):
            return "loyalty"
        return "chat"

    def _extract_search_filters(self, query: str) -> dict:
        q = query.lower()
        filters = {}
        # жанр
        for g in ["фантастик", "драм", "ужас", "анимаци", "комеди", "семейн", "боевик", "мелодрам"]:
            if g in q:
                filters["genre_stem"] = g
                break
        # дата
        if "сегодня" in q or "вечер" in q:
            filters["date"] = "today"
        elif "завтра" in q:
            filters["date"] = "tomorrow"
        elif "послезавтра" in q or "после завтра" in q:
            filters["date"] = "day_after"
        return filters

    def _extract_showing(self, query: str) -> dict:
        """Пытается вытащить film/time/seats из текста."""
        q = query.lower()
        out = {}
        # фильм по части названия
        for f in FILMS:
            title_stem = f["title"].lower().split(":")[0].strip()
            if title_stem in q:
                out["film_id"] = f["id"]
                break
        # время
        m = re.search(r"(\d{1,2}):(\d{2})", q)
        if m:
            out["time"] = f"{int(m.group(1)):02d}:{m.group(2)}"
        # дата
        if "сегодня" in q:
            out["date"] = "today"
        elif "завтра" in q:
            out["date"] = "tomorrow"
        # количество мест
        m = re.search(r"(\d+)\s*(мест|билет)", q)
        if m:
            out["count"] = int(m.group(1))
        elif "два" in q or "две" in q:
            out["count"] = 2
        elif "три" in q:
            out["count"] = 3
        return out

    def call(self, messages, system="", tools=None, max_tokens=1000, cache_static=False):
        last = messages[-1]

        in_text = system + json.dumps(messages, ensure_ascii=False) + json.dumps(tools or [], ensure_ascii=False)
        in_tokens = count_tokens(in_text)
        cached_tokens = count_tokens(system) + count_tokens(tools or []) if cache_static else 0

        if last["role"] == "user":
            intent = self._intent(last["content"])
            if intent == "search" and tools:
                filters = self._extract_search_filters(last["content"])
                response = {"type": "tool_call", "name": "search_showings", "args": filters}
            elif intent == "check_seats" and tools:
                showing = self._extract_showing(last["content"])
                # достаём showing_id если есть
                m = re.search(r"s\d{3}", last["content"].lower())
                sid = m.group(0) if m else showing.get("film_id", "auto")
                response = {"type": "tool_call", "name": "check_seats", "args": {"showing_id": sid}}
            elif intent == "reserve" and tools:
                showing = self._extract_showing(last["content"])
                # выбираем первый попавшийся сеанс этого фильма
                target = None
                for s in SCHEDULE:
                    if s.get("film_id") == showing.get("film_id"):
                        if showing.get("time") and s["time"] != showing["time"]:
                            continue
                        if showing.get("date") and s["date"] != showing["date"]:
                            continue
                        target = s
                        break
                sid = target["id"] if target else "s001"
                count = showing.get("count", 1)
                # подбираем первые свободные места
                taken = set(target["seats_taken"]) if target else set()
                seats = [c for c in all_seat_codes() if c not in taken][:count]
                response = {"type": "tool_call", "name": "reserve_seats",
                          "args": {"showing_id": sid, "seats": seats, "user_id": "current"}}
            elif intent == "policy" and tools:
                topic = "общие правила"
                q = last["content"].lower()
                for key in ["возврат", "оплат", "возраст", "лояльн"]:
                    if key in q:
                        topic = next(k for k in POLICIES if key in k)
                        break
                response = {"type": "tool_call", "name": "lookup_policy", "args": {"topic": topic}}
            elif intent == "loyalty" and tools:
                response = {"type": "tool_call", "name": "check_loyalty", "args": {"user_id": "current"}}
            else:
                response = {"type": "final", "text": "Чем могу помочь? Я помогу подобрать сеанс, проверить наличие мест, оформить бронь или рассказать про правила."}

        elif last["role"] == "tool":
            tool_result = last["content"]
            if isinstance(tool_result, dict) and tool_result.get("status") == "ok":
                data = tool_result.get("data")
                if isinstance(data, list) and data:
                    parts = []
                    for x in data[:5]:
                        if "title" in x and "time" in x:
                            parts.append(f"«{x['title']}» {x.get('date','')} в {x['time']} ({x.get('price','?')}₽)")
                        else:
                            parts.append(str(x))
                    txt = "Нашёл: " + "; ".join(parts)
                elif isinstance(data, dict):
                    if "seats" in data and "showing_id" in data:
                        txt = f"Готово. Забронировано: {data['seats']} на сеанс {data['showing_id']}. Итого: {data.get('total_price','?')}₽."
                    elif "tier" in data:
                        txt = f"Уровень: {data.get('tier')}, баллов: {data.get('points')}, скидка: {data.get('discount_pct')}%."
                    elif "available" in data:
                        seats = data.get("available", [])
                        n = data.get("seats_left", len(seats))
                        txt = f"Свободно мест: {n}. Примеры мест: {seats[:6]}"
                    else:
                        txt = str(data)
                else:
                    txt = str(data)
                response = {"type": "final", "text": txt}
            elif isinstance(tool_result, dict) and tool_result.get("status") == "error":
                response = {"type": "final", "text": f"Не получилось: {tool_result.get('error', 'ошибка')}."}
            else:
                response = {"type": "final", "text": str(tool_result)}
        else:
            response = {"type": "final", "text": "Чем могу помочь?"}

        out_text = json.dumps(response, ensure_ascii=False)
        out_tokens = min(count_tokens(out_text), max_tokens)

        return {
            "content": response,
            "usage": {"input_tokens": in_tokens, "cached_tokens": cached_tokens, "output_tokens": out_tokens},
            "model": self.model,
        }


def real_llm_call(messages, system, tools, max_tokens, cache_static, model="large"):
    raise NotImplementedError("Подключите свой API-провайдер здесь.")


def llm_call(messages, system="", tools=None, max_tokens=1000, cache_static=False, model="large"):
    if USE_REAL_API:
        return real_llm_call(messages, system, tools, max_tokens, cache_static, model)
    return MockLLM(model=model).call(messages, system, tools, max_tokens, cache_static)


# sanity check
test = llm_call(
    messages=[{"role": "user", "content": "что идёт сегодня вечером?"}],
    system="Ты консультант кинотеатра",
    tools=[{"name": "search_showings"}],
)
print("Test:", test["content"])
print("Usage:", test["usage"])