import io
import json
import logging
import os
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def scrape_rain_data(max_retries=3, delay=5):
  url = "https://www.thaiwater.net/weather/rainfall"

  for attempt in range(1, max_retries + 1):
    browser = None
    logger.info(
        f"Connecting to Thaiwater (Attempt {attempt}/{max_retries})..."
    )
    try:
      with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page.goto(url, wait_until="networkidle", timeout=60000)

        page.wait_for_selector("table tr:nth-child(2)", timeout=15000)
        page.wait_for_timeout(2000)
        html_content = page.content()

        browser.close()
        browser = None

      dfs = pd.read_html(io.StringIO(html_content))
      if not dfs:
        raise RuntimeError("ไม่พบตารางข้อมูลใน HTML")

      target_df = None
      for df_candidate in dfs:
        if isinstance(df_candidate.columns, pd.MultiIndex):
          df_candidate.columns = df_candidate.columns.get_level_values(-1)

        if {"ชื่อสถานี", "ที่ตั้ง"}.issubset(set(df_candidate.columns)):
          target_df = df_candidate
          break

      if target_df is None:
        raise RuntimeError(
            "โครงสร้างตารางเปลี่ยน ไม่พบตารางที่มีคอลัมน์ที่กำหนด"
        )

      df = target_df.iloc[:, :4]
      output_file = "thaiwater_rainfall_live.csv"
      df.to_csv(output_file, index=False, encoding="utf-8-sig")
      logger.info(f"Successfully updated {output_file}")
      return

    except Exception as e:
      logger.warning(f"Rain Scraper Attempt {attempt} failed: {e}")
      if attempt < max_retries:
        time.sleep(delay)
      else:
        logger.error(
            f"Rain Scraper failed after {max_retries} attempts: {e}"
        )
    finally:
      if browser:
        try:
          browser.close()
        except Exception:
          pass


def scrape_oil_price():
  logger.info("Fetching Oil Price data...")
  oil_data = []
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  # ช่องทางที่ 1: ดึงจาก Bangchak Official Web Service API
  try:
    api_url = "https://oil-price.bangchak.co.th/ApiOilPrice2/th"
    res = requests.get(api_url, headers=headers, timeout=10)
    if res.status_code == 200:
      data = res.json()
      items = []
      if isinstance(data, list) and len(data) > 0:
        items = data[0].get("oil", [])
      elif isinstance(data, dict):
        items = (
            data.get("oil", [])
            or data.get("responseData", {}).get("oil", [])
            or data.get("data", {}).get("oil", [])
        )

      for item in items:
        name = str(item.get("OilName", "") or item.get("name", "")).strip()
        if "ดีเซล" in name or "Diesel" in name:
          today = str(item.get("PriceToday", "") or item.get("today", ""))
          tomorrow = str(
              item.get("PriceTomorrow", "") or item.get("tomorrow", "")
          )
          oil_data.append({"name": name, "today": today, "tomorrow": tomorrow})
  except Exception as e:
    logger.warning(f"Bangchak Official API failed: {e}")

  # ช่องทางที่ 2: ดึงจาก Public Thai Oil API
  if not oil_data:
    try:
      open_api_url = "https://api.chnwt.dev/thai-oil-api/latest"
      res = requests.get(open_api_url, headers=headers, timeout=10)
      if res.status_code == 200:
        data = res.json()
        bcp_data = (
            data.get("response", {})
            .get("stations", {})
            .get("bangchak", {})
        )
        for key, val in bcp_data.items():
          name = val.get("name", "")
          if "ดีเซล" in name or "Diesel" in name:
            tomorrow_val = (
                str(val.get("tomorrow"))
                if val.get("tomorrow") is not None
                else ""
            )
            oil_data.append({
                "name": name,
                "today": str(val.get("price", "")),
                "tomorrow": tomorrow_val,
            })
    except Exception as e:
      logger.warning(f"Public Thai Oil API failed: {e}")

  # ช่องทางที่ 3: ใช้ Playwright เปิดหน้าเว็บตรง แกะตาราง HTML
  if not oil_data:
    logger.info("Falling back to Playwright for Oil Price...")
    browser = None
    try:
      with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=headers["User-Agent"])
        page.goto(
            "https://oil-price.bangchak.co.th/BcpOilPrice1/th",
            wait_until="networkidle",
            timeout=30000,
        )
        page.wait_for_timeout(2000)
        html_content = page.content()
        browser.close()
        browser = None

      soup = BeautifulSoup(html_content, "html.parser")
      rows = soup.find_all("tr")
      for row in rows:
        cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        if len(cols) >= 2:
          name = cols[0]
          if "ดีเซล" in name or "Diesel" in name:
            today_price = cols[1]
            tomorrow_price = cols[2] if len(cols) >= 3 else ""
            oil_data.append({
                "name": name,
                "today": today_price,
                "tomorrow": tomorrow_price,
            })
    except Exception as e:
      logger.error(f"Playwright Oil Scraper failed: {e}")
    finally:
      if browser:
        try:
          browser.close()
        except Exception:
          pass

  # เขียนไฟล์ oil_price.json เสมอ (ป้องกัน Git Error)
  if oil_data or not os.path.exists("oil_price.json"):
    with open("oil_price.json", "w", encoding="utf-8") as f:
      json.dump(oil_data, f, ensure_ascii=False, indent=2)
    logger.info(
        f"Successfully processed oil_price.json (Items: {len(oil_data)})"
    )


if __name__ == "__main__":
  scrape_rain_data()
  scrape_oil_price()
