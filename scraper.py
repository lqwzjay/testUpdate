import csv
import os
import re
import sys
from playwright.sync_api import sync_playwright

URL = "https://xinxipilu.chinawealth.com.cn/queryMenu/prodType/prodTypeDetail?prodRegCode=Z7001626000135"
OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "nav.csv")

def parse_nav_rows(rows):
    """从表格行中提取 (日期, 份额净值)"""
    result = []
    for cells in rows:
        if len(cells) < 2:
            continue
        # 找日期格式
        date_match = re.match(r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})", cells[0].strip())
        if not date_match:
            continue
        date = date_match.group(1).replace("-", "/")
        
        # 找净值（通常是有 4 位小数的数字，如 1.0188）
        nav = None
        for cell in cells[1:]:
            cleaned = cell.strip().replace(",", "")
            if re.match(r"^\d+\.\d{4}$", cleaned):  # 严格要求是4位小数
                nav = cleaned
                break
                
        if nav:
            result.append((date, nav))
    return result

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        # 伪装成真实的 Windows 浏览器
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = context.new_page()
        
        print(f"正在打开页面: {URL}")
        page.goto(URL, timeout=60000, wait_until="networkidle")
        page.wait_for_timeout(5000) # 留5秒给页面渲染

        # 获取页面上所有的表格
        tables = page.query_selector_all("table")
        print(f"页面上共找到 {len(tables)} 个表格，开始逐个排查...")

        nav_data = []
        
        # 遍历所有表格，哪个能解析出净值，就用哪个
        for i, table in enumerate(tables):
            rows = []
            for tr in table.query_selector_all("tr"):
                cells = [td.inner_text().strip() for td in tr.query_selector_all("td")]
                if cells:
                    rows.append(cells)
            
            # 尝试从这个表格里解析净值
            parsed = parse_nav_rows(rows)
            if parsed:
                print(f"✅ 在第 {i+1} 个表格中成功提取到 {len(parsed)} 条净值数据！")
                nav_data = parsed
                break # 找到了就停止寻找

        if not nav_data:
            print("❌ 翻遍了页面所有的表格，都没有找到符合格式的净值数据。")
            print("请确认该产品当前是否有净值展示。")
            browser.close()
            sys.exit(1)

        # 按日期升序排列，去重
        nav_data = sorted(set(nav_data), key=lambda x: x[0])

        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "nav"])
            writer.writerows(nav_data)

        print(f"✅ 已保存 {len(nav_data)} 条净值数据到 {OUTPUT_FILE}")
        print(f"   最新一条: {nav_data[-1]}")
        browser.close()

if __name__ == "__main__":
    main()
