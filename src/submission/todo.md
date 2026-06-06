Структура submission:

```
submission/
├── agent_observable.py
├── traces.json
├── golden_cases.yaml
├── eval_runner.py
├── metrics_baseline.json
├── agent_final.py
├── metrics_final.json
├── improvements.md
├── bonus.md                ← опционально
└── README.md               ← как запустить ваше решение
```

## План работы

1. **Прочитайте `homework.md`** целиком. Это полное условие.
2. **Откройте `starter.ipynb`** и посмотрите, как устроен baseline. Не правьте его.
3. **Part 1** (25 баллов) — оберните агента в трейсинг. Сохраните в `agent_observable.py` и `traces.json`.
4. **Part 2** (25 баллов) — соберите свой golden_cases.yaml, реализуйте eval_runner, прогоните baseline.
5. **Part 3** (50 баллов) — финальная версия со всеми защитами и оптимизациями. `agent_final.py` + `improvements.md`.
6. **Бонус** (10 баллов) — найдите атаку, которой нет в обязательной части.

## Локальная самопроверка

Гоняйте грейдер сколько угодно раз:

```bash
python grader.py part1 .              # только Part 1
python grader.py part2 .              # только Part 2
python grader.py part3 .              # только Part 3 (видимая часть)
python grader.py all  .               # всё сразу
```

Грейдер ищет ваши файлы в указанной папке. Если файла нет — баллы за соответствующий пункт = 0, но другие пункты проверятся.

uv run python -m submission.agent_observable
uv run python hw/grader.py part1 src/submission