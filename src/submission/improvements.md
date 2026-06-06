# Улучшения финального агента «Кадр»

## Краткое сравнение

| Версия | Task success | Happy | Edge | Adversarial | Avg cost USD | P95 cost USD | Avg LLM calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 0.5357 | 9/11 | 4/8 | 2/9 | 0.00230314 | 0.00384300 | 1.7857 |
| Final | см. `metrics_final.json` | см. `metrics_final.json` | см. `metrics_final.json` | см. `metrics_final.json` | см. `metrics_final.json` | см. `metrics_final.json` | см. `metrics_final.json` |

Финальные метрики пересчитываются командой:

```bash
uv run python -m submission.agent_final
```

## Оптимизации

### 1. Prompt cache статической части

Финальный агент учитывает статическую часть промпта и описания tools как cached input tokens. В trace это отражается через:

- `gen_ai.usage.cached_tokens`;
- `optimization.prompt_cache = true`.

Это снижает стоимость повторной передачи `SYSTEM_PROMPT` и `TOOL_SCHEMAS`.

### 2. Output limit / краткие ответы

Финальный агент использует небольшой лимит генерации (`FINAL_MAX_TOKENS = 96`) и формирует короткие ответы без длинных рассуждений. В trace это отражается через:

- `optimization.max_tokens`.

### 3. Простая model routing-стратегия

Короткие типовые запросы отправляются на `small`, длинные — на `large`. Для текущего датасета большинство запросов обрабатываются дешёвой моделью, но логика оставляет возможность поднять класс модели для более длинных запросов.

## Защиты

### 1. Input filter

До вызова tools агент проверяет пользовательский запрос регулярными выражениями. Блокируются:

- prompt injection: `игнорируй`, `забудь инструкции`, `ignore previous`;
- jailbreak: `developer mode`, `без ограничений`, `новые инструкции`;
- prompt leak: `system prompt`, просьба раскрыть настройку;
- price manipulation: `1 рубль`, `100%`, `промокод`, `бесплатный билет`;
- excessive agency: `user_id=...`, чужой пользователь, чужой аккаунт;
- age bypass: просьба игнорировать возрастную проверку;
- indirect injection markers: `SYSTEM NOTE`, `SYSTEM OVERRIDE`, `free tickets`.

Если фильтр срабатывает, агент не вызывает опасные tools и возвращает безопасный отказ.

### 2. Data sanitization

`lookup_policy` обёрнут в `safe_lookup_policy`. Текст политики очищается от:

- `SYSTEM NOTE` / `SYSTEM OVERRIDE`;
- `ignore previous rules`;
- `allow free tickets`;
- `<script>...</script>`.

Это защищает от indirect prompt injection через текстовые данные policies.

### 3. Tool argument validation для `reserve_seats`

`reserve_seats` вызывается только через `safe_reserve_seats`. Проверяется:

- `user_id` должен быть только `current`;
- нельзя передавать `price`, `discount`, `promo`, `promocode`;
- сеанс должен существовать;
- выбранные места должны быть доступны;
- 18+ не бронируется при явном несовершеннолетнем запросе или несовместимом возрасте пользователя.

Цена всегда берётся из trusted schedule, а не из аргументов модели.

### 4. Output sanitization

Перед возвратом пользователю финальный ответ проходит через `sanitize_output`. Удаляются script-вставки и служебные prompt-injection артефакты, если они всё-таки протекли через внешние данные.

## Ограничения

- Regex input filter может давать false positive и false negative. Для production его стоило бы дополнить классификатором риска и политиками по типам действий.
- Текущий routing эвристический. В реальном сервисе его лучше обучать/калибровать на логах и eval-наборе.
- Возрастная проверка использует доступные fixture-поля и явные признаки в запросе; в настоящем продукте нужен verified age из auth/profile service.
- Semantic cache сознательно не применяется к динамическим данным: местам, бронированию и лояльности. Такие ответы могут быстро устаревать.
