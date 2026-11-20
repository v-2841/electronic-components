# electronic-components

Учёт радиодеталей: что есть, сколько и где лежит. Сайт на Django с входом
по паролю и REST API.

- **Детали** — название, категория, номинал, корпус, монтаж (выводной / SMD),
  производитель, артикул, количество (шт или м), место хранения, фото,
  ссылки на даташит и товар, заметки.
- **Категории** — дерево в два уровня («Диоды → Шоттки»); фильтр по верхней
  категории показывает и все подкатегории.
- **Места хранения** — плоский список («Органайзер 1 / A3»); у детали одно
  место. Детали без места — список «разобрать».
- Поиск по словам во всех текстовых полях, без учёта регистра и для кириллицы
  (SQLite сам кириллицу не складывает — см. `parts/lookups.py`).
- Кнопки ± меняют количество одним запросом к базе, ниже нуля оно не опускается.
- Фото больше 1600 px по длинной стороне при загрузке ужимается в JPEG.

Стек: Python 3.15, Django 6.1, Django REST framework, drf-spectacular,
django-filter, SQLite, Bootstrap 5.3 с CDN (своих стилей нет).

## Запуск для разработки

```bash
poetry env use /usr/bin/python3.15
poetry install
cp .env.example .env   # SECRET_KEY любой, DEBUG=True
poetry run python manage.py migrate
poetry run python manage.py createsuperuser
poetry run python manage.py runserver
```

База — `db.sqlite3` в корне проекта (путь меняется переменной `DB_PATH`),
фото — `media/` (`MEDIA_PATH`). Репозиторий публичный: база, фото и `.env`
в git не попадают.

## Docker

Два контейнера: `app` (gunicorn) и `caddy` — он раздаёт `/static/` и
`/media/`, остальное передаёт в `app`. Наружу — только `127.0.0.1:8012`;
HTTPS делает веб-сервер на хосте, проксируя на этот порт.

```bash
cp .env.example .env   # свой SECRET_KEY из букв и цифр, DEBUG=False
touch db.sqlite3       # без файла Docker создаст на его месте папку
docker compose up -d --build
```

- База `./db.sqlite3`, фото `./media/`, собранная статика `./staticfiles/`
  монтируются в контейнеры и в образ не попадают.
- При старте `app` сам применяет миграции и собирает статику.
- Обновление: `git pull --ff-only && docker compose build app && docker compose up -d`
  (сайт работает, пока идёт сборка).

## Проверки

```bash
poetry run python manage.py test
poetry run flake8
poetry run djlint templates --lint
poetry run djlint templates --check   # --reformat — исправить форматирование
```

## API

Всё под `/api/v1/`, только для вошедших: сессия браузера или токен.
Версия — в адресе: несовместимые изменения (переименование или удаление
полей и методов, смена смысла) — только в новой версии `/api/v2/`, `v1`
при этом остаётся.
Документация и «попробовать» — Swagger на `/api/v1/docs/`, схема OpenAPI —
`/api/v1/schema/` (у каждого поля и метода есть описание).

**ИИ-агентам** — `GET /api/v1/guide/`: инструкция в markdown (доступ, данные,
типовые задачи, правила, ошибки). Текст лежит в `api/guide.md`, адрес API
подставляется из запроса. Агенту достаточно дать адрес сайта и токен.

```bash
# получить токен (он же виден в админке, раздел «Токены»)
curl -X POST https://example.com/api/v1/token/ \
     -d username=<логин> -d password=<пароль>

curl -H 'Authorization: Token <токен>' \
     'https://example.com/api/v1/parts/?q=10 кОм&in_stock=true'
```

| Метод и путь | Что делает |
|---|---|
| `GET/POST /api/v1/parts/` | список (по 50, `page`, `page_size` до 1000) и создание |
| `GET/PUT/PATCH/DELETE /api/v1/parts/{id}/` | одна деталь; фото — multipart-полем `photo`, `null` — убрать |
| `POST /api/v1/parts/{id}/adjust/` | `{"delta": -2}` — изменить количество |
| `/api/v1/categories/`, `/api/v1/categories/{id}/` | категории; `parent` — ID верхней категории или `null` |
| `/api/v1/locations/`, `/api/v1/locations/{id}/` | места хранения |

Фильтры списка деталей: `q` (поиск), `category` (ID; верхняя включает
подкатегории), `location` (ID или `none` — место не указано), `mounting`
(`tht` / `smd`), `in_stock` (`true` / `false`); сортировка `ordering` —
`name`, `quantity`, `created_at`, `updated_at` (с `-` — по убыванию).

Ошибки: третий уровень категорий — 400; удаление категории, где есть детали
или подкатегории, — 409. При удалении места у его деталей место становится
`null`.
