import requests
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Настройки
BOT_TOKEN = '7892638380:AAEE2HMiUBPzL_VyB7m1XUHYxrrPm4EarEo'
OWM_API_KEY = '7c43d41fec48024dae1a86734ba7ac14'

# Координаты населённых пунктов
LOCATIONS = {
    'grigoropolisskaya': {
        'name': 'Григорополисская',
        'lat': 45.2972,
        'lon': 40.6667
    },
    'mishelevka': {
        'name': 'Мишелевка',
        'lat': 52.8558,  # Примерные координаты, уточните!
        'lon': 103.1706
    }
}

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def location_keyboard():
    """Клавиатура для выбора населённого пункта"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Григорополисская", callback_data='grigoropolisskaya')],
        [InlineKeyboardButton("Мишелевка", callback_data='mishelevka')]
    ])

def main_menu_keyboard():
    """Основное меню прогнозов"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕒 Сейчас", callback_data='current')],
        [InlineKeyboardButton("📅 Сегодня по часам", callback_data='today')],
        [InlineKeyboardButton("🌞 Завтра", callback_data='tomorrow')],
        [InlineKeyboardButton("📆 Неделя", callback_data='week')],
        [InlineKeyboardButton("🔁 Сменить деревню", callback_data='change_city')]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await show_location_choice(update, context)

async def show_location_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор населённого пункта"""
    query = update.callback_query
    text = "📍 Выберите населённый пункт:"
    keyboard = location_keyboard()

    if query:
        await query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)

async def handle_location_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора населённого пункта"""
    query = update.callback_query
    await query.answer()

    location = LOCATIONS.get(query.data)
    if location:
        context.user_data['location'] = query.data
        await show_main_menu(query, location['name'])
    else:
        await query.edit_message_text("❌ Ошибка выбора населённого пункта")

async def show_main_menu(query, city_name):
    """Показать основное меню"""
    await query.edit_message_text(
        f"🌤 Выберите тип прогноза для {city_name}:",
        reply_markup=main_menu_keyboard()
    )

async def handle_forecast_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик основных кнопок прогноза"""
    query = update.callback_query
    await query.answer()

    location = context.user_data.get('location')
    if not location:
        await show_location_choice(update, context)
        return

    if query.data == 'change_city':
        await show_location_choice(update, context)
        return

    # Получение координат выбранного населённого пункта
    loc_data = LOCATIONS[location]

    try:
        if query.data == 'current':
            await send_current_weather(query, loc_data)
        elif query.data == 'today':
            await send_hourly_forecast(query, loc_data)
        elif query.data == 'tomorrow':
            await send_tomorrow_forecast(query, loc_data)
        elif query.data == 'week':
            await send_weekly_forecast(query, loc_data)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await query.edit_message_text("⚠️ Ошибка получения данных", reply_markup=main_menu_keyboard())

def get_weather_icon(icon_code):
    """Преобразование кодов иконок в эмодзи"""
    icons = {
        '01d': '☀️ Ясно',         '01n': '🌕 Ясная ночь',
        '02d': '⛅ Малооблачно',   '02n': '☁️ Облачно',
        '03d': '☁️ Облачно',       '03n': '☁️ Облачно',
        '04d': '☁️ Пасмурно',      '04n': '☁️ Пасмурно',
        '09d': '🌧️ Моросящий дождь', '09n': '🌧️ Моросящий дождь',
        '10d': '🌦️ Дождь',         '10n': '🌦️ Ночной дождь',
        '11d': '⛈️ Гроза',        '11n': '⛈️ Ночная гроза',
        '13d': '❄️ Снег',         '13n': '❄️ Снегопад',
        '50d': '🌫️ Туман',        '50n': '🌫️ Туман'
    }
    return icons.get(icon_code, '🌀 Неизвестно')

def temp_to_color(temp):
    """Цветовая маркировка температуры"""
    if temp < -10:
        return "❄️🔵"  # Синий - экстремальный холод
    elif temp < 0:
        return "🌨️🔵"  # Синий - холод
    elif temp < 10:
        return "🌊🔷"   # Голубой - прохладно
    elif temp < 20:
        return "🌿🟢"   # Зеленый - комфортно
    elif temp < 30:
        return "☀️🟠"   # Оранжевый - тепло
    else:
        return "🔥🔴"   # Красный - жара

def get_weather_warnings(weather_data):
    """Генерация предупреждений о аномалиях"""
    warnings = []

    # Проверка температуры
    temp = weather_data['main']['temp']
    if temp > 35:
        warnings.append("⚠️🔥 Аномальная жара! Оставайтесь в тени.")
    elif temp < -15:
        warnings.append("⚠️❄️ Экстремальный холод! Одевайтесь теплее.")

    # Проверка осадков
    if 'rain' in weather_data:
        if weather_data['rain'].get('1h', 0) > 20:
            warnings.append("⚠️🌧️ Сильный ливень! Возможны подтопления.")

    # Проверка ветра
    if weather_data['wind']['speed'] > 15:
        warnings.append("⚠️🌪️ Штормовой ветер! Будьте осторожны.")

    # Проверка грозы
    if any(w['main'] == 'Thunderstorm' for w in weather_data['weather']):
        warnings.append("⚠️⛈️ Гроза! Избегайте открытых пространств.")

    return warnings

async def send_current_weather(query, loc_data):
    """Текущая погода с цветом и предупреждениями"""
    data = get_weather_data('weather', loc_data)
    icon = get_weather_icon(data['weather'][0]['icon'])
    temp = data['main']['temp']
    color = temp_to_color(temp)
    warnings = get_weather_warnings(data)

    message = ""
    if warnings:
        message += "🚨 " + "\n🚨 ".join(warnings) + "\n\n"

    message += (
        f"{color} {icon}\n"
        f"🌡 Температура: {temp}°C\n"
        f"🥶 Ощущается как: {data['main']['feels_like']}°C\n"
        f"💨 Ветер: {data['wind']['speed']} м/с\n"
        f"💧 Влажность: {data['main']['humidity']}%"
    )

    await query.edit_message_text(message, reply_markup=main_menu_keyboard())

async def send_hourly_forecast(query, loc_data):
    """Почасовой прогноз с цветовой маркировкой"""
    data = get_weather_data('forecast', loc_data)
    forecast = []

    for item in data['list'][:8]:
        time = datetime.fromtimestamp(item['dt']).strftime('%H:%M')
        icon = get_weather_icon(item['weather'][0]['icon'])
        color = temp_to_color(item['main']['temp'])
        forecast.append(f"{time} {icon} {color} {item['main']['temp']}°C")

    message = f"📅 Прогноз на сегодня в {loc_data['name']}:\n" + "\n".join(forecast)

    # Общие предупреждения
    all_warnings = []
    for item in data['list'][:8]:
        all_warnings.extend(get_weather_warnings(item))

    if all_warnings:
        unique_warnings = list(set(all_warnings))
        message = "🚨 " + "\n🚨 ".join(unique_warnings) + "\n\n" + message

    await query.edit_message_text(message, reply_markup=main_menu_keyboard())

async def send_tomorrow_forecast(query, loc_data):
    """Прогноз на завтра с исправленными иконками"""
    try:
        data = get_weather_data('forecast', loc_data)
        now = datetime.now()
        tomorrow = now + timedelta(days=1)

        # Фильтрация данных только для завтрашнего дня
        target_date = tomorrow.date()
        period_data = [
            item for item in data['list']
            if datetime.fromtimestamp(item['dt']).date() == target_date
        ]

        if not period_data:
            await query.edit_message_text("⚠️ Данные на завтра еще не доступны", reply_markup=main_menu_keyboard())
            return

        periods = {
            '🌅 Утро': (6, 12),
            '☀️ День': (12, 18),
            '🌆 Вечер': (18, 23),
            '🌙 Ночь': (23, 6)
        }

        forecast = []
        for period_name, (start_hour, end_hour) in periods.items():
            period_items = [
                item for item in period_data
                if is_time_period(item['dt'], target_date, start_hour, end_hour)
            ]

            if not period_items:
                continue

            # Расчет средней температуры
            avg_temp = sum(item['main']['temp'] for item in period_items) / len(period_items)

            # Выбор наиболее частой иконки
            icon_counter = {}
            for item in period_items:
                icon = item['weather'][0]['icon']
                icon_counter[icon] = icon_counter.get(icon, 0) + 1

            most_common_icon = max(icon_counter, key=icon_counter.get)
            icon_emoji = get_weather_icon(most_common_icon)

            forecast.append(
                f"{period_name}: {icon_emoji} {avg_temp:.1f}°C"
            )

        if not forecast:
            await query.edit_message_text("⚠️ Нет данных для завтрашнего дня", reply_markup=main_menu_keyboard())
            return

        message = (
            f"🌞 Прогноз на завтра в {loc_data['name']}:\n"
            f"{'\n'.join(forecast)}"
        )

        await query.edit_message_text(message, reply_markup=main_menu_keyboard())

    except Exception as e:
        logger.error(f"Ошибка в прогнозе на завтра: {e}")
        await query.edit_message_text("⚠️ Ошибка при получении данных", reply_markup=main_menu_keyboard())

async def send_weekly_forecast(query, loc_data):
    """Прогноз на неделю с разбивкой по времени суток"""
    try:
        data = get_weather_data('forecast', loc_data)
        daily_data = {}
        periods = {
            '🌅 Утро': (6, 12),
            '☀️ День': (12, 18),
            '🌆 Вечер': (18, 23),
            '🌙 Ночь': (23, 6)
        }

        for item in data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            date = dt.strftime('%d.%m (%A)').replace('Sunday', 'Вс').replace('Monday', 'Пн').replace('Tuesday', 'Вт').replace('Wednesday', 'Ср').replace('Thursday', 'Чт').replace('Friday', 'Пт').replace('Saturday', 'Сб')

            if date not in daily_data:
                daily_data[date] = {period: [] for period in periods}

            for period, (start, end) in periods.items():
                if is_time_period(item['dt'], dt.date(), start, end):
                    daily_data[date][period].append({
                        'temp': item['main']['temp'],
                        'icon': get_weather_icon(item['weather'][0]['icon'])
                    })

        forecast = []
        for date, periods_data in list(daily_data.items())[:5]:
            day_forecast = [f"\n📅 {date}:"]
            for period, values in periods_data.items():
                if values:
                    temps = [v['temp'] for v in values]
                    icons = [v['icon'] for v in values]
                    avg_temp = sum(temps)/len(temps)
                    main_icon = max(set(icons), key=icons.count)
                    day_forecast.append(f"{period} {main_icon} {avg_temp:.1f}°C")

            forecast.append("\n".join(day_forecast))

        message = f"📆 Прогноз на неделю в {loc_data['name']}:\n" + "\n".join(forecast)
        await query.edit_message_text(message, reply_markup=main_menu_keyboard())

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await query.edit_message_text("⚠️ Ошибка получения данных", reply_markup=main_menu_keyboard())


def is_time_period(timestamp, target_date, start_hour, end_hour):
    """Проверка попадания времени в период"""
    dt = datetime.fromtimestamp(timestamp)
    if dt.date() != target_date:
        return False
    if start_hour < end_hour:
        return start_hour <= dt.hour < end_hour
    return dt.hour >= start_hour or dt.hour < end_hour

def get_weather_data(request_type, location):
    """Получение данных о погоде"""
    base_url = 'https://api.openweathermap.org/data/2.5/'
    url = f"{base_url}{request_type}"

    params = {
        'lat': location['lat'],
        'lon': location['lon'],
        'appid': OWM_API_KEY,
        'units': 'metric',
        'lang': 'ru'
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(handle_location_choice, pattern='^(grigoropolisskaya|mishelevka)$'))
    application.add_handler(CallbackQueryHandler(handle_forecast_choice))

    application.run_polling()

if __name__ == '__main__':
    main()
