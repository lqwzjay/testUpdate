import csv
import os
import re
import sys
from playwright.sync_api import sync_playwright

URL = "https://xinxipilu.chinawealth.com.cn/queryMenu/prodType/prodTypeDetail?prodRegCode=Z7001626000135"
OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "nav.csv")

# 自动尝试的表格选择器，按优先级排列
CANDIDATE_SELECTORS = [
    "table",                    # 最宽泛：页面上所有 table
    ".table",                   # 常见 class
    ".el-table",                # Element UI 风格
    ".ant-table",               # Ant Design 风格
    "[class*='table']",         # class 名里含 table 的任意元素
]

def looks_like_nav_table(rows):
    """判断抓到的行是否像净值表：至少有一行包含日期格式（如 2026/10/23）"""
    for cells in rows:
        for cell in cells:
            if re.match(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}", cell.strip()):
                return True
    return False

def extract_table_rows(page, selector):
    """在页面中查找匹配 selector 的表格，返回行数据列表"""
    tables = page.query_selector_all(selector)
    for table in tables:
        rows = []
        for tr in table.query_selector_all("tr"):
            cells = [td.inner_text().strip() for td in tr.query_selector_all("td")]
            if cells:
                rows.append(cells)
        if rows and looks_like_nav_table(rows):
            return rows
    return []

def parse_nav_rows(rows):
    """从表格行中提取 (日期, 份额净值)"""
    result = []
    for cells in rows:
        if len(cells) < 2:
            continue
        date_match = re.match(r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})", cells[0].strip())
        if not date_match:
            continue
        date = date_match.group(1).replace("-", "/")
        # 份额净值通常在第2列；如果第2列不是数字，尝试往后找第一个像净值的小数
        nav = None
        for cell in cells[1:]:
            cleaned = cell.strip().replace(",", "")
            if re.match(r"^\d+\.\d+$", cleaned):
                nav = cleaned
                break
        if nav:
            result.append((date, nav))
    return result

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as p:
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

        # 等待页面渲染，给动态加载的表格留时间
        page.wait_for_timeout(5000)

        rows = []
        used_selector = None
        for sel in CANDIDATE_SELECTORS:
            print(f"尝试选择器: {sel}")
            rows = extract_table_rows(page, sel)
            if rows:
                used_selector = sel
                print(f"✅ 使用选择器 '{sel}' 找到表格，共 {len(rows)} 行")
                break

        if not rows:
            print("❌ 未找到包含净值数据的表格。")
            print("   请用浏览器 F12 检查‘产品净值’表格的 HTML 元素，")
            print("   把它的 class 或 id 加到 CANDIDATE_SELECTORS 列表最前面。")
            browser.close()
            sys.exit(1)

        nav_data = parse_nav_rows(rows)
        if not nav_data:
            print("❌ 表格找到了，但没有解析出日期和净值。可能是列顺序和预期不同。")
            print("   表格前几行原始内容：")
            for r in rows[:5]:
                print("   ", r)
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
