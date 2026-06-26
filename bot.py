import os
import sys
import subprocess

# ---------- ПРОВЕРКА И УСТАНОВКА ЗАВИСИМОСТЕЙ ----------
try:
    import telebot
except ImportError:
    print("📦 Устанавливаем зависимости...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("✅ Зависимости установлены. Перезапускаем бота...")
    # Перезапускаем текущий скрипт
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ---------- ОСНОВНЫЕ ИМПОРТЫ (после успешной установки) ----------
import time
import threading
import requests
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import undetected_chromedriver as uc
import telebot

# ---------- КЛЮЧИ (ЗАМЕНИТЕ НА СВОИ) ----------
ODDS_API_KEY = "c5d200484e03743c549d12363e0a39fa0e539608253f42bc307f081f1f178c84"          # замените
TELEGRAM_TOKEN = "8835537497:AAEhi_RNjHm4WM6sNiZhHnbULOfIoc3k2P8"  # замените
CHAT_ID = "354290076"               # замените

# ---------- НАСТРОЙКИ ----------
SPORT = "soccer"
FILTER_DELAY = 4.0
LIGA_STAVOK_LIVE_URL = "https://www.ligastavok.ru/Live"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def send_telegram(text):
    try:
        bot.send_message(CHAT_ID, text)
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")

# ---------- ВСЕ ОСТАЛЬНЫЕ ФУНКЦИИ (без изменений) ----------
def get_wh_matches():
    url = f"https://api.odds-api.io/v1/odds/{SPORT}?apiKey={ODDS_API_KEY}&regions=eu&markets=totals"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            print(f"WH API ошибка: {resp.status_code}")
            return []
        data = resp.json()
        matches = []
        for event in data:
            for bookmaker in event.get('bookmakers', []):
                if bookmaker['key'] == 'williamhill':
                    for market in bookmaker.get('markets', []):
                        if market['key'] == 'totals':
                            for outcome in market.get('outcomes', []):
                                if outcome['description'] == 'Over 2.5':
                                    matches.append({
                                        'id': event['id'],
                                        'home': event['home_team'],
                                        'away': event['away_team'],
                                        'over_odds': float(outcome['price'])
                                    })
                                    break
        print(f"WH: найдено матчей: {len(matches)}")
        return matches
    except Exception as e:
        print(f"WH API ошибка: {e}")
        return []

def get_ls_matches():
    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = None
    try:
        driver = uc.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get(LIGA_STAVOK_LIVE_URL)
        time.sleep(5)
        
        links = driver.find_elements(By.XPATH, "//a[contains(@href, '/event/')]")
        matches = []
        for link in links:
            url = link.get_attribute("href")
            if url and "/event/" in url:
                text = link.text.strip()
                if " - " in text:
                    parts = text.split(" - ")
                    if len(parts) == 2:
                        home = parts[0].strip()
                        away = parts[1].strip()
                        home = ' '.join(home.split()).strip()
                        away = ' '.join(away.split()).strip()
                        if home and away and len(home) > 1 and len(away) > 1:
                            matches.append({
                                "home": home,
                                "away": away,
                                "url": url
                            })
        print(f"ЛС: найдено матчей: {len(matches)}")
        return matches
    except Exception as e:
        print(f"ЛС ошибка: {e}")
        return []
    finally:
        if driver:
            driver.quit()

def match_found(wh_match, ls_matches):
    wh_home = wh_match['home'].lower().strip()
    wh_away = wh_match['away'].lower().strip()
    for ls in ls_matches:
        ls_home = ls['home'].lower().strip()
        ls_away = ls['away'].lower().strip()
        if ls_home == wh_home and ls_away == wh_away:
            return ls['url']
        if (wh_home in ls_home or ls_home in wh_home) and (wh_away in ls_away or ls_away in wh_away):
            return ls['url']
    return None

def get_ls_odds(match_url):
    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = None
    try:
        driver = uc.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get(match_url)
        time.sleep(3)
        
        selectors = [
            "//span[contains(@class, 'total-over')]",
            "//div[contains(@class, 'total-over')]//span[contains(@class, 'price')]",
            "//button[contains(@class, 'total-over')]//span[contains(@class, 'coef')]",
            "//span[contains(text(), 'Более 2.5')]/following-sibling::span"
        ]
        for selector in selectors:
            try:
                element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                text = element.text.replace(',', '.').strip()
                if text and text != '-' and not text.lower().startswith(('закрыт', 'закрыто')):
                    try:
                        return float(text)
                    except:
                        continue
            except:
                continue
        return None
    except Exception as e:
        print(f"Ошибка получения коэф. ЛС: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def monitor_match(wh_match, ls_url):
    match_id = wh_match['id']
    home = wh_match['home']
    away = wh_match['away']
    wh_old = wh_match['over_odds']
    goal_time = None
    
    print(f"Начинаем мониторинг: {home} - {away}")
    while True:
        try:
            wh_new = None
            for m in get_wh_matches():
                if m['id'] == match_id:
                    wh_new = m['over_odds']
                    break
            if wh_new is None:
                time.sleep(2)
                continue
            
            if goal_time is None and wh_new < wh_old * 0.7:
                goal_time = datetime.now()
                msg = f"⚽ ГОЛ в {home} - {away} в {goal_time.strftime('%H:%M:%S')}"
                print(msg)
                send_telegram(msg)
            
            if goal_time is not None:
                ls_odds = get_ls_odds(ls_url)
                if ls_odds is None:
                    close_time = datetime.now()
                    delay = (close_time - goal_time).total_seconds()
                    if delay >= FILTER_DELAY:
                        msg = f"🔒 Задержка {delay:.1f} сек\n{home} - {away}"
                        print(msg)
                        send_telegram(msg)
                    else:
                        print(f"Задержка {delay:.1f} сек — пропускаем (< {FILTER_DELAY} сек)")
                    break
            
            wh_old = wh_new
            time.sleep(2)
        except Exception as e:
            print(f"Ошибка в monitor_match: {e}")
            time.sleep(5)

def main():
    send_telegram("🚀 Бот запущен. Ищем матчи...")
    print("🚀 Бот запущен")
    
    while True:
        try:
            wh_matches = get_wh_matches()
            if not wh_matches:
                print("Нет матчей на WH, ждём...")
                time.sleep(30)
                continue
            
            ls_matches = get_ls_matches()
            if not ls_matches:
                print("Нет матчей на ЛС, ждём...")
                time.sleep(30)
                continue
            
            matched = 0
            for wh in wh_matches:
                ls_url = match_found(wh, ls_matches)
                if ls_url:
                    matched += 1
                    print(f"✅ Совпадение: {wh['home']} - {wh['away']}")
                    t = threading.Thread(target=monitor_match, args=(wh, ls_url))
                    t.daemon = True
                    t.start()
            
            if matched == 0:
                print("❌ Совпадений не найдено. Возможно, разные названия команд.")
            
            time.sleep(300)  # 5 минут
        except Exception as e:
            print(f"Ошибка в main: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
