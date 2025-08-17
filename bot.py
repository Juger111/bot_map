import telebot
from telebot import types
from pathlib import Path

from config import TOKEN, DATABASE
from logic import DB_Map

bot = telebot.TeleBot(TOKEN)
manager = DB_Map(DATABASE)
manager.create_user_table()


def _city_from_text(text: str) -> str:
    """Возвращает всё после имени команды как название города."""
    # Пример: "/show_city New York" -> "New York"
    if not text:
        return ""
    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        return ""
    return parts[1].strip()


@bot.message_handler(commands=["start"])
def handle_start(message):
    bot.send_message(
        message.chat.id,
        "Привет! Я бот-картограф. Умею показывать города на карте и запоминать их.\n"
        "Напиши /help для списка команд.",
    )


@bot.message_handler(commands=["help"])
def handle_help(message):
    help_text = (
        "Доступные команды:\n"
        "/show_city <город на английском> — показать город на карте\n"
        "/remember_city <город на английском> — сохранить город\n"
        "/show_my_cities — показать все сохранённые города\n"
    )
    bot.send_message(message.chat.id, help_text)


@bot.message_handler(commands=["show_city"])
def handle_show_city(message):
    city_name = _city_from_text(message.text or "")
    if not city_name:
        bot.send_message(message.chat.id, "Формат: /show_city <city_name> (например, /show_city London)")
        return

    coords = manager.get_coords_by_name(city_name)
    if not coords:
        bot.send_message(message.chat.id, "Такого города я не знаю. Убедись, что он написан на английском!")
        return

    lat, lon, name = coords  # lon здесь — это фактически lng из БД
    path = Path(f"map_{message.chat.id}_single.png")
    img_path = manager.create_graph(
        str(path),
        [{"city": name, "lat": lat, "lon": lon}],  # можно и 'lng' передать — логика поддерживает оба ключа
    )
    with open(img_path, "rb") as img:
        bot.send_photo(message.chat.id, img)


@bot.message_handler(commands=["remember_city"])
def handle_remember_city(message):
    city_name = _city_from_text(message.text or "")
    if not city_name:
        bot.send_message(message.chat.id, "Формат: /remember_city <city_name>")
        return

    if manager.add_city(message.from_user.id, city_name):
        bot.send_message(message.chat.id, f"Город {city_name} успешно сохранён!")
    else:
        bot.send_message(message.chat.id, "Такого города я не знаю. Убедись, что он написан на английском!")


@bot.message_handler(commands=["show_my_cities"])
def handle_show_my_cities(message):
    cities = manager.select_cities(message.from_user.id)
    if not cities:
        bot.send_message(message.chat.id, "Пока нет сохранённых городов. Добавь через /remember_city <city_name>.")
        return

    path = Path(f"map_{message.chat.id}_all.png")
    img_path = manager.create_graph(str(path), cities)
    with open(img_path, "rb") as img:
        bot.send_photo(message.chat.id, img)


if __name__ == "__main__":
    bot.polling()
