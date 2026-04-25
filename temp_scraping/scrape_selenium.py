#!/usr/bin/env python3
"""
使用 Selenium 进行浏览器自动化抓取 Wiki 数据
解决 JavaScript 渲染和反爬问题
"""

import json
import time
import os
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# 输出目录
RAW_DATA_DIR = "d:/政治模块整理/temp_scraping/raw_data"

# Victoria 3 Wiki 页面
V3_PAGES = {
    "laws": "https://vic3.paradoxwikis.com/Laws",
    "interest_groups": "https://vic3.paradoxwikis.com/Interest_Groups",
    "government": "https://vic3.paradoxwikis.com/Government",
    "political_parties": "https://vic3.paradoxwikis.com/Political_Parties",
    "ideologies": "https://vic3.paradoxwikis.com/Ideologies",
    "voting_system": "https://vic3.paradoxwikis.com/Voting_system",
    "diplomacy": "https://vic3.paradoxwikis.com/Diplomacy",
    "power_blocs": "https://vic3.paradoxwikis.com/Power_Blocs",
    "population": "https://vic3.paradoxwikis.com/Population",
    "radicals_loyalists": "https://vic3.paradoxwikis.com/Radicals_and_Loyalists",
    "decisions": "https://vic3.paradoxwikis.com/Decisions",
    "journal_entries": "https://vic3.paradoxwikis.com/Journal_entries",
    "events": "https://vic3.paradoxwikis.com/Events",
}

# Victoria 3 国家页面
V3_COUNTRIES = {
    "USA": "https://vic3.paradoxwikis.com/United_States",
    "FRA": "https://vic3.paradoxwikis.com/France",
    "ENG": "https://vic3.paradoxwikis.com/United_Kingdom",
    "GER": "https://vic3.paradoxwikis.com/Germany",
    "JAP": "https://vic3.paradoxwikis.com/Japan",
    "SOV": "https://vic3.paradoxwikis.com/Russia",
    "CHI": "https://vic3.paradoxwikis.com/Qing",
    "ITA": "https://vic3.paradoxwikis.com/Italy",
    "SPA": "https://vic3.paradoxwikis.com/Spain",
    "BRA": "https://vic3.paradoxwikis.com/Brazil",
    "ARG": "https://vic3.paradoxwikis.com/Argentina",
    "AUS": "https://vic3.paradoxwikis.com/Australia",
    "BEL": "https://vic3.paradoxwikis.com/Belgium",
    "DEN": "https://vic3.paradoxwikis.com/Denmark",
    "SIA": "https://vic3.paradoxwikis.com/Siam",
    "PER": "https://vic3.paradoxwikis.com/Persia",
    "AFG": "https://vic3.paradoxwikis.com/Afghanistan",
    "SAU": "https://vic3.paradoxwikis.com/Arabia",
    "SWI": "https://vic3.paradoxwikis.com/Switzerland",
}

# Civ6 Wiki 页面
CIV6_PAGES = {
    "government": "https://civilization.fandom.com/wiki/Government_(Civ6)",
    "policies": "https://civilization.fandom.com/wiki/Policies_(Civ6)",
    "diplomacy": "https://civilization.fandom.com/wiki/Diplomacy_(Civ6)",
    "world_congress": "https://civilization.fandom.com/wiki/World_Congress_(Civ6)",
    "grievances": "https://civilization.fandom.com/wiki/Grievances_(Civ6)",
    "city_states": "https://civilization.fandom.com/wiki/City-States_(Civ6)",
    "alliances": "https://civilization.fandom.com/wiki/Alliances_(Civ6)",
}

# Civ6 国家页面
CIV6_COUNTRIES = {
    "USA": "https://civilization.fandom.com/wiki/American_(Civ6)",
    "FRA": "https://civilization.fandom.com/wiki/French_(Civ6)",
    "ENG": "https://civilization.fandom.com/wiki/English_(Civ6)",
    "GER": "https://civilization.fandom.com/wiki/German_(Civ6)",
    "JAP": "https://civilization.fandom.com/wiki/Japanese_(Civ6)",
    "RUS": "https://civilization.fandom.com/wiki/Russian_(Civ6)",
    "CHI": "https://civilization.fandom.com/wiki/Chinese_(Civ6)",
    "SPA": "https://civilization.fandom.com/wiki/Spanish_(Civ6)",
    "BRA": "https://civilization.fandom.com/wiki/Brazilian_(Civ6)",
    "AUS": "https://civilization.fandom.com/wiki/Australian_(Civ6)",
    "ARA": "https://civilization.fandom.com/wiki/Arabian_(Civ6)",
    "PER": "https://civilization.fandom.com/wiki/Persian_(Civ6)",
    "IND": "https://civilization.fandom.com/wiki/Indian_(Civ6)",
}

def setup_driver():
    """设置 Edge WebDriver"""
    options = Options()
    options.add_argument('--headless')  # 无头模式
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0')

    # 自动下载和管理 EdgeDriver
    service = Service(EdgeChromiumDriverManager().install())
    driver = webdriver.Edge(service=service, options=options)
    return driver

def extract_page_content(driver, url):
    """提取页面内容"""
    try:
        driver.get(url)
        # 等待页面加载
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "mw-parser-output"))
        )
        time.sleep(2)  # 额外等待动态内容

        # 提取主要内容
        content_div = driver.find_element(By.CLASS_NAME, "mw-parser-output")

        # 提取标题
        try:
            title = driver.find_element(By.ID, "firstHeading").text
        except:
            title = ""

        # 提取文本内容
        text_content = content_div.text

        # 提取表格数据
        tables = []
        for table in content_div.find_elements(By.CLASS_NAME, "wikitable"):
            table_data = []
            for row in table.find_elements(By.TAG_NAME, "tr"):
                row_data = []
                for cell in row.find_elements(By.TAG_NAME, "td") + row.find_elements(By.TAG_NAME, "th"):
                    row_data.append(cell.text.strip())
                if row_data:
                    table_data.append(row_data)
            if table_data:
                tables.append(table_data)

        # 提取 infobox
        infoboxes = []
        for infobox in content_div.find_elements(By.CLASS_NAME, "infobox"):
            box_data = []
            for row in infobox.find_elements(By.TAG_NAME, "tr"):
                row_data = []
                for cell in row.find_elements(By.TAG_NAME, "td") + row.find_elements(By.TAG_NAME, "th"):
                    row_data.append(cell.text.strip())
                if row_data:
                    box_data.append(row_data)
            if box_data:
                infoboxes.append(box_data)

        return {
            "url": url,
            "title": title,
            "text": text_content[:200000],  # 限制大小
            "tables": tables,
            "infoboxes": infoboxes,
            "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"提取失败: {url}")
        print(f"错误: {e}")
        return None

def save_data(data, filename):
    """保存数据到 JSON 文件"""
    filepath = os.path.join(RAW_DATA_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已保存: {filepath}")

def main():
    """主函数"""
    print("=" * 60)
    print("Selenium 浏览器自动化数据采集")
    print("=" * 60)

    driver = setup_driver()

    try:
        # ==================== Victoria 3 ====================
        print("\n[阶段 1] Victoria 3 核心政治系统")
        vic3_systems = {"game": "Victoria 3", "systems": {}}

        for name, url in V3_PAGES.items():
            print(f"抓取: {name}")
            content = extract_page_content(driver, url)
            if content:
                vic3_systems["systems"][name] = content
            time.sleep(1)

        save_data(vic3_systems, "vic3_political_systems_selenium.json")

        print("\n[阶段 2] Victoria 3 国家数据")
        for code, url in V3_COUNTRIES.items():
            print(f"抓取: {code}")
            content = extract_page_content(driver, url)
            if content:
                country_data = {
                    "game": "Victoria 3",
                    "country_code": code,
                    "page": content
                }
                save_data(country_data, f"vic3_{code.lower()}_selenium.json")
            time.sleep(1)

        # ==================== Civilization 6 ====================
        print("\n[阶段 3] Civilization 6 政治系统")
        civ6_systems = {"game": "Civilization 6", "systems": {}}

        for name, url in CIV6_PAGES.items():
            print(f"抓取: {name}")
            content = extract_page_content(driver, url)
            if content:
                civ6_systems["systems"][name] = content
            time.sleep(1)

        save_data(civ6_systems, "civ6_political_systems_selenium.json")

        print("\n[阶段 4] Civilization 6 国家数据")
        for code, url in CIV6_COUNTRIES.items():
            print(f"抓取: {code}")
            content = extract_page_content(driver, url)
            if content:
                civ_data = {
                    "game": "Civilization 6",
                    "country_code": code,
                    "page": content
                }
                save_data(civ_data, f"civ6_{code.lower()}_selenium.json")
            time.sleep(1)

        print("\n" + "=" * 60)
        print("数据采集完成!")
        print("=" * 60)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()