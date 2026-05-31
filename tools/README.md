# MILA GOLD — инструменты Instagram + Threads API

Скрипты для работы с Instagram и Threads через официальный Graph API:
аналитика, личные сообщения и публикация.

---

## Часть 1 — настройка (муж делает один раз, ~1 час)

### 1. Установить зависимости

```
pip install requests python-dotenv
```

### 2. Создать файл `.env`

Скопируйте `.env.example` → `.env` (в этой же папке `tools/`) и впишите
свои данные. **Файл `.env` никогда не отправляйте в чат и не выкладывайте
в интернет** — там секреты.

### 3. Получить доступы в Meta

Есть ДВА способа подключить Instagram (выбирается в `.env` через `IG_API_FLOW`):

**Способ A — Instagram Login (новый, проще, Facebook-страница НЕ нужна).** ← рекомендуется
1. https://developers.facebook.com → ваше приложение → **Add Product** → **Instagram**
   (раздел «Instagram API with Instagram Login» / «API setup with Instagram login»).
2. Instagram должен быть **Business** или **Creator** аккаунтом.
3. В разделе Instagram → **Generate access token**: войти в нужный IG-аккаунт,
   разрешить доступ. Скопировать токен.
4. В `.env`: `IG_API_FLOW=instagram_login`, токен → `IG_ACCESS_TOKEN`.
   `IG_USER_ID` можно не заполнять — `check_setup.py --write` подставит сам.

**Способ B — Facebook Login (старый, через Facebook-страницу).**
1. Приложение типа «Business» → продукт **Instagram Graph API**.
2. Instagram — **Business/Creator**, привязан к Facebook-странице.
3. **Graph API Explorer**: добавить разрешения `instagram_basic`,
   `instagram_content_publish`, `instagram_manage_comments`,
   `instagram_manage_insights`, `instagram_manage_messages`, `pages_show_list`.
4. Сгенерировать долгоживущий токен. В `.env`: `IG_API_FLOW=facebook`,
   токен → `IG_ACCESS_TOKEN`, `instagram_business_account.id` → `IG_USER_ID`.

### 4. Проверить, что всё работает

```
python check_setup.py
```

Покажет: жив ли токен, какие разрешения есть, какие страницы видны и
привязан ли Instagram. Когда найдёт IG-аккаунт — запустите
`python check_setup.py --write`, чтобы вписать `IG_USER_ID` и
`IG_ACCESS_TOKEN` в `.env` автоматически. Затем:

```
python get_analytics.py account
```

Если вывело имя аккаунта и число подписчиков — настройка готова.

---

## Часть 2 — использование (через Cowork, 5 минут в неделю)

### Instagram

| Команда | Что делает |
|---|---|
| `python get_analytics.py posts` | Топ постов по вовлечённости + охваты |
| `python get_analytics.py comments` | Все комментарии, помечает заявки (слова «хочу», «цена», «заказ»…) |
| `python get_analytics.py account` | Статистика аккаунта |
| `python get_dms.py` | Все диалоги Direct + последние сообщения |
| `python get_dms.py --unread` | Только непрочитанные |
| `python post_content.py photo --url "https://.../foto.jpg" --caption "..."` | Опубликовать фото |
| `python post_content.py reel --url "https://.../video.mp4" --caption "..."` | Опубликовать Reel |
| `python post_content.py photo --url "..." --caption "..." --threads` | Опубликовать в Instagram **и** Threads сразу |

### Threads

| Команда | Что делает |
|---|---|
| `python get_threads.py posts` | Топ тредов по вовлечённости |
| `python get_threads.py replies` | Ответы к тредам, помечает заявки |
| `python get_threads.py account` | Профиль Threads + подписчики |
| `python post_threads.py text --text "..."` | Опубликовать текстовый тред |
| `python post_threads.py image --url "https://.../foto.jpg" --text "..."` | Тред с картинкой |
| `python post_threads.py video --url "https://.../video.mp4" --text "..."` | Тред с видео |

Каждый запуск сохраняет данные в папку `reports/` (JSON), и Cowork может
по ним строить отчёты и черновики ответов. Примеры команд для Cowork:

```
Запусти get_analytics.py posts → составь отчёт, какие темы заходят лучше
Запусти get_analytics.py comments → подготовь ответы всем, кто написал «ХОЧУ»
Запусти get_dms.py → разбери новые сообщения, подготовь черновики ответов
```

---

## Что важно знать

- ✅ Публикация фото и Reels, чтение комментариев, аналитика — работают сразу.
- ⚠️ **Direct (DMs)** требует прохождения **App Review** в Meta
  (разрешения `instagram_manage_messages`). Пока проверка не пройдена,
  `get_dms.py` вернёт ошибку прав — это ожидаемо, не поломка.
- ⚠️ Публиковать можно только по **публичной ссылке** на медиа
  (локальный файл загрузить нельзя — сначала залейте на хостинг).
- 🔑 Токен живёт 60 дней. Когда перестанет работать — сгенерируйте новый
  и обновите `IG_ACCESS_TOKEN` в `.env`.

## Threads

- Threads — **отдельный API** (своё приложение, токен `THREADS_ACCESS_TOKEN`,
  ID `THREADS_USER_ID`, хост `graph.threads.net`). Заполните Threads-блок в `.env`.
- Публикация треда — в 2 шага (контейнер → публикация), как у Reels; для видео
  скрипт ждёт `status=FINISHED`. Медиа — только по публичной ссылке.
- `post_content.py --threads` дублирует ту же публикацию в Threads (photo→image,
  reel→video) — один вызов публикует и в Instagram, и в Threads.

## Файлы

- `_common.py` — общие функции (не запускается напрямую). Содержит и Instagram-
  (`load_config`), и Threads-конфиг (`load_threads_config`); запросы общие.
- `check_setup.py` — диагностика доступов (токен, scopes, страницы, IG). Запускать
  после каждого обновления токена; `--write` вписывает найденные ID в `.env`.
- `get_analytics.py`, `get_dms.py`, `post_content.py` — Instagram.
- `get_threads.py`, `post_threads.py` — Threads.
- `.env.example` — шаблон; ваш реальный `.env` рядом, в чат не отправлять.
