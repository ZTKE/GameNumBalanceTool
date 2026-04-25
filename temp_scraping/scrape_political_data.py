#!/usr/bin/env python3
"""
政治模块数据采集脚本
从 Paradox Wiki 和 Civilization Wiki 抓取政治系统相关数据
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re
from urllib.parse import urljoin, quote

# 输出目录
RAW_DATA_DIR = "d:/政治模块整理/temp_scraping/raw_data"

# User-Agent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# ==================== Victoria 3 Wiki 配置 ====================
V3_BASE = "https://vic3.paradoxwikis.com"

# Victoria 3 国家列表（主要国家）
V3_COUNTRIES = {
    "USA": "United_States",
    "FRA": "France",
    "ENG": "United_Kingdom",
    "GER": "Germany",
    "JAP": "Japan",
    "SOV": "Russia",  # 俄罗斯/苏联
    "CHI": "Qing",  # 大清
    "ITA": "Italy",
    "SPA": "Spain",
    "BRA": "Brazil",
    "ARG": "Argentina",
    "AUS": "Australia",
    "BEL": "Belgium",
    "DEN": "Denmark",
    "SIA": "Siam",  # 泰国
    "PER": "Persia",  # 伊朗
    "AFG": "Afghanistan",
    "SAU": "Arabia",  # 沙特阿拉伯
    "SWI": "Switzerland",
}

# Victoria 3 政治相关页面
V3_POLITICAL_PAGES = [
    # 权力结构
    "/Government",
    "/Laws",
    "/Voting_system",
    "/Political_Parties",
    "/Interest_Groups",
    "/Ideologies",

    # 社会力量
    "/Population",
    "/Pop_Needs",
    "/Radicals_and_Loyalists",
    "/Social_Mobility",

    # 宏观决策
    "/Decisions",
    "/Journal_entries",
    "/Events",

    # 外交
    "/Diplomacy",
    "/Diplomatic_Plays",
    "/Power_Blocs",
    "/Subjects",

    # 治理资源
    "/Authority",
    "/Influence",
    "/Prestige",
    "/Infamy",
]

# ==================== Civilization Wiki 配置 ====================
CIV6_BASE = "https://civilization.fandom.com"
CIV7_BASE = "https://civilization.fandom.com"

# Civilization 6 国家
CIV6_COUNTRIES = {
    "USA": "American_(Civ6)",
    "FRA": "French_(Civ6)",
    "ENG": "English_(Civ6)",
    "GER": "German_(Civ6)",
    "JAP": "Japanese_(Civ6)",
    "RUS": "Russian_(Civ6)",
    "CHI": "Chinese_(Civ6)",
    "ITA": "Roman_(Civ6)",  # 罗马代表意大利文明
    "SPA": "Spanish_(Civ6)",
    "BRA": "Brazilian_(Civ6)",
    "ARG": "Argentinian_(Civ6)" if False else None,  # 可能不存在
    "AUS": "Australian_(Civ6)",
    "ARA": "Arabian_(Civ6)",
    "PER": "Persian_(Civ6)",
    "IND": "Indian_(Civ6)",
    "GRE": "Greek_(Civ6)",
    "EGY": "Egyptian_(Civ6)",
}

# Civilization 6 政治相关页面
CIV6_POLITICAL_PAGES = [
    "/wiki/Government_(Civ6)",
    "/wiki/Policies_(Civ6)",
    "/wiki/Diplomacy_(Civ6)",
    "/wiki/World_Congress_(Civ6)",
    "/wiki/Grievances_(Civ6)",
    "/wiki/City-States_(Civ6)",
    "/wiki/Alliances_(Civ6)",
]

# Civilization 7 国家（基于现有信息）
CIV7_COUNTRIES = {
    "USA": None,  # 待确认
    "FRA": None,
    "ENG": None,
    "GER": None,
    "JAP": None,
    "CHI": None,
    "RUS": None,
}

def safe_request(url, max_retries=3):
    """安全的HTTP请求"""
    for i in range(max_retries):
        try:
            time.sleep(1)  # 礼貌性延迟
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response
        except Exception as e:
            print(f"请求失败 (尝试 {i+1}/{max_retries}): {url}")
            print(f"错误: {e}")
            if i < max_retries - 1:
                time.sleep(2)
    return None

def extract_text_content(soup):
    """提取页面的文本内容"""
    # 移除脚本和样式
    for script in soup(["script", "style", "nav", "footer"]):
        script.decompose()

    # 获取主要内容区域
    content = soup.find("div", class_="mw-parser-output")
    if not content:
        content = soup.find("div", class_="page-content")
    if not content:
        content = soup.body

    if not content:
        return ""

    # 提取文本
    text = content.get_text(separator='\n', strip=True)
    # 清理多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

def extract_tables(soup):
    """提取页面中的表格数据"""
    tables = []
    for table in soup.find_all("table", class_=["wikitable", "infobox"]):
        table_data = []
        for row in table.find_all("tr"):
            row_data = []
            for cell in row.find_all(["th", "td"]):
                row_data.append(cell.get_text(strip=True))
            if row_data:
                table_data.append(row_data)
        if table_data:
            tables.append(table_data)
    return tables

def extract_links(soup, base_url):
    """提取页面中的相关链接"""
    links = []
    content = soup.find("div", class_="mw-parser-output")
    if content:
        for a in content.find_all("a", href=True):
            href = a['href']
            if href.startswith('/') and not href.startswith('/File:'):
                full_url = urljoin(base_url, href)
                link_text = a.get_text(strip=True)
                if link_text:
                    links.append({"text": link_text, "url": full_url})
    return links

def scrape_vic3_country(country_code, country_name):
    """抓取Victoria 3单个国家数据"""
    print(f"正在抓取 Victoria 3: {country_name} ({country_code})...")

    country_data = {
        "game": "Victoria 3",
        "country_code": country_code,
        "country_name": country_name,
        "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pages": {}
    }

    # 尝试直接访问国家页面
    country_url = f"{V3_BASE}/{country_name}"
    response = safe_request(country_url)
    if response:
        soup = BeautifulSoup(response.text, 'html.parser')
        country_data["pages"]["country_main"] = {
            "url": country_url,
            "text": extract_text_content(soup),
            "tables": extract_tables(soup)
        }

    # 抓取政治相关页面
    for page in V3_POLITICAL_PAGES[:10]:  # 先抓取前10个核心页面
        page_url = f"{V3_BASE}{page}"
        response = safe_request(page_url)
        if response:
            soup = BeautifulSoup(response.text, 'html.parser')
            page_name = page.strip('/').replace('/', '_')
            country_data["pages"][page_name] = {
                "url": page_url,
                "text": extract_text_content(soup)[:50000],  # 限制大小
                "tables": extract_tables(soup)
            }
            print(f"  - 已抓取: {page}")

    return country_data

def scrape_vic3_core_systems():
    """抓取Victoria 3核心政治系统"""
    print("=" * 50)
    print("抓取 Victoria 3 核心政治系统...")
    print("=" * 50)

    systems_data = {
        "game": "Victoria 3",
        "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "systems": {}
    }

    # 核心政治机制页面
    core_pages = [
        "/Laws",
        "/Interest_Groups",
        "/Government",
        "/Political_Parties",
        "/Ideologies",
        "/Voting_system",
        "/Decisions",
        "/Journal_entries",
        "/Events",
        "/Diplomacy",
        "/Power_Blocs",
        "/Population",
        "/Radicals_and_Loyalists",
    ]

    for page in core_pages:
        page_url = f"{V3_BASE}{page}"
        response = safe_request(page_url)
        if response:
            soup = BeautifulSoup(response.text, 'html.parser')
            page_name = page.strip('/').replace('/', '_')
            systems_data["systems"][page_name] = {
                "url": page_url,
                "text": extract_text_content(soup)[:100000],
                "tables": extract_tables(soup),
                "links": extract_links(soup, V3_BASE)[:100]  # 限制链接数量
            }
            print(f"已抓取核心系统: {page}")

    return systems_data

def scrape_civ6_country(country_code, civ_name):
    """抓取Civilization 6单个国家数据"""
    if not civ_name:
        return None

    print(f"正在抓取 Civilization 6: {civ_name}...")

    country_data = {
        "game": "Civilization 6",
        "country_code": country_code,
        "civ_name": civ_name,
        "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pages": {}
    }

    # 访问文明主页面
    civ_url = f"{CIV6_BASE}/wiki/{civ_name}"
    response = safe_request(civ_url)
    if response:
        soup = BeautifulSoup(response.text, 'html.parser')
        country_data["pages"]["civ_main"] = {
            "url": civ_url,
            "text": extract_text_content(soup)[:50000],
            "tables": extract_tables(soup)
        }

    # 尝试获取领袖页面
    leader_links = []
    content = soup.find("div", class_="mw-parser-output") if response else None
    if content:
        for a in content.find_all("a", href=True):
            href = a['href']
            if 'leader' in href.lower() or 'Leader' in a.get_text():
                leader_links.append(urljoin(CIV6_BASE, href))

    for i, leader_url in enumerate(leader_links[:3]):  # 最多抓3个领袖
        response = safe_request(leader_url)
        if response:
            soup = BeautifulSoup(response.text, 'html.parser')
            country_data["pages"][f"leader_{i}"] = {
                "url": leader_url,
                "text": extract_text_content(soup)[:30000],
                "tables": extract_tables(soup)
            }

    return country_data

def scrape_civ6_political_systems():
    """抓取Civilization 6政治系统"""
    print("=" * 50)
    print("抓取 Civilization 6 政治系统...")
    print("=" * 50)

    systems_data = {
        "game": "Civilization 6",
        "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "systems": {}
    }

    for page in CIV6_POLITICAL_PAGES:
        page_url = f"{CIV6_BASE}{page}"
        response = safe_request(page_url)
        if response:
            soup = BeautifulSoup(response.text, 'html.parser')
            page_name = page.split('/')[-1].replace('(', '').replace(')', '')
            systems_data["systems"][page_name] = {
                "url": page_url,
                "text": extract_text_content(soup)[:100000],
                "tables": extract_tables(soup)
            }
            print(f"已抓取: {page}")

    return systems_data

def scrape_civ7_available():
    """抓取Civilization 7可用数据"""
    print("=" * 50)
    print("抓取 Civilization 7 可用数据...")
    print("=" * 50)

    civ7_data = {
        "game": "Civilization 7",
        "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pages": {}
    }

    # Civ7 可用的政治页面
    civ7_pages = [
        "/wiki/Civilization_VII",
        "/wiki/Government_(Civ7)",
        "/wiki/Diplomacy_(Civ7)",
        "/wiki/Leader_(Civ7)",
    ]

    for page in civ7_pages:
        page_url = f"{CIV7_BASE}{page}"
        response = safe_request(page_url)
        if response:
            soup = BeautifulSoup(response.text, 'html.parser')
            page_name = page.split('/')[-1].replace('(', '').replace(')', '')
            civ7_data["pages"][page_name] = {
                "url": page_url,
                "text": extract_text_content(soup)[:50000],
                "tables": extract_tables(soup)
            }
            print(f"已抓取 Civ7: {page}")

    return civ7_data

def save_data(data, filename):
    """保存数据到JSON文件"""
    filepath = os.path.join(RAW_DATA_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已保存: {filepath}")

def main():
    """主函数"""
    print("=" * 60)
    print("政治模块数据采集脚本启动")
    print(f"输出目录: {RAW_DATA_DIR}")
    print("=" * 60)

    # 1. 抓取 Victoria 3 核心系统
    print("\n[阶段 1] Victoria 3 核心政治系统")
    vic3_systems = scrape_vic3_core_systems()
    save_data(vic3_systems, "vic3_political_systems.json")

    # 2. 抓取 Victoria 3 关键国家
    print("\n[阶段 2] Victoria 3 国家数据")
    key_countries = ["USA", "FRA", "ENG", "GER", "JAP", "SOV", "CHI"]
    for code in key_countries:
        if code in V3_COUNTRIES:
            country_data = scrape_vic3_country(code, V3_COUNTRIES[code])
            save_data(country_data, f"vic3_{code.lower()}.json")

    # 3. 抓取 Civilization 6 政治系统
    print("\n[阶段 3] Civilization 6 政治系统")
    civ6_systems = scrape_civ6_political_systems()
    save_data(civ6_systems, "civ6_political_systems.json")

    # 4. 抓取 Civilization 6 关键国家
    print("\n[阶段 4] Civilization 6 国家数据")
    key_civs = ["USA", "FRA", "ENG", "GER", "JAP", "RUS", "CHI"]
    for code in key_civs:
        if code in CIV6_COUNTRIES and CIV6_COUNTRIES[code]:
            civ_data = scrape_civ6_country(code, CIV6_COUNTRIES[code])
            if civ_data:
                save_data(civ_data, f"civ6_{code.lower()}.json")

    # 5. 抓取 Civilization 7 可用数据
    print("\n[阶段 5] Civilization 7 数据")
    civ7_data = scrape_civ7_available()
    save_data(civ7_data, "civ7_available.json")

    print("\n" + "=" * 60)
    print("数据采集完成!")
    print(f"原始数据保存在: {RAW_DATA_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()