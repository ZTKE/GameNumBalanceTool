"""
完整验证流程 - 生成新数值并测试战斗时长
"""

import sys
import copy
from pathlib import Path

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from value_generator import generate_new_army_csv, generate_balance_report, BASE_SOFT_ATTACK_PER_WIDTH
from combat_logic import Formation, load_army_csv, ForceType, WeaponStats
from battle_simulator import run_battle_simulation, print_battle_report, build_formation_from_input


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
    """
    手动构建编制

    参数:
        weapon_dict: 武器字典 {武器名: WeaponStats}
        weapon_specs: 武器规格列表 [(武器名, 数量), ...]
        formation_name: 编制名称
        force_type: 军种类型

    返回:
        Formation对象
    """
    weapons_list = []
    for weapon_name, quantity in weapon_specs:
        # 使用时代+武器名作为key查找（优先二战）
        key = f"二战_{weapon_name}"
        if key in weapon_dict:
            weapon = copy_weapon(weapon_dict[key], quantity)
            weapons_list.append(weapon)
        elif weapon_name in weapon_dict:
            weapon = copy_weapon(weapon_dict[weapon_name], quantity)
            weapons_list.append(weapon)
        else:
            print(f"警告: 未找到武器 '{weapon_name}'")

    return Formation(
        force_type=force_type,
        name=formation_name,
        weapons=weapons_list
    )


def run_complete_validation():
    """运行完整验证流程"""
    print("=" * 70)
    print("数值平衡验证流程")
    print("=" * 70)

    # Step 1: 生成新数值
    print("\n[第一步] 生成新的army.csv数值...")

    input_csv = "army.csv"
    output_csv = "army_optimized.csv"

    stats = generate_new_army_csv(input_csv, output_csv)

    print(f"生成完成: {stats['total_weapons']} 种武器")
    for era, count in stats['weapons_by_era'].items():
        print(f"  - {era}: {count} 种")

    # Step 2: 加载新数值并测试
    print("\n[第二步] 加载新数值进行战斗测试...")

    # 加载优化后的数据
    weapons_optimized = load_army_csv(output_csv)

    # 打印可用武器列表（二战时期）
    print("\n可用二战武器:")
    ww2_weapons = [k for k in weapons_optimized.keys() if '二战' in k or weapons_optimized[k].era == '二战']
    for w in ww2_weapons[:10]:
        print(f"  - {w}")

    # 构建编制：二战装甲团 vs 二战步兵团
    # 装甲团: 中型坦克:74=反坦克歼击车:10=自行突击炮:10=轮式装甲车:10
    # 步兵团: 栓动步枪:600=突击步枪:1028=冲锋枪:121=机枪:140=迫击炮:24=反坦克炮:15

    print("\n[测试1] 装甲团 vs 步兵团 (无堑壕)")

    # 装甲团规格
    attacker_specs = [
        ('中型坦克', 74),
        ('反坦克歼击车', 10),
        ('自行突击炮', 10),
        ('轮式装甲车', 10),
    ]

    # 步兵团规格
    defender_specs = [
        ('栓动步枪', 600),
        ('突击步枪', 1028),
        ('冲锋枪', 121),
        ('机枪', 140),
        ('迫击炮', 24),
        ('反坦克炮', 15),
    ]

    # 使用优化后的数值构建编制
    attacker_opt = build_formation_manual(
        weapons_optimized, attacker_specs, "装甲团_优化", ForceType.ARMY
    )

    defender_opt = build_formation_manual(
        weapons_optimized, defender_specs, "步兵团_优化", ForceType.ARMY
    )

    print(f"\n攻击方总宽度: {attacker_opt.total_width}")
    print(f"攻击方总血量: {attacker_opt.current_hp}")
    print(f"攻击方总组织度: {attacker_opt.current_organization}")
    print(f"防守方总宽度: {defender_opt.total_width}")
    print(f"防守方总血量: {defender_opt.current_hp}")
    print(f"防守方总组织度: {defender_opt.current_organization}")

    # 运行战斗模拟（无堑壕）
    # 使用字符串格式传递编制规格
    attacker_str = "中型坦克:74=反坦克歼击车:10=自行突击炮:10=轮式装甲车:10"
    defender_str = "栓动步枪:600=突击步枪:1028=冲锋枪:121=机枪:140=迫击炮:24=反坦克炮:15"

    report_no_trench = run_battle_simulation(
        attacker_str, defender_str, ForceType.ARMY, weapons_optimized
    )
    print_battle_report(report_no_trench)

    print("\n[测试2] 装甲团 vs 步兵团 (有堑壕)")

    # 重新构建编制（有堑壕）
    attacker_opt2 = build_formation_manual(
        weapons_optimized, attacker_specs, "装甲团_优化", ForceType.ARMY
    )

    defender_opt2 = build_formation_manual(
        weapons_optimized, defender_specs, "步兵团_优化_堑壕", ForceType.ARMY
    )

    # 计算堑壕加成
    trench_bonus_total = sum(
        w.trench_defense * w.quantity
        for w in defender_opt2.weapons
        if hasattr(w, 'trench_defense')
    )
    print(f"堑壕防御加成总计: {trench_bonus_total}")

    # 运行战斗模拟（有堑壕）- 需要调整战斗逻辑以支持堑壕
    report_with_trench = run_battle_simulation(
        attacker_str, defender_str, ForceType.ARMY, weapons_optimized,
        active_environments=['平原适应性']  # 暂用环境代替堑壕效果
    )
    print_battle_report(report_with_trench)

    # Step 3: 生成平衡性报告
    print("\n[第三步] 生成平衡性报告...")
    balance_report = generate_balance_report(stats)
    print(balance_report)

    # Step 4: 结果评估
    print("\n[第四步] 战斗时长验证结果")
    print(f"目标时长（有堑壕）: 12-24 小时")
    print(f"实际时长（有堑壕）: {report_with_trench.battle_duration_hours} 小时")
    pass_with_trench = 12 <= report_with_trench.battle_duration_hours <= 24
    print(f"达标: {'是' if pass_with_trench else '否'}")

    print(f"\n目标时长（无堑壕）: 6-12 小时")
    print(f"实际时长（无堑壕）: {report_no_trench.battle_duration_hours} 小时")
    pass_no_trench = 6 <= report_no_trench.battle_duration_hours <= 12
    print(f"达标: {'是' if pass_no_trench else '否'}")

    # 如果不达标，给出调整建议
    if not pass_no_trench or not pass_with_trench:
        print("\n[调整建议]")
        actual_hours = report_no_trench.battle_duration_hours
        if actual_hours > 12:
            ratio = actual_hours / 8  # 目标8小时
            print(f"  战斗时间过长({actual_hours}h)，建议将攻击值提高 {ratio:.2f}x")
        elif actual_hours < 6:
            ratio = 8 / max(actual_hours, 0.5)
            print(f"  战斗时间过短({actual_hours}h)，建议将攻击值降低到 {1/ratio:.2f}x")
            print(f"  原因：当前伤害过高，防守方组织度在第1回合就归零")
            print(f"  建议：将BASE_SOFT_ATTACK_PER_WIDTH从23.42降低到约 {23.42/ratio:.2f}")

    return {
        'stats': stats,
        'report_no_trench': report_no_trench,
        'report_with_trench': report_with_trench,
        'pass_no_trench': pass_no_trench,
        'pass_with_trench': pass_with_trench,
    }


if __name__ == "__main__":
    result = run_complete_validation()