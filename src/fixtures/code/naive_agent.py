from fixtures.films import FILMS
from fixtures.schedule import SCHEDULE, hall_capacity, all_seat_codes
from fixtures.users import USERS, POLICIES

from .mock_llm import llm_call


def search_showings(genre_stem: str = "", date: str = "", **kwargs) -> dict:
    """Поиск сеансов по жанру и/или дате. Без фильтров — все сеансы на сегодня."""
    if not date and not genre_stem:
        date = "today"

    film_by_id = {f["id"]: f for f in FILMS}
    hits = []
    for s in SCHEDULE:
        if date and s["date"] != date:
            continue
        film = film_by_id.get(s["film_id"])
        if not film:
            continue
        if genre_stem and genre_stem not in film["genre"]:
            continue
        hits.append({
            "showing_id": s["id"],
            "film_id": film["id"],
            "title": film["title"],
            "rating": film["rating"],
            "genre": film["genre"],
            "date": s["date"],
            "time": s["time"],
            "hall": s["hall"],
            "price": s["price"],
            "seats_left": s["seats_left"],
        })
    return {"status": "ok", "data": hits}


def check_seats(showing_id: str, **kwargs) -> dict:
    """Возвращает свободные места на сеансе."""
    for s in SCHEDULE:
        if s["id"] == showing_id:
            taken = set(s["seats_taken"])
            available = [c for c in all_seat_codes() if c not in taken]
            return {"status": "ok", "data": {
                "showing_id": s["id"],
                "seats_left": s["seats_left"],
                "available": available[:10],   # первые 10 для краткости
                "total_available": len(available),
            }}
    return {"status": "error", "error": f"сеанс {showing_id} не найден"}


def reserve_seats(showing_id: str, seats: list, user_id: str = "current", **kwargs) -> dict:
    """
    Бронирует места.
    !!! УЯЗВИМОСТЬ (намеренно): не проверяется возраст пользователя vs рейтинг фильма.
    !!! УЯЗВИМОСТЬ (намеренно): user_id принимается каким угодно — нет проверки прав.
    !!! УЯЗВИМОСТЬ (намеренно): принимает **kwargs — можно прокинуть price=1 и т.п.
    Это всё надо исправить в agent_final.
    """
    for s in SCHEDULE:
        if s["id"] == showing_id:
            taken = set(s["seats_taken"])
            conflicts = [seat for seat in seats if seat in taken]
            if conflicts:
                return {"status": "error", "error": f"места уже заняты: {conflicts}"}

            # «обрабатываем» доп. параметры, если переданы (это уязвимость)
            override_price = kwargs.get("price")
            unit_price = override_price if override_price is not None else s["price"]
            total = unit_price * len(seats)

            order_id = f"ord-{showing_id}-{len(s['seats_taken'])+len(seats):03d}"
            return {"status": "ok", "data": {
                "order_id": order_id,
                "showing_id": s["id"],
                "seats": seats,
                "user_id": user_id,
                "total_price": total,
            }}
    return {"status": "error", "error": f"сеанс {showing_id} не найден"}


def lookup_policy(topic: str, **kwargs) -> dict:
    """
    Возвращает текст политики.
    !!! УЯЗВИМОСТЬ (намеренно): в политике «оплата» есть [SYSTEM NOTE] инъекция.
    Нужно отлавливать в data sanitization.
    """
    for key, val in POLICIES.items():
        if key in topic.lower():
            return {"status": "ok", "data": val}
    return {"status": "ok", "data": POLICIES["общие правила"]}


def check_loyalty(user_id: str = "current", **kwargs) -> dict:
    """Возвращает статус лояльности пользователя."""
    info = USERS.get(user_id)
    if not info:
        return {"status": "error", "error": f"пользователь {user_id} не найден"}
    return {"status": "ok", "data": {
        "user_id": user_id,
        "tier": info["tier"],
        "points": info["points"],
        "discount_pct": info["discount_pct"],
    }}


TOOLS = {
    "search_showings":  search_showings,
    "check_seats":      check_seats,
    "reserve_seats":    reserve_seats,
    "lookup_policy":    lookup_policy,
    "check_loyalty":    check_loyalty,
}

TOOL_SCHEMAS = [
    {"name": "search_showings",  "description": "Поиск сеансов по жанру и/или дате"},
    {"name": "check_seats",      "description": "Свободные места на сеансе"},
    {"name": "reserve_seats",    "description": "Бронирование мест"},
    {"name": "lookup_policy",    "description": "Политики кинотеатра"},
    {"name": "check_loyalty",    "description": "Статус лояльности пользователя"},
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
    """Самая простая версия. Это baseline — её надо обогнать в Part 3."""
    messages = [{"role": "user", "content": user_query}]

    for _ in range(max_iterations):
        resp = llm_call(messages=messages, system=SYSTEM_PROMPT, tools=TOOL_SCHEMAS)
        content = resp["content"]

        if content["type"] == "final":
            return content["text"]

        if content["type"] == "tool_call":
            tool_fn = TOOLS.get(content["name"])
            if not tool_fn:
                tool_result = {"status": "error", "error": f"неизвестный tool {content['name']}"}
            else:
                try:
                    tool_result = tool_fn(**content["args"])
                except TypeError as e:
                    tool_result = {"status": "error", "error": str(e)}
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "tool", "content": tool_result})  # type: ignore

    return "Не удалось сформулировать ответ за отведённое число шагов."