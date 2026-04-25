"""
编制配队战斗模拟
================
使用army_war.csv中的历史编制进行战斗模拟
"""

import sys
import csv
import copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from combat_logic import (
    load_army_csv, ForceType, Formation, WeaponStats,
    run_combat_loop, ARMY_WIDTH_LIMIT
)
from battle_simulator import CombatStatistics, deep_copy_formation


def parse_formations_from_csv(csv_path):
    """从army_war.csv解析编制数据"""
    formations_data = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            era = row['时代']
            period = row['时期']
            function = row['功能']
            weapon_config = row['武器编制']
            total_width = int(row['编制宽度占用合计(建议2200)'])

            # 解析武器配置: "武器名:数量=武器名:数量..."
            weapons = {}
            for item in weapon_config.split('='):
                if ':' in item:
                    weapon_name, quantity = item.split(':')
                    weapons[weapon_name.strip()] = int(quantity.strip())

            formations_data.append({
                'era': era,
                'period': period,
                'function': function,
                'weapons': weapons,
                'total_width': total_width
            })

    return formations_data


def copy_weapon(weapon, quantity):
    """复制武器并设置数量"""
    new_weapon = copy.deepcopy(weapon)
    new_weapon.quantity = quantity
    return new_weapon


def build_war_formation(army_db, formation_data, era):
    """根据编制数据构建Formation对象"""
    formation = Formation(ForceType.ARMY, f"{formation_data['era']}-{formation_data['function']}")

    for weapon_name, quantity in formation_data['weapons'].items():
        # 在数据库中查找对应时代的武器
        weapon = None
        for key, w in army_db.items():
            # 匹配武器名称和时代
            if weapon_name in w.weapon_type and w.era == era:
                weapon = w
                break
            # 也尝试匹配key
            if weapon_name in key and era in key:
                weapon = w
                break

        if weapon:
            formation.weapons.append(copy_weapon(weapon, quantity))
        else:
            print(f"  [警告] 未找到武器: {weapon_name} ({era})")

    formation._calculate_total_width()
    formation._initialize_stats()
    return formation


def run_battle_simulation(attacker, defender, battle_name, has_trench=False):
    """运行单次战斗模拟"""
    attacker_copy = deep_copy_formation(attacker)
    defender_copy = deep_copy_formation(defender)

    # 设置初始状态
    attacker_copy.current_distance_stage = 6
    defender_copy.current_distance_stage = 6
    defender_copy.is_defending = True

    if has_trench:
        # 计算堑壕加成
        trench_bonus = sum(w.trench_defense * w.width * w.quantity for w in defender_copy.weapons)
        for w in defender_copy.weapons:
            if w.defense:
                w.defense = [v + trench_bonus / 2200 for v in w.defense]

    stats = CombatStatistics()

    try:
        result = run_combat_loop(attacker_copy, defender_copy, ForceType.ARMY, [], 500, stats)
        return {
            'winner': result.get('winner', 'unknown'),
            'rounds': result.get('rounds', 0),
            'duration_hours': result.get('rounds', 0),
            'attacker_org_remaining': attacker_copy.current_organization,
            'attacker_org_initial': attacker.current_organization,
            'defender_org_remaining': defender_copy.current_organization,
            'defender_org_initial': defender.current_organization,
            'attacker_width': attacker.total_width,
            'defender_width': defender.total_width
        }
    except Exception as e:
        return {'error': str(e)}


def run_war_simulation():
    """运行编制战斗模拟"""
    print("=" * 70)
    print("编制配队战斗模拟")
    print("=" * 70)

    base_path = Path(__file__).parent.parent

    # 加载武器数据库
    army_db = load_army_csv(str(base_path / "army_new.csv"))

    # 解析编制数据
    formations_data = parse_formations_from_csv(str(base_path / "army_war.csv"))

    print(f"\n已加载 {len(formations_data)} 种编制")

    # 按时代分组
    eras = ['一战', '二战', '冷战', '现代']

    # ==========================================================================
    # 模拟1: 同时代步兵团 vs 装甲团（常规战）
    # ==========================================================================
    print("\n" + "=" * 70)
    print("【模拟1】步兵团 vs 装甲团（常规战）")
    print("=" * 70)

    for era in eras:
        # 找到步兵团和装甲团
        infantry_data = None
        armor_data = None

        for f in formations_data:
            if f['era'] == era:
                if '步兵团' in f['function']:
                    infantry_data = f
                elif '装甲团' in f['function']:
                    armor_data = f

        if infantry_data and armor_data:
            infantry = build_war_formation(army_db, infantry_data, era)
            armor = build_war_formation(army_db, armor_data, era)

            print(f"\n{era}时代:")
            print(f"  步兵团: 宽度={infantry.total_width}, 组织度={infantry.current_organization:.0f}")
            print(f"  装甲团: 宽度={armor.total_width}, 组织度={armor.current_organization:.0f}")

            # 运行3次战斗
            results = []
            for i in range(3):
                result = run_battle_simulation(armor, infantry, f"{era}装甲vs步兵")
                if 'error' not in result:
                    results.append(result)
                    print(f"  第{i+1}次: {result['duration_hours']}h, "
                          f"装甲团剩余组织度={result['attacker_org_remaining']:.0f}, "
                          f"步兵团剩余组织度={result['defender_org_remaining']:.0f}")
                else:
                    print(f"  第{i+1}次: 错误 - {result['error']}")

            if results:
                avg_duration = sum(r['duration_hours'] for r in results) / len(results)
                print(f"  平均战斗时长: {avg_duration:.1f}h")

    # ==========================================================================
    # 模拟2: 同时代步兵团 vs 装甲团（堑壕战）
    # ==========================================================================
    print("\n" + "=" * 70)
    print("【模拟2】步兵团 vs 装甲团（堑壕战）")
    print("=" * 70)

    for era in eras:
        infantry_data = None
        armor_data = None

        for f in formations_data:
            if f['era'] == era:
                if '步兵团' in f['function']:
                    infantry_data = f
                elif '装甲团' in f['function']:
                    armor_data = f

        if infantry_data and armor_data:
            infantry = build_war_formation(army_db, infantry_data, era)
            armor = build_war_formation(army_db, armor_data, era)

            print(f"\n{era}时代（有堑壕加成）:")

            results = []
            for i in range(3):
                result = run_battle_simulation(armor, infantry, f"{era}装甲vs步兵堑壕", has_trench=True)
                if 'error' not in result:
                    results.append(result)
                    print(f"  第{i+1}次: {result['duration_hours']}h, "
                          f"装甲团剩余={result['attacker_org_remaining']:.0f}, "
                          f"步兵团剩余={result['defender_org_remaining']:.0f}")
                else:
                    print(f"  第{i+1}次: 错误 - {result['error']}")

            if results:
                avg_duration = sum(r['duration_hours'] for r in results) / len(results)
                print(f"  平均战斗时长: {avg_duration:.1f}h")

    # ==========================================================================
    # 模拟3: 同时代装甲团 vs 装甲团
    # ==========================================================================
    print("\n" + "=" * 70)
    print("【模拟3】装甲团 vs 装甲团（装甲对决）")
    print("=" * 70)

    for era in eras:
        armor_data = None

        for f in formations_data:
            if f['era'] == era and '装甲团' in f['function']:
                armor_data = f
                break

        if armor_data:
            armor1 = build_war_formation(army_db, armor_data, era)
            armor2 = build_war_formation(army_db, armor_data, era)

            print(f"\n{era}时代装甲对决:")
            print(f"  双方装甲团: 宽度={armor1.total_width}, 组织度={armor1.current_organization:.0f}")

            results = []
            for i in range(3):
                result = run_battle_simulation(armor1, armor2, f"{era}装甲vs装甲")
                if 'error' not in result:
                    results.append(result)
                    print(f"  第{i+1}次: {result['duration_hours']}h, "
                          f"进攻方剩余={result['attacker_org_remaining']:.0f}, "
                          f"防守方剩余={result['defender_org_remaining']:.0f}")
                else:
                    print(f"  第{i+1}次: 错误 - {result['error']}")

            if results:
                avg_duration = sum(r['duration_hours'] for r in results) / len(results)
                print(f"  平均战斗时长: {avg_duration:.1f}h")

    # ==========================================================================
    # 汇总表格
    # ==========================================================================
    print("\n" + "=" * 70)
    print("战斗模拟汇总")
    print("=" * 70)
    print("\n编制来源: army_war.csv（德国历史编制）")
    print("武器数据: army_new.csv（新生成数值）")
    print("\n目标战斗时长:")
    print("- 常规战: 6-12小时")
    print("- 堑壕战: 12-24小时")


if __name__ == "__main__":
    run_war_simulation()