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

    # 1. รอจนกว่าตารางจะมีแถวข้อมูลจริงปรากฏขึ้นอย่างน้อย 1 แถว (ไม่นับ Header)
    page.wait_for_selector("table tr:nth-child(2)", timeout=15000)
    page.wait_for_timeout(2000)

    html_content = page.content()
    browser.close()

  dfs = pd.read_html(io.StringIO(html_content))
  if not dfs:
    raise RuntimeError("ไม่พบตารางข้อมูลใน HTML ของ thaiwater.net")

  df = dfs[0]

  # 2. ตรวจสอบชื่อคอลัมน์สำคัญ ป้องกันเว็บเปลี่ยนโครงสร้างตาราง
  expected_cols = {"ชื่อสถานี", "ที่ตั้ง"}
  if not expected_cols.issubset(df.columns):
    raise RuntimeError(
        f"โครงสร้างตารางเปลี่ยนไปจากเดิม คอลัมน์ที่พบ: {list(df.columns)}"
    )

  df = df.iloc[:, :4]

  output_file = "thaiwater_rainfall_live.csv"
  df.to_csv(output_file, index=False, encoding="utf-8-sig")
  print(f"Successfully updated {output_file}")


if __name__ == "__main__":
  scrape_data()
