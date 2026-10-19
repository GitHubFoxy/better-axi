# Исследование: можно ли применить `snapshot --delta` в better-axi

Дата: 2026-10-19. Повод: пост @ctatedev (Chris Tate) в X от 2026-10-18 о фиче `snapshot --delta` в agent-browser («73x fewer tokens filling a form»). Сам пост в X недоступен для прямой проверки, поэтому его текст и число 73x остаются только по постановке задачи и помечены ниже как непроверенные. Все остальные факты проверены по первоисточникам: клон [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) в состоянии HEAD `dac13bb8` (2026-10-19), клон [kunchenguid/chrome-devtools-axi](https://github.com/kunchenguid/chrome-devtools-axi) в HEAD `5a23296` (совпадает с gitHead опубликованного 0.1.44), реестр npm и локальные запуски CLI на этой машине.

## Вердикт

- Готовой опции сегодня нет: в `chrome-devtools-axi` — CLI, на котором стоит better-axi — параметра `--delta` нет.
- Фича существует и зрелая, но в другом продукте: `agent-browser` от vercel-labs добавил её в версии 0.38.0 (PR [#1811](https://github.com/vercel-labs/agent-browser/pull/1811), смержен 2026-09-15). При этом `chrome-devtools-axi` и `agent-browser` между собой не связаны: разные авторы, разные стеки (TypeScript-обёртка над `chrome-devtools-mcp` против Rust-демона), разные форматы uid.
- Реалистичный путь сегодня — вариант (d): локальная дельта внутри nav-цикла better-axi поверх уже читаемых полных снепшотов. Затраты в сотню-другую строк кода, никакой зависимости от чужих релизов.
- Число «73x fewer tokens» не подтверждается ни одним документом в обоих репозиториях и нигде в открытых источниках.

## Как работает `snapshot --delta` в agent-browser

### Проект и происхождение фичи

`agent-browser` — это [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser), «Browser automation CLI for AI agents»: npm-пакет [`agent-browser`](https://www.npmjs.com/package/agent-browser) (актуальная версия 0.39.1, опубликована 2026-10-13), CLI обёртка над Rust-демоном, основной код в `cli/src/*.rs`. С better-axi его связывает только общий домен задач.

Фича появилась в PR [#1811](https://github.com/vercel-labs/agent-browser/pull/1811) «feat: add automatic snapshot deltas»: автор petehunt (Pete Hunt), открыт 2026-09-07, смержен 2026-09-15 коммитом [`7e4aa1d8`](https://github.com/vercel-labs/agent-browser/commit/7e4aa1d85f795fc919a4fba903853de031526d5d), аппрув от ctate (Chris Tate). В описании PR автор называет мотив: обычная боль — агент многократно жжёт токены на полные снепшоты, хотя после его же действий на странице почти ничего не изменилось. Первое релизное появление — версия [v0.38.0](https://github.com/vercel-labs/agent-browser/blob/main/CHANGELOG.md) со строкой «Added automatic snapshot deltas with `snapshot --delta` … Use `--full` to refresh the baseline (#1811)»; там же рядом лежат смежные изменения стека: «persistent snapshot refs» (#1812) и «conditional screenshots» (#1813).

### Точная семантика

Разбор флагов в [cli/src/commands.rs](https://github.com/vercel-labs/agent-browser/blob/main/cli/src/commands.rs) (введено коммитом 7e4aa1d8): `snapshot --delta` ставит `delta: true`; `snapshot --delta --full` — дополнительно `full: true`.

Состояние живёт не в CLI-процессе, а в постоянном демоне: [`cli/src/native/actions.rs:550`](https://github.com/vercel-labs/agent-browser/blob/main/cli/src/native/actions.rs) — `snapshot_revisions: HashMap<String, SnapshotRevision>`, ключ — идентификатор сессии страницы. Записей максимум 32, лишние выкидываются по самой старой ревизии (строки 5859-5868). Хранится `SnapshotRevision { revision, url, options, tree, refs }`: полный **текст** дерева прошлой выдачи плюс словарь рефов (`role`/`name` на каждый ref вида `@e3`).

Три вида ответа и одно правило отката ([actions.rs:5844-5856, 5882-5955](https://github.com/vercel-labs/agent-browser/blob/main/cli/src/native/actions.rs)):

1. `kind: "full"` — база ещё не создана, задан `--full`, изменился URL или изменился набор опций снепшота (в ключ входят `selector`, `interactive`, `compact`, `depth`, `urls`). В ответе полный текст дерева и словарь рефов. Навигация (смена URL) сбрасывает базу — что соответствует и правилу better-axi «после перехода нужен новый snapshot».
2. `kind: "unchanged"` — текст дерева идентичен прошлому. Ответ `{ kind: "unchanged", baseRevision, revision }` без содержимого.
3. `kind: "delta"` — компактное изменение в двух частях:
   - `changes` — операции над рефами: `{ op: "add"|"remove"|"replace", ref, node?, field?, value? }`. База и текущий словари рефов сравниваются: исчезнувший ref даёт `remove`, новый — `add`, у изменившихся сравниваются поля `role` и `name` — это `replace`.
   - `treeChange` — точная текстовая склейка `{ startLine, deleteCount, lines }`: позиции 0-based, надо заменить `deleteCount` строк на `lines` начиная с `startLine`. Алгоритм: общий префикс и общий суффикс строк, заменяется середина. Комментарий в коде объясняет, зачем нужна вторая часть: метаданные рефов содержат только `role`/`name` и не описывают состояние чекбоксов, значения полей, иерархию и порядок; точная склейка строк даёт гарантию, что восстановленное клиентом дерево совпадёт с полным (проверено тестом `snapshot_delta_tree_splice_preserves_changes_missing_from_ref_metadata`).
4. Откат к `full` без смены базы, если дельта не экономит место: сериализованный дельта-объект сравнивается с размером дерева, порог `delta.length >= tree.len() * 7/10` ([actions.rs:5949](https://github.com/vercel-labs/agent-browser/blob/main/cli/src/native/actions.rs)).

Клиентский протокол применения описан в [skill-data/core/references/commands.md:55](https://github.com/vercel-labs/agent-browser/blob/main/skill-data/core/references/commands.md) и [docs/content/docs/commands.mdx, раздел «Snapshot deltas»](https://github.com/vercel-labs/agent-browser/blob/main/docs/content/docs/commands.mdx): применить `changes` к своим метаданным рефов; разбить прошлый текст дерева на строки, вставить `treeChange.lines` на `startLine` вместо `deleteCount` строк, склеить; обе части применять к `baseRevision` и только потом двигаться на `revision`; при недоступной базе — запросить `--full`.

Рефы и дельта связаны: смежный PR [#1812](https://github.com/vercel-labs/agent-browser/pull/1812) сделал реф-идентификаторы персистентными между снепшотами той же страницы (элементы, не покинувшие DOM, сохраняют свой ref; реф-связи сбрасываются при уходе со страницы), поэтому дельта адресует элементы по уже известным рефам.

Вывод на CLI ([cli/src/output.rs](https://github.com/vercel-labs/agent-browser/blob/main/cli/src/output.rs), блок обработки `kind` в коммите 7e4aa1d8): `full` печатает текст дерева как обычно, `unchanged` печатает одну строку «unchanged (revision N)», `delta` печатает компактный JSON с работающими `--max-output` и контент-барьерами. MCP-эквивалент: поля `delta` и `full` в схеме инструмента snapshot ([cli/src/mcp.rs:846-847](https://github.com/vercel-labs/agent-browser/blob/main/cli/src/mcp.rs), маппинг в аргументы CLI на 2657-2658).

Итог: дизайн рассчитан на частые повторные наблюдения той же страницы после собственных действий агента. Навигация и радикальные изменения DOM автоматически откатываются к полному ответу.

### Про «73x fewer tokens»

В клоне репозитория число 73 в контексте дельты не встречается: поиск по README, docs, CHANGELOG и всему коду даёт только попадания в lock-файлах pnpm. [benchmarks/README.md](https://github.com/vercel-labs/agent-browser/blob/main/benchmarks/README.md) измеряет только латентность и системные показатели (navigate, snapshot, click, fill, agent-loop), о токенах и дельте там нет ничего. В PR #1811 число не упоминается. Веб-поиск 2026-10-19 по запросам с «agent-browser», «snapshot --delta» и «73x» тоже ничего не находит. Вывод: число из поста @ctatedev непроверяемо; ссылка на бенчмарк не обнаружена ни в одном первоисточнике. Помечаем unverified.

## Статус chrome-devtools-axi

### Что это за пакет и как он связан с agent-browser

Никак не связан. [chrome-devtools-axi](https://github.com/kunchenguid/chrome-devtools-axi) — самостоятельный проект автора kunchenguid: GitHub-репозиторий создан 2026-03-27, `isFork: false`, описание в npm — «AXI-compliant chrome-devtools-mcp wrapper — combined operations, TOON output, contextual suggestions». Виды связи с agent-browser, которые мы проверили: автор — другой; стек — TypeScript против Rust; формат снепшота — другой (uids вида `uid=g7:237_15` против рефов `@e3` в строках вида `- button "Save" [ref=e1]`); общего кода нет. Внутри [chrome-devtools-axi обёртка над Google chrome-devtools-mcp](https://github.com/kunchenguid/chrome-devtools-axi/blob/main/README.md) («chrome-devtools-axi wraps chrome-devtools-mcp with an AXI-compliant CLI», README, строка 14): CLI-процессы общаются с постоянным bridge-процессом на порту `CHROME_DEVTOOLS_AXI_PORT`, а bridge проксирует вызовы MCP (`take_snapshot` с `pageId`) в chrome-devtools-mcp (функция `getSessionSnapshotIfRunning` в [src/client.ts](https://github.com/kunchenguid/chrome-devtools-axi/blob/main/src/client.ts), строки 906-931).

Актуальная опубликованная версия — **0.1.44, 2026-10-17** ([npm-метаданные](https://www.npmjs.com/package/chrome-devtools-axi), поле `time`). gitHead опубликованного релиза — `5a23296`, что совпадает с HEAD клона, то есть проверка велась ровно на опубликованном коде. Локальный нюанс: на этой машине `npx -y chrome-devtools-axi --version` выдаёт 0.1.34 из кеша npx, а `npx -y chrome-devtools-axi@latest --version` выдаёт 0.1.44.

### Есть ли там понятие дельты

Нет, по всем проверкам:

- регистронезависимый поиск `delta` по всему клону пуст: ни в коде, ни в README, ни в CHANGELOG;
- эмпирическая проверка опубликованного пакета без запуска браузера (2026-10-19):
  ```
  $ npx -y chrome-devtools-axi@latest snapshot --delta
  error: Unknown flag --delta for `snapshot`
  code: VALIDATION_ERROR
  help[1]: Run `chrome-devtools-axi snapshot --help` to see valid flags
  ```
  Валидация флагов происходит в парсере CLI до какой-либо попытки соединения с браузером;
- `npx -y chrome-devtools-axi@latest snapshot --help` показывает единственный флаг: `--full`, «Show complete snapshot without truncation» — это лишь отключение [дефолтной обрезки снепшота по 16 000 символов (src/snapshot.ts, `truncateSnapshot`, строки 102-116)](https://github.com/kunchenguid/chrome-devtools-axi/blob/main/src/snapshot.ts), а не дельта;
- issue и PR репозитория по запросу «delta» касаются другого (issue #46 — потоковые события DOM, там «дельта» в смысле дельты DOM); запросов на снапшот-дельту нет.

Понятие свежести в chrome-devtools-axi решено иначе: генерационные метки уидов ([src/snapshot.ts, `stampSnapshotGeneration`](https://github.com/kunchenguid/chrome-devtools-axi/blob/main/src/snapshot.ts): `uid=237_15` превращается в `uid=g7:237_15`) и ошибки `STALE_REF` при несовпадении поколений (тексты справки [src/cli.ts](https://github.com/kunchenguid/chrome-devtools-axi/blob/main/src/cli.ts), строки 186 и 308). Это защищает от устаревших рефов, но никак не экономит токены при повторном чтении страницы: каждый `snapshot` — снова полный текст.

Если upstream однажды добавит `--delta`, базу пришлось бы хранить на стороне их bridge-процесса (по аналогии с `snapshot_revisions` демона agent-browser), и контракт better-axi почти не изменился бы — но планов на это в репозитории не видно.

## Локальный анализ: где better-axi потребляет снепшоты и что пришлось бы менять

### Полный поток текста

Каждый вызов better-axi запускает новый процесс CLI: [bin/better-axi:78-92](../bin/better-axi) (`callAxi` через `execFileSync("npx", ["-y", "chrome-devtools-axi", ...])`, тайм-аут 30 с) с явными `CHROME_DEVTOOLS_AXI_PORT`, `CHROME_DEVTOOLS_AXI_BROWSER_URL`, `CHROME_DEVTOOLS_AXI_SESSION` ([bin/better-axi:61-76](../bin/better-axi)). Постоянно живёт только bridge chrome-devtools-axi; сам CLI перезапускается на каждый вызов и состояния между вызовами не хранит. Значит, если бы `chrome-devtools-axi` добавил `--delta`, базу пришлось бы вести на стороне его bridge-процесса, как `snapshot_revisions` ведётся в демоне agent-browser.

Nav-адаптер страницы: [bin/better-axi:127-151](../bin/better-axi). `page.snapshot()` — прямой `callAxi('snapshot')`; клики и fill выполняются через префиксированные uids (`@<uid>`).

Поток текста внутри [core/agent/loop.mjs](../core/agent/loop.mjs):

- **[129](../core/agent/loop.mjs)**: полный `page.snapshot()` на каждом шаге цикла; переменная `snapshot` актуальна для конкретного шага.
- **[8-29](../core/agent/loop.mjs)** `parseSnapshotElements`: парсер строк в формате `uid=<id> role "label" [value=...]`; регекс `uid=(\S+)\s+(\w+)...` совместим и с генерационными метками chrome-devtools-axi (`uid=g7:237_15`) — \S+ их захватывает.
- **[40-45](../core/agent/loop.mjs)** `looksBlocked`: антибот определяется по первым 4 строкам снепшота; если это сделать по дельте — потеряется контекст проверки, надо обязательно оставлять голову дерева в компактной выдаче.
- **[47-89](../core/agent/loop.mjs)** `generateActions`: строит `FILL:<uid>` / `CLICK:<uid>` по **всем** интерактивным элементам текущего снепшота. Без полного списка текущих элементов получился бы неполный выбор целей — это главный довод против «дельты вместо полного текущего снепшота» в генерации действий.
- **[141-149](../core/agent/loop.mjs)**: у каждой цели собирается короткая подпись формата `role uid=X: label` (обрезается до 2000 символов) — это критерии выбора `target_N` в PAG.
- **[191-198](../core/agent/loop.mjs)**: то, что реально уходит в PAG — `state.page.text = snapshot.slice(0, 12000)` после простой замены по регексу (маскируются строки с `password|secret|cvv|token|card`, затем `value="..."`). Для длинных страниц payload упирается в лимит 12 000 и отрезается сверху вниз — именно здесь локальная дельта дала бы выигрыш.
- **[200](../core/agent/loop.mjs)**: `recent_actions` — только названия последних 6 выборов; состояние страницы при каждом решении отправляется заново, цикл не рассчитывает на память PAG между шагами.
- **[238-258](../core/agent/loop.mjs)**: обработка отказов: повторный `page.snapshot()` и подбор цели по `role + label + kind` — это фактическая локальная реализация «refresh on STALE_REF». Если внедрять дельту, здесь нужно сбрасывать сохранённый предыдущий текст снепшота и на следующем шаге снова отправлять полный.
- **[267-274](../core/agent/loop.mjs)**: результат nav возвращает полный последний снепшот наружу.

Потребление снепшотов ограничено nav: классификация и извлечение их не читают — поиск «snapshot» в [core/agent/classifier.mjs](../core/agent/classifier.mjs), [core/agent/evaluator.mjs](../core/agent/evaluator.mjs) и [core/extractor/bridge.py](../core/extractor/bridge.py) не находит ничего. Значит, дельта затрагивает только nav.

### Контекст PAG и почему «только дельта» недостаточна

Каждое решение — отдельный [POST /v1/decisions](pag-integration.md) ([core/pag/client.mjs:50-98](../core/pag/client.mjs)). Модель видит только текст в текущем payload. Поэтому дельта без подкрепления контекстом небезопасна: чтобы выбирать `target_N`, модели нужен полный список текущих интерактивных элементов с uid и подписями. Значит, у «дельты для PAG» есть обязательный минимум: заголовок-контекст страницы, перечень всех интерактивных элементов, затем только дельта-изменения; схема «как у agent-browser» (склейка `treeChange` над реконструированным текстом) реализуема и в better-axi, потому что предыдущий текст достижим внутри одного процесса цикла, а не между независимыми вызовами CLI.

### Пункты SKILL.md, основанные на полных снепшотах

Эти фразы останутся верными и после внедрения дельты, потому что описывают AXI-интерфейс поверх полных снепшотов; дополнить придётся только секцию PAG:

- [SKILL.md:159](../SKILL.md): «Использовать `snapshot`, затем свежие `uid`. После перехода или изменения состояния подтвердить результат новым `snapshot` или `eval`. При `STALE_REF` обновить snapshot».
- [SKILL.md:196-201](../SKILL.md): описание nav — цикл читает accessibility snapshot, отдаёт его (отредактированным) в PAG, выполняет выбор и снова читает страницу; результат возвращает последний snapshot.
- [SKILL.md:211-213](../SKILL.md): правило редактора PAG — «PAG получает цель навигации и отредактированный accessibility snapshot» + список маскируемых полей.
- [SKILL.md:217-219](../SKILL.md): «Перед использованием UID получи свежий `snapshot`. После навигации или изменения страницы получи новый snapshot; не используй устаревшие UID».
- [SKILL.md:227](../SKILL.md): после прохода CAPTCHA — «получить новый snapshot».

## Варианты и затраты

### (a) Ждать/обновить chrome-devtools-axi до релиза с `--delta`

Непригоден сегодня: флага нет, issue/PR upstream нет, о планах ничего не заявлено. Апгрейд до 0.1.44 по этой фиче ничего не даёт — в коде дельты нет. Сопутствующий практический момент: голый спек `npx -y chrome-devtools-axi` на этой машине даёт 0.1.34 из кеша npx, тогда как `@latest` даёт 0.1.44; при необходимости конкретную версию можно указать прямо в [bin/better-axi:81](../bin/better-axi). Если upstream однажды реализует дельту, better-axi останется лишь изменить вызов `callAxi('snapshot', ['--delta'])` и добавить разбор ответа — затраты минимальны, но срок появления фичи неизвестен.

### (b) Перевести better-axi на agent-browser

Технически возможно: [agent-browser умеет подключаться к уже запущенному браузеру по CDP](https://github.com/vercel-labs/agent-browser/blob/main/README.md) (глобальная опция `--cdp <port|url>`), значит к Helium с `--remote-debugging-port` подключиться можно. Но это глубокое переписывание ради одной фичи:

- другой формат снепшота: строки вида `- button "Save" [ref=e1]` с рефами `@e3`; текущий парсер [core/agent/loop.mjs:8-29](../core/agent/loop.mjs) и контракты [tests/test_loop.test.mjs:9-57](../tests/test_loop.test.mjs) рассчитаны на `uid=... role`;
- другая модель сессий: свой daemon, `--session`, свои каталоги состояния — против действующей пары CDP-порт и AXI-bridge порт `N`/`N+110` со всей дисциплиной запуска [SKILL.md:52-78](../SKILL.md) и env-контрактом [bin/better-axi:61-76](../bin/better-axi);
- SKILL.md в текущей форме привязан к AXI (профили Helium, bridge-порты, `chrome-devtools-axi stop`), переиначить пришлось бы целиком;
- теряются «Остальные возможности AXI» ([SKILL.md:217](../SKILL.md)): прямые команды (`network`, `console`, `emulate`, `upload`, …), на которые nav не опирается, но которые скилл советует для действий вне цикла «в той же сессии»;
- agent-browser сам по себе — daemon на Rust плюс npm-обёртка, то есть дополнительное runtime-звено в цепи вызовов.

Затраты: большие (переписать page-адаптер, парсер, SKILL.md, тесты). Выгода ровно одна — экономия токенов на повторных снепшотах, которую можно получить и без смены инструмента (см. (c)).

### (c) Реализовать дельту локально в better-axi поверх двух полных снепшотов

better-axi и так каждый шаг делает полный `page.snapshot()`, так что сырьё для диффа уже есть. Вся новая работа остаётся внутри better-axi.

Место: [core/agent/loop.mjs](../core/agent/loop.mjs), удобнее выделить отдельным модулем `core/agent/delta.mjs` с тестами в [tests/](../tests). Что делается:

1. Хранить предыдущий полный текст снепшота (в цикле уже есть переменная [loop.mjs:117, 129](../core/agent/loop.mjs)).
2. После очередного `page.snapshot()` прогнать обе версии через `parseSnapshotElements` и вычислить добавленные, удалённые и изменённые uid-строки (тот же uid, другой value/label/state).
3. Компоновать компактный `state.page.text` для PAG: голова снепшота (URL/`RootWebArea` — нужна для `looksBlocked` и контекста), счётчик неизменённых элементов, только добавленные/изменённые/удалённые строки с их uid, плюс полный перечень всех интерактивных элементов, которые `generateActions` предложит как `target_N`. Такой payload даёт модели и контекст, и полный список выбора.
4. Локально повторить защитный порог из agent-browser: если скомпонованный дельта-текст не короче полного — отправлять полный.
5. Сбрасывать базу (следующий шаг снова полный текст) при: навигации (`task.start_url`, `open`), пробе `looksBlocked`, восстановлении после ошибки действия ([loop.mjs:238-258](../core/agent/loop.mjs)) — это согласуется с правилами SKILL.md «после изменения состояния — новый snapshot».

Что не меняется: `parseSnapshotElements`, `generateActions`, `performAction`, [bin/better-axi](../bin/better-axi) — они продолжают работать с полными снепшотами; фактические вызовы AXI остаются прежними. Дифф влияет только на payload решения.

Затраты: порядка 100-200 строк кода и тестов; риск невелик, потому что оба текста каждый шаг уже собираются. Формат дельты — по образцу agent-browser (изменённые строки с uid, счётчик или точная склейка), но самостоятельный: дельта формируется и применяется внутри better-axi, AXI и PAG о ней не знают.

### (d) Гибрид: дельта внутри nav-цикла, полный снепшот наружу

Вариант (c) с уточнением ролей: полный текст снепшота каждый шаг всё равно запрашивается у AXI и возвращается из nav наружу (уже так: [loop.mjs:267-274](../core/agent/loop.mjs)); дельта используется только в payload для PAG. Люди и прямые вызовы AXI продолжают видеть полный текст; сами правила SKILL.md про «новый snapshot после навигации» остаются действительными, потому что относятся к полным снепшотам. Это реалистичный первый шаг: можно делать сегодня, не дожидаясь внешних релизов.

## Рекомендация

1. Реализовать (d): локальный модуль диффа в better-axi (рядом с loop.mjs), с порогом отката к полному тексту и сбросом базы при навигации, блокировке и восстановлении после ошибок. Выигрыш — непосредственно в payload решения PAG ([loop.mjs:191-198](../core/agent/loop.mjs)), полный AXI-контракт остаётся прежним.
2. Дополнить SKILL.md и [docs/pag-integration.md](pag-integration.md) одним абзацем: описание того, что nav может отправлять в PAG дельту страницы (голова + изменения + перечень интерактивных элементов), при этом требования «полный snapshot после навигации / после STALE_REF / после CAPTCHA» остаются и относятся к полным снепшотам AXI.
3. `--delta` agent-browser — хороший референс, но не совместимый формат: рефы `@eN` против `uid=...`, схема с `changes`/`treeChange` опирается на персистентные рефы из PR #1812 (строки снепшота agent-browser строят refs иначе), которых у AXI нет. Учитывать при проектировании, не копировать вслепую.
4. Вариант (a) — отслеживать [kunchenguid/chrome-devtools-axi](https://github.com/kunchenguid/chrome-devtools-axi); вариант (b) — не делать.

Итог исследования: единственный созданный или изменённый файл — этот документ; прочие файлы репозитория не тронуты.
