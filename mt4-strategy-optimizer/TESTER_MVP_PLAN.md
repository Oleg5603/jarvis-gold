# EA Optimizer Lab — проверяемая спецификация MVP

Источник: публичная ветка ChatGPT
`https://chatgpt.com/share/6a895bdc-0188-83eb-9132-bb4730d45ea8`.

Статус: **Orchestrator / Phase 2 — CEO review**.

## Идея

Windows-приложение для воспроизводимой оптимизации готовых советников:

```text
MT5 + EA + диапазоны input
  -> Optuna выбирает trial
  -> MetaTrader Strategy Tester выполняет тест
  -> Score ранжирует Train
  -> лучшие 20–50 проходят Forward
  -> Stability Test проверяет соседние параметры
  -> TOP-20 -> выбор пользователя -> .set -> установка с backup
```

AI в версии 1.0 только объясняет агрегированные результаты. Он не выбирает
trials, не меняет MQL, не заменяет EA и не запускает реальную торговлю.

## Пользовательский результат

- воспроизводимый manifest эксперимента;
- TOP-20 с отдельными Train и Forward метриками;
- Parameter Stability Score;
- графики equity/drawdown, прибыль по месяцам/годам, часам и BUY/SELL;
- выбранный `.set`, резервная копия предыдущего и журнал установки;
- история запусков в SQLite;
- необязательный отчёт Qwen с зависимостями параметров.

## Версия 1.0

1. **MT4-first**, затем MT5 на том же общем ядре и контракте адаптера.
2. Выбор терминала, EA, символа, TF, периода, депозита, плеча и tick model.
3. Явные spread, commission, swap/slippage, если доступны.
4. Чтение и редактирование диапазонов `input`: min/max/step, bool choices.
5. Ограничения параметров, например `FAST < MID < SLOW`.
6. Optuna и версионируемая функция Score.
7. Обязательные Train/Forward и Stability Test.
8. TOP-20, таблица, фильтры и графики.
9. `.set` export/import, backup-first и безопасная установка.
10. SQLite: проекты, версии EA, runs, trials, tests, artifacts, AI reports, log.
11. `NoAI` и `OllamaQwen` через единый аналитический интерфейс.
12. Resume после сбоя и полный журнал действий.

Не входит: изменение/компиляция MQL, live trading, автоматическая замена EA,
параллельная реализация двух адаптеров в одном этапе, распределённые workers и
обещание доходности.

## Архитектура

```text
PySide6 UI -> Run Coordinator
                  |-- MT5 Adapter -> tester config/launch/report parser
                  |-- Optuna -> constraints/Score/ranking
                  |-- Validation -> Train/Forward/Stability/TOP-20
                  |-- SQLite -> projects/runs/trials/artifacts/log
                  |-- Export -> .set/backup/manifest
                  `-- AI Analyzer -> NoAI/OllamaQwen
```

Модули: `domain`, `mt5`, `optimizer`, `validation`, `storage`, `export`, `ai`,
`ui`; тесты используют fake MT5 adapter и зафиксированные реальные отчёты MT5.

## Score

```text
score = profit + profit_factor + recovery
        - drawdown
        - penalty_low_trades
        - penalty_instability
        - penalty_invalid_run
```

Все компоненты нормализуются; PF/Recovery ограничиваются сверху. Веса и hard
gates записываются в manifest и не меняются внутри study. Минимум сделок и
максимум DD обязательны. Forward не входит в Train Score.

## Защита от look-ahead и переоптимизации

1. Граница Train/Forward фиксируется до первого trial.
2. Optuna видит только Train-метрики.
3. Forward запускается после заморозки Train-ranking только для финалистов.
4. Изменение Forward-данных не может менять последовательность Train trials.
5. Stability использует то же временное разделение и модель издержек.
6. Manifest хранит даты, символ, TF, tick model, spread, commission, deposit,
   leverage, seed, версии и хеши EA/terminal/config.
7. Одинаковый manifest должен воспроизводить входные конфигурации; расхождение
   отчётов маркируется как nondeterministic.
8. Корректность использования закрытых баров внутри EA проверяется отдельно и
   не предполагается автоматически.

## Stability Test

Для финалиста проверяются допустимые соседи `-step/current/+step`. Stability
Score учитывает долю прибыльных соседей, медиану/разброс Score, ухудшение DD,
число сделок и одиночный пик. Бюджет sampling и seed фиксируются.

## AI Analyzer

```python
analyze(aggregated_results)
suggest_improvements(strategy_summary)
compare_versions(v1_summary, v2_summary)
```

AI получает агрегаты, не ключи и не торговые реквизиты. Текст хранится отдельно
от фактических метрик и ссылается на run/metric IDs. `NoAI` обеспечивает полный
цикл без Ollama.

## Этапы

### E0 — MT4 spike

Подтвердить управляемый запуск MT4 Strategy Tester, получить реальный report fixture,
зафиксировать tester config и `.set`; принять go/no-go по интеграции.

**Контрольная развилка:** внешний Optuna не является обязательным условием первого
рабочего результата. Если одиночные управляемые прогоны MT4, получение отчётов и
воспроизводимость стабильны, E1 использует Optuna ask/tell. Если интеграция нестабильна,
MVP использует штатную оптимизацию MT4, а Optuna переносится в v1.1.

### E1 — headless vertical slice

Domain, manifest, SQLite, fake/real MT4 adapters, parser, CLI, 10 trials, Score.

### E1.5 — MT5 vertical slice

Добавить MT5 adapter к тому же контракту запуска/отчёта, реальные MT5 fixtures и
smoke-flow. Domain, Score, Train/Forward, Stability и SQLite остаются общими.

### E2 — optimization pipeline

Optuna, constraints, resume, Train/Forward, hard gates, TOP-20.

### E3 — stability/export

Neighbourhood, Stability Score, `.set` round-trip, backup/rollback.

### E4 — PySide6 UI

Setup, Parameters, Progress, Results, Export; loading/empty/error/partial/success.

### E5 — history/AI

Projects, version comparison, NoAI/Qwen, audit log.

## Проверки приёмки

1. Парсер извлекает numeric/bool/enum inputs из fixture EA.
2. `FAST < MID < SLOW` отсекается до запуска MT5.
3. Fake adapter подтверждает точный tester config каждого trial.
4. Report parser сверяется с реальным зафиксированным MT5 report.
5. Все издержки и параметры среды присутствуют в manifest.
6. Forward-метрики недоступны callback Optuna Train study.
7. Изменение Forward не меняет Train trials.
8. TOP-20 содержит только кандидатов, прошедших hard gates.
9. Stability отвергает искусственный одиночный пик и принимает плато.
10. Одинаковый seed + fake adapter дают одинаковые trials/ranking.
11. Crash/resume не дублирует trial.
12. Нулевые издержки дают предупреждение и остаются в manifest.
13. `.set` round-trip сохраняет типы и значения.
14. Без успешного backup рабочий `.set` не заменяется.
15. NoAI проходит весь smoke flow.
16. AI API не имеет методов изменения MQL/live trading/установки EA.
17. Ошибка UI содержит: что произошло, вероятная причина, что сделать.
18. Smoke: fixture EA -> 10 trials -> Train -> Forward -> Stability -> TOP -> `.set`.

## Риски и rescue

| Риск | Rescue |
|---|---|
| MT5 не запускается стабильно | E0 spike; поддерживаемая сборка/portable profile |
| Тесты слишком медленные | trial budget, pruning, exact-set cache; parallel позже |
| Report зависит от локали/версии | versioned fixtures, fail-closed parser |
| Утечка Forward | отдельные сервисы/таблицы и информационный тест |
| Одиночный оптимум | Stability hard gate |
| Скрытые настройки MT5 | dedicated profile и полный manifest |
| AI выдумывает | ссылки на фактические IDs, recommendation отдельно от facts |
| Потеря `.set` | atomic backup-first и rollback test |

## Следующие версии

- v1.1: Walk Forward и стресс-тесты;
- v1.1: расширенные Walk Forward и стресс-тесты после базовой поддержки MT5/MT4;
- v2.0: AI предлагает MQL-патч, компиляция и сравнение только через approval.

## Premise gate Оркестратора

Подтвердить перед CEO -> Design -> Eng -> DX:

1. v1.0 оптимизирует готовый EA, не переписывает стратегию.
2. Поддерживаются MT4 и MT5: сначала завершается MT4-срез, затем MT5-срез.
3. Optuna выбирает параметры; AI только анализирует и может быть выключен.
4. Train/Forward и Stability обязательны для TOP.
5. Live trading и автоматическая замена EA запрещены.

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | Intake | MT5-first | Taste, pending gate | Explicit | Один интеграционный вертикальный срез | MT4+MT5 сразу |
| 2 | Intake | Нативный MetaTrader Tester | Mechanical | DRY | Совпадает с идеей и реальным исполнением | Новый свечной движок |
| 3 | Intake | Optuna ищет, LLM объясняет | Mechanical | Pragmatic | Воспроизводимый численный поиск | LLM выбирает trials |
| 4 | Intake | Forward изолирован | Mechanical | Completeness | Иначе есть утечка | Смешанный Train/Forward Score |
| 5 | Intake | AI не меняет MQL в v1 | User direction | Safety | Явная граница исходной идеи | Автономная эволюция EA |
| 6 | CEO | Optuna после E0 go/no-go | User-approved | Reversibility | Не ставить весь MVP в зависимость от недоказанной автоматизации одиночных прогонов MT5 | Сразу строить обязательный внешний цикл Optuna |
| 7 | CEO | MT5 и MT4 в продукте, последовательно | User-approved | DRY | Пользователю нужны оба терминала; единое ядро снижает дублирование, последовательность снижает интеграционный риск | MT5-only и параллельная разработка двух адаптеров |
| 8 | CEO | MT4 имеет первый приоритет | User-approved | User outcome | На ПК уже есть MT4, реальные `.set` и отчёты; пользователь прямо выбрал MT4 первым | MT5-first |
