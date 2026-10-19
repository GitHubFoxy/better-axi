# Исследование: подключение better-axi к уже открытому браузеру через CDP-relay расширения browse

Дата: 2026-10-19.

Состояние кода: better-axi `e35edcc`; `R44VC0RP/browse` `c0b0d82` (2026-10-19).

Повод: текущий better-axi запускает отдельный Helium с `--remote-debugging-port` и отдельным `--user-data-dir`. Это не позволяет работать в основном профиле пользователя: с Chrome 136 нативный remote debugging игнорируется для дефолтного каталога данных. Расширение `browse` от Райана Вогеля обещает CDP-совместимый relay для уже открытого браузера. Нужно понять, можно ли подключить better-axi к этому relay и что это меняет.

## Короткий вывод

Технически это возможно. Relay `browse` отдаёт `/json/version`, `/json/list` и websocket `/devtools/browser/<id>`, а также обрабатывает базовые команды `Target.*`, которых достаточно для Playwright `connectOverCDP` и, вероятно, для `chrome-devtools-axi`.

Но это не проверено end-to-end с самим better-axi. Нужен короткий spike: подключить `chrome-devtools-axi` к `http://127.0.0.1:19988`, выполнить `pages`, `snapshot`, `click`, `fill`, `eval`. Если AXI принимает relay, интеграция сводится к новому режиму подключения и проверке `doctor`, без переписывания nav-цикла.

Рекомендация: добавить opt-in режим «attached browser» и не заменять текущий изолированный запуск Helium. Основной профиль даёт удобство и настоящие логины, но одновременно даёт агенту доступ ко всем аккаунтам пользователя. Это должен быть осознанный выбор, а не дефолт.

## Зачем это нужно

Сейчас better-axi работает так:

1. Пользователь выбирает профиль Career, Ozon или временный.
2. Скрипт запускает отдельный Helium с `--remote-debugging-port=N` и `--user-data-dir=<profile>`.
3. `chrome-devtools-axi` подключается к CDP-порту, а better-axi общается с AXI через bridge-порт `N + 110`.
4. `CHROME_DEVTOOLS_AXI_BROWSER_URL` указывает на CDP-браузер, `CHROME_DEVTOOLS_AXI_PORT` на bridge (`bin/better-axi:61-76`, `README.md:40-47`).

Проблема в шаге 2. Нативный CDP-порт нельзя включить в уже запущенном браузере. Его нужно указывать при старте. Chrome 136+ дополнительно игнорирует `--remote-debugging-port` и `--remote-debugging-pipe`, если используется дефолтный каталог данных. Поэтому «просто подключиться к моему обычному Chrome» нативно не получается: либо отдельный профиль, либо копирование профиля, либо расширение.

Расширение `browse` решает именно эту проблему: оно цепляется к уже открытому браузеру через `chrome.debugger` и выставляет CDP-совместимый relay. Пользователю не нужно перезапускать браузер и отказываться от своего профиля.

## Что такое browse

`R44VC0RP/browse` описывает себя так: «Let your AI agents use your real browser: your tabs, your logins, your extensions. An MCP server and a Chromium extension» (`README.md:6-7`).

Архитектура:

```text
agent
  -> browse MCP server (stdio)
  -> relay на 127.0.0.1:19988
  -> WebSocket
  -> Chrome extension
  -> chrome.debugger
  -> вкладка в обычном браузере
```

Ключевые факты из README:

- relay это «local Chrome DevTools endpoint backed by the extension», он «starts on demand» (`README.md:90-91`);
- расширение выполняет команды через `chrome.debugger` (`README.md:92-93`);
- `execute` использует Patchright, поэтому страница не видит debugger, а ввод двигается по-человечески (`README.md:94-96`);
- расширение просит permissions `debugger`, `tabs`, `tabGroups`, `storage`, `alarms`, `offscreen`, `tabCapture` (`README.md:98-99`);
- одновременно может быть подключён только один браузерный профиль (`README.md:107`).

Важно: `browse` не «включает CDP в браузере». Он даёт CDP-совместимый фасад над `chrome.debugger`. Это не нативный DevTools-сервер Chrome, а шим. Для большинства задач Playwright этого достаточно, но не для всех.

## Что именно отдаёт relay

HTTP:

- `GET /json/version` возвращает `Browser: OpenCode-Browser/<version>`, `Protocol-Version: 1.3` и `webSocketDebuggerUrl` вида `ws://127.0.0.1:19988/devtools/browser/<id>` (`cli/src/http-api.ts:108-119`).
- `GET /json/list` возвращает список целей (`cli/src/http-api.ts:137-139`).
- `GET /extension/status` показывает, подключено ли расширение (`cli/src/http-api.ts:141-145`).

WebSocket:

- `/devtools/browser/<id>` принимает CDP-клиентов (`cli/src/relay.ts:688-702`).

Поддерживаемые CDP-команды, важные для клиента:

- `Browser.getVersion` (`cli/src/relay.ts:1265`);
- `Target.setDiscoverTargets` (`cli/src/relay.ts:1277`);
- `Target.getTargets` (`cli/src/relay.ts:1300`);
- `Target.attachToTarget` (`cli/src/relay.ts:1308`);
- `Target.createTarget` и `Target.closeTarget` (`cli/src/relay.ts:1335-1354`);
- `Target.attachToBrowserTarget` (`cli/src/relay.ts:1305`).

Этого набора хватает, чтобы Playwright сделал `connectOverCDP`. В коде прямо описаны «raw `connectOverCDP` clients» (`cli/src/cdp-visibility.ts:15-21`). То есть relay проектировался не только под свой MCP, но и под внешние CDP-клиенты.

## Видимость вкладок

Это критично для better-axi. Relay не отдаёт агенту все вкладки пользователя молча.

Правила (`cli/src/cdp-visibility.ts:1-36`):

- цели, созданные сессией OpenCode Browser, видны только клиентам этой сессии;
- вкладки, которые пользователь явно отдал через кнопку в тулбаре, видны всем клиентам, чтобы работал `--target-url`;
- цели, созданные raw CDP-клиентом без session id, видны raw-клиентам и сессионному клиенту, у которого ещё нет своей цели;
- два одновременных raw-клиента могут мешать друг другу. Изолированный и поддерживаемый путь это сессии OpenCode Browser.

Для better-axi это значит: если подключаться как raw CDP-клиент, агент увидит только те вкладки, которые пользователь явно отдал, плюс те, которые создаст сам. Это хороший safety default, но UX надо документировать: «нажми кнопку на вкладке, иначе агент её не увидит».

## Чем это отличается от нативного CDP

| | Нативный CDP | browse relay |
|---|---|---|
| Когда включается | только при запуске браузера с флагом | в любой момент, расширение уже установлено |
| Основной профиль | Chrome 136+ игнорирует флаг на дефолтном `--user-data-dir` | работает с основным профилем |
| Транспорт | TCP-порт Chrome | локальный relay + WebSocket + `chrome.debugger` |
| Полнота протокола | полный DevTools Protocol | шим, покрывает не всё |
| Закрытие браузера, очистка куков | доступны | заблокированы guardrails |
| Скачивание файлов | работает | не работает через `chrome.debugger` |
| Изоляция | отдельный профиль | общий профиль пользователя |
| Риск | ограничен профилем автоматизации | весь реальный профиль и все логины |

Нативная схема остаётся лучшей для изоляции. Relay лучше для сценариев «у меня уже открыт браузер, я залогинен, сделай что-то в моей вкладке».

## Совместимость с better-axi

Формально better-axi уже умеет указывать CDP-URL:

```sh
export CHROME_DEVTOOLS_AXI_BROWSER_URL=http://127.0.0.1:19988
export CHROME_DEVTOOLS_AXI_PORT=9445   # bridge, не CDP
export CHROME_DEVTOOLS_AXI_SESSION=open-browser
```

`bin/better-axi:61-76` прокидывает эти переменные в `chrome-devtools-axi`, а `README.md:40-47` прямо разделяет bridge-порт и CDP-URL. То есть код менять почти не нужно, если AXI принимает relay.

Что нужно проверить в spike:

1. Запускается ли relay без ручного `opencode-browser serve`, по первому вызову CLI/MCP.
2. Отдаёт ли `/json/version` то, что ожидает `chrome-devtools-axi`.
3. Работает ли `chrome-devtools-axi pages` и видит ли он вкладки.
4. Работает ли `snapshot` на вкладке, которую пользователь отдал кнопкой.
5. Работают ли `click`, `fill`, `press`, `eval` через `chrome.debugger`.
6. Работает ли `Target.createTarget` для новой вкладки агента.
7. Не ломается ли `STALE_REF` и генерационные uid.
8. Как ведёт себя `network` и `console`, если AXI их использует.
9. Что происходит, если вкладка уже открыта в DevTools: расширение такие вкладки исключает (`cli/skills/browse/SKILL.md:57-60`).
10. Что происходит при двух клиентах: AXI и MCP одновременно.

Потенциальные точки отказа:

- `chrome-devtools-axi` может ожидать поля `/json/version`, которых relay не отдаёт (`User-Agent`, `V8-Version`, `WebKit-Version`). В relay есть только `Browser`, `Protocol-Version`, `webSocketDebuggerUrl`.
- AXI может выбирать цель по `webSocketDebuggerUrl` на уровне страницы, а relay отдаёт его только на уровне браузера.
- `chrome.debugger` не даёт полный `Runtime` и может отличаться по событиям.
- Relay блокирует разрушительные CDP-команды (`cli/skills/browse/SKILL.md:401-403`), и это может ломать сценарии, которые AXI считает нормальными.
- Скачивание файлов через `page.waitForEvent("download")` не работает (`cli/skills/browse/SKILL.md:380-383`).

Пока эти пункты не проверены, нельзя обещать, что «better-axi просто заработает с browse». Нужен эксперимент, а не вывод из документации.

## Риски и ограничения

1. **Реальный профиль.** Агент получает доступ к вкладкам, где пользователь залогинен в банк, почту, маркетплейсы. Prompt injection на любой странице может привести к действиям от имени пользователя. Нужны явные handoff-и и запрет на платежи без подтверждения.
2. **Один debugger на вкладку.** Если вкладка уже отлаживается через DevTools, расширение не сможет к ней подключиться. Это не ошибка better-axi, это ограничение Chrome.
3. **Один браузер на relay.** Нельзя одновременно подключить два профиля. При переключении нужно отключать расширение в текущем.
4. **Guardrails.** Relay не даёт закрыть браузер и очистить куки. Это хорошо для безопасности, но может мешать тестам, которые ожидают полный контроль.
5. **Не полный CDP.** Сложные сценарии с сетевыми перехватами, загрузками и некоторыми `Runtime`-фичами могут не работать.
6. **Доверие к расширению.** Расширение имеет доступ ко всем сайтам и к `debugger`. Это большой permission footprint. Ставить его стоит только в тот браузер, где это действительно нужно.
7. **Публичность и ToS.** Использование агента на сайтах, которые запрещают автоматизацию, остаётся на ответственности пользователя. Relay не делает автоматизацию «легальной», он только меняет способ подключения.

## Предлагаемый план

### Этап 0. Spike, без изменений в better-axi

1. Установить `browse`: `npx opencode-browser-cli install` или `bun run setup` из клона.
2. Загрузить расширение в Helium.
3. Открыть тестовую вкладку и отдать её агенту кнопкой в тулбаре.
4. Проверить relay:

```sh
curl -s http://127.0.0.1:19988/json/version
curl -s http://127.0.0.1:19988/json/list
curl -s http://127.0.0.1:19988/extension/status
```

5. Подключить AXI:

```sh
CHROME_DEVTOOLS_AXI_BROWSER_URL=http://127.0.0.1:19988 \
CHROME_DEVTOOLS_AXI_PORT=9445 \
CHROME_DEVTOOLS_AXI_SESSION=open-browser \
npx -y chrome-devtools-axi@latest pages
```

6. Прогнать `snapshot`, `click`, `fill`, `eval` на тестовой странице.
7. Записать результат в этот документ или в комментарий к issue.

### Этап 1. Режим подключения в better-axi

Если spike успешен:

- добавить в `bin/better-axi` явный флаг `--browser-url` или предупреждение, если `CHROME_DEVTOOLS_AXI_BROWSER_URL` указывает на `127.0.0.1:19988`;
- добавить `doctor`-проверку: `GET /json/version`, `GET /json/list`, `GET /extension/status`, сравнить `Browser` с `OpenCode-Browser/`;
- внятная ошибка, если relay не запущен: «запусти `opencode-browser` или установи расширение»;
- не запускать `opencode-browser serve` автоматически без согласия пользователя;
- документировать, что bridge-порт и CDP-URL это разные вещи.

### Этап 2. UX для вкладок пользователя

- `--target-url` уже есть в AXI; добавить в better-axi понятную ошибку, если вкладка не отдана;
- подсказка в `nav`: «нажми кнопку OpenCode Browser на вкладке, чтобы агент её увидел»;
- запрет на работу с вкладками, которые не отданы явно;
- read-only режим для инспекции без кликов.

### Этап 3. Тесты

- unit-тест на разбор `/json/version` с `Browser: OpenCode-Browser/...`;
- интеграционный тест, который поднимает фейковый relay и проверяет, что better-axi не путает bridge-порт с CDP-URL;
- gated-тест с настоящим расширением, только по env-флагу.

## Критерии готовности

- [ ] `chrome-devtools-axi pages` видит вкладку, отданную пользователем.
- [ ] `snapshot` возвращает accessibility tree.
- [ ] `click` и `fill` работают на этой вкладке.
- [ ] `nav` проходит простой сценарий на публичной странице.
- [ ] Ошибки relay объясняются человеку, а не выглядят как «AXI сломался».
- [ ] В README и SKILL.md описаны оба режима: изолированный Helium и attached browser.
- [ ] По умолчанию остаётся изолированный профиль.

## Открытые вопросы

1. Принимает ли `chrome-devtools-axi` relay как обычный CDP-браузер, или ему нужны поля, которых нет в `/json/version`?
2. Поддерживает ли AXI `Target.createTarget` через relay так же, как через нативный Chrome?
3. Не конфликтует ли AXI bridge с relay при одновременной работе MCP `browse` и better-axi?
4. Нужно ли better-axi само поднимать relay, или это всегда ответственность пользователя?
5. Как показывать пользователю, какая вкладка отдана агенту, чтобы он не забыл её забрать?
6. Что делать с CAPTCHA и 2FA: relay умеет handoff, но better-axi пока не знает об этом протоколе.

## Источники

- `R44VC0RP/browse`, HEAD `c0b0d82` (2026-10-19): `README.md`, `cli/src/http-api.ts`, `cli/src/relay.ts`, `cli/src/cdp-visibility.ts`, `cli/src/relay-helpers.ts`, `cli/skills/browse/SKILL.md`.
- better-axi, HEAD `e35edcc`: `bin/better-axi`, `README.md`, `SKILL.md`, `docs/pag-integration.md`.
- Chrome for Developers, «Changes to remote debugging switches to improve security»: https://developer.chrome.com/blog/remote-debugging-port
- Chrome DevTools Protocol, Target domain: https://chromedevtools.github.io/devtools-protocol/tot/Target/
- Patchright: https://github.com/Kaliiiiiiiiii-Vinyzu/patchright
