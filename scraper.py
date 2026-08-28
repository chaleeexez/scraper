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
        )
    )
    page.goto(url, wait_until="domcontentloaded")

    try:
      page.wait_for_selector("table", timeout=15000)
    except Exception:
      page.wait_for_timeout(5000)

    html_content = page.content()
    browser.close()

  dfs = pd.read_html(html_content)
  df = dfs[0]

  # บันทึกลง CSV
  output_file = "thaiwater_rainfall_live.csv"
  df.to_csv(output_file, index=False, encoding="utf-8-sig")
  print(f"Successfully updated {output_file}")


if __name__ == "__main__":
  scrape_data()
