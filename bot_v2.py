"""
╔══════════════════════════════════════════════════════════════╗
║        🐍 PYTHON QUIZ BOT v4.0 — с монетизацией             ║
║                                                              ║
║  Новое в v4.0:                                               ║
║  💳 Оплата через Telegram Stars (встроенная)                 ║
║  💎 VIP-статус с привилегиями                                ║
║  🛒 Магазин: подсказки, XP, доступ к сложным вопросам        ║
║  👑 Подписка (30 дней Premium)                               ║
║  🔧 Админ-панель (/admin)                                    ║
║  📊 Статистика продаж для админа                             ║
║  🎁 Выдача Premium вручную через команду                     ║
╚══════════════════════════════════════════════════════════════╝

КАК РАБОТАЕТ ОПЛАТА:
  Telegram Stars — внутренняя валюта Telegram.
  Пользователь покупает Stars в Telegram, затем тратит их в боте.
  Никаких банков и регистрации — всё встроено в Telegram.
  Вывод Stars → рубли возможен через @BotFather (Fragment).

НАСТРОЙКА:
  1. Укажи BOT_TOKEN и ADMIN_ID ниже
  2. Запусти: python bot_v4.py
"""

import asyncio
import json
import logging
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ─────────────────────────────────────────────────────────────
# КОНФИГУРАЦИЯ — заполни перед запуском
# ─────────────────────────────────────────────────────────────

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# BOT_TOKEN = "вставь_токен_сюда"

# Твой Telegram user_id — получить можно у @userinfobot
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
# ADMIN_ID = 123456789

if not BOT_TOKEN:
    raise SystemExit("❌ Укажи BOT_TOKEN в .env файле")

STATS_FILE = Path("stats.json")

# ─────────────────────────────────────────────────────────────
# МАГАЗИН — цены в Telegram Stars
# ─────────────────────────────────────────────────────────────

SHOP_ITEMS = {
    "premium_30": {
        "title":       "👑 Premium на 30 дней",
        "description": "VIP-статус, безлимитные подсказки, доступ к сложным вопросам, значок 💎 в лидерборде",
        "stars":       100,
        "payload":     "premium_30",
    },
    "hints_10": {
        "title":       "💡 10 подсказок",
        "description": "Пакет из 10 подсказок без штрафа к XP",
        "stars":       25,
        "payload":     "hints_10",
    },
    "xp_boost": {
        "title":       "⚡ XP x2 на 7 дней",
        "description": "Удвоенный опыт за все правильные ответы на 7 дней",
        "stars":       50,
        "payload":     "xp_boost",
    },
    "hard_access": {
        "title":       "🔴 Доступ к сложным вопросам",
        "description": "Разблокировка всех вопросов уровня Hard навсегда",
        "stars":       75,
        "payload":     "hard_access",
    },
}

# ─────────────────────────────────────────────────────────────
# ЛОГИРОВАНИЕ
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# FSM
# ─────────────────────────────────────────────────────────────

class QuizStates(StatesGroup):
    in_progress = State()
    study_mode  = State()

# ─────────────────────────────────────────────────────────────
# СИСТЕМА УРОВНЕЙ
# ─────────────────────────────────────────────────────────────

LEVELS = [
    (0,    "🥚 Новичок"),
    (50,   "🐣 Начинающий"),
    (150,  "📖 Ученик"),
    (300,  "🔍 Исследователь"),
    (500,  "⚡ Знаток"),
    (800,  "🧠 Эксперт"),
    (1200, "🏆 Мастер"),
    (2000, "🌟 Легенда"),
]

def get_level(xp: int) -> tuple[int, str]:
    lv, name = 0, LEVELS[0][1]
    for i, (req, n) in enumerate(LEVELS):
        if xp >= req:
            lv, name = i, n
    return lv, name

def xp_bar(xp: int, w: int = 10) -> str:
    cur_req, next_req = 0, LEVELS[-1][0]
    for i, (req, _) in enumerate(LEVELS):
        if xp >= req:
            cur_req = req
            next_req = LEVELS[i+1][0] if i+1 < len(LEVELS) else req
    if next_req == cur_req:
        return "█" * w
    filled = int((xp - cur_req) / (next_req - cur_req) * w)
    return "█" * filled + "░" * (w - filled)

# ─────────────────────────────────────────────────────────────
# ДОСТИЖЕНИЯ
# ─────────────────────────────────────────────────────────────

ACHIEVEMENTS = {
    "first_quiz":    {"icon": "🎯", "name": "Первый шаг",       "desc": "Пройди первый квиз"},
    "perfect_5":     {"icon": "⭐", "name": "Идеал",             "desc": "Все верно без подсказок"},
    "streak_3":      {"icon": "🔥", "name": "3 дня подряд",      "desc": "Серия 3 дня"},
    "streak_7":      {"icon": "🏅", "name": "Недельная серия",   "desc": "Серия 7 дней"},
    "all_categories":{"icon": "🗺️", "name": "Путешественник",   "desc": "Все категории"},
    "level_5":       {"icon": "⚡", "name": "Знаток",            "desc": "Достигни 5-го уровня"},
    "hundred_xp":    {"icon": "💯", "name": "100 XP",            "desc": "Набери 100 XP"},
    "no_hints":      {"icon": "🧠", "name": "Своим умом",        "desc": "Квиз без подсказок"},
    "vip_member":    {"icon": "💎", "name": "VIP-участник",      "desc": "Купи Premium"},
    "supporter":     {"icon": "❤️", "name": "Поддержал проект",  "desc": "Сделай любую покупку"},
}

def check_achievements(u: dict) -> list[str]:
    earned = set(u.get("achievements", []))
    new_ach = []
    def unlock(k):
        if k not in earned:
            new_ach.append(k)
            earned.add(k)
    if u.get("total_games", 0) >= 1:      unlock("first_quiz")
    if u.get("perfect_games", 0) >= 1:    unlock("perfect_5")
    if u.get("streak", 0) >= 3:           unlock("streak_3")
    if u.get("streak", 0) >= 7:           unlock("streak_7")
    if len(u.get("cats_played", [])) >= 6: unlock("all_categories")
    if get_level(u.get("xp", 0))[0] >= 5: unlock("level_5")
    if u.get("xp", 0) >= 100:             unlock("hundred_xp")
    if u.get("no_hint_games", 0) >= 1:    unlock("no_hints")
    if u.get("is_premium", False):        unlock("vip_member")
    if u.get("total_purchases", 0) >= 1:  unlock("supporter")
    u["achievements"] = list(earned)
    return new_ach

# ─────────────────────────────────────────────────────────────
# ВОПРОСЫ
# ─────────────────────────────────────────────────────────────

QUESTIONS_DB: dict[str, list[dict]] = {
    "basics": [
        {"difficulty": "easy",
         "question": "🐍 Какой тип у <code>[]</code>?",
         "options": ["tuple","list","dict","set"], "correct": 1,
         "hint": "[] — литерал списка.",
         "explanation": "<b>[]</b> — это <b>list</b>.\n<pre>type([]) → list\ntype(()) → tuple\ntype({}) → dict</pre>"},
        {"difficulty": "easy",
         "question": "🐍 Результат?\n\n<code>print(10 // 3)</code>",
         "options": ["3.33","3","4","1"], "correct": 1,
         "hint": "// — целочисленное деление.",
         "explanation": "<b>//</b> отбрасывает остаток:\n<pre>10 // 3 = 3\n10 % 3  = 1  (остаток)</pre>"},
        {"difficulty": "medium",
         "question": "🐍 Что такое <code>None</code>?",
         "options": ["Ноль","Пустая строка","Отсутствие значения","False"], "correct": 2,
         "hint": "None — singleton, означает «ничего».",
         "explanation": "<b>None</b> — специальный объект:\n<pre>bool(None) → False\nNone is None → True\ntype(None) → NoneType</pre>"},
        {"difficulty": "hard",
         "question": "🐍 Что выведет?\n\n<code>x = [1,2,3]\nprint(bool(x), bool([]))</code>",
         "options": ["True True","True False","False True","False False"], "correct": 1,
         "hint": "Пустые коллекции — False.",
         "explanation": "Пустые объекты — <b>False</b>:\n<pre>bool([])  → False\nbool([1]) → True</pre>"},
    ],
    "loops": [
        {"difficulty": "easy",
         "question": "🔁 Что делает <code>break</code>?",
         "options": ["Пропуск итерации","Прерывает цикл","Перезапуск","Ошибка"], "correct": 1,
         "hint": "break — выход из цикла.",
         "explanation": "<b>break</b> — немедленный выход:\n<pre>for i in range(10):\n    if i == 3: break\n# 0 1 2</pre>"},
        {"difficulty": "easy",
         "question": "🔁 Сколько раз?\n\n<code>for i in range(5): pass</code>",
         "options": ["4","5","6","0"], "correct": 1,
         "hint": "range(5) → 0,1,2,3,4",
         "explanation": "<b>range(n)</b> генерирует <b>n</b> чисел от 0 до n-1."},
        {"difficulty": "medium",
         "question": "🔁 Что выведет?\n\n<code>for i in range(2,10,3):\n    print(i,end=' ')</code>",
         "options": ["2 5 8","2 4 6 8","3 6 9","2 3 4"], "correct": 0,
         "hint": "range(2,10,3) → 2,5,8",
         "explanation": "<b>range(start,stop,step)</b>:\n<pre>2 → 5 → 8 → 11(стоп)</pre>"},
        {"difficulty": "hard",
         "question": "🔁 Что выведет?\n\n<code>for i in range(3):\n    for j in range(3):\n        if i==j: print(i,end=' ')</code>",
         "options": ["0 1 2","0 0 1 1 2 2","0 1 2 3","Error"], "correct": 0,
         "hint": "Печатаем только когда i == j.",
         "explanation": "При i==j: 0,1,2 → результат <b>0 1 2</b>"},
    ],
    "lists": [
        {"difficulty": "easy",
         "question": "📋 Добавить в конец списка?",
         "options": ["add()","push()","append()","insert()"], "correct": 2,
         "hint": "append — «добавить».",
         "explanation": "<b>append(x)</b> — в конец:\n<pre>[1,2].append(3) → [1,2,3]</pre>"},
        {"difficulty": "easy",
         "question": "📋 Что вернёт?\n\n<code>lst=[10,20,30]\nprint(lst[1])</code>",
         "options": ["10","20","30","Error"], "correct": 1,
         "hint": "Индексы с нуля!",
         "explanation": "Индексация с <b>0</b>:\n<pre>lst[0]=10, lst[1]=20, lst[2]=30</pre>"},
        {"difficulty": "medium",
         "question": "📋 Что вернёт?\n\n<code>'Python'[::-1]</code>",
         "options": ["'Python'","'nohtyP'","Error","list"], "correct": 1,
         "hint": "Шаг -1 разворачивает.",
         "explanation": "<b>[::-1]</b> — обратный порядок:\n<pre>'Python'[::-1] → 'nohtyP'</pre>"},
        {"difficulty": "hard",
         "question": "📋 Что в a?\n\n<code>a=[1,2,3]\nb=a\nb.append(4)\nprint(a)</code>",
         "options": ["[1,2,3]","[1,2,3,4]","[4]","Error"], "correct": 1,
         "hint": "b=a — ссылка, не копия!",
         "explanation": "<b>b=a</b> не копирует!\n<pre>b = a.copy()  # правильно</pre>"},
    ],
    "functions": [
        {"difficulty": "easy",
         "question": "⚙️ Функция без return возвращает?",
         "options": ["0","''","False","None"], "correct": 3,
         "hint": "Специальное значение «ничего».",
         "explanation": "Без <b>return</b> → <b>None</b>:\n<pre>def f(): pass\nf() is None → True</pre>"},
        {"difficulty": "easy",
         "question": "⚙️ Что выведет?\n\n<code>def f(x,y=10): return x+y\nprint(f(5))</code>",
         "options": ["5","10","15","Error"], "correct": 2,
         "hint": "y=10 по умолчанию.",
         "explanation": "<b>f(5)</b> → 5 + 10 = <b>15</b>"},
        {"difficulty": "medium",
         "question": "⚙️ Что делает <code>*args</code>?",
         "options": ["Умножает","Любое кол-во позиц. арг.","Именованные арг.","Ссылка"], "correct": 1,
         "hint": "*args → кортеж аргументов.",
         "explanation": "<b>*args</b> — любое кол-во:\n<pre>def f(*a): print(a)\nf(1,2,3) → (1,2,3)</pre>"},
        {"difficulty": "hard",
         "question": "⚙️ Что выведет?\n\n<code>def f(lst=[]):\n    lst.append(1)\n    return lst\nprint(f())\nprint(f())</code>",
         "options": ["[1] [1]","[1] [1,1]","[1,1] [1,1]","Error"], "correct": 1,
         "hint": "Мutable default — ловушка!",
         "explanation": "Default создаётся <b>один раз</b>!\n<pre>def f(lst=None):\n    if lst is None: lst=[]</pre>"},
    ],
    "dicts": [
        {"difficulty": "easy",
         "question": "📦 Безопасный доступ к ключу?",
         "options": ["d['key']","d.get('key')","d.find('key')","d.fetch('key')"], "correct": 1,
         "hint": "get() не бросает KeyError.",
         "explanation": "<b>get(key, default)</b>:\n<pre>d.get('x')    → None\nd.get('x', 0) → 0</pre>"},
        {"difficulty": "medium",
         "question": "📦 Что вернёт <code>d.items()</code>?",
         "options": ["Ключи","Значения","Пары (ключ,знач.)","Длину"], "correct": 2,
         "hint": "items — и ключи, и значения.",
         "explanation": "<b>d.items()</b> → пары:\n<pre>for k,v in d.items(): ...</pre>"},
        {"difficulty": "hard",
         "question": "📦 Результат?\n\n<code>d={i:i**2 for i in range(4)}\nprint(d[3])</code>",
         "options": ["3","6","9","Error"], "correct": 2,
         "hint": "Dict comprehension: {0:0,1:1,2:4,3:9}",
         "explanation": "<b>d[3]</b> = 3² = <b>9</b>"},
    ],
    "strings": [
        {"difficulty": "easy",
         "question": "🔤 Что делает <code>upper()</code>?",
         "options": ["Удаляет пробелы","Верхний регистр","Первая заглавная","Разворот"], "correct": 1,
         "hint": "upper — «верхний».",
         "explanation": "<pre>'hello'.upper() → 'HELLO'</pre>"},
        {"difficulty": "medium",
         "question": "🔤 Что выведет?\n\n<code>'hello world'.split()</code>",
         "options": ["['hello world']","['hello','world']","('hello','world')","Error"], "correct": 1,
         "hint": "split() делит по пробелам.",
         "explanation": "<b>split()</b> → список слов:\n<pre>'a b c'.split() → ['a','b','c']</pre>"},
        {"difficulty": "hard",
         "question": "🔤 Что вернёт?\n\n<code>s='abcde'\nprint(s[1:4:2])</code>",
         "options": ["'bc'","'bd'","'ace'","Error"], "correct": 1,
         "hint": "Срез [1:4:2] — шаг 2 от 1 до 4.",
         "explanation": "<pre>s[1:4:2]: b(1), d(3) → 'bd'</pre>"},
    ],
}

CATEGORIES = {
    "basics":    {"label": "🐍 Основы",    "emoji": "🐍"},
    "loops":     {"label": "🔁 Циклы",     "emoji": "🔁"},
    "lists":     {"label": "📋 Списки",    "emoji": "📋"},
    "functions": {"label": "⚙️ Функции",   "emoji": "⚙️"},
    "dicts":     {"label": "📦 Словари",   "emoji": "📦"},
    "strings":   {"label": "🔤 Строки",    "emoji": "🔤"},
}

DIFFICULTY_CONFIG = {
    "easy":   {"label": "🟢 Лёгкий",  "xp": 5,  "stars_bonus": 0},
    "medium": {"label": "🟡 Средний", "xp": 10, "stars_bonus": 0},
    "hard":   {"label": "🔴 Сложный", "xp": 20, "stars_bonus": 0},
}

# ─────────────────────────────────────────────────────────────
# РАБОТА СО СТАТИСТИКОЙ
# ─────────────────────────────────────────────────────────────

def load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_stats(stats: dict):
    STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

def get_user(stats: dict, uid: int, name: str) -> dict:
    key = str(uid)
    if key not in stats:
        stats[key] = {
            "username": name, "xp": 0, "total_games": 0,
            "total_correct": 0, "total_questions": 0,
            "best_score": 0, "perfect_games": 0, "no_hint_games": 0,
            "streak": 0, "last_play": "", "cats_played": [],
            "achievements": [], "daily_date": "", "daily_count": 0,
            "history": [], "total_purchases": 0, "total_stars_spent": 0,
            # Premium
            "is_premium": False, "premium_until": "",
            # Покупки
            "hints_left": 3,      # бесплатные подсказки
            "xp_boost_until": "", # XP x2
            "hard_unlocked": False,
        }
    stats[key]["username"] = name
    return stats[key]

def is_premium_active(u: dict) -> bool:
    if not u.get("is_premium"):
        return False
    until = u.get("premium_until", "")
    if not until:
        return False
    return datetime.fromisoformat(until) > datetime.now()

def is_xp_boost(u: dict) -> bool:
    until = u.get("xp_boost_until", "")
    if not until:
        return False
    return datetime.fromisoformat(until) > datetime.now()

def premium_badge(u: dict) -> str:
    return " 💎" if is_premium_active(u) else ""

def update_streak(u: dict) -> int:
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))
    last = u.get("last_play", "")
    bonus = 0
    if last == today:
        pass
    elif last == yesterday:
        u["streak"] = u.get("streak", 0) + 1
        if u["streak"] > 1:
            bonus = 10
    else:
        u["streak"] = 1
    u["last_play"] = today
    return bonus

def apply_purchase(u: dict, payload: str) -> str:
    """Применяет покупку к пользователю. Возвращает сообщение."""
    if payload == "premium_30":
        now = datetime.now()
        until = now + timedelta(days=30)
        u["is_premium"] = True
        u["premium_until"] = until.isoformat()
        u["hints_left"] = 9999  # безлимитные подсказки для Premium
        return f"👑 Premium активирован до {until.strftime('%d.%m.%Y')}!"
    elif payload == "hints_10":
        u["hints_left"] = u.get("hints_left", 0) + 10
        return "💡 Добавлено 10 подсказок!"
    elif payload == "xp_boost":
        until = datetime.now() + timedelta(days=7)
        u["xp_boost_until"] = until.isoformat()
        return f"⚡ XP x2 активирован до {until.strftime('%d.%m.%Y')}!"
    elif payload == "hard_access":
        u["hard_unlocked"] = True
        return "🔴 Доступ к сложным вопросам разблокирован навсегда!"
    return "✅ Покупка успешна!"

# ─────────────────────────────────────────────────────────────
# КЛАВИАТУРЫ
# ─────────────────────────────────────────────────────────────

def kb_main(u: dict = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🎯 Начать квиз",       callback_data="choose_cat")
    b.button(text="📝 Режим обучения",    callback_data="study_start")
    b.button(text="📅 Вопрос дня",        callback_data="daily")
    b.button(text="🛒 Магазин",           callback_data="shop")
    b.button(text="🏆 Лидеры",            callback_data="leaderboard")
    b.button(text="👤 Профиль",           callback_data="profile")
    b.button(text="🎖 Достижения",        callback_data="achievements")
    b.adjust(1)
    return b.as_markup()

def kb_shop() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, item in SHOP_ITEMS.items():
        b.button(
            text=f"{item['title']} — ⭐{item['stars']}",
            callback_data=f"buy:{key}",
        )
    b.button(text="🏠 Меню", callback_data="main_menu")
    b.adjust(1)
    return b.as_markup()

def kb_categories(prefix="cat") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for k, m in CATEGORIES.items():
        b.button(text=m["label"], callback_data=f"{prefix}:{k}")
    b.button(text="🎲 Случайная", callback_data=f"{prefix}:random")
    b.button(text="🏠 Меню",     callback_data="main_menu")
    b.adjust(2)
    return b.as_markup()

def kb_difficulty(category: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for k, cfg in DIFFICULTY_CONFIG.items():
        b.button(text=cfg["label"], callback_data=f"diff:{category}:{k}")
    b.button(text="⬅️ Назад", callback_data="choose_cat")
    b.adjust(1)
    return b.as_markup()

def kb_quiz(q_idx: int, questions: list, hints_left: int, is_prem: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, opt in enumerate(questions[q_idx]["options"]):
        b.button(text=opt, callback_data=f"ans:{q_idx}:{i}")
    b.adjust(1)
    if hints_left > 0 or is_prem:
        hint_label = "💡 Подсказка (∞)" if is_prem else f"💡 Подсказка ({hints_left} шт.)"
        b.button(text=hint_label, callback_data=f"hint:{q_idx}")
    else:
        b.button(text="💡 Купить подсказки →", callback_data="shop_from_quiz")
    b.button(text="🚪 Выйти", callback_data="quit_quiz")
    b.adjust(1)
    return b.as_markup()

def kb_study(q_idx: int, questions: list, answered: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if not answered:
        for i, opt in enumerate(questions[q_idx]["options"]):
            b.button(text=opt, callback_data=f"st_ans:{q_idx}:{i}")
        b.adjust(1)
    else:
        if q_idx + 1 < len(questions):
            b.button(text="➡️ Следующий", callback_data=f"st_next:{q_idx+1}")
        else:
            b.button(text="🏁 Завершить", callback_data="main_menu")
    b.button(text="🏠 Меню", callback_data="main_menu")
    return b.as_markup()

def kb_back() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Ещё раз", callback_data="choose_cat")
    b.button(text="🏠 Меню",    callback_data="main_menu")
    b.adjust(1)
    return b.as_markup()

# ─────────────────────────────────────────────────────────────
# УТИЛИТЫ
# ─────────────────────────────────────────────────────────────

def medal(p: int) -> str:
    return {1:"🥇",2:"🥈",3:"🥉"}.get(p, f"{p}.")

def result_comment(score: int, total: int) -> str:
    r = score/total if total else 0
    if r == 1.0: return "🏆 Идеально!"
    if r >= 0.8: return "🎉 Отлично!"
    if r >= 0.6: return "👍 Неплохо!"
    if r >= 0.4: return "📖 Повтори материал."
    return "💪 Попробуй режим обучения!"

def fmt_q(q_idx: int, questions: list, category: str, difficulty: str) -> str:
    total = len(questions)
    q     = questions[q_idx]
    bar   = "█" * q_idx + "░" * (total - q_idx)
    xp    = DIFFICULTY_CONFIG[difficulty]["xp"]
    return (
        f"<b>{CATEGORIES[category]['label']}  {DIFFICULTY_CONFIG[difficulty]['label']}</b>\n"
        f"Вопрос {q_idx+1}/{total}  +{xp} XP\n"
        f"<code>[{bar}]</code>\n\n"
        f"{q['question']}"
    )

def get_daily_q() -> dict:
    all_q = [{**q, "category": k} for k, qs in QUESTIONS_DB.items() for q in qs]
    return random.Random(date.today().toordinal()).choice(all_q)

# ─────────────────────────────────────────────────────────────
# РОУТЕР
# ─────────────────────────────────────────────────────────────

router = Router()

# ── /start ──────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    name  = message.from_user.first_name or "друг"
    stats = load_stats()
    u     = get_user(stats, message.from_user.id, name)
    save_stats(stats)

    xp       = u.get("xp", 0)
    _, lv    = get_level(xp)
    prem_str = " 💎 <b>Premium</b>" if is_premium_active(u) else ""
    boost    = " ⚡<i>XP x2</i>" if is_xp_boost(u) else ""

    await message.answer(
        f"👋 Привет, <b>{name}</b>!{prem_str}\n\n"
        f"┌──────────────────────────┐\n"
        f"│  🐍 Python Quiz Bot v4   │\n"
        f"└──────────────────────────┘\n\n"
        f"🏅 {lv}  •  ✨ {xp} XP{boost}\n\n"
        f"🎯 Квиз  📝 Обучение  📅 День\n"
        f"🛒 Магазин  🏆 Лидеры  👤 Профиль",
        reply_markup=kb_main(u),
        parse_mode="HTML",
    )

@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    prem  = " 💎" if is_premium_active(u) else ""
    await callback.message.edit_text(
        f"🏠 <b>Главное меню</b>{prem}",
        reply_markup=kb_main(u),
        parse_mode="HTML",
    )
    await callback.answer()

# ── МАГАЗИН ──────────────────────────────────────────────────

@router.callback_query(F.data == "shop")
async def show_shop(callback: CallbackQuery):
    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    prem  = is_premium_active(u)
    boost = is_xp_boost(u)
    hints = u.get("hints_left", 0)

    status = []
    if prem:
        until = datetime.fromisoformat(u["premium_until"]).strftime("%d.%m.%Y")
        status.append(f"👑 Premium до {until}")
    if boost:
        until = datetime.fromisoformat(u["xp_boost_until"]).strftime("%d.%m.%Y")
        status.append(f"⚡ XP x2 до {until}")
    if u.get("hard_unlocked"):
        status.append("🔴 Hard вопросы разблокированы")
    status_str = "\n".join(status) + "\n\n" if status else ""

    text = (
        f"🛒 <b>Магазин</b>\n\n"
        f"{status_str}"
        f"💡 Подсказок: <b>{hints if not prem else '∞'}</b>\n\n"
        f"Оплата через <b>Telegram Stars ⭐</b>\n"
        f"Stars можно купить прямо в Telegram\n\n"
    )
    for item in SHOP_ITEMS.values():
        text += f"{item['title']}\n<i>{item['description']}</i>\n⭐ {item['stars']} Stars\n\n"

    await callback.message.edit_text(text, reply_markup=kb_shop(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "shop_from_quiz")
async def shop_from_quiz(callback: CallbackQuery):
    await callback.answer("Подсказки закончились! Купи в магазине 🛒", show_alert=True)

# ── ПОКУПКА ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("buy:"))
async def buy_item(callback: CallbackQuery, bot: Bot):
    key  = callback.data.split(":")[1]
    item = SHOP_ITEMS.get(key)
    if not item:
        await callback.answer("Товар не найден!")
        return

    logger.info(f"[SHOP] user={callback.from_user.id} item={key} stars={item['stars']}")

    # Отправляем инвойс через Telegram Stars
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=item["title"],
        description=item["description"],
        payload=item["payload"],
        currency="XTR",                # XTR = Telegram Stars
        prices=[LabeledPrice(label=item["title"], amount=item["stars"])],
    )
    await callback.answer()

# ── ПОДТВЕРЖДЕНИЕ ОПЛАТЫ ─────────────────────────────────────

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    """Telegram вызывает это перед списанием Stars — нужно подтвердить."""
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def payment_success(message: Message, bot: Bot):
    """Вызывается после успешной оплаты."""
    payment = message.successful_payment
    payload = payment.invoice_payload
    stars   = payment.total_amount
    uid     = message.from_user.id
    name    = message.from_user.first_name or "Игрок"

    logger.info(f"[PAYMENT] user={uid} payload={payload} stars={stars}")

    # Обновляем данные пользователя
    stats = load_stats()
    u     = get_user(stats, uid, name)
    u["total_purchases"]  = u.get("total_purchases", 0) + 1
    u["total_stars_spent"] = u.get("total_stars_spent", 0) + stars

    # Применяем покупку
    result_msg = apply_purchase(u, payload)

    # Проверяем новые достижения
    new_ach = check_achievements(u)
    save_stats(stats)

    # Уведомляем пользователя
    ach_text = ""
    if new_ach:
        icons = " ".join(ACHIEVEMENTS[a]["icon"] for a in new_ach)
        ach_text = f"\n\n🎖 Новые достижения: {icons}"

    await message.answer(
        f"✅ <b>Оплата прошла!</b>\n\n"
        f"⭐ Потрачено: {stars} Stars\n\n"
        f"{result_msg}{ach_text}",
        reply_markup=kb_main(u),
        parse_mode="HTML",
    )

    # Уведомляем админа
    if ADMIN_ID:
        item_name = next((i["title"] for i in SHOP_ITEMS.values() if i["payload"] == payload), payload)
        try:
            await bot.send_message(
                ADMIN_ID,
                f"💰 <b>Новая покупка!</b>\n\n"
                f"👤 {name} (id: {uid})\n"
                f"🛒 {item_name}\n"
                f"⭐ {stars} Stars",
                parse_mode="HTML",
            )
        except Exception:
            pass

# ── ВЫБОР КАТЕГОРИИ И СЛОЖНОСТИ ──────────────────────────────

@router.callback_query(F.data == "choose_cat")
async def choose_cat(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🎯 <b>Выбери категорию:</b>",
        reply_markup=kb_categories("cat"),
        parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cat:"))
async def choose_diff(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.split(":")[1]
    if cat == "random":
        cat = random.choice(list(QUESTIONS_DB.keys()))
    await state.update_data(category=cat)

    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    prem  = is_premium_active(u)
    hard_ok = prem or u.get("hard_unlocked", False)

    text = (
        f"<b>{CATEGORIES[cat]['label']}</b>\n\n"
        f"Выбери сложность:\n\n"
        f"🟢 Лёгкий   +5 XP\n"
        f"🟡 Средний  +10 XP\n"
        f"🔴 Сложный  +20 XP"
        + ("" if hard_ok else "\n\n<i>🔒 Hard требует Premium или покупки</i>")
    )

    b = InlineKeyboardBuilder()
    b.button(text="🟢 Лёгкий",  callback_data=f"diff:{cat}:easy")
    b.button(text="🟡 Средний", callback_data=f"diff:{cat}:medium")
    if hard_ok:
        b.button(text="🔴 Сложный", callback_data=f"diff:{cat}:hard")
    else:
        b.button(text="🔒 Сложный (разблокировать →)", callback_data="shop")
    b.button(text="⬅️ Назад", callback_data="choose_cat")
    b.adjust(1)

    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()

# ── СТАРТ КВИЗА ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("diff:"))
async def start_quiz(callback: CallbackQuery, state: FSMContext):
    _, cat, diff = callback.data.split(":")
    all_q     = QUESTIONS_DB[cat]
    filtered  = [q for q in all_q if q.get("difficulty") == diff] or all_q
    questions = random.sample(filtered, min(len(filtered), 5))

    await state.set_state(QuizStates.in_progress)
    await state.update_data(
        cat=cat, diff=diff, questions=questions,
        idx=0, score=0, used_hint=False, any_hint=False, answered=False,
    )

    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    prem  = is_premium_active(u)
    hints = u.get("hints_left", 0)

    await callback.message.edit_text(
        fmt_q(0, questions, cat, diff),
        reply_markup=kb_quiz(0, questions, hints, prem),
        parse_mode="HTML",
    )
    await callback.answer()

# ── ВЫХОД ────────────────────────────────────────────────────

@router.callback_query(QuizStates.in_progress, F.data == "quit_quiz")
async def quit_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🚪 Вышел из квиза.", reply_markup=kb_back(), parse_mode="HTML")
    await callback.answer()

# ── ПОДСКАЗКА ────────────────────────────────────────────────

@router.callback_query(QuizStates.in_progress, F.data.startswith("hint:"))
async def show_hint(callback: CallbackQuery, state: FSMContext):
    data      = await state.get_data()
    q_idx     = int(callback.data.split(":")[1])
    questions = data["questions"]
    cat       = data["cat"]
    diff      = data["diff"]

    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    prem  = is_premium_active(u)

    if not prem:
        if u.get("hints_left", 0) <= 0:
            await callback.answer("Подсказки закончились! Купи в магазине 🛒", show_alert=True)
            return
        u["hints_left"] -= 1
        save_stats(stats)

    await state.update_data(used_hint=True, any_hint=True)

    hints_left = u.get("hints_left", 0) if not prem else 9999

    await callback.message.edit_text(
        f"{fmt_q(q_idx, questions, cat, diff)}\n\n"
        f"{'─'*22}\n"
        f"💡 <b>Подсказка:</b> {questions[q_idx]['hint']}\n"
        f"<i>Осталось подсказок: {'∞' if prem else hints_left}</i>",
        reply_markup=kb_quiz(q_idx, questions, hints_left, prem),
        parse_mode="HTML",
    )
    await callback.answer("💡")

# ── ОТВЕТ ────────────────────────────────────────────────────

@router.callback_query(QuizStates.in_progress, F.data.startswith("ans:"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("answered"):
        await callback.answer("Уже ответил!")
        return

    _, qs, os_ = callback.data.split(":")
    q_idx = int(qs); opt = int(os_)
    questions = data["questions"]
    cat, diff = data["cat"], data["diff"]
    q         = questions[q_idx]
    any_hint  = data.get("any_hint", False)

    is_correct = (opt == q["correct"])
    new_score  = data["score"] + (1 if is_correct else 0)
    await state.update_data(score=new_score, answered=True)

    correct_text = q["options"][q["correct"]]
    if is_correct and not data.get("used_hint"):
        feedback = f"✅ <b>Правильно!</b>\n💡 {q['hint']}"
    elif is_correct:
        feedback = f"✅ <b>Правильно (с подсказкой)</b>\n💡 {q['hint']}"
    else:
        feedback = f"❌ <b>Неверно.</b>\nОтвет: <b>{correct_text}</b>\n💡 {q['hint']}"

    next_idx = q_idx + 1
    total    = len(questions)
    await state.update_data(used_hint=False)

    if next_idx < total:
        stats = load_stats()
        u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
        prem  = is_premium_active(u)
        hints = u.get("hints_left", 0)

        await state.update_data(idx=next_idx, answered=False)
        await callback.message.edit_text(
            f"{fmt_q(q_idx, questions, cat, diff)}\n\n{'─'*22}\n{feedback}\n{'─'*22}\n\n"
            f"{fmt_q(next_idx, questions, cat, diff)}",
            reply_markup=kb_quiz(next_idx, questions, hints, prem),
            parse_mode="HTML",
        )
        await callback.answer("✅" if is_correct else "❌")
    else:
        # Финал
        name = callback.from_user.first_name or "Игрок"
        uid  = callback.from_user.id

        stats = load_stats()
        u     = get_user(stats, uid, name)

        # XP
        base_xp = DIFFICULTY_CONFIG[diff]["xp"] * new_score
        earned  = int(base_xp * (2 if is_xp_boost(u) else 1))
        if new_score == total and not any_hint:
            earned += 30
            u["perfect_games"] = u.get("perfect_games", 0) + 1
        if not any_hint:
            u["no_hint_games"] = u.get("no_hint_games", 0) + 1

        bonus_streak = update_streak(u)
        earned += bonus_streak

        u["xp"]             = u.get("xp", 0) + earned
        u["total_games"]    = u.get("total_games", 0) + 1
        u["total_correct"]  = u.get("total_correct", 0) + new_score
        u["total_questions"]= u.get("total_questions", 0) + total
        u["best_score"]     = max(u.get("best_score", 0), new_score)
        cats = u.get("cats_played", [])
        if cat not in cats: cats.append(cat)
        u["cats_played"] = cats
        u["history"].append({"date": str(date.today()), "cat": cat, "diff": diff, "score": new_score, "total": total, "xp": earned})
        u["history"] = u["history"][-20:]

        new_ach = check_achievements(u)
        save_stats(stats)

        xp_total = u["xp"]
        _, lv    = get_level(xp_total)
        bar      = xp_bar(xp_total)
        streak   = u.get("streak", 0)
        stars    = "⭐" * new_score + "☆" * (total - new_score)
        prem     = is_premium_active(u)
        boost    = " ⚡XP x2" if is_xp_boost(u) else ""

        ach_text = ""
        if new_ach:
            icons = " ".join(ACHIEVEMENTS[a]["icon"] for a in new_ach)
            ach_text = f"\n\n🎖 <b>Новые достижения!</b> {icons}"

        await state.clear()
        await callback.message.edit_text(
            f"🏁 <b>Квиз завершён!</b>\n\n"
            f"{fmt_q(q_idx, questions, cat, diff)}\n\n"
            f"{'─'*22}\n{feedback}\n{'═'*22}\n\n"
            f"🎯 <b>{new_score}/{total}</b>  {stars}\n"
            f"✨ +{earned} XP{boost}"
            + (f"  🔥{streak} дн." if streak > 1 else "") + f"\n\n"
            f"{lv}  <code>[{bar}]</code>  {xp_total} XP\n\n"
            f"{result_comment(new_score, total)}{ach_text}",
            reply_markup=kb_back(),
            parse_mode="HTML",
        )
        await callback.answer()

@router.message(QuizStates.in_progress)
async def quiz_guard(message: Message):
    await message.answer("⚠️ Нажимай на кнопки! 👆")

# ── РЕЖИМ ОБУЧЕНИЯ ───────────────────────────────────────────

@router.callback_query(F.data == "study_start")
async def study_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("📝 <b>Режим обучения</b>\n\nВыбери тему:", reply_markup=kb_categories("st_cat"), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("st_cat:"))
async def study_begin(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.split(":")[1]
    if cat == "random": cat = random.choice(list(QUESTIONS_DB.keys()))
    qs  = random.sample(QUESTIONS_DB[cat], min(len(QUESTIONS_DB[cat]), 5))
    await state.set_state(QuizStates.study_mode)
    await state.update_data(cat=cat, questions=qs, idx=0)
    await callback.message.edit_text(
        f"📝 <b>Обучение: {CATEGORIES[cat]['label']}</b>\nВопрос 1/{len(qs)}\n\n{qs[0]['question']}",
        reply_markup=kb_study(0, qs), parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(QuizStates.study_mode, F.data.startswith("st_ans:"))
async def study_ans(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    q_idx, opt = int(callback.data.split(":")[1]), int(callback.data.split(":")[2])
    qs, cat    = data["questions"], data["cat"]
    q          = qs[q_idx]
    is_correct = opt == q["correct"]
    correct_t  = q["options"][q["correct"]]
    fb = "✅ <b>Правильно!</b>" if is_correct else f"❌ <b>Неверно.</b> Ответ: <b>{correct_t}</b>"
    await callback.message.edit_text(
        f"📝 <b>Обучение: {CATEGORIES[cat]['label']}</b>\nВопрос {q_idx+1}/{len(qs)}\n\n"
        f"{q['question']}\n\n{'─'*22}\n{fb}\n\n📖 <b>Объяснение:</b>\n{q['explanation']}",
        reply_markup=kb_study(q_idx, qs, answered=True), parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(QuizStates.study_mode, F.data.startswith("st_next:"))
async def study_next(callback: CallbackQuery, state: FSMContext):
    data    = await state.get_data()
    nxt     = int(callback.data.split(":")[1])
    qs, cat = data["questions"], data["cat"]
    await state.update_data(idx=nxt)
    await callback.message.edit_text(
        f"📝 <b>Обучение: {CATEGORIES[cat]['label']}</b>\nВопрос {nxt+1}/{len(qs)}\n\n{qs[nxt]['question']}",
        reply_markup=kb_study(nxt, qs), parse_mode="HTML",
    )
    await callback.answer()

# ── ВОПРОС ДНЯ ───────────────────────────────────────────────

@router.callback_query(F.data == "daily")
async def daily(callback: CallbackQuery, state: FSMContext):
    q      = get_daily_q()
    today  = str(date.today())
    data   = await state.get_data()
    done   = data.get("daily_date") == today
    cat    = CATEGORIES.get(q["category"], {}).get("label", "")
    b      = InlineKeyboardBuilder()

    if not done:
        await state.update_data(daily_q=q)
        for i, opt in enumerate(q["options"]):
            b.button(text=opt, callback_data=f"daily_a:{i}")
        b.adjust(1)
    else:
        ct = q["options"][q["correct"]]
        b.button(text="🏠 Меню", callback_data="main_menu")
        await callback.message.edit_text(
            f"📅 <b>Вопрос дня — {today}</b>\nТема: {cat}\n\n{q['question']}\n\n{'─'*20}\n✅ Уже отвечал!\nОтвет: <b>{ct}</b>",
            reply_markup=b.as_markup(), parse_mode="HTML",
        )
        await callback.answer()
        return

    b.button(text="🏠 Меню", callback_data="main_menu")
    await callback.message.edit_text(
        f"📅 <b>Вопрос дня — {today}</b>\nТема: {cat}  •  +15 XP\n\n{q['question']}",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data.startswith("daily_a:"))
async def daily_ans(callback: CallbackQuery, state: FSMContext):
    data  = await state.get_data()
    q     = data.get("daily_q") or get_daily_q()
    opt   = int(callback.data.split(":")[1])
    today = str(date.today())
    ok    = opt == q["correct"]
    await state.update_data(daily_date=today)

    stats = load_stats()
    u     = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    if ok:
        bonus = int(15 * (2 if is_xp_boost(u) else 1))
        u["xp"] = u.get("xp", 0) + bonus
    u["daily_count"] = u.get("daily_count", 0) + 1
    save_stats(stats)

    ct = q["options"][q["correct"]]
    fb = f"✅ <b>Правильно! +15 XP</b>\n💡 {q['hint']}" if ok else f"❌ <b>Неверно.</b>\nОтвет: <b>{ct}</b>\n💡 {q['hint']}"
    b  = InlineKeyboardBuilder()
    b.button(text="🏠 Меню", callback_data="main_menu")
    await callback.message.edit_text(
        f"📅 <b>Вопрос дня — {today}</b>\n\n{q['question']}\n\n{'─'*20}\n{fb}",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )
    await callback.answer("✅" if ok else "❌")

# ── ПРОФИЛЬ ──────────────────────────────────────────────────

@router.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    stats = load_stats()
    name  = callback.from_user.first_name or "Игрок"
    u     = get_user(stats, callback.from_user.id, name)

    xp        = u.get("xp", 0)
    lv_n, lv  = get_level(xp)[0], get_level(xp)[1]
    bar       = xp_bar(xp)
    prem      = is_premium_active(u)
    boost     = is_xp_boost(u)
    games     = u.get("total_games", 0)
    correct   = u.get("total_correct", 0)
    total_q   = u.get("total_questions", 0)
    avg       = f"{correct/total_q*100:.0f}%" if total_q else "—"
    streak    = u.get("streak", 0)
    hints     = "∞" if prem else str(u.get("hints_left", 0))
    spent     = u.get("total_stars_spent", 0)

    status = []
    if prem:
        until = datetime.fromisoformat(u["premium_until"]).strftime("%d.%m.%Y")
        status.append(f"👑 Premium до {until}")
    if boost:
        until = datetime.fromisoformat(u["xp_boost_until"]).strftime("%d.%m.%Y")
        status.append(f"⚡ XP x2 до {until}")
    if u.get("hard_unlocked"):
        status.append("🔴 Hard разблокирован")
    status_str = "\n".join(status) + "\n\n" if status else ""

    hist = u.get("history", [])[-3:]
    hist_lines = []
    for h in reversed(hist):
        cat  = CATEGORIES.get(h.get("cat",""), {}).get("emoji","🎯")
        diff = DIFFICULTY_CONFIG.get(h.get("diff","easy"),{}).get("label","")
        hist_lines.append(f"  {cat} {h['score']}/{h['total']} {diff} +{h.get('xp',0)} XP")

    await callback.message.edit_text(
        f"👤 <b>{name}</b>{premium_badge(u)}\n\n"
        f"{status_str}"
        f"{'─'*22}\n"
        f"🏅 Ур.{lv_n}: <b>{lv}</b>\n"
        f"✨ XP: <b>{xp}</b>\n"
        f"<code>[{bar}]</code>\n\n"
        f"🔥 Серия: <b>{streak} дн.</b>\n"
        f"🎮 Игр: <b>{games}</b>  📈 Точность: <b>{avg}</b>\n"
        f"💡 Подсказок: <b>{hints}</b>\n"
        f"⭐ Потрачено Stars: <b>{spent}</b>\n"
        + (f"\n📊 <b>Последние игры:</b>\n" + "\n".join(hist_lines) if hist_lines else ""),
        reply_markup=kb_back(), parse_mode="HTML",
    )
    await callback.answer()

# ── ДОСТИЖЕНИЯ ───────────────────────────────────────────────

@router.callback_query(F.data == "achievements")
async def achievements(callback: CallbackQuery):
    stats  = load_stats()
    u      = get_user(stats, callback.from_user.id, callback.from_user.first_name or "")
    earned = set(u.get("achievements", []))
    lines  = [
        f"{a['icon']} <b>{a['name']}</b> — {a['desc']}" if k in earned
        else f"🔒 <i>{a['name']}</i> — {a['desc']}"
        for k, a in ACHIEVEMENTS.items()
    ]
    b = InlineKeyboardBuilder()
    b.button(text="🏠 Меню", callback_data="main_menu")
    await callback.message.edit_text(
        f"🎖 <b>Достижения</b>  {len(earned)}/{len(ACHIEVEMENTS)}\n\n" + "\n".join(lines),
        reply_markup=b.as_markup(), parse_mode="HTML",
    )
    await callback.answer()

# ── ЛИДЕРБОРД ────────────────────────────────────────────────

@router.callback_query(F.data == "leaderboard")
async def leaderboard(callback: CallbackQuery):
    stats   = load_stats()
    leaders = sorted(
        [{"name": u["username"], "xp": u.get("xp",0), "lv": get_level(u.get("xp",0))[1],
          "games": u.get("total_games",0), "streak": u.get("streak",0),
          "prem": is_premium_active(u)}
         for u in stats.values() if u.get("total_questions",0) > 0],
        key=lambda x: x["xp"], reverse=True
    )[:10]

    if not leaders:
        await callback.message.edit_text("🏆 <b>Лидеры</b>\n\nПока пусто!", reply_markup=kb_back(), parse_mode="HTML")
        await callback.answer()
        return

    lines = []
    for i, l in enumerate(leaders, 1):
        badge  = " 💎" if l["prem"] else ""
        streak = f"  🔥{l['streak']}" if l["streak"] > 1 else ""
        lines.append(f"{medal(i)} <b>{l['name']}</b>{badge}  {l['lv']}\n   ✨{l['xp']} XP  🎮{l['games']}{streak}")

    await callback.message.edit_text(
        "🏆 <b>Таблица лидеров</b>\n\n" + "\n\n".join(lines),
        reply_markup=kb_back(), parse_mode="HTML",
    )
    await callback.answer()

# ── АДМИН-ПАНЕЛЬ ─────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return

    stats = load_stats()
    users = len(stats)
    total_stars = sum(u.get("total_stars_spent", 0) for u in stats.values())
    total_games = sum(u.get("total_games", 0) for u in stats.values())
    premium_cnt = sum(1 for u in stats.values() if is_premium_active(u))
    purchases   = sum(u.get("total_purchases", 0) for u in stats.values())

    b = InlineKeyboardBuilder()
    b.button(text="👥 Список пользователей", callback_data="admin_users")
    b.button(text="📊 Статистика продаж",    callback_data="admin_sales")
    b.button(text="🎁 Выдать Premium",       callback_data="admin_give_prem")
    b.adjust(1)

    await message.answer(
        f"🔧 <b>Админ-панель</b>\n\n"
        f"👥 Пользователей: <b>{users}</b>\n"
        f"💎 Активных Premium: <b>{premium_cnt}</b>\n"
        f"🎮 Всего игр: <b>{total_games}</b>\n"
        f"💰 Покупок: <b>{purchases}</b>\n"
        f"⭐ Stars получено: <b>{total_stars}</b>",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )

@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    stats = load_stats()
    lines = []
    for uid, u in list(stats.items())[:20]:
        prem  = "💎" if is_premium_active(u) else ""
        lines.append(f"{prem}<b>{u['username']}</b> — ✨{u.get('xp',0)} XP, 🎮{u.get('total_games',0)} игр, ⭐{u.get('total_stars_spent',0)}")
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data="admin_back")
    await callback.message.edit_text(
        f"👥 <b>Пользователи</b> (до 20):\n\n" + "\n".join(lines) if lines else "Пусто",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data == "admin_sales")
async def admin_sales(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    stats    = load_stats()
    by_item  = {}
    for u in stats.values():
        for h in u.get("history", []):
            pass  # история квизов, не покупок
    total_stars   = sum(u.get("total_stars_spent", 0) for u in stats.values())
    total_purch   = sum(u.get("total_purchases", 0) for u in stats.values())
    premium_active = sum(1 for u in stats.values() if is_premium_active(u))
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data="admin_back")
    await callback.message.edit_text(
        f"📊 <b>Статистика продаж</b>\n\n"
        f"💰 Всего покупок: <b>{total_purch}</b>\n"
        f"⭐ Всего Stars: <b>{total_stars}</b>\n"
        f"💎 Активных Premium: <b>{premium_active}</b>",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data == "admin_give_prem")
async def admin_give_prem_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    await callback.message.answer("Введи команду:\n<code>/giveprem USER_ID дней</code>\nНапример: <code>/giveprem 123456789 30</code>", parse_mode="HTML")
    await callback.answer()

@router.message(Command("giveprem"))
async def give_premium(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /giveprem USER_ID дней")
        return
    try:
        target_id = int(parts[1])
        days      = int(parts[2])
    except ValueError:
        await message.answer("Неверный формат. Пример: /giveprem 123456789 30")
        return

    stats = load_stats()
    uid   = str(target_id)
    if uid not in stats:
        await message.answer(f"Пользователь {target_id} не найден в базе.")
        return

    u           = stats[uid]
    until       = datetime.now() + timedelta(days=days)
    u["is_premium"]    = True
    u["premium_until"] = until.isoformat()
    u["hints_left"]    = 9999
    save_stats(stats)

    await message.answer(f"✅ Premium выдан пользователю {u['username']} ({target_id}) до {until.strftime('%d.%m.%Y')}")

    try:
        await bot.send_message(
            target_id,
            f"🎁 <b>Тебе выдан Premium на {days} дней!</b>\n\n"
            f"👑 Активен до: {until.strftime('%d.%m.%Y')}\n"
            f"💡 Безлимитные подсказки\n"
            f"🔴 Доступ к сложным вопросам\n"
            f"💎 Значок в лидерборде",
            parse_mode="HTML",
        )
    except Exception:
        pass

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    await admin_panel.__wrapped__(callback.message) if hasattr(admin_panel, '__wrapped__') else None
    await callback.answer()

# ─────────────────────────────────────────────────────────────
# ЗАПУСК
# ─────────────────────────────────────────────────────────────

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Python Quiz Bot v4.0 запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
