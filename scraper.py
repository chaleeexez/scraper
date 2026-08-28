import io
import logging
import time
import pandas as pd
from playwright.sync_api import sync_playwright

# ตั้งค่า Logging ให้สอดคล้องกับ flask_app.py
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def scrape_data(max_retries=3, delay=5):
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

        # รอจนมีแถวข้อมูลในตาราง
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
        # ยุบ MultiIndex หากฝั่งเว็บปรับ Header ซ้อนชั้น
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
      logger.warning(f"Attempt {attempt} failed: {e}")
      if attempt < max_retries:
        time.sleep(delay)
      else:
        logger.error(f"Scraper failed after {max_retries} attempts: {e}")
        raise RuntimeError(f"Scraper failed after {max_retries} attempts: {e}")
    finally:
      # บังคับคืนทรัพยากรเบราว์เซอร์เสมอ ไม่ว่าจะสำเร็จหรือเกิด Error
      if browser:
        try:
          browser.close()
        except Exception:
          pass


if __name__ == "__main__":
  scrape_data()
