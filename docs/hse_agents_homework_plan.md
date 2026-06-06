# План выполнения домашнего задания по агенту «Кадр»

## Цель

Сделать компактное сдаваемое решение в `submission/` на основе семинара: наблюдаемость, golden dataset, eval-runner, финальный агент с оптимизациями и защитами.

## Целевая структура

```text
submission/
├── agent_observable.py
├── traces.json
├── golden_cases.yaml
├── eval_runner.py
├── metrics_baseline.json
├── agent_final.py
├── metrics_final.json
├── improvements.md
└── README.md
```

Данные задания используем из installable-пакета:

```python
from fixtures.films import FILMS
from fixtures.schedule import SCHEDULE
from fixtures.users import USERS
from fixtures.reference_queries import REFERENCE_QUERIES
```

---

## Этап 0. Подготовка проекта

Проверить, что есть:

```text
src/fixtures/
submission/
hw/grader.py
hw/homework.md
hw/starter.ipynb
```

Проверить импорты:

```bash
uv run python -c "from fixtures.films import FILMS; print(len(FILMS))"
uv run python -c "from fixtures.schedule import SCHEDULE; print(len(SCHEDULE))"
uv run python -c "from fixtures.users import USERS; print(len(USERS))"
uv run python -c "from fixtures.reference_queries import REFERENCE_QUERIES; print(len(REFERENCE_QUERIES))"
```

Если `fixtures.reference_queries` ещё нет — создать `src/fixtures/reference_queries.py` с 10 reference-запросами.

---

## Этап 1. Вынести baseline-логику из `starter.ipynb`

Изучить реальные контракты в `starter.ipynb` и воспроизвести в `.py`:

- `MockLLM`;
- `count_tokens`;
- `cost_of`;
- tools:
  - `search_showings`;
  - `check_seats`;
  - `reserve_seats`;
  - `lookup_policy`;
  - `check_loyalty`;
- простой ReAct-loop.

Notebook напрямую не импортировать. Решение должно быть обычным Python-кодом в `submission/`.

---

## Этап 2. Part 1 — Observability

Файл:

```text
submission/agent_observable.py
```

Нужно реализовать:

```python
def run_agent_observable(query: str) -> tuple[str, dict]:
    ...
```

Требования:

- каждый LLM-вызов — отдельный span;
- каждый tool-вызов — отдельный span;
- LLM-span содержит:
  - `gen_ai.system`;
  - `gen_ai.request.model`;
  - `gen_ai.usage.input_tokens`;
  - `gen_ai.usage.output_tokens`;
  - `gen_ai.usage.cached_tokens`;
  - `cost_usd`;
- tool-span содержит:
  - `tool.name`;
  - `tool.args`;
  - `error`;
- `duration_ms` должен быть положительным;
- root-span должен иметь children.

Сгенерировать:

```text
submission/traces.json
```

В нём должно быть ровно 10 root trace-объектов по `REFERENCE_QUERIES`.

Особая проверка: для запроса про бронирование двух мест на «Дюну» в 21:00 в trace должны быть вызовы:

```text
search_showings → check_seats → reserve_seats
```

Проверка:

```bash
uv run python hw/grader.py part1 submission
```

---

## Этап 3. Part 2 — Golden Dataset и eval-runner

Файлы:

```text
submission/golden_cases.yaml
submission/eval_runner.py
submission/metrics_baseline.json
```

Golden dataset:

- минимум 25 кейсов;
- минимум 10 `happy`;
- минимум 7 `edge`;
- минимум 8 `adversarial`.

Схема кейса:

```yaml
- id: h-01
  category: happy
  input: "Что идёт сегодня вечером?"
  must_call_tool: search_showings
  answer_contains_any:
    - "сеанс"
    - "сегодня"
  answer_must_not_contain:
    - "не знаю"
```

Adversarial-кейсы должны покрыть минимум три типа атак из шести:

- prompt injection;
- jailbreak;
- excessive agency;
- prompt leak;
- manipulation цен/скидок;
- indirect injection.

`eval_runner.py` должен:

1. читать `golden_cases.yaml`;
2. запускать baseline/observable-агента;
3. доставать called tools из trace;
4. проверять `must_call_tool`, `answer_contains_any`, `answer_must_not_contain`;
5. считать метрики:
   - `task_success_rate`;
   - `by_category`;
   - `avg_cost_usd`;
   - `p95_cost_usd`;
   - `avg_llm_calls`;
   - `total_cases`.

Проверка:

```bash
uv run python hw/grader.py part2 submission
```

---

## Этап 4. Part 3 — Финальный агент

Файлы:

```text
submission/agent_final.py
submission/metrics_final.json
submission/improvements.md
```

### Оптимизации

Внедрить минимум две техники. Наиболее безопасный набор:

1. prompt caching статической части;
2. output limit / краткие ответы;
3. semantic или exact cache для стабильных policy-запросов.

Model routing можно добавить, если удобно поддерживается `small/large`, но не ценой качества.

### Безопасность

Внедрить минимум три слоя, лучше четыре:

1. input filter против prompt injection / jailbreak / prompt leak / manipulation скидок;
2. data sanitization для результатов tools, особенно `lookup_policy`;
3. tool argument validation для `reserve_seats`;
4. output sanitization финального ответа.

Для `reserve_seats` обязательно валидировать:

- `user_id` нельзя брать произвольно из LLM args;
- нельзя передавать произвольную цену или скидку;
- сеанс должен существовать;
- места должны быть доступны;
- возрастное ограничение должно проходить проверку.

`improvements.md` должен содержать:

- таблицу baseline vs final;
- описание каждой оптимизации;
- описание каждого слоя защиты;
- какие атаки блокируются;
- ограничения подхода.

Проверка:

```bash
uv run python hw/grader.py part3 submission
```

---

## Этап 5. Финальная проверка

Полный прогон:

```bash
uv run python hw/grader.py all submission
```

После успешного прогона проверить:

- все требуемые файлы лежат в `submission/`;
- нет временных debug-файлов;
- `README.md` объясняет запуск;
- код можно объяснить на code-review;
- нет hard-code под конкретные видимые тесты грейдера.

---

## Рабочий порядок

```text
1. Инспектируем starter.ipynb и grader.py.
2. Проверяем/создаём fixtures.reference_queries.py.
3. Пишем agent_observable.py.
4. Генерируем traces.json.
5. Запускаем grader part1.
6. Пишем golden_cases.yaml.
7. Пишем eval_runner.py и metrics_baseline.json.
8. Запускаем grader part2.
9. Пишем agent_final.py.
10. Генерируем metrics_final.json и improvements.md.
11. Запускаем grader part3/all.
12. Чистим код и README.
```
