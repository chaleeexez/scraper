import io
import logging
import time
import pandas as pd
from playwright.sync_api import sync_playwright

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

        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # บังคับรอจนกว่าแถว "ไม่มีข้อมูล" จะหายไป และมีแถวข้อมูลจริงมากกว่า 3 แถว
        try:
          page.wait_for_function(
              "() => document.querySelectorAll('table tr').length > 3 &&"
              " !document.querySelector('table').innerText.includes('ไม่มีข้อมูล')",
              timeout=30000,
          )
        except Exception:
          # หากหน้านั้นโหลดช้า ให้รอเพิ่ม 5 วินาที
          page.wait_for_timeout(5000)

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
          # กรองเอาเฉพาะแถวที่มีข้อมูลจริง ตัดแถว 'ไม่มีข้อมูล' ออก
          filtered_df = df_candidate[
              df_candidate["ชื่อสถานี"] != "ไม่มีข้อมูล"
          ]
          if not filtered_df.empty:
            target_df = filtered_df
            break

      if target_df is None:
        raise RuntimeError("ไม่พบข้อมูลฝนในตาราง หรือตารางยังโหลดไม่เสร็จ")

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
      if browser:
        try:
          browser.close()
        except Exception:
          pass


if __name__ == "__main__":
  scrape_data()
