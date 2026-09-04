import telebot
import time
import ftplib
import io
import json
import os
import re
import socket
import threading
import requests
import random
import subprocess
import shutil
import zipfile
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReactionTypeEmoji

TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_USERNAME = "@dev_tokio"
CARD_NUMBER = os.getenv("CARD_NUMBER", "2204120135107775")
PRICE = 699
SUB_CHANNEL = "@bannystudios"

# Telegram Mini App
MINIAPP_URL = os.getenv("MINIAPP_URL", "")
MINIAPP_HOST = os.getenv("MINIAPP_HOST", "0.0.0.0")
MINIAPP_PORT = int(os.getenv("MINIAPP_PORT", "8080"))
MINIAPP_DIR = os.path.dirname(os.path.abspath(__file__))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Export BOT_TOKEN before starting the bot.")

bot = telebot.TeleBot(TOKEN)
DATA_FILE = "bunny_data.json"

REACTIONS = ["🔥", "👍", "❤️", "👏", "⚡", "🎉", "💯", "😍"]

def send_with_reaction(chat_id, text, keyboard=None, parse_mode="HTML"):
    try:
        if keyboard:
            msg = bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode=parse_mode)
        else:
            msg = bot.send_message(chat_id, text, parse_mode=parse_mode)
        try:
            reaction = random.choice(REACTIONS)
            bot.set_message_reaction(chat_id, msg.message_id, [ReactionTypeEmoji(emoji=reaction)], is_big=False)
        except:
            pass
        return msg
    except:
        return None

def send_colored_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        msg_id = result.get('result', {}).get('message_id')
        if msg_id:
            try:
                reaction = random.choice(REACTIONS)
                bot.set_message_reaction(chat_id, msg_id, [ReactionTypeEmoji(emoji=reaction)], is_big=False)
            except:
                pass
    except:
        try:
            send_with_reaction(chat_id, text, None)
        except:
            pass

def save_user_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": {str(k): v for k, v in user_data.items()}, "promos": promocodes, "categories": SHOP_CATEGORIES, "receipts": receipts, "orders": orders, "support_chats": support_chats}, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        print(f"[save] {ex}")

def load_user_data():
    global user_data, promocodes, receipts, orders, support_chats, SHOP_CATEGORIES
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                user_data = {int(k): v for k, v in data.get("users", {}).items()}
                promocodes = data.get("promos", {})
                saved_categories = data.get("categories", {})
                for key, value in saved_categories.items():
                    if key != "banny_premium_v3":
                        SHOP_CATEGORIES[key] = value
                receipts = data.get("receipts", {})
                orders = data.get("orders", {})
                support_chats = data.get("support_chats", {})
        except:
            user_data = {}
            promocodes = {}
            orders = {}
            support_chats = {}
    else:
        user_data = {}
        promocodes = {}

def notify_admin(text, keyboard=None):
    try:
        send_with_reaction(ADMIN_ID, text, keyboard)
    except:
        pass

def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(SUB_CHANNEL, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

bot.set_my_commands([
    telebot.types.BotCommand("/start", "Главное меню"),
    telebot.types.BotCommand("/help", "Помощь"),
    telebot.types.BotCommand("/cancel", "Отменить")
])

original_send = bot.send_message
def safe_send(*args, **kwargs):
    try:
        return original_send(*args, **kwargs)
    except:
        pass
bot.send_message = safe_send

user_data = {}
promocodes = {}
receipts = {}
orders = {}
support_chats = {}

def get_user(uid):
    if uid not in user_data:
        user_data[uid] = {}
    return user_data[uid]

def touch_user(message):
    uid = message.from_user.id
    u = get_user(uid)
    u["first_name"] = message.from_user.first_name or u.get("first_name", "")
    u["last_name"] = message.from_user.last_name or u.get("last_name", "")
    u["username"] = message.from_user.username or u.get("username", "")
    u["language_code"] = getattr(message.from_user, "language_code", None) or u.get("language_code", "")
    u["last_seen"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return u

def chat_log(uid, sender, text, kind="text"):
    key = str(uid)
    support_chats.setdefault(key, [])
    support_chats[key].append({"sender": sender, "text": str(text or ""), "kind": kind, "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "ts": time.time()})
    support_chats[key] = support_chats[key][-300:]

def mark_chat_read(uid):
    get_user(uid)["admin_read_at"] = time.time()

def unread_count(uid):
    read_at = float(get_user(uid).get("admin_read_at", 0) or 0)
    return sum(1 for m in support_chats.get(str(uid), []) if m.get("sender") == "user" and float(m.get("ts", 0) or 0) > read_at)

def create_order(uid, product_key, title, amount, method="card"):
    oid = "BN" + str(int(time.time()*1000))[-10:] + str(random.randint(10,99))
    while oid in orders:
        oid = "BN" + str(int(time.time()*1000))[-10:] + str(random.randint(10,99))
    orders[oid] = {"id": oid, "user_id": uid, "product": product_key, "title": title, "amount": amount, "payment_method": method, "status": "paying", "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    return oid

COLORS = {
    "red": ("🔴 Красный", "0xFF0000FF"),
    "blue": ("🔵 Синий", "0x0000FFFF"),
    "green": ("🟢 Зелёный", "0x00FF00FF"),
    "yellow": ("🟡 Жёлтый", "0xFFFF00FF"),
    "purple": ("🟣 Фиолетовый", "0x800080FF"),
    "orange": ("🟠 Оранжевый", "0xFFA500FF"),
    "white": ("⚪ Белый", "0xFFFFFFFF")
}

BANNY_PRODUCT = {
    "name": "BANNY PREMIUM V3",
    "price": 699,
    "desc": "🔥 ВЫХОДИТ В ПРОДАЖУ КОМПЛЕКТ BANNY PREMIUM V3\n\n🎮 В моде множество систем из оригинального BLACK RUSSIA.\n\n❓ Что входит:\n1. Лаунчер х Исходники - 32/64\n2. Игровой мод - FULL VERSION\n3. Полная кастомизация\n4. Убрано авторство\n\n🌐 Функционал:\n— Работы новичков\n— Стайлинг центр\n— Шиномонтажный\n— Контейнеры\n— Планшет\n— Автосалоны\n— GPS x Навигатор\n— Выбор спавна\n— Скины x Пол\n— Регистрация\n— /reward\n— Кейсы\n— Донат меню\n— Аукцион\n— Багажник\n\n💸 Цена: 699₽",
    "functional": "Работы новичков, стайлинг центр, шиномонтажный, контейнеры, планшет, автосалоны, GPS, выбор спавна, скины x пол, регистрация, /reward, кейсы, донат меню, аукцион, багажник"
}


# -------------------- SHOP / UI --------------------
# Put optional Telegram photo file IDs or local paths here. If a photo is not
# configured, the bot falls back to a normal message, so the UI still works.
# Local images: put the photos folder next to bot.py.
PHOTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")
SHOP_PHOTO = os.path.join(PHOTOS_DIR, "shop.png")
PRODUCT_PHOTO = os.path.join(PHOTOS_DIR, "banny_premium_v3.png")
PROFILE_PHOTO = os.path.join(PHOTOS_DIR, "profile.png")
SUPPORT_PHOTO = os.path.join(PHOTOS_DIR, "support.png")
REVIEWS_PHOTO = os.path.join(PHOTOS_DIR, "reviews.png")
COMPILER_PHOTO = os.path.join(PHOTOS_DIR, "compiler.png")
PROJECTS_PHOTO = os.path.join(PHOTOS_DIR, "my_projects.png")

SHOP_CATEGORIES = {
    "banny_premium_v3": {
        "title": "🔥 BANNY PREMIUM",
        "price": 0,
        "description": (
            "🔥 <b>BANNY PREMIUM V3</b>\n\n"
            "🎮 <b>Полная версия игрового мода</b> с большим набором систем.\n\n"
            "📦 <b>В комплекте:</b>\n"
            "• Лаунчер × исходники — 32/64\n"
            "• Игровой мод — FULL VERSION\n"
            "• Полная кастомизация\n"
            "• Убрано авторство\n\n"
            "💰 <b>Цена: 699₽</b>"
        ),
        "callback": "show_banny_product",
    },
    # Добавляй сюда следующие товары вручную — они НЕ создаются из админки.
    # "next_product": {
    #     "title": "🆕 НОВЫЙ ТОВАР",
    #     "price": 999,
    #     "description": "...",
    #     "callback": "show_next_product",
    # },
}

# Initialize/load saved data only after SHOP_CATEGORIES exists.
load_user_data()
SHOP_CATEGORIES["banny_premium_v3"].setdefault("products", [])

def shop_main_keyboard():
    """Уровень 1: только категории магазина."""
    rows = []
    for key, category in SHOP_CATEGORIES.items():
        rows.append([{
            "text": category.get("title", key),
            "callback_data": "category_" + key,
            "style": "primary"
        }])
    rows.append([{
        "text": "🔙 Главное меню",
        "callback_data": "back_to_main",
        "style": "danger"
    }])
    return rows

def send_photo_or_message(cid, photo, text, keyboard=None):
    """Send a local photo with the caption and attach the keyboard to the photo."""
    try:
        if photo and os.path.isfile(photo):
            with open(photo, "rb") as image_file:
                markup = None
                if keyboard:
                    markup = telebot.types.InlineKeyboardMarkup()
                    for row in keyboard:
                        buttons = []
                        for item in row:
                            buttons.append(
                                telebot.types.InlineKeyboardButton(
                                    text=item["text"],
                                    callback_data=item.get("callback_data"),
                                    url=item.get("url")
                                )
                            )
                        markup.row(*buttons)
                bot.send_photo(
                    cid,
                    image_file,
                    caption=text,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
            return
    except Exception as ex:
        print(f"[photo] {ex}")
    send_colored_message(cid, text, keyboard)

def legacy_show_shop(cid):
    text = (
        "🛍 <b>SHOP BANNY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛠 <b>Сборка проектов, компилятор — всё в одном месте.</b>\n\n"
        "👇 <b>Выбери нужный раздел ниже.</b>\n\n"
        "💳 <b>Оплата принимается:</b> переводом на карту, Telegram Stars, СБП\n"
        "⚡ <b>После оплаты товар выдаётся автоматически.</b>\n\n"
        "📦 <b>ТОВАРЫ</b>"
    )
    send_photo_or_message(cid, SHOP_PHOTO, text, shop_main_keyboard())

def legacy_show_banny_product(cid):
    product = SHOP_CATEGORIES["banny_premium_v3"]
    keyboard = [
        [{"text": f"🏎 Купить за {product['price']}₽", "callback_data": "buy_access", "style": "success"}],
        [{"text": "📋 Весь функционал", "callback_data": "show_functional", "style": "primary"}],
        [{"text": "⭐ Отзывы", "url": "https://t.me/bannyotzv", "style": "primary"}],
        [{"text": "🎟 Промокод", "callback_data": "enter_promo", "style": "primary"}],
        [{"text": "🔙 Назад в магазин", "callback_data": "back_to_shop", "style": "danger"}],
    ]
    send_photo_or_message(cid, PRODUCT_PHOTO, product["description"], keyboard)

def show_section(cid, title, body, photo="", keyboard=None):
    text = f"📌 <b>{title}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{body}"
    send_photo_or_message(cid, photo, text, keyboard)

def send_subscription_menu(cid):
    keyboard = [[{"text": "📢 Подписаться", "url": "https://t.me/bannystudios"}]]
    keyboard.append([{"text": "✅ Проверить", "callback_data": "check_sub", "style": "success"}])
    text = (
        "⛔️ <b>ОБЯЗАТЕЛЬНАЯ ПОДПИСКА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📢 <b>Для продолжения подпишитесь на:</b>\n"
        "<b>@bannystudios</b>\n\n"
        "✅ <b>После подписки нажмите «Проверить».</b>"
    )
    send_colored_message(cid, text, keyboard)

def send_agreement(cid):
    keyboard = [
        [{"text": "✅ Принимаю", "callback_data": "accept_agreement", "style": "success"}],
        [{"text": "❌ Отклоняю", "callback_data": "reject_agreement", "style": "danger"}]
    ]
    text = (
        "📋 <b>КОНФИДЕНЦИАЛЬНОСТЬ И ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Продолжая, вы подтверждаете согласие с:\n\n"
        "• <b>Политикой конфиденциальности</b>\n"
        "• <b>Пользовательским соглашением</b>\n"
        "• <b>Правилами использования</b>\n\n"
        "👇 <b>Выберите действие:</b>"
    )
    send_colored_message(cid, text, keyboard)

def show_shop(cid):
    keyboard = [
        [{"text": "🔥 BANNY PREMIUM V3 — 699₽", "callback_data": "show_banny_product", "style": "primary"}]
    ]
    keyboard.append([{"text": "🔙 Назад", "callback_data": "back_to_main", "style": "danger"}])
    
    text = (
        "🛍 <b>SHOP BANNY</b>\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "🛠 <b>Сборка проектов, компилятор все в одном месте.</b>\n\n"
        "👇 <b>Выбери нужный раздел ниже:</b>\n\n"
        "💳 <b>Оплата:</b> Переводом на карту\n"
        "⚡ <b>После оплаты сразу выдаётся товар</b>"
    )
    send_colored_message(cid, text, keyboard)

def show_banny_product(cid):
    keyboard = [
        [{"text": "🏎 Купить за 699₽", "callback_data": "buy_access", "style": "success"}],
        [{"text": "📋 Весь функционал", "callback_data": "show_functional", "style": "primary"}],
        [{"text": "⭐ Отзывы", "url": "https://t.me/bannyotzv", "style": "primary"}],
        [{"text": "🎟 Промокод", "callback_data": "enter_promo", "style": "primary"}],
        [{"text": "🔙 В магазин", "callback_data": "back_to_shop", "style": "danger"}]
    ]
    send_colored_message(cid, BANNY_PRODUCT['desc'], keyboard)

def start_install(cid, u):
    u['state'] = None
    u['in_progress'] = True
    send_with_reaction(cid, "🔔 <b>Начинаю установку проекта...</b>")
    try:
        ftp = ftplib.FTP()
        ftp.connect(u['ftp_data'][0], timeout=60)
        ftp.login(u['ftp_data'][1], u['ftp_data'][2])
        project_name = u.get('project_name', 'Banny Server')
        color_code = u.get('server_color', '0xFFFFFFFF')
        cfg_content = f"hostname {project_name}\nbind {u['server_ip']}\nport {u.get('server_port', 7777)}\nserver_color {color_code}\n"
        cfg_io = io.BytesIO(cfg_content.encode('utf-8'))
        ftp.storbinary('STOR server.cfg', cfg_io)
        local_mod_dir = "modbyba"
        if os.path.exists(local_mod_dir):
            def upload_ftp_tree(ftp_conn, local_dir):
                for item in os.listdir(local_dir):
                    local_path = os.path.join(local_dir, item)
                    if item in ["byba.sql", "server.cfg"]:
                        continue
                    if os.path.isfile(local_path):
                        with open(local_path, 'rb') as f:
                            ftp_conn.storbinary(f'STOR {item}', f)
                    elif os.path.isdir(local_path):
                        try: ftp_conn.mkd(item)
                        except: pass
                        try:
                            ftp_conn.cwd(item)
                            upload_ftp_tree(ftp_conn, local_path)
                            ftp_conn.cwd("..")
                        except: pass
            upload_ftp_tree(ftp, local_mod_dir)
        try:
            try: ftp.cwd('scriptfiles')
            except:
                ftp.mkd('scriptfiles')
                ftp.cwd('scriptfiles')
            ini_content = f"host = {u['server_ip']}\nusername = {u['db_user']}\npassword = {u['db_pass']}\ndatabase = {u['db_name']}\n"
            ini_io = io.BytesIO(ini_content.encode('utf-8'))
            ftp.storbinary('STOR mysql_settings.ini', ini_io)
            ftp.cwd('..')
        except: pass
        ftp.quit()
        sql_path = os.path.join(local_mod_dir, "byba.sql")
        if os.path.exists(sql_path):
            with open(sql_path, "rb") as sql_file:
                bot.send_document(cid, sql_file, caption="🗄 <b>Импортируйте в phpMyAdmin!</b>", parse_mode="HTML")
        color_display = COLORS.get(u.get('server_color_name', ''), ('⚪ Белый', ''))[0]
        caption = "✅ <b>Проект установлен!</b>\n\n🏷 <b>Название:</b> " + project_name + "\n📡 <b>IP:</b> <code>" + str(u['server_ip']) + ":" + str(u.get('server_port', 7777)) + "</code>\n🎨 <b>Цвет:</b> " + color_display + "\n🎁 <b>Бонусы:</b> 💰" + str(u['bonus_money']) + " 💎" + str(u['bonus_donate'])
        send_with_reaction(cid, caption)
        try:
            with open("launcher/launcher.apk", "rb") as apk:
                bot.send_document(cid, apk, caption="📱 <b>Ваш лаунчер!</b>", parse_mode="HTML")
        except: pass
        u['project_status'] = 'installed'
        u['in_progress'] = False
        save_user_data()
        notify_admin("📋 <b>НОВЫЙ ЗАКАЗ!</b>\n\n👤 @" + str(u.get('username', 'нет')) + "\n🏷 " + project_name + "\n📡 " + str(u['server_ip']) + ":" + str(u.get('server_port', 7777)))
        return True
    except Exception as e:
        send_with_reaction(cid, "🚨 <b>Ошибка:</b> <code>" + str(e) + "</code>")
        notify_admin("🚨 <b>Ошибка у юзера " + str(cid) + "!</b>\n" + str(e))
        u['in_progress'] = False
        return False


def make_product_key(category_key, title):
    base = re.sub(r"[^a-z0-9_]+", "_", title.lower()).strip("_") or "product"
    key = category_key + "_" + base
    existing = set()
    for cat in SHOP_CATEGORIES.values():
        for i, product in enumerate(cat.get("products", [])):
            existing.add(str(product.get("key", f"product_{i}")))
    candidate = key
    n = 2
    while candidate in existing or candidate == "banny_premium_v3":
        candidate = key + "_" + str(n)
        n += 1
    return candidate

def admin_product_category_keyboard():
    rows=[]
    for key, cat in SHOP_CATEGORIES.items():
        rows.append([{"text":"📁 "+str(cat.get("title",key)),"callback_data":"admin_product_cat_"+key}])
    rows.append([{"text":"🔙 Админ-панель","callback_data":"back_to_admin"}])
    return rows

def is_admin_user(user_id):
    return user_id == ADMIN_ID or bool(get_user(user_id).get('is_admin'))

def admin_panel(chat_id):
    keyboard = [
        [{"text": "📊 Статистика", "callback_data": "admin_stats"}],
        [{"text": "📋 Заказы", "callback_data": "admin_orders"}],
        [{"text": "🧾 Список чеков", "callback_data": "admin_receipts"}],
        [{"text": "🗂 Категории магазина", "callback_data": "admin_categories"}],
        [{"text": "📢 Рассылка", "callback_data": "admin_broadcast"}],
        [{"text": "💬 Чаты", "callback_data": "admin_chats"}],
        [{"text": "🎁 Выдать доступ", "callback_data": "admin_give_access"}],
        [{"text": "🚫 Забрать доступ", "callback_data": "admin_take_access"}],
        [{"text": "🎟 Создать промокод", "callback_data": "admin_create_promo"}],
        [{"text": "👑 Выдать админа", "callback_data": "admin_give_admin"}],
        [{"text": "📤 Отправить лаунчер", "callback_data": "admin_send_launcher"}],
        [{"text": "🏠 Главное меню", "callback_data": "back_to_main", "style": "danger"}],
    ]
    send_colored_message(chat_id, "👑 <b>АДМИН-ПАНЕЛЬ</b>\n━━━━━━━━━━━━━━━━━━━━\n\nВыберите действие:", keyboard)

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "⛔ <b>Доступ запрещён.</b>", parse_mode="HTML")
        return
    admin_panel(message.chat.id)

@bot.message_handler(commands=['start', 'help'])
def start(message):
    cid = message.chat.id
    u = get_user(cid)
    if not message.from_user.is_bot:
        u['username'] = message.from_user.username
    
    if not u.get('notified'):
        notify_admin("🔔 <b>Новый пользователь!</b>\n\nID: " + str(cid) + "\nUsername: @" + str(u.get('username', 'нет')))
        u['notified'] = True
    
    first_name = message.from_user.first_name or "друг"
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if MINIAPP_URL:
        markup.add(KeyboardButton("🛍 BANNY SHOP", web_app=telebot.types.WebAppInfo(url=MINIAPP_URL)))
    else:
        markup.add(KeyboardButton("🛍 Магазин"))
    markup.add(KeyboardButton("📋 Мои проекты"))
    markup.add(KeyboardButton("⚙️ Компилятор"), KeyboardButton("👤 Профиль"))
    markup.add(KeyboardButton("👨‍💻 Поддержка"), KeyboardButton("⭐ Отзывы"))
    if is_admin_user(cid):
        markup.add(KeyboardButton("👑 Админ-панель"))
    
    text = (
        "🚀 <b>ПРИВЕТ, " + first_name.upper() + "!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛠 <b>Сборка проектов, компилятор и готовые решения — в одном месте.</b>\n\n"
        "⚡ <b>Быстро. Удобно. Автоматически.</b>\n\n"
        "👇 <b>Выбери нужный раздел:</b>"
    )
    
    send_with_reaction(cid, text, markup)

@bot.message_handler(func=lambda message: message.text in ["🛍 Магазин", "📋 Мои проекты", "⚙️ Компилятор", "👤 Профиль", "👨‍💻 Поддержка", "⭐ Отзывы", "👑 Админ-панель"])
def handle_keyboard(message):
    cid = message.chat.id
    u = get_user(cid)
    
    if message.text == "👑 Админ-панель":
        if is_admin_user(cid):
            admin_panel(cid)
        return

    if message.text == "🛍 Магазин":
        if not is_subscribed(cid):
            send_subscription_menu(cid)
            return
        
        if not u.get('agreement_accepted'):
            send_agreement(cid)
            return
        
        show_shop(cid)
    
    elif message.text == "📋 Мои проекты":
        if not u.get('project_name'):
            show_section(cid, "МОИ ПРОЕКТЫ", "📂 <b>У вас пока нет созданных проектов.</b>\n\nНажмите «Создать проект», когда приобретёте доступ.", PROJECTS_PHOTO)
            return
        color_display = COLORS.get(u.get('server_color_name', ''), ('⚪ Белый', ''))[0]
        text = "📋 <b>МОЙ ПРОЕКТ</b>\n\n🏷 <b>Проект:</b> " + u.get('project_name', 'Нет') + "\n📡 <b>IP:</b> <code>" + str(u.get('server_ip', 'Нет')) + ":" + str(u.get('server_port', 7777)) + "</code>\n🎨 <b>Цвет:</b> " + color_display + "\n📊 <b>Статус:</b> " + u.get('project_status', 'в процессе')
        send_with_reaction(cid, text)
    
    elif message.text == "⚙️ Компилятор":
        keyboard = [[{"text": "🔧 JNI компилятор", "callback_data": "compiler_jni", "style": "primary"}]]
        show_section(cid, "КОМПИЛЯТОР", "🔧 <b>Выберите инструмент для сборки проекта:</b>", COMPILER_PHOTO, keyboard)
    
    elif message.text == "👤 Профиль":
        status = "✅ Куплен" if u.get('has_access') else "❌ Не куплен"
        username = message.from_user.username or "не указан"
        text = "👤 <b>ПРОФИЛЬ</b>\n━━━━━━━━━━━━━━━━━━━━\n\n👤 <b>Username:</b> @" + username + "\n🆔 <b>ID:</b> <code>" + str(cid) + "</code>\n🔑 <b>Доступ:</b> " + status + "\n💸 <b>Скидка:</b> " + str(u.get('discount', 0)) + "%"
        keyboard = [[{"text": "🎟 Ввести промокод", "callback_data": "enter_promo", "style": "primary"}], [{"text": "🛠 Создать проект", "callback_data": "create_project", "style": "success"}]]
        send_colored_message(cid, text, keyboard)
    
    elif message.text == "👨‍💻 Поддержка":
        show_section(cid, "ПОДДЕРЖКА", "👨‍💻 <b>Нужна помощь? Выберите действие ниже.</b>", SUPPORT_PHOTO, [[{"text": "💬 Написать в поддержку", "url": "https://t.me/dev_tokio"}], [{"text": "📨 Обратиться", "url": "https://t.me/dev_tokio"}], [{"text": "🏠 Главное меню", "callback_data": "back_to_main", "style": "danger"}]])
    
    elif message.text == "⭐ Отзывы":
        keyboard = [[{"text": "⭐ Отзывы", "url": "https://t.me/bannyotzv"}]]
        show_section(cid, "ОТЗЫВЫ", "⭐ <b>Отзывы наших пользователей смотрите в официальном канале:</b>", REVIEWS_PHOTO, keyboard)


def server_color_keyboard():
    rows = []
    for key, value in COLORS.items():
        rows.append([InlineKeyboardButton(value[0], callback_data="server_color_" + key)])
    return InlineKeyboardMarkup(rows)

def find_shop_product(product_key):
    if product_key == "banny_premium_v3":
        cat = SHOP_CATEGORIES.get("banny_premium_v3", {})
        return "banny_premium_v3", {
            "key": "banny_premium_v3",
            "title": "🔥 BANNY PREMIUM V3",
            "price": 699,
            "description": cat.get("description", BANNY_PRODUCT.get("desc", "")),
            "functional": BANNY_PRODUCT.get("functional", ""),
            "photo": PRODUCT_PHOTO,
        }
    for category_key, category in SHOP_CATEGORIES.items():
        for index, product in enumerate(category.get("products", [])):
            key = str(product.get("key", f"{category_key}_{index}"))
            if key == str(product_key):
                p = dict(product)
                p.setdefault("key", key)
                p.setdefault("title", f"Товар {index + 1}")
                p.setdefault("price", 0)
                p.setdefault("description", "Описание отсутствует.")
                p.setdefault("functional", "Функционал не указан.")
                p.setdefault("photo", category.get("photo", SHOP_PHOTO))
                return category_key, p
    return None, None


def product_keyboard(category_key, product):
    key = str(product.get("key", ""))
    if key == "banny_premium_v3":
        buy_callback = "buy_access"
    else:
        buy_callback = "buy_product_" + key
    return [
        [{"text": "💳 Купить за " + str(product.get("price", 0)) + "₽", "callback_data": buy_callback, "style": "success"}],
        [{"text": "📋 Весь функционал", "callback_data": "product_functional_" + key, "style": "primary"}],
        [{"text": "⭐ Отзывы", "url": "https://t.me/bannyotzv", "style": "primary"}],
        [{"text": "🎟 Промокод", "callback_data": "enter_promo", "style": "primary"}],
        [{"text": "🔙 К товарам", "callback_data": "category_" + category_key, "style": "danger"}],
        [{"text": "🛍 К категориям", "callback_data": "back_to_shop"}],
    ]


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    cid = call.message.chat.id
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    u = get_user(cid)
    

    if call.data.startswith("server_color_"):
        color_key = call.data[len("server_color_"):]
        if color_key not in COLORS:
            bot.answer_callback_query(call.id, "❌ Цвет не найден", show_alert=True)
            return
        u['server_color_name'] = color_key
        save_user_data()
        color_display = COLORS[color_key][0]
        bot.answer_callback_query(call.id, "✅ Цвет выбран")
        bot.send_message(
            cid,
            "🎨 <b>Цвет сервера выбран:</b> " + color_display,
            parse_mode="HTML"
        )
        # Continue the project setup if the next state is waiting for color.
        if u.get('state') == 'waiting_server_color':
            u['state'] = None
        return

    if call.data.startswith("approve_") or call.data.startswith("reject_"):
        if not is_admin_user(cid):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещён", show_alert=True)
            return

        parts = call.data.split("_")
        if len(parts) < 2:
            bot.answer_callback_query(call.id, "❌ Некорректный чек", show_alert=True)
            return

        try:
            user_id = int(parts[1])
        except ValueError:
            bot.answer_callback_query(call.id, "❌ Некорректный ID", show_alert=True)
            return

        receipt_id = parts[2] if len(parts) > 2 else None
        receipt = receipts.get(receipt_id) if receipt_id else None

        # Do not process the same receipt twice.
        if receipt and receipt.get("status") != "ожидает":
            bot.answer_callback_query(
                call.id,
                "ℹ️ Чек уже обработан: " + str(receipt.get("status")),
                show_alert=True
            )
            return

        approved = call.data.startswith("approve_")

        if receipt_id and receipt:
            receipt["status"] = "подтверждён" if approved else "отклонён"
            oid = receipt.get("order_id")
            if oid in orders:
                orders[oid]["status"] = "paid" if approved else "rejected"
                orders[oid]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            receipt["processed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            receipt["processed_by"] = cid

        if approved:
            target = get_user(user_id)
            target["has_access"] = True
            target["state"] = "waiting_ftp"
            target["project_status"] = "ожидает данные проекта"
            target["selected_product"] = receipt.get("product", "banny_premium_v3") if receipt else "banny_premium_v3"
            target["selected_product_price"] = receipt.get("amount", PRICE) if receipt else PRICE
            save_user_data()

            # Immediate callback response so the Telegram button visibly reacts.
            bot.answer_callback_query(call.id, "✅ Оплата подтверждена")

            # Remove action buttons from the admin receipt message and show status.
            try:
                status_keyboard = InlineKeyboardMarkup()
                status_keyboard.add(
                    InlineKeyboardButton("✅ Оплата подтверждена", callback_data="receipt_done")
                )
                bot.edit_message_reply_markup(
                    cid,
                    call.message.message_id,
                    reply_markup=status_keyboard
                )
            except Exception:
                pass

            # Immediately begin project onboarding.
            send_with_reaction(
                user_id,
                "🎉 <b>Оплата подтверждена!</b>\n\n"
                "🛠 <b>Теперь создадим ваш проект.</b>\n"
                "После получения данных бот автоматически настроит сервер, "
                "загрузит мод и выполнит установку.\n\n"
                "ℹ️ <b>Шаг 1 из 6 — данные FTP</b>\n\n"
                "Отправьте одной строкой:\n"
                "<code>IP ЛОГИН ПАРОЛЬ</code>"
            )
        else:
            if receipt_id and receipt:
                save_user_data()

            bot.answer_callback_query(call.id, "❌ Чек отклонён")

            try:
                status_keyboard = InlineKeyboardMarkup()
                status_keyboard.add(
                    InlineKeyboardButton("❌ Чек отклонён", callback_data="receipt_done")
                )
                bot.edit_message_reply_markup(
                    cid,
                    call.message.message_id,
                    reply_markup=status_keyboard
                )
            except Exception:
                pass

            send_with_reaction(
                user_id,
                "❌ <b>Оплата отклонена.</b>\n\n"
                "Если это произошло по ошибке, отправьте новый чек."
            )
        return

    if call.data == "receipt_done":
        bot.answer_callback_query(call.id, "ℹ️ Чек уже обработан")
        return

    if call.data == "check_sub":
        if is_subscribed(cid):
            bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
            if not u.get('agreement_accepted'):
                send_agreement(cid)
            else:
                show_shop(cid)
        else:
            bot.answer_callback_query(call.id, "❌ Вы не подписались!", show_alert=True)
        return
    
    if call.data == "accept_agreement":
        u['agreement_accepted'] = True
        save_user_data()
        bot.answer_callback_query(call.id, "✅ Принято!")
        show_shop(cid)
        return
    
    if call.data == "reject_agreement":
        bot.answer_callback_query(call.id, "❌ Отклонено")
        send_with_reaction(cid, "❌ <b>Вы отклонили соглашение.</b>")
        return
    
    if call.data == "back_to_main":
        try: bot.delete_message(cid, call.message.message_id)
        except: pass
        start(call.message)
        return
    
    if call.data == "back_to_shop":
        show_shop(cid)
        return
    
    if call.data.startswith("category_"):
        category_key = call.data.replace("category_", "", 1)
        if category_key in SHOP_CATEGORIES:
            show_category(cid, category_key)
        return

    if call.data.startswith("shop_product_"):
        product_key = call.data[len("shop_product_"):]
        category_key, product = find_shop_product(product_key)
        if not product:
            bot.answer_callback_query(call.id, "❌ Товар не найден", show_alert=True)
            return
        bot.answer_callback_query(call.id, "🛒 Товар открыт")
        send_photo_or_message(
            cid,
            product.get("photo", SHOP_PHOTO),
            "🛒 <b>" + str(product.get("title", "Товар")) + "</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n" +
            str(product.get("description", "Описание отсутствует.")) + "\n\n"
            "💰 <b>Цена: " + str(product.get("price", 0)) + "₽</b>",
            product_keyboard(category_key, product)
        )
        return

    if call.data.startswith("product_info_"):
        product_key = call.data[len("product_info_"):]
        category_key, product = find_shop_product(product_key)
        if not product:
            bot.answer_callback_query(call.id, "❌ Товар не найден", show_alert=True)
            return
        bot.answer_callback_query(call.id, "📋 Описание")
        send_colored_message(
            cid,
            "📋 <b>" + str(product.get("title", "Товар")) + " — ОПИСАНИЕ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n" +
            str(product.get("description", "Описание отсутствует.")),
            [[{"text": "🔙 К товару", "callback_data": "shop_product_" + product_key, "style": "danger"}]]
        )
        return

    if call.data.startswith("product_functional_"):
        product_key = call.data[len("product_functional_"):]
        category_key, product = find_shop_product(product_key)
        if not product:
            bot.answer_callback_query(call.id, "❌ Товар не найден", show_alert=True)
            return
        bot.answer_callback_query(call.id, "📋 Весь функционал")
        send_colored_message(
            cid,
            "📋 <b>" + str(product.get("title", "Товар")) + " — ВЕСЬ ФУНКЦИОНАЛ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n" +
            str(product.get("functional", "Функционал не указан.")),
            [[{"text": "🔙 К товару", "callback_data": "shop_product_" + product_key, "style": "danger"}]]
        )
        return

    if call.data.startswith("buy_product_"):
        product_key = call.data[len("buy_product_"):]
        category_key, product = find_shop_product(product_key)
        if not product:
            bot.answer_callback_query(call.id, "❌ Товар не найден", show_alert=True)
            return
        if u.get('has_access'):
            bot.answer_callback_query(call.id, "✅ У вас уже есть доступ", show_alert=True)
            return
        price = product.get("price", 0)
        try:
            price_num = float(price)
            price = int(price_num) if price_num.is_integer() else price_num
        except Exception:
            pass
        u['selected_product'] = product_key
        u['selected_product_title'] = product.get('title', 'Товар')
        u['selected_product_price'] = price
        u['state'] = "waiting_receipt"
        save_user_data()
        bot.answer_callback_query(call.id, "💳 Оплата")
        send_with_reaction(
            cid,
            "💳 <b>ОПЛАТА ТОВАРА</b>\n\n"
            "🛒 <b>Товар:</b> " + str(product.get('title', 'Товар')) + "\n"
            "💰 <b>Сумма:</b> " + str(price) + "₽\n\n"
            "✅ <b>РЕКВИЗИТЫ:</b>\n"
            "Карта [МИР]: <code>" + CARD_NUMBER + "</code>\n"
            "Банк: YooMoney\n\n"
            "📸 <b>Отправьте чек сюда.</b>"
        )
        return

    if call.data == "show_banny_product":
        show_banny_product(cid)
        return
    
    if call.data == "show_functional":
        text = "📋 <b>ВЕСЬ ФУНКЦИОНАЛ</b>\n\n" + BANNY_PRODUCT['functional']
        keyboard = [[{"text": "🔙 Назад", "callback_data": "show_banny_product", "style": "danger"}]]
        send_colored_message(cid, text, keyboard)
        return
    
    if call.data == "buy_access":
        if u.get('has_access'):
            bot.answer_callback_query(call.id, "✅ Уже куплен!", show_alert=True)
            return
        price = PRICE
        if u.get('discount'):
            price = int(PRICE * (1 - u['discount'] / 100))
        text = "💳 <b>ОПЛАТА</b>\n\n💸 <b>Сумма:</b> " + str(price) + "₽\n\n✅ <b>РЕКВИЗИТЫ:</b>\nКарта [МИР]: <code>" + CARD_NUMBER + "</code>\nБанк: YooMoney\n\n📸 <b>Отправьте чек сюда.</b>\n\n⚡ <i>Автовыдача скоро!</i>"
        send_with_reaction(cid, text)
        u['state'] = "waiting_receipt"
        return
    
    if call.data == "compiler_jni":
        bot.send_message(cid, "🔧 <b>JNI компилятор</b>\n\nОтправьте <code>.zip</code> с папкой <b>jni</b>", parse_mode="HTML")
        u['state'] = "waiting_jni"
        return
    
    if call.data == "enter_promo":
        bot.send_message(cid, "🎟 <b>Введите промокод:</b>", parse_mode="HTML")
        u['state'] = "waiting_promo"
        return
    
    if call.data == "create_project":
        if not u.get('has_access'):
            bot.answer_callback_query(call.id, "❌ Купите доступ!", show_alert=True)
            return
        bot.send_message(cid, "🛠 <b>СОЗДАНИЕ ПРОЕКТА</b>\n\nℹ️ <b>Шаг 1 из 6</b> — FTP\n\nОтправь одной строкой:\n<code>IP ЛОГИН ПАРОЛЬ</code>", parse_mode="HTML")
        u['state'] = "waiting_ftp"
        return
    
    if call.data == "admin_stats":
        paid = sum(1 for uid, d in user_data.items() if d.get('has_access'))
        send_with_reaction(cid, "📊 <b>Юзеров:</b> " + str(len(user_data)) + "\n✅ <b>Купили:</b> " + str(paid))
        return
    
    if call.data == "admin_receipts":
        if not is_admin_user(cid):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещён", show_alert=True)
            return
        if not receipts:
            send_with_reaction(cid, "🧾 <b>Чеков пока нет.</b>")
            return
        text = "🧾 <b>СПИСОК ЧЕКОВ</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        buttons = []
        for rid, receipt in list(receipts.items())[-20:][::-1]:
            status = receipt.get("status", "ожидает")
            username = receipt.get("username", "нет")
            amount = receipt.get("amount", PRICE)
            text += f"#{rid} • @{username} • {amount}₽ • <b>{status}</b>\n"
            buttons.append([{"text": f"🧾 Чек #{rid}", "callback_data": f"receipt_{rid}"}])
        buttons.append([{"text": "🏠 Главное меню", "callback_data": "back_to_main", "style": "danger"}])
        send_colored_message(cid, text, buttons)
        return

    if call.data.startswith("receipt_"):
        if not is_admin_user(cid):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещён", show_alert=True)
            return
        rid = call.data.split("_", 1)[1]
        receipt = receipts.get(rid)
        if not receipt:
            bot.answer_callback_query(call.id, "Чек не найден", show_alert=True)
            return
        uid = receipt.get("user_id")
        markup = [
            [{"text": "✅ Подтвердить", "callback_data": f"approve_{uid}_{rid}", "style": "success"}],
            [{"text": "❌ Отклонить", "callback_data": f"reject_{uid}_{rid}", "style": "danger"}],
            [{"text": "🧾 Список чеков", "callback_data": "admin_receipts"}]
        ]
        send_colored_message(
            cid,
            f"🧾 <b>ЧЕК #{rid}</b>\n\n👤 @{receipt.get('username','нет')}\n🆔 <code>{uid}</code>\n💰 <b>{receipt.get('amount', PRICE)}₽</b>\n📅 {receipt.get('created_at','')}\n📊 <b>{receipt.get('status','ожидает')}</b>",
            markup
        )
        return

    if call.data.startswith("admin_category_"):
        if not is_admin_user(cid):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещён", show_alert=True)
            return
        key = call.data[len("admin_category_"):]
        cat = SHOP_CATEGORIES.get(key)
        if not cat:
            bot.answer_callback_query(call.id, "❌ Категория не найдена", show_alert=True)
            return
        bot.answer_callback_query(call.id, "✅ Открыто")
        send_colored_message(
            cid,
            "📁 <b>" + cat.get("title", key) + "</b>\n\n" + cat.get("description", "Без описания") +
            "\n\n🛒 <b>Товаров:</b> " + str(len(cat.get("products", []))),
            [
                [{"text": "➕ Создать товар", "callback_data": "admin_add_product_" + key, "style": "success"}],
                [{"text": "🗂 Категории магазина", "callback_data": "admin_categories"}]
            ]
        )
        return

    if call.data == "admin_categories":
        if not is_admin_user(cid):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещён", show_alert=True)
            return
        rows = [
            [{"text": "➕ Добавить категорию", "callback_data": "admin_add_category", "style": "success"}],
            [{"text": "🛒 Создать товар", "callback_data": "admin_add_product", "style": "success"}]
        ]
        for key, cat in SHOP_CATEGORIES.items():
            rows.append([{"text": "📁 " + cat.get("title", key), "callback_data": "admin_category_" + key}])
        rows.append([{"text": "🏠 Главное меню", "callback_data": "back_to_main", "style": "danger"}])
        send_colored_message(cid, "🗂 <b>КАТЕГОРИИ МАГАЗИНА</b>\n\n🔥 <b>BANNY PREMIUM V3</b> — постоянная категория, удалить её нельзя.", rows)
        return

    if call.data == "back_to_admin":
        bot.answer_callback_query(call.id, "👑 Админ-панель")
        admin_panel(cid)
        return

    if call.data.startswith("admin_product_cat_"):
        if not is_admin_user(cid):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещён", show_alert=True)
            return
        key = call.data[len("admin_product_cat_"):]
        if key not in SHOP_CATEGORIES:
            bot.answer_callback_query(call.id, "❌ Категория не найдена", show_alert=True)
            return
        u["admin_product_category"] = key
        u["state"] = "admin_waiting_product_title"
        bot.answer_callback_query(call.id, "✅ Категория выбрана")
        bot.send_message(
            cid,
            "🛒 <b>СОЗДАНИЕ ТОВАРА</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "📁 Категория: <b>" + str(SHOP_CATEGORIES[key].get("title", key)) + "</b>\n\n"
            "✏️ <b>Шаг 2 из 6 — название товара</b>\n\n"
            "Отправьте название товара:",
            parse_mode="HTML"
        )
        return

    if call.data == "admin_add_product":
        if not is_admin_user(cid):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещён", show_alert=True)
            return
        u["state"] = "admin_select_product_category"
        send_colored_message(cid, "🛒 <b>СОЗДАНИЕ ТОВАРА</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📁 <b>Шаг 1 из 6 — выберите категорию</b>", admin_product_category_keyboard())
        return

    if call.data.startswith("admin_add_product_"):
        if not is_admin_user(cid):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещён", show_alert=True)
            return
        key=call.data[len("admin_add_product_"):]
        if key not in SHOP_CATEGORIES:
            bot.answer_callback_query(call.id, "❌ Категория не найдена", show_alert=True)
            return
        u["admin_product_category"]=key
        u["state"]="admin_waiting_product_title"
        bot.answer_callback_query(call.id, "✅ Категория выбрана")
        bot.send_message(cid, "🛒 <b>СОЗДАНИЕ ТОВАРА</b>\n\n📁 Категория: <b>"+str(SHOP_CATEGORIES[key].get("title",key))+"</b>\n\n✏️ <b>Шаг 2 из 6 — название товара</b>\n\nОтправьте название товара.", parse_mode="HTML")
        return

    if call.data == "admin_skip_product_photo":
        if not is_admin_user(cid) or u.get("state") != "admin_waiting_product_photo":
            bot.answer_callback_query(call.id, "⛔ Сейчас этот шаг недоступен", show_alert=True)
            return
        key=u["admin_product_category"]; title=u["admin_product_title"]; price=u["admin_product_price"]; desc=u["admin_product_description"]; functional=u["admin_product_functional"]
        product_key=make_product_key(key,title)
        SHOP_CATEGORIES.setdefault(key,{}).setdefault("products",[]).append({"key":product_key,"title":title,"price":price,"description":desc,"functional":functional,"photo":SHOP_CATEGORIES[key].get("photo",SHOP_PHOTO)})
        save_user_data()
        for k in ["admin_product_category","admin_product_title","admin_product_price","admin_product_description","admin_product_functional"]: u.pop(k,None)
        u["state"]=None
        bot.answer_callback_query(call.id,"✅ Товар создан")
        send_with_reaction(cid,"✅ <b>ТОВАР СОЗДАН!</b>\n\n🛒 <b>"+title+"</b>\n💰 Цена: <b>"+str(price)+"₽</b>")
        return

    if call.data == "admin_add_category":
        if not is_admin_user(cid):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещён", show_alert=True)
            return
        u["state"] = "admin_waiting_category"
        bot.send_message(cid, "🗂 <b>Введите категорию в формате:</b>\n<code>Название | Описание</code>\n\nНапример:\n<code>Lua | Готовые Lua-решения</code>", parse_mode="HTML")
        return

    if call.data == "admin_orders":
        orders = []
        for uid, d in user_data.items():
            if d.get('project_name'):
                orders.append((uid, d))
        if not orders:
            send_with_reaction(cid, "📋 <b>Заказов пока нет.</b>")
            return
        text = "📋 <b>СПИСОК ЗАКАЗОВ:</b>\n\n"
        for i, (uid, order) in enumerate(orders, 1):
            text += str(i) + ". <b>" + order.get('project_name', 'Нет') + "</b>\n👤 @" + order.get('username', 'нет') + "\n📡 <code>" + order.get('server_ip', 'Нет') + ":" + str(order.get('server_port', 7777)) + "</code>\n📊 " + order.get('project_status', 'в процессе') + "\n\n"
        send_with_reaction(cid, text)
        return
    
    if call.data == "admin_broadcast":
        bot.send_message(cid, "📢 <b>Текст рассылки:</b>", parse_mode="HTML")
        u['state'] = "admin_waiting_broadcast"
        return
    
    if call.data == "admin_chats":
        bot.send_message(cid, "💬 <b>@username или ID:</b>", parse_mode="HTML")
        u['state'] = "admin_waiting_chat_id"
        return
    
    if call.data == "admin_give_access":
        bot.send_message(cid, "🎁 <b>@username или ID:</b>", parse_mode="HTML")
        u['state'] = "admin_waiting_give_access"
        return
    
    if call.data == "admin_take_access":
        bot.send_message(cid, "🚫 <b>@username или ID:</b>", parse_mode="HTML")
        u['state'] = "admin_waiting_take_access"
        return
    
    if call.data == "admin_create_promo":
        bot.send_message(cid, "🎟 <b>Промокод и скидка:</b>\n<code>PROMO 50</code>", parse_mode="HTML")
        u['state'] = "admin_waiting_create_promo"
        return
    
    if call.data == "admin_give_admin":
        bot.send_message(cid, "👑 <b>@username или ID:</b>", parse_mode="HTML")
        u['state'] = "admin_waiting_give_admin"
        return
    
    if call.data == "admin_send_launcher":
        bot.send_message(cid, "📤 <b>@username или ID:</b>", parse_mode="HTML")
        u['state'] = "admin_waiting_send_launcher"
        return
    
    if call.data.startswith("color_") or call.data.startswith("server_color_"):
        prefix = "color_" if call.data.startswith("color_") else "server_color_"
        color_name = call.data[len(prefix):]
        if color_name not in COLORS:
            bot.answer_callback_query(call.id, "❌ Цвет не найден", show_alert=True)
            return
        display_name, color_code = COLORS[color_name]
        u['server_color_name'] = color_name
        u['server_color'] = color_code
        u['state'] = None
        save_user_data()
        bot.answer_callback_query(call.id, "✅ Цвет выбран!")
        send_with_reaction(cid, "🔔 <b>Начинаю установку...</b>")
        start_install(cid, u)
        return
    try:
        bot.answer_callback_query(call.id, "ℹ️ Готово")
    except Exception:
        pass


@bot.message_handler(content_types=["web_app_data"])
def handle_web_app_data(message):
    touch_user(message)
    """Actions sent by the Mini App through Telegram.WebApp.sendData()."""
    cid = message.chat.id
    u = get_user(cid)
    try:
        payload = json.loads(message.web_app_data.data or "{}")
    except Exception:
        bot.send_message(cid, "❌ <b>Некорректный запрос Mini App.</b>", parse_mode="HTML")
        return

    action = payload.get("action")
    if action in ("buy", "create_order"):
        product_key = str(payload.get("product", ""))
        category_key, product = find_shop_product(product_key)
        if not product:
            bot.send_message(cid, "❌ <b>Товар не найден.</b>", parse_mode="HTML")
            return
        if u.get("has_access"):
            bot.send_message(cid, "✅ <b>У вас уже есть доступ.</b>", parse_mode="HTML")
            return
        price = product.get("price", 0)
        try:
            price_num = float(price)
            price = int(price_num) if price_num.is_integer() else price_num
        except Exception:
            pass
        if product_key == "banny_premium_v3" and u.get("discount"):
            price = int(PRICE * (1 - u["discount"] / 100))
        u["selected_product"] = product_key
        u["selected_product_title"] = product.get("title", "Товар")
        u["selected_product_price"] = price
        order_id = create_order(cid, product_key, product.get("title", "Товар"), price, str(payload.get("payment_method", "card")))
        u["active_order_id"] = order_id
        u["state"] = "waiting_receipt"
        save_user_data()
        send_with_reaction(
            cid,
            "💳 <b>ОПЛАТА ТОВАРА</b>\n\n"
            "🛒 <b>Товар:</b> " + str(product.get("title", "Товар")) + "\n"
            "💰 <b>Сумма:</b> " + str(price) + "₽\n\n"
            "✅ <b>РЕКВИЗИТЫ:</b>\n"
            "Карта [МИР]: <code>" + CARD_NUMBER + "</code>\n"
            "Банк: YooMoney\n\n"
            "📸 <b>Отправьте чек сюда.</b>"
        )
        return

    if action == "promo":
        promo = str(payload.get("code", "")).strip()
        if promo in promocodes:
            u["discount"] = promocodes[promo]
            save_user_data()
            bot.send_message(cid, "✅ <b>Промокод применён!</b>\nСкидка: " + str(promocodes[promo]) + "%", parse_mode="HTML")
        else:
            bot.send_message(cid, "❌ <b>Промокод не найден.</b>", parse_mode="HTML")
        return

    if action == "close":
        return


@bot.message_handler(content_types=["photo"])
def handle_product_photo(message):
    touch_user(message)
    cid=message.chat.id; u=get_user(cid)
    if u.get("state")!="admin_waiting_product_photo" or not is_admin_user(cid): return
    try:
        key=u["admin_product_category"]; title=u["admin_product_title"]; price=u["admin_product_price"]; desc=u["admin_product_description"]; functional=u["admin_product_functional"]
        product_key=make_product_key(key,title)
        file_info=bot.get_file(message.photo[-1].file_id); data=bot.download_file(file_info.file_path)
        os.makedirs(PHOTOS_DIR,exist_ok=True); path=os.path.join(PHOTOS_DIR,"product_"+product_key+".jpg")
        with open(path,"wb") as f: f.write(data)
        SHOP_CATEGORIES.setdefault(key,{}).setdefault("products",[]).append({"key":product_key,"title":title,"price":price,"description":desc,"functional":functional,"photo":path})
        save_user_data()
        for k in ["admin_product_category","admin_product_title","admin_product_price","admin_product_description","admin_product_functional"]: u.pop(k,None)
        u["state"]=None
        send_with_reaction(cid,"✅ <b>ТОВАР СОЗДАН!</b>\n\n🛒 <b>"+title+"</b>\n💰 Цена: <b>"+str(price)+"₽</b>\n🖼 Фото: добавлено")
    except Exception as ex:
        u["state"]=None; send_with_reaction(cid,"🚨 <b>Ошибка сохранения товара:</b>\n<code>"+str(ex)+"</code>")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    touch_user(message)
    cid = message.chat.id
    u = get_user(cid)
    if u.get('state') == "waiting_receipt":
        rid = str(int(time.time() * 1000))
        while rid in receipts:
            rid = str(int(time.time() * 1000) + random.randint(1, 999))
        selected_key = u.get("selected_product", "banny_premium_v3")
        amount = u.get("selected_product_price", PRICE)
        order_id = u.get("active_order_id")
        if not order_id or order_id not in orders:
            _, prod = find_shop_product(selected_key)
            order_id = create_order(cid, selected_key, (prod or {}).get("title", "Товар"), amount, "receipt")
            u["active_order_id"] = order_id
        orders[order_id]["status"] = "checking"
        orders[order_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        receipts[rid] = {
            "user_id": cid,
            "username": u.get("username", "нет"),
            "amount": amount,
            "product": selected_key,
            "order_id": order_id,
            "status": "ожидает",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Подтвердить", callback_data=f"approve_{cid}_{rid}"))
        markup.add(InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{cid}_{rid}"))
        bot.forward_message(ADMIN_ID, cid, message.message_id)
        notify_admin("🚨 <b>НОВЫЙ ЧЕК!</b>\n\n🧾 Чек #" + rid + "\n👤 @" + str(u.get('username', 'нет')) + "\nID: " + str(cid), markup)
        send_with_reaction(cid, "⏳ <b>Чек отправлен!</b>")
        u['state'] = None
        save_user_data()
        u['state'] = None

@bot.message_handler(content_types=['document'])
def handle_document(message):
    touch_user(message)
    cid = message.chat.id
    u = get_user(cid)
    if u.get('state') == "waiting_jni":
        if message.document.file_name.endswith('.zip'):
            send_with_reaction(cid, "⏳ <b>Компилирую...</b>")
            file_info = bot.get_file(message.document.file_id)
            downloaded = bot.download_file(file_info.file_path)
            zip_path = f"jni_{cid}.zip"
            with open(zip_path, 'wb') as f:
                f.write(downloaded)
            success, result = compile_jni_from_zip(cid, zip_path)
            if not success:
                send_with_reaction(cid, result)
            os.remove(zip_path)
            u['state'] = None

@bot.message_handler(content_types=['text'])
def handle_text(message):
    touch_user(message)
    cid = message.chat.id
    u = get_user(cid)
    state = u.get('state')
    if not (is_admin_user(cid) and state and state.startswith("admin_")):
        chat_log(cid, "user", message.text, "text")
    
    if state == "waiting_promo":
        promo = message.text.strip()
        if promo in promocodes:
            u['discount'] = promocodes[promo]
            save_user_data()
            send_with_reaction(cid, "✅ <b>Скидка:</b> " + str(promocodes[promo]) + "%")
        else:
            send_with_reaction(cid, "❌ <b>Не найден.</b>")
        u['state'] = None
        return
    
    if state == "admin_waiting_product_title":
        if not is_admin_user(cid): u["state"]=None; return
        title=message.text.strip()
        if not title: send_with_reaction(cid,"❌ <b>Название не может быть пустым.</b>"); return
        u["admin_product_title"]=title[:100]; u["state"]="admin_waiting_product_price"
        bot.send_message(cid,"💰 <b>Шаг 3 из 6 — цена товара</b>\n\nВведите цену числом, например <code>699</code>.",parse_mode="HTML"); return

    if state == "admin_waiting_product_price":
        if not is_admin_user(cid): u["state"]=None; return
        raw=message.text.strip().replace("₽","").replace(" ","").replace(",",".")
        try:
            value=float(raw)
            if value<0: raise ValueError
            price=int(value) if value.is_integer() else round(value,2)
        except ValueError:
            send_with_reaction(cid,"❌ <b>Введите корректную цену.</b> Например: <code>699</code>"); return
        u["admin_product_price"]=price; u["state"]="admin_waiting_product_description"
        bot.send_message(cid,"📝 <b>Шаг 4 из 6 — описание товара</b>\n\nОтправьте короткое описание товара. Оно будет показано непосредственно в карточке товара.",parse_mode="HTML"); return

    if state == "admin_waiting_product_description":
        if not is_admin_user(cid): u["state"]=None; return
        desc=message.text.strip()
        if not desc: send_with_reaction(cid,"❌ <b>Описание не может быть пустым.</b>"); return
        u["admin_product_description"]=desc[:4000]; u["state"]="admin_waiting_product_functional"
        bot.send_message(cid,"📋 <b>Шаг 5 из 6 — весь функционал</b>\n\nОтправьте полный текст функционала товара.",parse_mode="HTML"); return

    if state == "admin_waiting_product_functional":
        if not is_admin_user(cid): u["state"]=None; return
        functional=message.text.strip()
        if not functional: send_with_reaction(cid,"❌ <b>Функционал не может быть пустым.</b>"); return
        u["admin_product_functional"]=functional[:8000]; u["state"]="admin_waiting_product_photo"
        mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton("⏭ Пропустить фото",callback_data="admin_skip_product_photo"))
        bot.send_message(cid,"🖼 <b>Шаг 6 из 6 — фото товара</b>\n\nОтправьте фото или нажмите «Пропустить фото».",parse_mode="HTML",reply_markup=mk); return

    if state == "admin_waiting_category":
        if not is_admin_user(cid):
            u['state'] = None
            return
        parts = message.text.split("|", 1)
        if len(parts) != 2 or not parts[0].strip():
            send_with_reaction(cid, "❌ <b>Формат:</b> Название | Описание")
            return
        title = parts[0].strip()[:60]
        description = parts[1].strip()[:1000]
        slug = re.sub(r"[^a-z0-9_]+", "_", title.lower()).strip("_") or "category_" + str(int(time.time()))
        base_slug = slug
        n = 2
        while slug in SHOP_CATEGORIES:
            slug = base_slug + "_" + str(n)
            n += 1
        SHOP_CATEGORIES[slug] = {
            "title": title,
            "price": 0,
            "description": description,
            "callback": "category_" + slug,
            "products": []
        }
        save_user_data()
        u['state'] = None
        send_with_reaction(cid, "✅ <b>Категория добавлена!</b>\nОна уже появилась в магазине.")
        return

    if state == "admin_waiting_broadcast":
        success = 0
        for uid in list(user_data.keys()):
            try:
                send_with_reaction(uid, "🔔 " + message.text)
                success += 1
            except: pass
        send_with_reaction(cid, "✅ <b>Отправлено: " + str(success) + "</b>")
        u['state'] = None
        return
    
    if state == "admin_waiting_chat_id":
        target = message.text.replace('@', '')
        tid = None
        if target.isdigit():
            tid = int(target)
        else:
            for uid, d in user_data.items():
                if d.get('username') == target:
                    tid = uid
                    break
        if tid:
            u['chatting_with'] = tid
            u['state'] = f"chatting_{tid}"
            send_with_reaction(cid, "💬 <b>Чат начат!</b>\n/stop — завершить")
        else:
            send_with_reaction(cid, "❌ <b>Не найден.</b>")
            u['state'] = None
        return
    
    if state and state.startswith("chatting_"):
        if message.text == "/stop":
            send_with_reaction(cid, "✅ <b>Чат завершён.</b>")
            u['state'] = None
            u['chatting_with'] = None
            return
        target_id = int(state.split("_")[1])
        send_with_reaction(target_id, "💬 <b>Поддержка:</b>\n\n" + message.text)
        chat_log(target_id, "admin", message.text, "text")
        save_user_data()
        send_with_reaction(cid, "✅ <b>Отправлено.</b>")
        return
    
    if state == "admin_waiting_give_access":
        target = message.text.replace('@', '')
        tid = None
        if target.isdigit():
            tid = int(target)
        else:
            for uid, d in user_data.items():
                if d.get('username') == target:
                    tid = uid
                    break
        if tid:
            get_user(tid)['has_access'] = True
            save_user_data()
            send_with_reaction(cid, "✅ <b>Выдано!</b>")
            send_with_reaction(tid, "🎁 <b>Доступ выдан!</b>")
        else:
            send_with_reaction(cid, "❌ <b>Не найден.</b>")
        u['state'] = None
        return
    
    if state == "admin_waiting_take_access":
        target = message.text.replace('@', '')
        tid = None
        if target.isdigit():
            tid = int(target)
        else:
            for uid, d in user_data.items():
                if d.get('username') == target:
                    tid = uid
                    break
        if tid:
            get_user(tid)['has_access'] = False
            save_user_data()
            send_with_reaction(cid, "✅ <b>Снято!</b>")
        else:
            send_with_reaction(cid, "❌ <b>Не найден.</b>")
        u['state'] = None
        return
    
    if state == "admin_waiting_create_promo":
        parts = message.text.split()
        if len(parts) == 2 and parts[1].isdigit():
            promocodes[parts[0]] = int(parts[1])
            save_user_data()
            send_with_reaction(cid, "✅ <b>Промокод создан!</b>")
        else:
            send_with_reaction(cid, "❌ <b>Формат: PROMO 50</b>")
        u['state'] = None
        return
    
    if state == "admin_waiting_give_admin":
        target = message.text.replace('@', '')
        tid = None
        if target.isdigit():
            tid = int(target)
        else:
            for uid, d in user_data.items():
                if d.get('username') == target:
                    tid = uid
                    break
        if tid:
            get_user(tid)['is_admin'] = True
            save_user_data()
            send_with_reaction(cid, "✅ <b>Выдано!</b>")
        else:
            send_with_reaction(cid, "❌ <b>Не найден.</b>")
        u['state'] = None
        return
    
    if state == "admin_waiting_send_launcher":
        target = message.text.replace('@', '')
        tid = None
        if target.isdigit():
            tid = int(target)
        else:
            for uid, d in user_data.items():
                if d.get('username') == target:
                    tid = uid
                    break
        if tid:
            try:
                with open("launcher/launcher.apk", "rb") as apk:
                    bot.send_document(tid, apk, caption="📱 <b>Лаунчер!</b>", parse_mode="HTML")
                send_with_reaction(cid, "✅ <b>Отправлен!</b>")
            except:
                send_with_reaction(cid, "❌ <b>Файл не найден!</b>")
        else:
            send_with_reaction(cid, "❌ <b>Не найден.</b>")
        u['state'] = None
        return
    
    if state == "waiting_ftp":
        data = message.text.split()
        if len(data) >= 3:
            u['ftp_data'] = [data[0], data[1], data[2]]
            u['state'] = "waiting_project_name"
            save_user_data()
            send_with_reaction(cid, "✅ <b>FTP принят.</b>\n\nℹ️ <b>Шаг 2 из 6</b> — Название проекта")
        else:
            send_with_reaction(cid, "❌ <b>Нужно: ip login password</b>")
        return
    
    if state == "waiting_project_name":
        u['project_name'] = message.text.strip()[:64]
        u['state'] = "waiting_server_ip"
        save_user_data()
        send_with_reaction(cid, "✅ <b>Название принято.</b>\n\nℹ️ <b>Шаг 3 из 6</b> — IP:Порт")
        return
    
    if state == "waiting_server_ip":
        ip_input = message.text.strip()
        if ":" in ip_input:
            host_part, _, port_part = ip_input.rpartition(":")
            try:
                port = int(port_part)
            except:
                send_with_reaction(cid, "❌ <b>Порт — число.</b>")
                return
        else:
            host_part = ip_input
            port = 7777
        u['server_ip'] = host_part
        u['server_port'] = port
        u['state'] = "waiting_bonuses"
        save_user_data()
        send_with_reaction(cid, "✅ <b>IP принят.</b>\n\nℹ️ <b>Шаг 4 из 6</b> — Бонусы (деньги донат)")
        return
    
    if state == "waiting_bonuses":
        bonuses = message.text.split()
        if len(bonuses) == 2 and bonuses[0].isdigit() and bonuses[1].isdigit():
            u['bonus_money'] = bonuses[0]
            u['bonus_donate'] = bonuses[1]
            u['state'] = "waiting_mysql"
            save_user_data()
            send_with_reaction(cid, "✅ <b>Бонусы приняты.</b>\n\nℹ️ <b>Шаг 5 из 6</b> — Настройки хоста (логин пароль база)")
        else:
            send_with_reaction(cid, "❌ <b>Два числа.</b>")
        return
    
    if state == "waiting_mysql":
        mysql_data = message.text.split()
        if len(mysql_data) == 3:
            u['db_user'] = mysql_data[0]
            u['db_pass'] = mysql_data[1]
            u['db_name'] = mysql_data[2]
            u['state'] = "waiting_color"
            save_user_data()
            color_keyboard = [
                [{"text": "🔴 Красный", "callback_data": "color_red", "style": "danger"}],
                [{"text": "🔵 Синий", "callback_data": "color_blue", "style": "primary"}],
                [{"text": "🟢 Зелёный", "callback_data": "color_green", "style": "success"}],
                [{"text": "🟡 Жёлтый", "callback_data": "color_yellow"}],
                [{"text": "🟣 Фиолетовый", "callback_data": "color_purple", "style": "primary"}],
                [{"text": "🟠 Оранжевый", "callback_data": "color_orange"}],
                [{"text": "⚪ Белый", "callback_data": "color_white"}]
            ]
            send_colored_message(cid, "🎨 <b>Шаг 6 из 6</b> — Выберите цвет:", color_keyboard)
        else:
            send_with_reaction(cid, "❌ <b>Три значения.</b>")
        return


class MiniAppHandler(SimpleHTTPRequestHandler):
    """Small dependency-free HTTP server for the Telegram Mini App."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=MINIAPP_DIR, **kwargs)

    def _send_json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _auth_user(self):
        """Validate Telegram WebApp initData when the browser sends it."""
        init_data = self.headers.get("X-Telegram-Init-Data", "")
        if not init_data:
            return None
        try:
            from urllib.parse import parse_qsl
            import hashlib
            import hmac
            params = dict(parse_qsl(init_data, keep_blank_values=True))
            received_hash = params.pop("hash", "")
            if not received_hash:
                return None
            data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
            secret_key = hmac.new(b"WebAppData", TOKEN.encode("utf-8"), hashlib.sha256).digest()
            calculated = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(calculated, received_hash):
                return None
            user = json.loads(params.get("user", "{}"))
            return user if user.get("id") else None
        except Exception:
            return None

    def _catalog(self):
        categories = []
        products = []
        for category_key, category in SHOP_CATEGORIES.items():
            category_products = []
            if category_key == "banny_premium_v3":
                _, product = find_shop_product("banny_premium_v3")
                if product:
                    category_products.append(product)
            else:
                for product in category.get("products", []):
                    key = str(product.get("key", ""))
                    _, normalized = find_shop_product(key)
                    if normalized:
                        category_products.append(normalized)
            categories.append({
                "key": category_key,
                "title": category.get("title", category_key),
                "description": category.get("description", ""),
                "count": len(category_products),
            })
            for product in category_products:
                item = dict(product)
                item["category_key"] = category_key
                photo = item.get("photo", "")
                if photo and os.path.isfile(photo):
                    item["photo"] = "/media/" + os.path.basename(photo)
                else:
                    item["photo"] = ""
                products.append(item)
        return {"categories": categories, "products": products}

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/admin/chat/send":
            admin = self._admin_auth()
            if not admin: self._send_json({"ok":False,"error":"forbidden"},403); return
            try:
                length=int(self.headers.get("Content-Length","0")); payload=json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                uid=int(payload.get("user_id")); text=str(payload.get("text","")).strip()
            except Exception: self._send_json({"ok":False,"error":"bad_json"},400); return
            if not text: self._send_json({"ok":False,"error":"empty"},400); return
            try: bot.send_message(uid, "💬 <b>Поддержка:</b>\n\n"+text, parse_mode="HTML")
            except Exception as ex: self._send_json({"ok":False,"error":"send_failed"},500); return
            chat_log(uid, "admin", text); save_user_data(); self._send_json({"ok":True}); return
        if parsed.path == "/api/admin/chat/read":
            admin = self._admin_auth()
            if not admin:
                self._send_json({"ok": False, "error": "forbidden"}, 403); return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                uid = int(payload.get("user_id"))
            except Exception:
                self._send_json({"ok": False, "error": "bad_json"}, 400); return
            if uid not in user_data:
                self._send_json({"ok": False, "error": "user_not_found"}, 404); return
            mark_chat_read(uid); save_user_data()
            self._send_json({"ok": True, "unread": 0}); return
        if parsed.path not in ("/api/buy", "/api/promo"):
            self._send_json({"ok": False, "error": "not_found"}, 404)
            return
        user = self._auth_user()
        if not user:
            self._send_json({"ok": False, "error": "unauthorized"}, 401)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            self._send_json({"ok": False, "error": "bad_json"}, 400)
            return

        uid = int(user["id"])
        u = get_user(uid)
        if parsed.path == "/api/promo":
            code = str(payload.get("code", "")).strip()
            if code in promocodes:
                u["discount"] = promocodes[code]
                save_user_data()
                self._send_json({"ok": True, "discount": promocodes[code]})
            else:
                self._send_json({"ok": False, "error": "promo_not_found"}, 400)
            return

        product_key = str(payload.get("product", ""))
        category_key, product = find_shop_product(product_key)
        if not product:
            self._send_json({"ok": False, "error": "product_not_found"}, 404)
            return
        if u.get("has_access"):
            self._send_json({"ok": False, "error": "already_owned"}, 400)
            return
        price = product.get("price", 0)
        try:
            price_num = float(price)
            price = int(price_num) if price_num.is_integer() else price_num
        except Exception:
            pass
        if product_key == "banny_premium_v3" and u.get("discount"):
            price = int(PRICE * (1 - u["discount"] / 100))
        u["selected_product"] = product_key
        u["selected_product_title"] = product.get("title", "Товар")
        u["selected_product_price"] = price
        u["active_order_id"] = create_order(uid, product_key, product.get("title", "Товар"), price, str(payload.get("payment_method", "card")))
        u["state"] = "waiting_receipt"
        save_user_data()
        try:
            send_with_reaction(uid,
                "💳 <b>ОПЛАТА ТОВАРА</b>\n\n"
                "🛒 <b>Товар:</b> " + str(product.get("title", "Товар")) + "\n"
                "💰 <b>Сумма:</b> " + str(price) + "₽\n\n"
                "✅ <b>РЕКВИЗИТЫ:</b>\n"
                "Карта [МИР]: <code>" + CARD_NUMBER + "</code>\n"
                "Банк: YooMoney\n\n"
                "📸 <b>Отправьте чек сюда.</b>"
            )
        except Exception as ex:
            print(f"[MiniApp buy] {ex}")
        self._send_json({"ok": True, "price": price, "order_id": u["active_order_id"], "status": "paying"})

    def _admin_auth(self):
        user = self._auth_user()
        if not user or not is_admin_user(int(user["id"])):
            return None
        return user

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/admin/summary":
            if not self._admin_auth(): self._send_json({"ok":False,"error":"forbidden"},403); return
            self._send_json({"ok":True,"users":len(user_data),"paid_users":sum(1 for d in user_data.values() if d.get("has_access")),"orders":len(orders),"pending":sum(1 for o in orders.values() if o.get("status") in ("paying","checking")),"chats":sum(1 for v in support_chats.values() if v)})
            return
        if path == "/api/admin/users":
            if not self._admin_auth(): self._send_json({"ok":False,"error":"forbidden"},403); return
            items=[]
            for uid,d in user_data.items():
                items.append({"id":uid,"first_name":d.get("first_name",""),"last_name":d.get("last_name",""),"username":d.get("username",""),"has_access":bool(d.get("has_access")),"last_seen":d.get("last_seen",""),"unread":unread_count(uid), "last_message":(support_chats.get(str(uid), [])[-1].get("text", "") if support_chats.get(str(uid)) else ""), "last_message_at":(support_chats.get(str(uid), [])[-1].get("created_at", "") if support_chats.get(str(uid)) else "")})
            items.sort(key=lambda x:x.get("last_seen", ""), reverse=True)
            self._send_json({"ok":True,"users":items})
            return
        if path.startswith("/api/admin/chats/"):
            if not self._admin_auth(): self._send_json({"ok":False,"error":"forbidden"},403); return
            try: uid=int(path.rsplit("/",1)[1])
            except: self._send_json({"ok":False,"error":"bad_user"},400); return
            d=get_user(uid)
            self._send_json({"ok":True,"user":{"id":uid,"first_name":d.get("first_name",""),"last_name":d.get("last_name",""),"username":d.get("username",""),"language_code":d.get("language_code",""),"has_access":bool(d.get("has_access")),"last_seen":d.get("last_seen","")},"messages":support_chats.get(str(uid),[]),"unread":unread_count(uid)})
            return
        if path == "/api/admin/orders":
            if not self._admin_auth(): self._send_json({"ok":False,"error":"forbidden"},403); return
            arr=[]
            for oid,o in orders.items():
                d=get_user(int(o.get("user_id",0)))
                arr.append(dict(o, username=d.get("username",""), first_name=d.get("first_name","")))
            arr.sort(key=lambda x:x.get("created_at",""), reverse=True)
            self._send_json({"ok":True,"orders":arr[:100]})
            return
        if path.startswith("/api/order/"):
            user=self._auth_user()
            if not user: self._send_json({"ok":False,"error":"unauthorized"},401); return
            oid=path.rsplit("/",1)[1]; o=orders.get(oid)
            if not o or int(o.get("user_id",0)) != int(user["id"]): self._send_json({"ok":False,"error":"not_found"},404); return
            self._send_json({"ok":True,"order":o}); return
        if path == "/api/health":
            self._send_json({"ok": True, "service": "banny-miniapp"})
            return
        if path == "/api/catalog":
            self._send_json(self._catalog())
            return
        if path == "/api/me":
            user = self._auth_user()
            if not user:
                self._send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            uid = int(user["id"])
            data = get_user(uid)
            self._send_json({
                "ok": True,
                "user": user,
                "has_access": bool(data.get("has_access")),
                "discount": data.get("discount", 0),
                "purchases": [
                    {"product": r.get("product"), "amount": r.get("amount"), "date": r.get("created_at"), "title": r.get("product")}
                    for r in receipts.values()
                    if r.get("user_id") == uid and r.get("status") == "подтверждён"
                ],
            })
            return
        if path.startswith("/media/"):
            name = os.path.basename(unquote(path[len("/media/"):]))
            full = os.path.join(PHOTOS_DIR, name)
            if not os.path.isfile(full):
                self.send_error(404)
                return
            try:
                with open(full, "rb") as f:
                    data = f.read()
                ext = os.path.splitext(full)[1].lower()
                content_type = {".jpg":"image/jpeg", ".jpeg":"image/jpeg", ".png":"image/png", ".webp":"image/webp"}.get(ext, "application/octet-stream")
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_error(500)
            return
        super().do_GET()

    def log_message(self, format, *args):
        print("[MiniApp] " + format % args)


def start_miniapp_server():
    if not os.path.isdir(MINIAPP_DIR):
        print("[MiniApp] Папка miniapp не найдена — сервер не запущен.")
        return None
    try:
        server = ThreadingHTTPServer((MINIAPP_HOST, MINIAPP_PORT), MiniAppHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"[MiniApp] http://{MINIAPP_HOST}:{MINIAPP_PORT}")
        if MINIAPP_URL:
            print(f"[MiniApp] Telegram URL: {MINIAPP_URL}")
        return server
    except Exception as ex:
        print(f"[MiniApp] Ошибка запуска: {ex}")
        return None


# Final shop UI definitions (kept after legacy code so these are the active versions).
def show_shop(cid):
    text = (
        "🛍 <b>SHOP BANNY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛠 <b>Сборка проектов, компилятор — всё в одном месте.</b>\n\n"
        "👇 <b>Выбери нужный раздел ниже.</b>\n\n"
        "💳 <b>Оплата принимается:</b> переводом на карту, Telegram Stars, СБП\n"
        "⚡ <b>После оплаты товар выдаётся автоматически.</b>\n\n"
        "📦 <b>ТОВАРЫ</b>"
    )
    send_photo_or_message(cid, SHOP_PHOTO, text, shop_main_keyboard())

def show_banny_product(cid):
    category_key, product = find_shop_product("banny_premium_v3")
    if not product:
        send_with_reaction(cid, "❌ <b>Товар не найден.</b>")
        return
    send_photo_or_message(
        cid,
        product.get("photo", PRODUCT_PHOTO),
        "🛒 <b>" + str(product.get("title", "BANNY PREMIUM V3")) + "</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n" +
        str(product.get("description", "")) + "\n\n"
        "💰 <b>Цена: " + str(product.get("price", 699)) + "₽</b>",
        product_keyboard(category_key, product)
    )


def show_category(cid, category_key):
    """Уровень 2: внутри категории показываем список товаров."""
    category = SHOP_CATEGORIES.get(category_key)
    if not category:
        send_with_reaction(cid, "❌ <b>Категория не найдена.</b>")
        return

    rows = []

    # Постоянная категория BANNY PREMIUM всегда содержит свой товар.
    if category_key == "banny_premium_v3":
        rows.append([{
            "text": "🔥 BANNY PREMIUM V3",
            "callback_data": "show_banny_product",
            "style": "primary"
        }])
    else:
        # Для дополнительных категорий поддерживаем список products.
        for index, product in enumerate(category.get("products", [])):
            product_key = str(product.get("key", f"{category_key}_{index}"))
            product_title = str(product.get("title", f"Товар {index + 1}"))
            rows.append([{
                "text": product_title,
                "callback_data": "shop_product_" + product_key,
                "style": "primary"
            }])

    rows.append([{
        "text": "🔙 К категориям",
        "callback_data": "back_to_shop",
        "style": "danger"
    }])

    if rows[:-1]:
        body = (
            "📁 <b>" + str(category.get("title", category_key)) + "</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🛒 <b>Товары в категории:</b>\n\n"
            "Выберите нужный товар:"
        )
    else:
        body = (
            "📁 <b>" + str(category.get("title", category_key)) + "</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 <b>Товары в этой категории пока не добавлены.</b>"
        )

    send_photo_or_message(cid, SHOP_PHOTO, body, rows)

def configure_miniapp_menu():
    if not MINIAPP_URL:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/setChatMenuButton",
            json={"menu_button": {"type": "web_app", "text": "🛍 BANNY SHOP", "web_app": {"url": MINIAPP_URL}}},
            timeout=10,
        )
        print("[MiniApp] Кнопка меню Telegram настроена.")
    except Exception as ex:
        print(f"[MiniApp] Не удалось настроить кнопку меню: {ex}")


miniapp_server = start_miniapp_server()
configure_miniapp_menu()

def auto_save():
    while True:
        time.sleep(30)
        save_user_data()

threading.Thread(target=auto_save, daemon=True).start()

if __name__ == "__main__":
    print("[BANNY] Бот запущен!")
    save_user_data()
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)