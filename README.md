# Production AI-агент «Кадр»

Это решение для домашнего задания по production-ready AI-агенту сети кинотеатров «Кадр».

Задание требует три основные части:

1. **Observability** — добавить трейсинг LLM/tool-вызовов и сохранить `traces.json`.
2. **Evaluation** — собрать golden dataset, написать eval-runner и посчитать baseline-метрики.
3. **Final agent** — добавить оптимизации стоимости и защитные слои, затем посчитать финальные метрики.

Текущая видимая проверка грейдера проходит:

```text
Part 1 · Observability: 25/25
Part 2 · Evaluation:    25/25
Part 3 · Visible:       22/50
Visible total:          72/100
```

Оставшиеся баллы Part 3 проверяются преподавательским hidden test set.

---

## 1. Структура проекта

Основная рабочая структура:

```text
src/
├── fixtures/
│   ├── films.py
│   ├── schedule.py
│   ├── users.py
│   └── reference_queries.py
└── submission/
    ├── __init__.py
    ├── baseline_agent.py
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

`fixtures` и `submission` являются Python-пакетами внутри `src`, поэтому код запускается через `python -m ...` и использует нормальные импорты без `sys.path`-хаков.

---

## 2. Что лежит в основных файлах

### `baseline_agent.py`

Наивный baseline-агент, вынесенный из `starter.ipynb` в обычный Python-модуль.

Содержит:

- `MockLLM`;
- расчёт токенов и стоимости;
- tools: `search_showings`, `check_seats`, `reserve_seats`, `lookup_policy`, `check_loyalty`;
- простой ReAct-loop.

Этот агент нужен как точка отсчёта. Он намеренно оставляет проблемы starter-версии: нет полноценной безопасности, есть ошибки intent-routing, `reserve_seats` недостаточно защищён, `lookup_policy` не очищается от потенциально опасных вставок.

### `agent_observable.py`

Observable-версия baseline-агента.

Закрывает Part 1 задания:

- создаёт root-span `agent.run`;
- пишет отдельные span-ы для каждого LLM-вызова;
- пишет отдельные span-ы для каждого tool-вызова;
- добавляет обязательные `gen_ai.*` атрибуты;
- считает `cost_usd`;
- генерирует `traces.json` для 10 reference-запросов.

### `traces.json`

Массив из 10 trace-объектов для Part 1.

Грейдер проверяет:

- что JSON парсится;
- что в нём ровно 10 трейсов;
- что структура span-ов корректна;
- что LLM-span-ы содержат `gen_ai.*`;
- что стоимость сходится с пересчётом;
- что в бронировании видна цепочка `search_showings → check_seats → reserve_seats`.

### `golden_cases.yaml`

Golden dataset для Part 2.

Содержит 28 кейсов:

- 11 happy cases;
- 8 edge cases;
- 9 adversarial cases.

Adversarial-кейсы покрывают шесть типов атак:

- prompt injection;
- jailbreak;
- excessive agency;
- prompt leak;
- price manipulation;
- indirect injection.

### `eval_runner.py`

Eval-runner для проверки агента на `golden_cases.yaml`.

Он:

1. читает датасет;
2. запускает агента;
3. достаёт вызванные tools из trace;
4. проверяет `must_call_tool`, `answer_contains_any`, `answer_must_not_contain`;
5. считает метрики качества, стоимости и количества LLM-вызовов.

### `metrics_baseline.json`

Метрики baseline-агента на golden dataset.

Текущие основные значения:

```json
{
  "task_success_rate": 0.5357,
  "happy": "9/11",
  "edge": "4/8",
  "adversarial": "2/9",
  "avg_cost_usd": 0.00230314,
  "p95_cost_usd": 0.003843,
  "avg_llm_calls": 1.7857
}
```

### `agent_final.py`

Финальная версия агента для Part 3.

Сохраняет ReAct-подход для обычных tool-сценариев:

```text
LLM → tool → LLM final
```

При этом добавляет production-слои:

- prompt cache accounting;
- model routing / cheaper model accounting;
- `max_tokens` как заготовку под реальный LLM API;
- input filter для adversarial-запросов;
- data sanitization для `lookup_policy`;
- tool argument validation для `reserve_seats`;
- output sanitization;
- безопасную preflight-цепочку для бронирования.

### `metrics_final.json`

Метрики финального агента на том же golden dataset.

Текущие основные значения:

```json
{
  "task_success_rate": 0.8929,
  "happy": "10/11",
  "edge": "6/8",
  "adversarial": "9/9",
  "avg_cost_usd": 0.00007994,
  "p95_cost_usd": 0.00023934,
  "avg_llm_calls": 1.25
}
```

### `improvements.md`

Описание изменений финального агента.

Содержит:

- таблицу baseline vs final;
- описание оптимизаций;
- описание защит;
- конкретные провалы baseline-а;
- объяснение trade-offs и ограничений;
- команды для воспроизведения метрик.

---

## 3. Как установить зависимости

Из корня проекта:

```bash
uv sync
```

Проверка импортов:

```bash
uv run python -c "from fixtures.films import FILMS; print(len(FILMS))"
uv run python -c "from fixtures.schedule import SCHEDULE; print(len(SCHEDULE))"
uv run python -c "from fixtures.users import USERS; print(len(USERS))"
uv run python -c "from fixtures.reference_queries import REFERENCE_QUERIES; print(len(REFERENCE_QUERIES))"
```

Ожидаемые значения:

```text
15
30
4
10
```

---

## 4. Как запускать

### 4.1. Baseline-agent

```bash
uv run python -m submission.baseline_agent
```

### 4.2. Сгенерировать `traces.json`

```bash
uv run python -m submission.agent_observable
```

Файл будет записан в:

```text
src/submission/traces.json
```

### 4.3. Пересчитать baseline-метрики

```bash
uv run python -m submission.eval_runner
```

Файл будет записан в:

```text
src/submission/metrics_baseline.json
```

### 4.4. Пересчитать final-метрики

```bash
uv run python -m submission.agent_final
```

Файл будет записан в:

```text
src/submission/metrics_final.json
```

---

## 5. Как запускать грейдер

Из корня проекта:

```bash
uv run python hw/grader.py part1 src/submission
uv run python hw/grader.py part2 src/submission
uv run python hw/grader.py part3 src/submission
uv run python hw/grader.py all src/submission
```

Текущий ожидаемый visible result:

```text
Part 1 · Наблюдаемость: 25/25
Part 2 · Оценка:        25/25
Part 3 · Visible:       22/50
Итого visible:          72/100
```

Part 3 полностью оценивается только на hidden test set преподавателя.

---

## 6. Проверка требований задания

### Part 1 · Observability

Сделано:

- `agent_observable.py` есть;
- `run_agent_observable(query)` реализован;
- `traces.json` содержит 10 трейсов;
- LLM-span-ы содержат `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cached_tokens`, `cost_usd`;
- tool-span-ы содержат `tool.name`, `tool.args`, `error`;
- цепочка бронирования видна как `search_showings → check_seats → reserve_seats`.

### Part 2 · Evaluation

Сделано:

- `golden_cases.yaml` есть;
- всего 28 кейсов;
- happy: 11;
- edge: 8;
- adversarial: 9;
- adversarial покрывают минимум 3 типа атак, фактически 6;
- `eval_runner.py` есть;
- `metrics_baseline.json` есть.

### Part 3 · Optimization + Security

Сделано:

- `agent_final.py` есть;
- `metrics_final.json` есть;
- `improvements.md` есть;
- описаны и реализованы оптимизации: prompt caching, model routing / cheaper model accounting, max_tokens как production-заготовка;
- реализованы защитные слои: input filter, data sanitization, tool argument validation, output sanitization;
- `reserve_seats` защищён от чужого `user_id`, ручной цены/скидки, несуществующего сеанса, недоступных мест и age-bypass;
- финальные метрики подтверждают улучшение качества, безопасности и стоимости.

### Bonus

Файл `bonus.md` есть.
