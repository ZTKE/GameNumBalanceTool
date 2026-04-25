"""
跨域战斗模拟测试
测试所有军种之间的战斗组合，验证逻辑一致性
"""

import sys
import copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from combat_logic import (
    load_army_csv, load_air_csv, load_navy_csv,
    ForceType, Formation, WeaponStats,
    run_combat_loop, army_ground_to_ground_damage,
    air_to_ground_damage, army_ground_to_air_damage,
    navy_to_navy_damage, army_ground_to_sea_damage, air_to_sea_damage,
    AIR_WIDTH_LIMIT, NAVY_WIDTH_LIMIT, ARMY_WIDTH_LIMIT
)
from battle_simulator import CombatStatistics, deep_copy_formation, copy_weapon


def find_weapon_by_keyword(weapons_db, keywords):
    """根据关键词查找武器"""
    for key, weapon in weapons_db.items():
        match = True
        for kw in keywords:
            if kw not in key:
                match = False
                break
        if match:
            return weapon
    return None


def build_full_width_air(air_db, era="二战"):
    """构建满宽度空军编制"""
    formation = Formation(ForceType.AIR, f"{era}空军大队")

    # 找战斗机
    fighter = find_weapon_by_keyword(air_db, ["战斗机", era])
    if fighter:
        # 计算需要多少架填满宽度
        count = AIR_WIDTH_LIMIT // fighter.width
        formation.weapons.append(copy_weapon(fighter, count))

    formation._calculate_total_width()
    formation._initialize_stats()
    return formation


def build_full_width_navy(navy_db, era="二战", composition="mixed"):
    """构建满宽度海军编制"""
    formation = Formation(ForceType.NAVY, f"{era}海军舰队")

    if composition == "mixed":
        # 混合编制：战列舰+驱逐舰
        bb = find_weapon_by_keyword(navy_db, ["战列舰", era])
        dd = find_weapon_by_keyword(navy_db, ["驱逐舰", era])

        if bb and dd:
            # 1战列舰 + 多驱逐舰
            formation.weapons.append(copy_weapon(bb, 1))
            remaining_width = NAVY_WIDTH_LIMIT - bb.width
            dd_count = remaining_width // dd.width
            formation.weapons.append(copy_weapon(dd, dd_count))
    elif composition == "cruiser":
        # 巡洋舰编制
        cruiser = find_weapon_by_keyword(navy_db, ["巡洋舰", era])
        if cruiser:
            count = NAVY_WIDTH_LIMIT // cruiser.width
            formation.weapons.append(copy_weapon(cruiser, count))

    formation._calculate_total_width()
    formation._initialize_stats()
    return formation


def build_full_width_army(army_db, era="二战"):
    """构建满宽度陆军编制"""
    formation = Formation(ForceType.ARMY, f"{era}步兵团")

    # 找基础步兵武器
    rifle = find_weapon_by_keyword(army_db, ["栓动步枪" if era == "一战" else "步枪", era])
    if not rifle:
        rifle = find_weapon_by_keyword(army_db, ["步枪", era])
    mg = find_weapon_by_keyword(army_db, ["机枪", era])
    artillery = find_weapon_by_keyword(army_db, ["迫击炮", era])

    if rifle:
        # 步兵占大部分宽度
        rifle_count = int(ARMY_WIDTH_LIMIT * 0.8 / rifle.width)
        formation.weapons.append(copy_weapon(rifle, rifle_count))

    if mg:
        # 机枪支援
        remaining = ARMY_WIDTH_LIMIT - formation.total_width
        mg_count = int(remaining * 0.5 / mg.width) if mg.width else 0
        if mg_count > 0:
            formation.weapons.append(copy_weapon(mg, mg_count))

    if artillery:
        remaining = ARMY_WIDTH_LIMIT - formation.total_width
        art_count = int(remaining / artillery.width) if artillery.width else 0
        if art_count > 0:
            formation.weapons.append(copy_weapon(artillery, art_count))

    formation._calculate_total_width()
    formation._initialize_stats()
    return formation


def run_single_battle(attacker, defender, force_type, max_rounds=500):
    """运行单次战斗并返回结果"""
    # 保存初始状态
    attacker_initial = deep_copy_formation(attacker)
    defender_initial = deep_copy_formation(defender)

    # 重置状态
    attacker.current_distance_stage = 6
    defender.current_distance_stage = 6
    defender.is_defending = True

    stats = CombatStatistics()

    try:
        result = run_combat_loop(attacker, defender, force_type, [], max_rounds, stats)
        return {
            'winner': result.get('winner', 'unknown'),
            'rounds': result.get('rounds', 0),
            'attacker_remaining_org': attacker.current_organization,
            'defender_remaining_org': defender.current_organization,
            'attacker_initial_org': attacker_initial.current_organization,
            'defender_initial_org': defender_initial.current_organization,
            'error': None
        }
    except Exception as e:
        return {
            'winner': 'error',
            'rounds': 0,
            'error': str(e)
        }


def simulate_combat_type(attacker_type, defender_type, attacker_force, defender_force,
                          attacker_db, defender_db, num_runs=3):
    """模拟特定战斗组合"""
    results = []

    for i in range(num_runs):
        # 每次重新构建编制（避免状态污染）
        if attacker_type == "air":
            attacker = build_full_width_air(attacker_db, "二战")
        elif attacker_type == "navy":
            attacker = build_full_width_navy(attacker_db, "二战", "mixed")
        elif attacker_type == "army":
            attacker = build_full_width_army(attacker_db, "二战")

        if defender_type == "air":
            defender = build_full_width_air(defender_db, "二战")
        elif defender_type == "navy":
            defender = build_full_width_navy(defender_db, "二战", "mixed")
        elif defender_type == "army":
            defender = build_full_width_army(defender_db, "二战")

        result = run_single_battle(attacker, defender, attacker_force)
        results.append(result)

    return results


# 目标战斗时长（小时）
TARGET_DURATION = {
    'air': (2, 6),      # 空战：2-6小时
    'navy': (6, 12),    # 海战：6-12小时
    'army': (24, 72),   # 陆战：1-3天
}

def analyze_results(combat_name, results, combat_type=None):
    """分析结果并检查逻辑问题"""
    print(f"\n{'='*60}")
    print(f"【{combat_name}】模拟结果")
    print(f"{'='*60}")

    valid_results = [r for r in results if r['error'] is None]
    error_results = [r for r in results if r['error'] is not None]

    if error_results:
        print(f"[!] 错误: {len(error_results)} 次运行出错")
        for r in error_results:
            print(f"   错误信息: {r['error']}")

    if not valid_results:
        print("[X] 无有效结果")
        return []

    # 统计胜率
    attacker_wins = sum(1 for r in valid_results if r['winner'] == 'attacker')
    defender_wins = sum(1 for r in valid_results if r['winner'] == 'defender')

    avg_duration = sum(r['rounds'] for r in valid_results) / len(valid_results)

    print(f"\n运行次数: {len(valid_results)}")
    print(f"胜率: 攻击方 {attacker_wins}/{len(valid_results)}, 防守方 {defender_wins}/{len(valid_results)}")

    # 显示战斗时长（小时）
    print(f"\n战斗时长: {avg_duration:.1f} 小时")
    if combat_type and combat_type in TARGET_DURATION:
        min_h, max_h = TARGET_DURATION[combat_type]
        if avg_duration < min_h:
            print(f"  [!] 过短 - 目标: {min_h}-{max_h}小时")
        elif avg_duration > max_h:
            print(f"  [!] 过长 - 目标: {min_h}-{max_h}小时")
        else:
            print(f"  [OK] 符合目标 ({min_h}-{max_h}小时)")

    # 显示单次时长
    print(f"  单次时长: {[r['rounds'] for r in valid_results]} 小时")

    # 检查逻辑问题
    issues = []

    # 1. 检查时长是否极端
    if avg_duration < 1:
        issues.append(f"时长过短(<1小时)，伤害过高")
    elif avg_duration > 500:
        issues.append(f"时长过长(>500小时)，伤害过低或判定循环")

    # 2. 检查胜率是否极端（同军种战斗）
    if combat_type and attacker_wins == 0 and defender_wins == len(valid_results):
        issues.append("防守方100%胜率，可能攻击方伤害不足")
    elif combat_type and defender_wins == 0 and attacker_wins == len(valid_results):
        issues.append("攻击方100%胜率，可能防守方伤害不足")

    if issues:
        print(f"\n[!] 发现问题:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print(f"\n[OK] 时长合理")

    return issues


def main():
    """主测试流程"""
    base_path = Path(__file__).parent.parent  # 战争模块目录
    print(f"基础路径: {base_path}")

    # 加载CSV数据
    print("\n【加载CSV数据】")
    army_db = load_army_csv(str(base_path / "army.csv"))
    air_db = load_air_csv(str(base_path / "air.csv"))
    navy_db = load_navy_csv(str(base_path / "navy.csv"))

    print(f"陆军武器: {len(army_db)} 种")
    print(f"空军武器: {len(air_db)} 种")
    print(f"海军武器: {len(navy_db)} 种")

    # 列出一些武器用于调试
    if air_db:
        print("\n空军武器示例:")
        for key in list(air_db.keys())[:5]:
            print(f"  - {key}: 宽度={air_db[key].width}, 组织度={air_db[key].organization}")

    if navy_db:
        print("\n海军武器示例:")
        for key in list(navy_db.keys())[:5]:
            print(f"  - {key}: 宽度={navy_db[key].width}, 结构值={navy_db[key].structure}")

    if army_db:
        print("\n陆军武器示例:")
        for key in list(army_db.keys())[:5]:
            print(f"  - {key}: 宽度={army_db[key].width}, 组织度={army_db[key].organization}")

    all_issues = []

    # 1. 空军 vs 空军
    print("\n" + "="*70)
    print("开始空军 vs 空军模拟")
    issues = analyze_results("空军 vs 空军",
        simulate_combat_type("air", "air", ForceType.AIR, ForceType.AIR, air_db, air_db, 3),
        "air")
    if issues:
        all_issues.extend([("空军vs空军", i) for i in issues])

    # 2. 海军 vs 海军
    print("\n" + "="*70)
    print("开始海军 vs 海军模拟")
    issues = analyze_results("海军 vs 海军",
        simulate_combat_type("navy", "navy", ForceType.NAVY, ForceType.NAVY, navy_db, navy_db, 3),
        "navy")
    if issues:
        all_issues.extend([("海军vs海军", i) for i in issues])

    # 3. 陆军 vs 陆军
    print("\n" + "="*70)
    print("开始陆军 vs 陆军模拟")
    issues = analyze_results("陆军 vs 陆军",
        simulate_combat_type("army", "army", ForceType.ARMY, ForceType.ARMY, army_db, army_db, 3),
        "army")
    if issues:
        all_issues.extend([("陆军vs陆军", i) for i in issues])

    # 4. 跨域战斗 - 海军 vs 空军 (海对空)
    print("\n" + "="*70)
    print("开始海军 vs 空军模拟（海对空，逻辑上空军攻击海军）")
    # 注意：这里需要特殊处理，空军攻击海军用air_to_sea_damage
    # 我们用空军作为攻击方，海军作为防守方
    issues = analyze_results("海军 vs 空军（空军攻击海军）",
        simulate_combat_type("air", "navy", ForceType.NAVY, ForceType.AIR, air_db, navy_db, 3))
    if issues:
        all_issues.extend([("海军vs空军", i) for i in issues])

    # 5. 海军 vs 陆军 (海军岸轰陆军)
    print("\n" + "="*70)
    print("开始海军 vs 陆军模拟（海军岸轰）")
    issues = analyze_results("海军 vs 陆军（岸轰）",
        simulate_combat_type("navy", "army", ForceType.ARMY, ForceType.NAVY, navy_db, army_db, 3))
    if issues:
        all_issues.extend([("海军vs陆军", i) for i in issues])

    # 6. 陆军 vs 空军 (地对空)
    print("\n" + "="*70)
    print("开始陆军 vs 空军模拟（地对空）")
    issues = analyze_results("陆军 vs 空军（地对空）",
        simulate_combat_type("army", "air", ForceType.AIR, ForceType.ARMY, army_db, air_db, 3))
    if issues:
        all_issues.extend([("陆军vs空军", i) for i in issues])

    # 7. 陆军 vs 海军 (海岸炮对海军)
    print("\n" + "="*70)
    print("开始陆军 vs 海军模拟（海岸炮）")
    issues = analyze_results("陆军 vs 海军（海岸炮）",
        simulate_combat_type("army", "navy", ForceType.NAVY, ForceType.ARMY, army_db, navy_db, 3))
    if issues:
        all_issues.extend([("陆军vs海军", i) for i in issues])

    # 汇总报告
    print("\n" + "="*70)
    print("【模拟汇总报告】")
    print("="*70)

    if all_issues:
        print(f"\n发现 {len(all_issues)} 个潜在逻辑问题:")
        for combat, issue in all_issues:
            print(f"\n[{combat}]")
            print(f"  {issue}")
    else:
        print("\n[OK] 所有战斗模拟未发现明显逻辑问题")

    print("\n模拟完成！")


if __name__ == "__main__":
    main()