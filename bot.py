import os
import time
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ---------- КЛЮЧ ODDS-API (замените) ----------
ODDS_API_KEY = "c5d200484e03743c549d12363e0a39fa0e539608253f42bc307f081f1f178c84"

# ---------- НАСТРОЙКИ ----------
SPORT = "soccer"  # все лиги
FILTER_DELAY = 4.0
LS_MATCH_URL = "https://www.ligastavok.ru/sports/soccer/rubin-kazan-kamaz-id-23289981-service-id-27-ext-id-897087"
LS_MATCH_HOME = "Рубин Казань"
LS_MATCH_AWAY = "КАМАЗ"

# ---------- ЛОГ ----------
def log(text):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}")

# ---------- 1. Получить все матчи с WH (для отладки) ----------
def get_all_wh_matches():
    url = f"https://api.odds-api.io/v1/odds/{SPORT}?apiKey={ODDS_API_KEY}&regions=eu&markets=totals"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            log(f"WH API ошибка: {resp.status_code}")
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
        return matches
    except Exception as e:
        log(f"WH API ошибка: {e}")
        return []

# ---------- 2. Найти нужный матч на WH ----------
def find_wh_match(home, away):
    matches = get_all_wh_matches()
    if not matches:
        return None
    
    # Сначала точное совпадение
    for m in matches:
        if m['home'].lower() == home.lower() and m['away'].lower() == away.lower():
            return m
    
    # Затем частичное
    for m in matches:
        if (home.lower() in m['home'].lower() or m['home'].lower() in home.lower()) and \
           (away.lower() in m['away'].lower() or m['away'].lower() in away.lower()):
            return m
    
    # Если не нашли, выводим все матчи в лог для отладки
    log("❌ Матч не найден. Доступные матчи на WH:")
    for m in matches[:10]:  # покажем первые 10
        log(f"  {m['home']} - {m['away']}")
    return None

# ---------- 3. Получить коэффициент с Лиги Ставок ----------
def get_ls_odds():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get(LS_MATCH_URL)
        time.sleep(10)  # ждём загрузки
        
        selectors = [
            "//span[contains(@class, 'total-over')]",
            "//div[contains(@class, 'total-over')]//span[contains(@class, 'price')]",
            "//button[contains(@class, 'total-over')]//span[contains(@class, 'coef')]",
            "//span[contains(text(), 'Более 2.5')]/following-sibling::span",
            "//div[contains(@class, 'outcome')]//span[contains(text(), '2.5')]/following-sibling::span",
            "//span[contains(@class, 'odds')][contains(text(), '2.5')]"
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
        
        # Проверяем, не закрыт ли рынок
        if 'закрыт' in driver.page_source.lower():
            return None
        
        log("Не удалось найти коэффициент Over 2.5 на странице ЛС")
        return None
    except Exception as e:
        log(f"Ошибка получения коэф. ЛС: {e}")
        return None
    finally:
        if driver:
            driver.quit()

# ---------- 4. Мониторинг одного матча (бесконечный цикл с перезапуском) ----------
def monitor_match():
    log(f"Начинаем мониторинг: {LS_MATCH_HOME} - {LS_MATCH_AWAY}")
    
    # Находим матч на WH
    wh_match = find_wh_match(LS_MATCH_HOME, LS_MATCH_AWAY)
    if not wh_match:
        log("Матч не найден на William Hill. Повторная попытка через 60 секунд...")
        time.sleep(60)
        return  # выходим, main перезапустит
    
    wh_old = wh_match['over_odds']
    goal_time = None
    log(f"Начальный коэффициент WH: {wh_old}")
    
    while True:
        try:
            # Обновляем коэффициент WH
            wh_match = find_wh_match(LS_MATCH_HOME, LS_MATCH_AWAY)
            if not wh_match:
                log("Матч пропал с WH, ждём 30 секунд...")
                time.sleep(30)
                continue
            
            wh_new = wh_match['over_odds']
            
            # Проверяем гол (падение ≥ 30%)
            if goal_time is None and wh_new < wh_old * 0.7:
                goal_time = datetime.now()
                log(f"⚽ ГОЛ в {LS_MATCH_HOME} - {LS_MATCH_AWAY} в {goal_time.strftime('%H:%M:%S')}")
            
            # Если гол был, проверяем закрытие на ЛС
            if goal_time is not None:
                ls_odds = get_ls_odds()
                if ls_odds is None:  # рынок закрыт
                    close_time = datetime.now()
                    delay = (close_time - goal_time).total_seconds()
                    if delay >= FILTER_DELAY:
                        log(f"🔒 Задержка {delay:.1f} сек - {LS_MATCH_HOME} - {LS_MATCH_AWAY}")
                    else:
                        log(f"Задержка {delay:.1f} сек — пропускаем (< {FILTER_DELAY} сек)")
                    break  # завершаем мониторинг этого матча (потом main перезапустит)
            
            wh_old = wh_new
            time.sleep(2)
            
        except Exception as e:
            log(f"Ошибка в monitor_match: {e}")
            time.sleep(10)

# ---------- 5. Главный цикл (бесконечный) ----------
def main():
    log("🚀 Бот запущен. Мониторим матч: Рубин Казань - КАМАЗ")
    while True:
        try:
            monitor_match()
            log("Мониторинг завершён. Перезапуск через 10 секунд...")
            time.sleep(10)
        except Exception as e:
            log(f"Критическая ошибка: {e}, перезапуск через 30 секунд...")
            time.sleep(30)

if __name__ == "__main__":
    main()
