"""
简化空军海军验证 - 直接使用Formation对象
"""

import sys
import copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from combat_logic import (
    load_air_csv, load_navy_csv,
    ForceType, Formation, WeaponStats,
    run_combat_loop
)
from battle_simulator import CombatStatistics, generate_battle_report, print_battle_report
from air_navy_generator import generate_new_air_csv, generate_new_navy_csv


def copy_weapon(weapon: WeaponStats, quantity: int) -> WeaponStats:
    """复制武器并设置新数量"""
    new_weapon = copy.deepcopy(weapon)
    new_weapon.quantity = quantity
    return new_weapon


def run_simple_battle(attacker: Formation, defender: Formation, force_type: ForceType):
    """运行简单战斗"""
    stats = CombatStatistics()
    result = run_combat_loop(attacker, defender, force_type, stats_collector=stats)

    # 生成报告
    report = generate_battle_report(
        result, stats,
        attacker, attacker,  # 初始和最终相同（简化）
        defender, defender,
        force_type, []
    )
    return report


def main():
    print("=" * 70)
    print("空军海军数值验证")
    print("=" * 70)

    # 生成优化CSV
    print("\n[生成优化数值]")
    air_stats = generate_new_air_csv("air.csv", "air_optimized.csv")
    navy_stats = generate_new_navy_csv("navy.csv", "navy_optimized.csv")
    print(f"空军: {air_stats['total_weapons']} 种")
    print(f"海军: {navy_stats['total_weapons']} 种")

    # 加载
    print("\n[加载优化数值]")
    air_weapons = load_air_csv("air_optimized.csv")
    navy_weapons = load_navy_csv("navy_optimized.csv")

    # 查找二战战斗机
    print("\n[空战测试] 二战战斗机对战")
    fighter_key = None
    for k in air_weapons:
        if '战斗机' in k and '二战' in k:
            fighter_key = k
            break

    if fighter_key:
        fighter = air_weapons[fighter_key]
        print(f"使用武器: {fighter_key}")
        print(f"  宽度: {fighter.width}")
        print(f"  组织度: {fighter.organization}")

        # 构建10架战斗机的编制
        attacker = Formation(ForceType.AIR, "攻击方")
        attacker.weapons = [copy_weapon(fighter, 10)]
        attacker._calculate_total_width()
        attacker._initialize_stats()

        defender = Formation(ForceType.AIR, "防守方")
        defender.weapons = [copy_weapon(fighter, 10)]
        defender._calculate_total_width()
        defender._initialize_stats()

        print(f"攻击方宽度: {attacker.total_width}, 组织度: {attacker.current_organization}")
        print(f"防守方宽度: {defender.total_width}, 组织度: {defender.current_organization}")

        try:
            result = run_combat_loop(attacker, defender, ForceType.AIR, max_rounds=100)
            rounds = result.get('rounds', 0)
            winner = result.get('winner', 'unknown')
            print(f"战斗结果: {rounds}回合, 胜方: {winner}")
            print(f"战斗时长: {rounds} 小时")

            if rounds < 2:
                print("建议: 伤害值过高，战斗太快")
            elif rounds > 15:
                print("建议: 伤害值过低，战斗太慢")
            else:
                print("战斗时长合理!")
        except Exception as e:
            print(f"战斗错误: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("未找到二战战斗机")

    # 海战测试
    print("\n[海战测试] 战列舰 vs 驱逐舰")
    bs_key = None
    dd_key = None
    for k in navy_weapons:
        if '战列舰' in k and '二战' in k:
            bs_key = k
        if '驱逐舰' in k and '二战' in k:
            dd_key = k

    if bs_key and dd_key:
        bs = navy_weapons[bs_key]
        dd = navy_weapons[dd_key]
        print(f"战列舰: {bs_key}, 宽度={bs.width}, 结构值={bs.structure}")
        print(f"驱逐舰: {dd_key}, 宽度={dd.width}, 结构值={dd.structure}")

        # 1战列舰 vs 4驱逐舰
        attacker = Formation(ForceType.NAVY, "战列舰")
        attacker.weapons = [copy_weapon(bs, 1)]
        attacker._calculate_total_width()
        attacker._initialize_stats()

        defender = Formation(ForceType.NAVY, "驱逐舰群")
        defender.weapons = [copy_weapon(dd, 4)]
        defender._calculate_total_width()
        defender._initialize_stats()

        print(f"攻击方宽度: {attacker.total_width}, 结构值: {attacker.current_structure}")
        print(f"防守方宽度: {defender.total_width}, 结构值: {defender.current_structure}")

        try:
            result = run_combat_loop(attacker, defender, ForceType.NAVY, max_rounds=100)
            rounds = result.get('rounds', 0)
            winner = result.get('winner', 'unknown')
            print(f"战斗结果: {rounds}回合, 胜方: {winner}")
            print(f"战斗时长: {rounds} 小时")

            if rounds < 3:
                print("建议: 伤害值过高，战斗太快")
            elif rounds > 20:
                print("建议: 伤害值过低，战斗太慢")
            else:
                print("战斗时长合理!")
        except Exception as e:
            print(f"战斗错误: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"未找到舰船 (战列舰:{bs_key}, 驱逐舰:{dd_key})")

    # 代差测试
    print("\n[代差测试] 现代 vs 二战")
    modern_key = None
    ww2_key = None
    for k in navy_weapons:
        if '巡洋舰' in k:
            if '现代' in k:
                modern_key = k
            if '二战' in k:
                ww2_key = k

    if modern_key and ww2_key:
        modern = navy_weapons[modern_key]
        ww2 = navy_weapons[ww2_key]
        print(f"现代巡洋舰: {modern_key}")
        print(f"二战巡洋舰: {ww2_key}")

        attacker = Formation(ForceType.NAVY, "现代巡洋舰")
        attacker.weapons = [copy_weapon(modern, 1)]
        attacker._calculate_total_width()
        attacker._initialize_stats()

        defender = Formation(ForceType.NAVY, "二战巡洋舰")
        defender.weapons = [copy_weapon(ww2, 1)]
        defender._calculate_total_width()
        defender._initialize_stats()

        try:
            result = run_combat_loop(attacker, defender, ForceType.NAVY, max_rounds=50)
            rounds = result.get('rounds', 0)
            winner = result.get('winner', 'unknown')
            print(f"代差战斗: {rounds}回合, 胜方: {winner}")
            print("预期: 现代舰船快速碾压二战舰船")
        except Exception as e:
            print(f"战斗错误: {e}")
    else:
        print(f"未找到巡洋舰")

    print("\n" + "=" * 70)
    print("验证完成")
    print("=" * 70)
    print("生成文件: air_optimized.csv, navy_optimized.csv")


if __name__ == "__main__":
    main()