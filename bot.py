import os, time, threading, requests
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import undetected_chromedriver as uc
import telebot

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SPORT = "soccer_epl"
bot = telebot.TeleBot(TELEGRAM_TOKEN)

def send_telegram(text):
    try: bot.send_message(CHAT_ID, text)
    except: pass

def get_live_matches():
    url = f"https://api.odds-api.io/v1/odds/{SPORT}?apiKey={ODDS_API_KEY}&regions=eu&markets=totals"
    resp = requests.get(url)
    if resp.status_code != 200: return []
    data = resp.json()
    matches = []
    for event in data:
        for bookmaker in event.get('bookmakers', []):
            if bookmaker['key'] == 'williamhill':
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'totals':
                        for outcome in market.get('outcomes', []):
                            if outcome['description'] == 'Over 2.5':
                                matches.append({'id': event['id'], 'home': event['home_team'], 'away': event['away_team'], 'over_odds': float(outcome['price'])})
                                break
    return matches

def get_ls_odds(match_url):
    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = uc.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(match_url)
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//span[contains(@class, 'total-over')]")))
        text = element.text.replace(',', '.')
        if 'закрыт' in text.lower() or text.strip() == '': return None
        return float(text)
    except: return None
    finally: driver.quit()

def monitor_match(match):
    match_id, home, away = match['id'], match['home'], match['away']
    ls_url = "https://www.ligastavok.ru/sport/football/..."  # замените позже
    wh_old = match['over_odds']
    goal_time = None
    while True:
        wh_new = None
        for m in get_live_matches():
            if m['id'] == match_id:
                wh_new = m['over_odds']
                break
        if wh_new is None:
            time.sleep(2)
            continue
        if goal_time is None and wh_new < wh_old * 0.7:
            goal_time = datetime.now()
            send_telegram(f"⚽ ГОЛ в {home} - {away} в {goal_time.strftime('%H:%M:%S')}")
        if goal_time is not None:
            ls_new = get_ls_odds(ls_url)
            if ls_new is None:
                delay = (datetime.now() - goal_time).total_seconds()
                send_telegram(f"🔒 Котировки ЛС закрылись через {delay:.1f} сек\n{home} - {away}")
                break
        wh_old = wh_new
        time.sleep(2)

def main():
    send_telegram("🚀 Бот запущен")
    while True:
        matches = get_live_matches()
        if not matches:
            time.sleep(10)
            continue
        for match in matches:
            t = threading.Thread(target=monitor_match, args=(match,))
            t.daemon = True
            t.start()
        time.sleep(3600)

if __name__ == "__main__":
    main()
