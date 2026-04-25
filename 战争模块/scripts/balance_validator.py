"""
全维度战斗时长验证器
====================
用于验证各军种战斗时长是否符合目标区间

目标时长：
- 陆军常规战：6-12小时
- 陆军堑壕战：12-24小时
- 海军舰队决战：6-8小时
- 空战：1-2小时
- 地对空：3-6小时重创24宽度空军
- 空对地/海：1小时显著伤害（6%+组织度）
"""

import sys
import copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from combat_logic import (
    load_army_csv, load_air_csv, load_navy_csv,
    ForceType, Formation, WeaponStats,
    run_combat_loop, army_ground_to_ground_damage,
    army_ground_to_air_damage, air_to_ground_damage,
    navy_to_navy_damage, execute_air_combat_round,
    ARMY_WIDTH_LIMIT, AIR_WIDTH_LIMIT, NAVY_WIDTH_LIMIT
)
from battle_simulator import CombatStatistics, deep_copy_formation, copy_weapon


# =============================================================================
# 目标时长定义
# =============================================================================

TARGET_DURATION = {
    'army_normal': (6, 12),      # 陆军常规战
    'army_trench': (12, 24),     # 陆军堑壕战
    'navy_battle': (6, 8),       # 海军舰队决战
    'air_combat': (1, 2),        # 空战高爆发
    'ground_to_air': (3, 6),     # 地对空重创空军
}


# =============================================================================
# 编制构建工具
# =============================================================================

def find_weapon_by_keyword(weapons_db, keywords, era="二战"):
    """根据关键词和时代查找武器"""
    for key, weapon in weapons_db.items():
        if era in key or weapon.era == era:
            match = True
            for kw in keywords:
                if kw not in key and kw not in weapon.weapon_type:
                    match = False
                    break
            if match:
                return weapon
    return None


def build_formation(weapons_db, weapon_specs, force_type, name, era="二战"):
    """从武器规格列表构建编制"""
    formation = Formation(force_type, name)

    for weapon_name, quantity in weapon_specs:
        weapon = find_weapon_by_keyword(weapons_db, [weapon_name], era)
        if weapon:
            formation.weapons.append(copy_weapon(weapon, quantity))

    formation._calculate_total_width()
    formation._initialize_stats()
    return formation


def build_army_formation(army_db, era, formation_type):
    """构建陆军编制 - 支持多时代"""
    if formation_type == "armor":
        # 装甲团配置（按时代）
        if era == "一战":
            specs = [
                ('轻型坦克', 150),  # 一战以轻型坦克为主
                ('重型坦克', 30),   # 一战重型坦克支援
            ]
        elif era == "二战":
            specs = [
                ('中型坦克', 74),
                ('反坦克歼击车', 10),
                ('自行突击炮', 10),
                ('轮式装甲车', 10),
            ]
        elif era == "冷战":
            specs = [
                ('中型坦克', 80),   # 冷战仍有中型坦克
                ('重型坦克', 20),
            ]
        else:  # 现代
            specs = [
                ('主战坦克', 60),
                ('履带式步兵战车', 50),
            ]
    else:
        # 步兵团配置（按时代）
        if era == "一战":
            specs = [
                ('栓动步枪', 1800),
                ('机枪', 100),
                ('迫击炮', 20),
            ]
        elif era == "二战":
            specs = [
                ('栓动步枪', 600),
                ('突击步枪', 1028),
                ('冲锋枪', 121),
                ('机枪', 140),
                ('迫击炮', 24),
                ('反坦克炮', 15),
            ]
        elif era == "冷战":
            specs = [
                ('突击步枪', 1500),
                ('机枪', 150),
                ('迫击炮', 30),
                ('反坦克炮', 20),
            ]
        else:  # 现代
            specs = [
                ('突击步枪', 1200),
                ('机枪', 100),
                ('迫击炮', 20),
                ('反坦克导弹', 30),
            ]

    return build_formation(army_db, specs, ForceType.ARMY, f"{era}{formation_type}团", era)


def build_air_formation(air_db, era, formation_type):
    """构建空军编制 - 支持多时代"""
    if era == "一战":
        # 一战没有空军，返回二战的作为替代
        era = "二战"

    if formation_type == "fighter":
        specs = [('战斗机', 12)]
    elif formation_type == "bomber":
        specs = [('轰炸机', 8)]
    else:
        specs = [('战斗机', 10), ('轰炸机', 2)]

    return build_formation(air_db, specs, ForceType.AIR, f"{era}{formation_type}队", era)


def build_navy_formation(navy_db, era, formation_type):
    """构建海军编制"""
    if formation_type == "battle":
        # 战列线
        specs = [('战列舰', 1), ('巡洋舰', 2), ('驱逐舰', 4)]
    elif formation_type == "carrier":
        specs = [('航空母舰', 1), ('巡洋舰', 1), ('驱逐舰', 3)]
    elif formation_type == "submarine":
        specs = [('潜艇', 5)]
    else:
        specs = [('驱逐舰', 5)]

    return build_formation(navy_db, specs, ForceType.NAVY, f"{era}{formation_type}舰队", era)


# =============================================================================
# 战斗模拟与验证
# =============================================================================

def run_battle_test(attacker, defender, force_type, max_rounds=500, has_trench=False):
    """运行战斗测试并返回时长"""
    attacker_copy = deep_copy_formation(attacker)
    defender_copy = deep_copy_formation(defender)

    attacker_copy.current_distance_stage = 6
    defender_copy.current_distance_stage = 6
    defender_copy.is_defending = True

    if has_trench:
        # 计算堑壕加成
        trench_bonus = sum(w.trench_defense * w.width * w.quantity for w in defender_copy.weapons)
        # 堑壕加成需要通过修改防御值实现
        for w in defender_copy.weapons:
            if w.defense:
                w.defense = [v + trench_bonus / 2200 for v in w.defense]

    stats = CombatStatistics()

    try:
        result = run_combat_loop(attacker_copy, defender_copy, force_type, [], max_rounds, stats)
        return {
            'winner': result.get('winner', 'unknown'),
            'rounds': result.get('rounds', 0),
            'duration_hours': result.get('rounds', 0),
            'attacker_remaining_org': attacker_copy.current_organization,
            'defender_remaining_org': defender_copy.current_organization,
            'error': None
        }
    except Exception as e:
        return {
            'winner': 'error',
            'rounds': 0,
            'duration_hours': 0,
            'error': str(e)
        }


def validate_duration(combat_name, result, target_range):
    """验证战斗时长是否符合目标"""
    min_h, max_h = target_range
    duration = result['duration_hours']

    passed = min_h <= duration <= max_h

    print(f"\n【{combat_name}】")
    print(f"  战斗时长: {duration} 小时")
    print(f"  目标区间: {min_h}-{max_h} 小时")
    print(f"  验证结果: {'[OK] 通过' if passed else '[X] 未通过'}")

    if not passed:
        if duration < min_h:
            print(f"  原因: 战斗过快，需降低攻击值或提高防御值")
            ratio = min_h / max(duration, 0.5)
            print(f"  建议: 将攻击值降低到 {1/ratio:.2f}x")
        else:
            print(f"  原因: 战斗过慢，需提高攻击值或降低防御值")
            ratio = duration / max_h
            print(f"  建议: 将攻击值提高 {ratio:.2f}x")

    return passed


# =============================================================================
# 全维度验证函数
# =============================================================================

def validate_army_battles(army_db):
    """验证陆军战斗时长"""
    print("=" * 70)
    print("陆军战斗时长验证")
    print("=" * 70)

    results = []

    # 二战装甲团 vs 步兵团（常规战）
    print("\n[测试1] 二战装甲团 vs 步兵团（常规战）")
    armor = build_army_formation(army_db, "二战", "armor")
    infantry = build_army_formation(army_db, "二战", "infantry")

    print(f"  装甲团宽度: {armor.total_width}, 组织度: {armor.current_organization:.0f}")
    print(f"  步兵团宽度: {infantry.total_width}, 组织度: {infantry.current_organization:.0f}")

    result = run_battle_test(armor, infantry, ForceType.ARMY, has_trench=False)
    passed = validate_duration("陆军常规战", result, TARGET_DURATION['army_normal'])
    results.append(('army_normal', passed, result))

    # 二战装甲团 vs 步兵团（堑壕战）
    print("\n[测试2] 二战装甲团 vs 步兵团（堑壕战）")
    armor2 = build_army_formation(army_db, "二战", "armor")
    infantry2 = build_army_formation(army_db, "二战", "infantry")

    result = run_battle_test(armor2, infantry2, ForceType.ARMY, has_trench=True)
    passed = validate_duration("陆军堑壕战", result, TARGET_DURATION['army_trench'])
    results.append(('army_trench', passed, result))

    return results


def validate_air_battles(air_db):
    """验证空战时长"""
    print("=" * 70)
    print("空战时长验证")
    print("=" * 70)

    results = []

    # 二战战斗机队 vs 战斗机队
    print("\n[测试] 二战战斗机队 vs 战斗机队")
    fighter1 = build_air_formation(air_db, "二战", "fighter")
    fighter2 = build_air_formation(air_db, "二战", "fighter")

    print(f"  战斗机队宽度: {fighter1.total_width}, 组织度: {fighter1.current_organization:.0f}")

    result = run_battle_test(fighter1, fighter2, ForceType.AIR, max_rounds=50)
    passed = validate_duration("空战高爆发", result, TARGET_DURATION['air_combat'])
    results.append(('air_combat', passed, result))

    return results


def validate_navy_battles(navy_db):
    """验证海战时长"""
    print("=" * 70)
    print("海战时长验证")
    print("=" * 70)

    results = []

    # 二战战列线对决
    print("\n[测试] 二战战列线舰队对决")
    fleet1 = build_navy_formation(navy_db, "二战", "battle")
    fleet2 = build_navy_formation(navy_db, "二战", "battle")

    print(f"  舰队宽度: {fleet1.total_width}, 结构值: {fleet1.current_structure:.0f}")

    result = run_battle_test(fleet1, fleet2, ForceType.NAVY)
    passed = validate_duration("海军舰队决战", result, TARGET_DURATION['navy_battle'])
    results.append(('navy_battle', passed, result))

    return results


def validate_cross_domain(army_db, air_db, navy_db):
    """验证跨维度战斗"""
    print("=" * 70)
    print("跨维度战斗验证")
    print("=" * 70)

    results = []

    # 地对空测试
    print("\n[测试] 陆军防空 vs 空军轰炸队")
    # 构建防空编制（使用防空炮作为主要防空武器）
    # 按照需求：2200宽度陆军防空应在3-6小时重创24宽度空军
    # 防空炮宽度约2，50门 = 100宽度；步枪2000 = 2000宽度；总计2100
    air_defense_spec = [('防空炮', 50), ('栓动步枪', 2000)]  # 防空团配置
    air_defense = build_formation(army_db, air_defense_spec, ForceType.ARMY, "防空团", "二战")

    bomber = build_air_formation(air_db, "二战", "bomber")

    print(f"  防空团宽度: {air_defense.total_width}")
    print(f"  轰炸队宽度: {bomber.total_width}, 组织度: {bomber.current_organization:.0f}")

    # 地对空战斗：陆军攻击空军
    result = run_battle_test(air_defense, bomber, ForceType.AIR)  # 使用空战逻辑但陆军有防空面板
    passed = validate_duration("地对空", result, TARGET_DURATION['ground_to_air'])
    results.append(('ground_to_air', passed, result))

    return results


# =============================================================================
# 主验证流程
# =============================================================================

def run_full_validation():
    """运行全维度验证"""
    print("=" * 70)
    print("全维度战斗时长验证器")
    print("=" * 70)

    base_path = Path(__file__).parent.parent

    # 首先生成新数值
    print("\n[生成新数值]")
    try:
        from value_generator import generate_new_army_csv
        from air_navy_generator import generate_new_air_csv, generate_new_navy_csv

        army_stats = generate_new_army_csv(str(base_path / "army.csv"), str(base_path / "army_new.csv"))
        air_stats = generate_new_air_csv(str(base_path / "air.csv"), str(base_path / "air_new.csv"))
        navy_stats = generate_new_navy_csv(str(base_path / "navy.csv"), str(base_path / "navy_new.csv"))

        print(f"  陆军新数值: {army_stats['total_weapons']} 种武器")
        print(f"  空军新数值: {air_stats['total_weapons']} 种武器")
        print(f"  海军新数值: {navy_stats['total_weapons']} 种武器")
    except Exception as e:
        print(f"  数值生成警告: {e}")

    # 加载CSV数据（使用新生成的）
    print("\n[加载CSV数据]")
    army_path = base_path / "army_new.csv"
    air_path = base_path / "air_new.csv"
    navy_path = base_path / "navy_new.csv"

    # 如果新文件不存在，使用原文件
    if not army_path.exists():
        army_path = base_path / "army.csv"
    if not air_path.exists():
        air_path = base_path / "air.csv"
    if not navy_path.exists():
        navy_path = base_path / "navy.csv"

    army_db = load_army_csv(str(army_path))
    air_db = load_air_csv(str(air_path))
    navy_db = load_navy_csv(str(navy_path))

    print(f"  陆军武器: {len(army_db)} 种")
    print(f"  空军武器: {len(air_db)} 种")
    print(f"  海军武器: {len(navy_db)} 种")

    all_results = []

    # 验证各维度
    all_results.extend(validate_army_battles(army_db))
    all_results.extend(validate_air_battles(air_db))
    all_results.extend(validate_navy_battles(navy_db))
    all_results.extend(validate_cross_domain(army_db, air_db, navy_db))

    # 汇总报告
    print("\n" + "=" * 70)
    print("验证汇总报告")
    print("=" * 70)

    passed_count = sum(1 for _, passed, _ in all_results if passed)
    total_count = len(all_results)

    print(f"\n总计: {passed_count}/{total_count} 项通过")

    for name, passed, result in all_results:
        status = "[OK]" if passed else "[X]"
        duration = result['duration_hours']
        target = TARGET_DURATION.get(name, (0, 0))
        print(f"  {status} {name}: {duration}h (目标 {target[0]}-{target[1]}h)")

    if passed_count == total_count:
        print("\n[OK] 所有验证项通过！数值平衡达标。")
    else:
        print(f"\n[X] {total_count - passed_count} 项未通过，需调整数值。")

    return all_results


# =============================================================================
# 执行入口
# =============================================================================

if __name__ == "__main__":
    run_full_validation()