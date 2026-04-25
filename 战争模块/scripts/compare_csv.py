"""
对比原始army.csv和优化后的数值
"""

import csv
from pathlib import Path

def parse_10_stage(value_str):
    """解析10阶段数值"""
    if not value_str or value_str == '0':
        return [0.0] * 10
    try:
        return [float(x) for x in value_str.split('=')]
    except:
        return [0.0] * 10

def compare_csv():
    """对比两个CSV文件的关键数值"""

    # 读取原始CSV
    with open('army.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        original = {row[0]+'_'+row[1]: row for row in reader}

    # 读取优化CSV
    with open('army_optimized.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        optimized = {row[0]+'_'+row[1]: row for row in reader}

    # 列索引
    COLS = {
        'soft_attack': 54,  # 对地软攻
        'hard_attack': 53,  # 对地硬攻
        'defense': 8,       # 防御
        'penetration': 17,  # 对地穿透
        'armor': 9,         # 装甲厚度
        'suppression': 18,  # 对地压制
        'trench_defense': 52,  # 堑壕防御
    }

    # 对比关键武器
    key_weapons = [
        ('栓动步枪_二战', '步兵基准'),
        ('突击步枪_二战', '步兵进阶'),
        ('机枪_二战', '压制专家'),
        ('中型坦克_二战', '装甲主力'),
        ('反坦克炮_二战', '反装甲'),
        ('迫击炮_二战', '支援火力'),
        ('野战火炮_二战', '远程支援'),
        ('反坦克歼击车_二战', '机动反坦克'),
    ]

    print("=" * 80)
    print("关键武器数值对比（二战时期）")
    print("=" * 80)

    for weapon_key, desc in key_weapons:
        if weapon_key not in original or weapon_key not in optimized:
            print(f"\n{desc}({weapon_key}): 未找到")
            continue

        orig = original[weapon_key]
        opt = optimized[weapon_key]

        print(f"\n【{desc}】{weapon_key}")
        print("-" * 60)

        # 软攻对比
        orig_soft = parse_10_stage(orig[COLS['soft_attack']])
        opt_soft = parse_10_stage(opt[COLS['soft_attack']])
        print(f"软攻峰值: 原{max(orig_soft):.2f} → 新{max(opt_soft):.2f} (变化{(max(opt_soft)/max(orig_soft)-1)*100:+.1f}%)")

        # 硬攻对比
        orig_hard = parse_10_stage(orig[COLS['hard_attack']])
        opt_hard = parse_10_stage(opt[COLS['hard_attack']])
        if max(orig_hard) > 0:
            print(f"硬攻峰值: 原{max(orig_hard):.2f} → 新{max(opt_hard):.2f} (变化{(max(opt_hard)/max(orig_hard)-1)*100:+.1f}%)")
        else:
            print(f"硬攻峰值: 原{max(orig_hard):.2f} → 新{max(opt_hard):.2f}")

        # 防御对比
        orig_def = parse_10_stage(orig[COLS['defense']])
        opt_def = parse_10_stage(opt[COLS['defense']])
        print(f"防御峰值: 原{max(orig_def):.2f} → 新{max(opt_def):.2f} (变化{(max(opt_def)/max(orig_def)-1)*100:+.1f}%)")

        # 穿透对比
        orig_pen = parse_10_stage(orig[COLS['penetration']])
        opt_pen = parse_10_stage(opt[COLS['penetration']])
        print(f"穿透峰值: 原{max(orig_pen):.2f} → 新{max(opt_pen):.2f}")

        # 装甲对比
        orig_armor = float(orig[COLS['armor']] or 0)
        opt_armor = float(opt[COLS['armor']] or 0)
        print(f"装甲厚度: 原{orig_armor:.2f} → 新{opt_armor:.2f}")

        # 堑壕对比
        orig_trench = float(orig[COLS['trench_defense']] or 0)
        opt_trench = float(opt[COLS['trench_defense']] or 0)
        print(f"堑壕防御: 原{orig_trench:.2f} → 新{opt_trench:.2f}")

        # 10阶段软攻曲线对比
        print(f"\n软攻10阶段曲线:")
        print(f"  原: {orig_soft[0]:.1f}→{orig_soft[2]:.1f}→{orig_soft[5]:.1f}→{orig_soft[9]:.1f}")
        print(f"  新: {opt_soft[0]:.1f}→{opt_soft[2]:.1f}→{opt_soft[5]:.1f}→{opt_soft[9]:.1f}")

    # 统计总体变化
    print("\n" + "=" * 80)
    print("总体变化统计")
    print("=" * 80)

    changes = {'soft_attack': [], 'hard_attack': [], 'defense': []}

    for key in original:
        if key not in optimized:
            continue
        if '二战' not in key:
            continue

        orig = original[key]
        opt = optimized[key]

        orig_soft = parse_10_stage(orig[COLS['soft_attack']])
        opt_soft = parse_10_stage(opt[COLS['soft_attack']])
        if max(orig_soft) > 0:
            changes['soft_attack'].append(max(opt_soft) / max(orig_soft))

        orig_hard = parse_10_stage(orig[COLS['hard_attack']])
        opt_hard = parse_10_stage(opt[COLS['hard_attack']])
        if max(orig_hard) > 0:
            changes['hard_attack'].append(max(opt_hard) / max(orig_hard))

        orig_def = parse_10_stage(orig[COLS['defense']])
        opt_def = parse_10_stage(opt[COLS['defense']])
        if max(orig_def) > 0:
            changes['defense'].append(max(opt_def) / max(orig_def))

    for attr, ratios in changes.items():
        if ratios:
            avg_change = sum(ratios) / len(ratios)
            print(f"{attr}平均变化: {avg_change:.2f}x ({(avg_change-1)*100:+.1f}%)")


if __name__ == "__main__":
    compare_csv()