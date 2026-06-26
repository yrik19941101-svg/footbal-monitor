import os
import time
import requests
from datetime import datetime

# ========== НАСТРОЙКИ ==========
ODDS_API_KEY = "c5d200484e03743c549d12363e0a39fa0e539608253f42bc307f081f1f178c84"   # замените на свой

# Параметры матча
SPORT = "soccer"                     # можно уточнить лигу, но "soccer" ищет по всем
HOME_TEAM = "NFA"                    # или "Be1 NFA" — как в API
AWAY_TEAM = "Zalgiris II"            # или "Kauno Zalgiris II"

# Порог падения коэффициента (при голе он падает на 30–50%)
DROP_THRESHOLD = 0.70                # 0.70 = падение на 30%

# ========== ЛОГИРОВАНИЕ ==========
def log(text):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}")

# ========== ПОЛУЧЕНИЕ КОЭФФИЦИЕНТА ==========
def get_over_odds():
    url = f"https://api.odds-api.io/v1/odds/{SPORT}?apiKey={ODDS_API_KEY}&regions=eu&markets=totals"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            log(f"API ошибка: {resp.status_code}")
            return None

        data = resp.json()
        for event in data:
            home = event.get('home_team', '').lower()
            away = event.get('away_team', '').lower()

            # Ищем нужный матч по названиям (частичное совпадение)
            if (HOME_TEAM.lower() in home or home in HOME_TEAM.lower()) and \
               (AWAY_TEAM.lower() in away or away in AWAY_TEAM.lower()):

                for bookmaker in event.get('bookmakers', []):
                    if bookmaker['key'] == 'williamhill':
                        for market in bookmaker.get('markets', []):
                            if market['key'] == 'totals':
                                for outcome in market.get('outcomes', []):
                                    if outcome['description'] == 'Over 2.5':
                                        return float(outcome['price'])
        return None
    except Exception as e:
        log(f"Ошибка: {e}")
        return None

# ========== ГЛАВНЫЙ ЦИКЛ ==========
def main():
    log("🚀 Бот запущен. Мониторим матч NFA vs Zalgiris II")
    log("Ожидаем первый коэффициент...")

    # Ждём, пока матч появится в линии
    old_odds = None
    while old_odds is None:
        old_odds = get_over_odds()
        if old_odds is None:
            log("Матч пока не найден, ждём 30 сек...")
            time.sleep(30)

    log(f"Начальный коэффициент Over 2.5: {old_odds}")

    # Мониторинг изменений
    while True:
        new_odds = get_over_odds()
        if new_odds is None:
            time.sleep(2)
            continue

        # Если коэффициент упал ниже порога — считаем, что гол забит
        if new_odds < old_odds * DROP_THRESHOLD:
            goal_time = datetime.now().strftime('%H:%M:%S')
            log(f"⚽ ГОЛ! Коэффициент упал с {old_odds} до {new_odds} в {goal_time}")
            # Здесь можно отправить уведомление (Telegram, email и т.п.)
            # Например, через print — в логах Bothost вы увидите сообщение
            # Если нужен Telegram — раскомментируйте блок ниже

            # ===== Telegram (опционально) =====
            # import requests as req
            # TOKEN = "ВАШ_ТОКЕН"
            # CHAT_ID = "ВАШ_ID"
            # req.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            #          json={"chat_id": CHAT_ID, "text": f"⚽ ГОЛ в NFA vs Zalgiris II в {goal_time}"})
            # =================================

            # После гола можно завершить цикл или продолжать мониторить дальше
            break

        old_odds = new_odds
        time.sleep(1)  # проверка каждую секунду для максимальной скорости

    log("🔚 Мониторинг завершён.")

if __name__ == "__main__":
    main()
