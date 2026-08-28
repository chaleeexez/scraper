import io
import pandas as pd
from playwright.sync_api import sync_playwright


def scrape_data():
  url = "https://www.thaiwater.net/weather/rainfall"
  print("Connecting to Thaiwater...")

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    )

    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(5000)

    html_content = page.content()
    browser.close()

  # แปลง HTML เป็น Pandas DataFrame
  dfs = pd.read_html(io.StringIO(html_content))
  df = dfs[0]

  # [วางตรงนี้] คลีนเลือกเฉพาะ 4 คอลัมน์แรก (ตัด Unnamed: 4 ออก)
  df = df.iloc[:, :4]

  # บันทึกลง CSV
  output_file = "thaiwater_rainfall_live.csv"
  df.to_csv(output_file, index=False, encoding="utf-8-sig")
  print(f"Successfully updated {output_file}")


if __name__ == "__main__":
  scrape_data()
