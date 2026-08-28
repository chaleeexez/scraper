import io
import json
import logging
import os
import time
import feedparser
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import requests

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
  url = "https://www.bangchak.co.th/th/rss/oilprice"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }

  logger.info("Fetching Oil Price RSS from Bangchak...")
  oil_data = []

  try:
    res = requests.get(url, headers=headers, timeout=15)
    if res.status_code == 200:
      feed = feedparser.parse(res.text)
      if feed.entries:
        latest_entry = feed.entries[0]
        content = latest_entry.get("summary", "") or latest_entry.get(
            "description", ""
        )
        soup = BeautifulSoup(content, "html.parser")

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
    else:
      logger.error(f"Failed to fetch oil price RSS: HTTP {res.status_code}")
  except Exception as e:
    logger.error(f"Error scraping oil price: {e}")

  # สร้างไฟล์ oil_price.json เสมอ (แม้อ่านข้อมูลไม่ได้) เพื่อป้องกันปัญหา Git Error
  if oil_data or not os.path.exists("oil_price.json"):
    with open("oil_price.json", "w", encoding="utf-8") as f:
      json.dump(oil_data, f, ensure_ascii=False, indent=2)
    logger.info("Successfully processed oil_price.json")


if __name__ == "__main__":
  scrape_rain_data()
  scrape_oil_price()
