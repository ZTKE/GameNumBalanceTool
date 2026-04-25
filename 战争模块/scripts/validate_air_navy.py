"""
空军海军数值验证流程
====================

测试场景：
- 空战：战斗机对战斗机，代差碾压测试
- 海战：战列舰对驱逐舰，航母对战列舰
- 目标时长：空战2-6小时，海战4-12小时
"""

import sys
import copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from combat_logic import (
    load_air_csv, load_navy_csv, load_army_csv,
    ForceType, Formation, WeaponStats
)
from battle_simulator import run_battle_simulation, print_battle_report
from air_navy_generator import (
    generate_new_air_csv, generate_new_navy_csv,
    BASE_AIR_TO_GROUND_DAMAGE, BASE_AIR_TO_AIR_DAMAGE,
    BASE_NAVY_HEAVY_GUN_DAMAGE, BASE_NAVY_TORPEDO_DAMAGE,
    ERA_SCALING
)


def copy_weapon(weapon: WeaponStats, quantity: int) -> WeaponStats:
    """复制武器并设置新数量"""
    new_weapon = copy.deepcopy(weapon)
    new_weapon.quantity = quantity
    return new_weapon


def build_formation_manual(
    weapon_dict: dict,
    weapon_specs: list,
    formation_name: str,
    force_type: ForceType
) -> Formation:
    """手动构建编制"""
    weapons_list = []
    for weapon_name, quantity in weapon_specs:
        key = f"二战_{weapon_name}"
        if key in weapon_dict:
            weapon = copy_weapon(weapon_dict[key], quantity)
            weapons_list.append(weapon)
        elif weapon_name in weapon_dict:
            weapon = copy_weapon(weapon_dict[weapon_name], quantity)
            weapons_list.append(weapon)
        else:
            # 尝试不带时代的key
            for k in weapon_dict:
                if weapon_name in k:
                    weapon = copy_weapon(weapon_dict[k], quantity)
                    weapons_list.append(weapon)
                    break

    return Formation(
        force_type=force_type,
        name=formation_name,
        weapons=weapons_list
    )


def validate_air_navy():
    """验证空军海军数值"""
    print("=" * 70)
    print("空军海军数值验证")
    print("=" * 70)

    # Step 1: 生成优化CSV
    print("\n[Step 1] 生成优化数值...")
    air_stats = generate_new_air_csv("air.csv", "air_optimized.csv")
    navy_stats = generate_new_navy_csv("navy.csv", "navy_optimized.csv")

    print(f"空军: {air_stats['total_weapons']} 种武器")
    for era, count in air_stats['weapons_by_era'].items():
        print(f"  {era}: {count} 种")

    print(f"海军: {navy_stats['total_weapons']} 种武器")
    for era, count in navy_stats['weapons_by_era'].items():
        print(f"  {era}: {count} 种")

    # Step 2: 加载数值
    print("\n[Step 2] 加载优化数值...")
    air_weapons = load_air_csv("air_optimized.csv")
    navy_weapons = load_navy_csv("navy_optimized.csv")

    # 显示所有可用武器（加载后的key）
    print("\n加载后空军武器keys:")
    for k in list(air_weapons.keys())[:15]:
        w = air_weapons[k]
        print(f"  {k} (时代:{w.era}, 宽度:{w.width})")

    print("\n加载后海军武器keys:")
    for k in list(navy_weapons.keys())[:15]:
        w = navy_weapons[k]
        print(f"  {k} (时代:{w.era}, 宽度:{w.width})")

    # Step 3: 空战测试（使用实际存在的武器）
    print("\n" + "=" * 70)
    print("空战测试")
    print("=" * 70)

    # 找到二战轻型战斗机
    ww2_fighters = [k for k in air_weapons.keys() if '战斗机' in k and air_weapons[k].era == '二战']
    print(f"\n二战战斗机: {ww2_fighters}")

    if ww2_fighters:
        fighter_name = ww2_fighters[0]
        print(f"\n[测试] {fighter_name} vs {fighter_name}")

        fighter = air_weapons[fighter_name]
        print(f"  速度: {fighter.speed} km/h")
        print(f"  组织度: {fighter.organization}")
        print(f"  血量: {fighter.hp}")

        # 构建10架战斗机
        attacker = Formation(ForceType.AIR, "攻击方战斗机")
        attacker.weapons = [copy_weapon(fighter, 10)]
        attacker._calculate_total_width()
        attacker._initialize_stats()

        defender = Formation(ForceType.AIR, "防守方战斗机")
        defender.weapons = [copy_weapon(fighter, 10)]
        defender._calculate_total_width()
        defender._initialize_stats()

        print(f"攻击方总宽度: {attacker.total_width}")
        print(f"防守方总宽度: {defender.total_width}")
        print(f"攻击方组织度: {attacker.current_organization}")
        print(f"防守方组织度: {defender.current_organization}")

        # 使用字符串格式运行战斗
        try:
            # 用武器名:数量格式
            spec_str = f"{fighter_name}:10"
            report = run_battle_simulation(spec_str, spec_str, ForceType.AIR, air_weapons)
            print_battle_report(report)

            duration = report.battle_duration_hours
            print(f"\n战斗时长: {duration} 小时")
            if duration < 2:
                print("建议: 提高伤害值（当前战斗过快）")
            elif duration > 10:
                print("建议: 降低伤害值（当前战斗过慢）")
            else:
                print("时长合理!")
        except Exception as e:
            print(f"战斗模拟错误: {e}")

    # Step 4: 海战测试
    print("\n" + "=" * 70)
    print("海战测试")
    print("=" * 70)

    # 找二战战列舰和驱逐舰
    ww2_ships = [k for k in navy_weapons.keys() if navy_weapons[k].era == '二战']
    print(f"\n二战舰船: {ww2_ships[:10]}")

    battleships = [k for k in ww2_ships if '战列舰' in k]
    destroyers = [k for k in ww2_ships if '驱逐舰' in k]

    if battleships and destroyers:
        bs_name = battleships[0]
        dd_name = destroyers[0]

        print(f"\n[测试] {bs_name} vs {dd_name}x4")

        bs = navy_weapons[bs_name]
        dd = navy_weapons[dd_name]

        print(f"战列舰: 宽度={bs.width}, 结构值={bs.structure}")
        print(f"驱逐舰: 宽度={dd.width}, 结构值={dd.structure}")

        # 战列舰 vs 4驱逐舰
        attacker = Formation(ForceType.NAVY, "战列舰")
        attacker.weapons = [copy_weapon(bs, 1)]
        attacker._calculate_total_width()
        attacker._initialize_stats()

        defender = Formation(ForceType.NAVY, "驱逐舰群")
        defender.weapons = [copy_weapon(dd, 4)]
        defender._calculate_total_width()
        defender._initialize_stats()

        print(f"攻击方总宽度: {attacker.total_width}")
        print(f"防守方总宽度: {defender.total_width}")
        print(f"攻击方结构值: {attacker.current_structure}")
        print(f"防守方结构值: {defender.current_structure}")

        try:
            report = run_battle_simulation(
                f"{bs_name}:1", f"{dd_name}:4",
                ForceType.NAVY, navy_weapons
            )
            print_battle_report(report)

            duration = report.battle_duration_hours
            print(f"\n战斗时长: {duration} 小时")
            if duration < 3:
                print("建议: 提高伤害值")
            elif duration > 15:
                print("建议: 降低伤害值")
            else:
                print("时长合理!")
        except Exception as e:
            print(f"战斗模拟错误: {e}")

    # Step 5: 代差测试（现代vs二战）
    print("\n" + "=" * 70)
    print("代差碾压测试")
    print("=" * 70)

    modern_ships = [k for k in navy_weapons.keys() if navy_weapons[k].era == '现代']
    print(f"\n现代舰船: {modern_ships[:5]}")

    modern_bs = [k for k in modern_ships if '战列' in k or '巡洋' in k]
    if modern_bs and ww2_ships:
        modern_name = modern_bs[0] if modern_bs else modern_ships[0]
        ww2_name = ww2_ships[0]

        print(f"\n[测试] {modern_name}（现代） vs {ww2_name}（二战）")
        print("预期：现代舰船碾压二战舰船")

        try:
            report = run_battle_simulation(
                f"{modern_name}:1", f"{ww2_name}:1",
                ForceType.NAVY, navy_weapons
            )
            print_battle_report(report)
            print(f"\n现代vs二战用时: {report.battle_duration_hours} 小时")
            print(f"IC交换比: {report.ic_exchange_ratio}")
        except Exception as e:
            print(f"战斗模拟错误: {e}")

    # Step 6: 总结
    print("\n" + "=" * 70)
    print("验证总结")
    print("=" * 70)

    print("\n生成文件:")
    print("  - air_optimized.csv (33种武器)")
    print("  - navy_optimized.csv (41种武器)")

    print("\n下一步建议:")
    print("  1. 如果战斗时长不合理，调整BASE_AIR_TO_GROUND_DAMAGE等基准值")
    print("  2. 测试更多组合验证平衡性")
    print("  3. 将优化值更新到正式CSV")


if __name__ == "__main__":
    validate_air_navy()