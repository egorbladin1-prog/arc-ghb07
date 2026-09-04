# BANNY SHOP V5 — Neon Store

Полноценный Telegram-магазин: каталог, готовые категории, карточки товаров, промокоды, ручная оплата по реквизитам, загрузка чека через бота, статусы заказа и BANNY CONTROL.

## Важно
GitHub Pages не может выполнять Python API. Mini App нужно открывать по публичному HTTPS-адресу сервера, где запущен `bot.py`. `bot.py` сам раздаёт HTML/CSS/JS и API.

## Переменные
- `BOT_TOKEN` — токен бота
- `ADMIN_ID` — Telegram ID администратора
- `CARD_NUMBER` — реквизиты оплаты
- `MINIAPP_HOST=0.0.0.0`
- `MINIAPP_PORT` — порт хостинга (для Render обычно `10000`)
- `MINIAPP_URL` — публичный HTTPS URL Mini App

## Запуск
```bash
pip install -r requirements.txt
export BOT_TOKEN='...'
export ADMIN_ID='...'
export CARD_NUMBER='2204120135107775'
export MINIAPP_HOST='0.0.0.0'
export MINIAPP_PORT='8080'
export MINIAPP_URL='https://your-domain.example'
python bot.py
```

## Render
В репозитории уже есть `render.yaml`. Создай Web Service из репозитория и задай секреты `BOT_TOKEN`, `ADMIN_ID`, `MINIAPP_URL`. После деплоя поставь `MINIAPP_URL` равным выданному Render HTTPS URL.

## Магазин
Готовые категории: `🔥 BANNY PREMIUM`, `🎮 Игровые моды`, `💻 Софт`, `🧩 Скрипты`, `📦 Проекты`. Новые категории и товары можно добавлять из BANNY CONTROL.

## Оплата
Покупка создаёт заказ и отправляет пользователю реквизиты в бот. Пользователь присылает фото чека в бот, администратор подтверждает/отклоняет его. Telegram Stars в интерфейсе обозначены как отдельная опция, но фактическая интеграция Stars не включена в эту сборку.

## Безопасность
Никогда не коммить `BOT_TOKEN` или GitHub PAT в репозиторий. Если секрет уже публиковался, перевыпусти его.
