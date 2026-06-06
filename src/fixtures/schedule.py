"""Расписание сеансов на 3 ближайших дня в трёх залах. ~40 сеансов."""

# Структура зала: 5 рядов × 10 мест. Места обозначаются как "R1-S5"
# Сеанс: id, film_id, date (today/tomorrow/day_after), time, hall, price, seats_left

SCHEDULE = [
    # === TODAY ===
    {"id": "s001", "film_id": "f01", "date": "today",     "time": "10:00", "hall": 1, "price": 350, "seats_left": 42, "seats_taken": ["R3-S5", "R3-S6", "R5-S1", "R5-S2", "R1-S8", "R2-S4", "R4-S9", "R4-S10"]},
    {"id": "s002", "film_id": "f04", "date": "today",     "time": "10:30", "hall": 2, "price": 300, "seats_left": 38, "seats_taken": ["R1-S1", "R1-S2", "R2-S5", "R2-S6", "R3-S5", "R4-S3", "R5-S7", "R5-S8", "R3-S6", "R3-S7", "R4-S4", "R5-S9"]},
    {"id": "s003", "film_id": "f05", "date": "today",     "time": "11:00", "hall": 3, "price": 320, "seats_left": 45, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5"]},
    {"id": "s004", "film_id": "f02", "date": "today",     "time": "13:30", "hall": 1, "price": 450, "seats_left": 30, "seats_taken": ["R2-S5", "R2-S6", "R3-S5", "R3-S6", "R3-S7", "R3-S8", "R4-S5", "R4-S6", "R4-S7", "R4-S8", "R5-S4", "R5-S5", "R5-S6", "R5-S7", "R1-S5", "R1-S6", "R2-S7", "R2-S8", "R2-S9", "R5-S8"]},
    {"id": "s005", "film_id": "f08", "date": "today",     "time": "14:00", "hall": 2, "price": 380, "seats_left": 0,  "seats_taken": ["R1-S1","R1-S2","R1-S3","R1-S4","R1-S5","R1-S6","R1-S7","R1-S8","R1-S9","R1-S10","R2-S1","R2-S2","R2-S3","R2-S4","R2-S5","R2-S6","R2-S7","R2-S8","R2-S9","R2-S10","R3-S1","R3-S2","R3-S3","R3-S4","R3-S5","R3-S6","R3-S7","R3-S8","R3-S9","R3-S10","R4-S1","R4-S2","R4-S3","R4-S4","R4-S5","R4-S6","R4-S7","R4-S8","R4-S9","R4-S10","R5-S1","R5-S2","R5-S3","R5-S4","R5-S5","R5-S6","R5-S7","R5-S8","R5-S9","R5-S10"]},
    {"id": "s006", "film_id": "f11", "date": "today",     "time": "16:00", "hall": 3, "price": 350, "seats_left": 28, "seats_taken": ["R3-S5", "R3-S6", "R3-S7", "R3-S8", "R4-S5", "R4-S6", "R4-S7", "R4-S8", "R5-S5", "R5-S6", "R5-S7", "R5-S8", "R2-S5", "R2-S6", "R1-S5", "R1-S6", "R2-S7", "R2-S8", "R3-S9", "R4-S9", "R5-S9", "R5-S10"]},
    {"id": "s007", "film_id": "f01", "date": "today",     "time": "18:00", "hall": 1, "price": 500, "seats_left": 25, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R1-S5", "R1-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R2-S7", "R2-S8", "R3-S9", "R4-S9", "R5-S9", "R2-S9", "R2-S10", "R1-S7", "R1-S8"]},
    {"id": "s008", "film_id": "f07", "date": "today",     "time": "21:00", "hall": 2, "price": 450, "seats_left": 35, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R2-S7"]},
    {"id": "s009", "film_id": "f06", "date": "today",     "time": "19:30", "hall": 3, "price": 480, "seats_left": 22, "seats_taken": ["R3-S5", "R3-S6", "R3-S7", "R3-S8", "R4-S5", "R4-S6", "R4-S7", "R4-S8", "R5-S5", "R5-S6", "R5-S7", "R5-S8", "R2-S5", "R2-S6", "R2-S7", "R2-S8", "R1-S5", "R1-S6", "R5-S9", "R5-S10", "R1-S7", "R1-S8", "R4-S9", "R4-S10", "R3-S9", "R3-S10", "R2-S9", "R2-S10"]},

    # === TOMORROW ===
    {"id": "s010", "film_id": "f15", "date": "tomorrow",  "time": "11:00", "hall": 2, "price": 320, "seats_left": 48, "seats_taken": ["R5-S5", "R5-S6"]},
    {"id": "s011", "film_id": "f10", "date": "tomorrow",  "time": "12:30", "hall": 3, "price": 280, "seats_left": 42, "seats_taken": ["R3-S5", "R3-S6", "R3-S7", "R3-S8", "R4-S5", "R4-S6", "R4-S7", "R4-S8"]},
    {"id": "s012", "film_id": "f03", "date": "tomorrow",  "time": "14:00", "hall": 1, "price": 400, "seats_left": 38, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R5-S7", "R5-S8", "R2-S5", "R2-S6", "R2-S7", "R2-S8"]},
    {"id": "s013", "film_id": "f12", "date": "tomorrow",  "time": "15:30", "hall": 2, "price": 380, "seats_left": 32, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R2-S7", "R2-S8", "R1-S5", "R1-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8"]},
    {"id": "s014", "film_id": "f02", "date": "tomorrow",  "time": "17:00", "hall": 3, "price": 480, "seats_left": 25, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R2-S7", "R1-S5", "R1-S6", "R5-S9", "R5-S10", "R2-S8", "R3-S9", "R4-S9", "R3-S10", "R4-S10", "R2-S9"]},
    {"id": "s015", "film_id": "f01", "date": "tomorrow",  "time": "19:00", "hall": 1, "price": 500, "seats_left": 15, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R1-S5", "R1-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R2-S7", "R2-S8", "R1-S7", "R1-S8", "R3-S9", "R4-S9", "R5-S9", "R2-S9", "R1-S9", "R3-S10", "R4-S10", "R5-S10", "R2-S10", "R1-S10", "R3-S1", "R4-S1", "R5-S1", "R2-S1", "R1-S1"]},
    {"id": "s016", "film_id": "f08", "date": "tomorrow",  "time": "20:00", "hall": 2, "price": 400, "seats_left": 30, "seats_taken": ["R3-S5", "R3-S6", "R3-S7", "R3-S8", "R4-S5", "R4-S6", "R4-S7", "R4-S8", "R5-S5", "R5-S6", "R5-S7", "R5-S8", "R2-S5", "R2-S6", "R2-S7", "R2-S8", "R1-S5", "R1-S6", "R5-S9", "R5-S10"]},
    {"id": "s017", "film_id": "f09", "date": "tomorrow",  "time": "21:30", "hall": 3, "price": 450, "seats_left": 28, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R1-S5", "R1-S6", "R2-S7", "R2-S8", "R1-S7", "R1-S8", "R3-S9", "R5-S9"]},
    {"id": "s018", "film_id": "f07", "date": "tomorrow",  "time": "22:00", "hall": 1, "price": 450, "seats_left": 35, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R1-S5"]},
    {"id": "s019", "film_id": "f14", "date": "tomorrow",  "time": "22:30", "hall": 2, "price": 480, "seats_left": 40, "seats_taken": ["R3-S5", "R3-S6", "R3-S7", "R3-S8", "R4-S5", "R4-S6", "R4-S7", "R4-S8", "R5-S5", "R5-S6"]},

    # === DAY AFTER TOMORROW ===
    {"id": "s020", "film_id": "f04", "date": "day_after", "time": "10:00", "hall": 1, "price": 300, "seats_left": 45, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5"]},
    {"id": "s021", "film_id": "f05", "date": "day_after", "time": "11:30", "hall": 2, "price": 320, "seats_left": 42, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R2-S5", "R2-S6", "R1-S5"]},
    {"id": "s022", "film_id": "f13", "date": "day_after", "time": "13:00", "hall": 3, "price": 380, "seats_left": 38, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R2-S5", "R2-S6", "R1-S5", "R3-S7", "R3-S8", "R4-S7", "R4-S8"]},
    {"id": "s023", "film_id": "f11", "date": "day_after", "time": "14:30", "hall": 1, "price": 350, "seats_left": 35, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R1-S5"]},
    {"id": "s024", "film_id": "f12", "date": "day_after", "time": "16:00", "hall": 2, "price": 380, "seats_left": 32, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R1-S5", "R1-S6", "R2-S7", "R2-S8"]},
    {"id": "s025", "film_id": "f06", "date": "day_after", "time": "17:30", "hall": 3, "price": 480, "seats_left": 22, "seats_taken": ["R3-S5", "R3-S6", "R3-S7", "R3-S8", "R4-S5", "R4-S6", "R4-S7", "R4-S8", "R5-S5", "R5-S6", "R5-S7", "R5-S8", "R2-S5", "R2-S6", "R2-S7", "R2-S8", "R1-S5", "R1-S6", "R5-S9", "R5-S10", "R1-S7", "R1-S8", "R4-S9", "R4-S10", "R3-S9", "R3-S10", "R2-S9", "R2-S10"]},
    {"id": "s026", "film_id": "f01", "date": "day_after", "time": "19:00", "hall": 1, "price": 500, "seats_left": 18, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R1-S5", "R1-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R2-S7", "R2-S8", "R1-S7", "R1-S8", "R3-S9", "R4-S9", "R5-S9", "R2-S9", "R1-S9", "R3-S10", "R4-S10", "R5-S10", "R2-S10", "R1-S10", "R3-S1", "R4-S1"]},
    {"id": "s027", "film_id": "f02", "date": "day_after", "time": "20:00", "hall": 2, "price": 480, "seats_left": 28, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R2-S7", "R1-S5", "R1-S6", "R5-S9", "R5-S10", "R3-S9", "R4-S9", "R2-S8"]},
    {"id": "s028", "film_id": "f09", "date": "day_after", "time": "21:30", "hall": 3, "price": 450, "seats_left": 30, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R2-S7", "R2-S8", "R1-S5", "R1-S6", "R3-S9", "R4-S9"]},
    {"id": "s029", "film_id": "f14", "date": "day_after", "time": "22:00", "hall": 1, "price": 480, "seats_left": 38, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8"]},
    {"id": "s030", "film_id": "f07", "date": "day_after", "time": "22:30", "hall": 2, "price": 450, "seats_left": 35, "seats_taken": ["R3-S5", "R3-S6", "R4-S5", "R4-S6", "R5-S5", "R5-S6", "R2-S5", "R2-S6", "R3-S7", "R3-S8", "R4-S7", "R4-S8", "R5-S7", "R5-S8", "R1-S5"]},
]


def hall_capacity(hall_id: int) -> int:
    """Все три зала одинаковы — 5 рядов × 10 мест = 50."""
    return 50


def all_seat_codes() -> list[str]:
    """Возвращает все 50 возможных кодов места в зале."""
    return [f"R{r}-S{s}" for r in range(1, 6) for s in range(1, 11)]
