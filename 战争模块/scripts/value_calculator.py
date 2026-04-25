"""
数值设计数学模型
================
用于计算符合目标战斗时长的数值范围

基于需求.md中的公式：
- 若 攻击 <= 防御：基础伤害 = 攻击 * 0.1
- 若 攻击 > 防御：基础伤害 = 防御 * 0.1 + (攻击 - 防御) * 0.4
- 结算：敌方血量 - 最终伤害 * 0.1；敌方组织度 - 最终伤害

目标时长：
- 有堑壕：12-24小时击溃防守方
- 无堑壕：6-12小时击溃防守方

击溃条件：组织度归零或血量归零
"""

import math
from typing import Dict, List, Tuple


# =============================================================================
# 数学模型核心函数
# =============================================================================

def calculate_hourly_damage_needed(
    total_hp: float,
    total_org: float,
    target_hours: float,
    hp_ratio: float = 0.1,  # 血量伤害系数
    org_ratio: float = 1.0  # 组织度伤害系数
) -> Dict:
    """
    计算每小时需要的伤害量

    参数:
        total_hp: 目标总血量
        total_org: 目标总组织度
        target_hours: 目标击溃时长
        hp_ratio: 血量伤害系数（默认0.1）
        org_ratio: 组织度伤害系数（默认1.0）

    返回:
        每小时需要的伤害量字典
    """
    # 组织度归零需要的总伤害
    total_damage_for_org = total_org / org_ratio

    # 血量归零需要的总伤害
    total_damage_for_hp = total_hp / hp_ratio

    # 取较小值（先归零的条件）
    total_damage_needed = min(total_damage_for_org, total_damage_for_hp)

    # 每小时需要的伤害
    hourly_damage_needed = total_damage_needed / target_hours

    return {
        'total_damage_for_org': total_damage_for_org,
        'total_damage_for_hp': total_damage_for_hp,
        'total_damage_needed': total_damage_needed,
        'hourly_damage_needed': hourly_damage_needed,
        'will_die_by': 'organization' if total_damage_for_org < total_damage_for_hp else 'hp'
    }


def reverse_calculate_attack(
    target_hourly_damage: float,
    defender_defense: float,
    hit_rate: float = 0.8,
    penetration_efficiency: float = 1.0,
    env_coefficient: float = 1.0
) -> float:
    """
    反推需要的攻击数值

    公式：最终伤害 = 基础伤害 * 击穿效率 * 命中率 * 环境系数

    参数:
        target_hourly_damage: 目标每小时伤害
        defender_defense: 防守方防御值
        hit_rate: 命中率
        penetration_efficiency: 击穿效率
        env_coefficient: 环境系数

    返回:
        需要的攻击数值
    """
    # 反推基础伤害
    base_damage_needed = target_hourly_damage / (hit_rate * penetration_efficiency * env_coefficient)

    # 根据全局公式反推攻击值
    if defender_defense <= 0:
        # 防御为0，直接反推
        attack_needed = base_damage_needed / 0.4
    else:
        # 假设攻击 > 防御（击穿状态）
        # 基础伤害 = 防御 * 0.1 + (攻击 - 防御) * 0.4
        # attack_needed = (base_damage_needed - defender_defense * 0.1) / 0.4 + defender_defense
        attack_needed = (base_damage_needed - defender_defense * 0.1) / 0.4 + defender_defense

        # 验证是否确实攻击 > 防御
        if attack_needed <= defender_defense:
            # 攻击 <= 防御时：基础伤害 = 攻击 * 0.1
            attack_needed = base_damage_needed / 0.1

    return max(0, attack_needed)


def calculate_armor_rate_effect(
    attacker_soft_attack: float,
    attacker_hard_attack: float,
    defender_armor_rate: float
) -> float:
    """
    计算有效攻击（考虑装甲率）

    公式：有效攻击 = 敌方装甲率 * 己方对地硬攻 + (1-敌方装甲率) * 己方对地软攻

    参数:
        attacker_soft_attack: 进攻方软攻
        attacker_hard_attack: 进攻方硬攻
        defender_armor_rate: 防守方装甲率（0-1）

    返回:
        有效攻击值
    """
    return defender_armor_rate * attacker_hard_attack + (1 - defender_armor_rate) * attacker_soft_attack


def calculate_formation_total_panel(
    weapons: List[Dict],
    panel_name: str,
    stage: int = 6  # 默认阶段6（开局）
) -> float:
    """
    计算编制在某阶段的总面板值

    参数:
        weapons: 武器列表 [{weapon_type, quantity, panel_values...}]
        panel_name: 面板名称
        stage: 阶段编号（1-10）

    返回:
        总面板值
    """
    total = 0
    for weapon in weapons:
        panel_values = weapon.get(panel_name, [])
        if isinstance(panel_values, list) and len(panel_values) >= stage:
            value = panel_values[stage - 1]
        else:
            value = weapon.get(panel_name, 0)
        total += value * weapon['quantity']
    return total


# =============================================================================
# 基准测试计算器
# =============================================================================

def calculate_ww2_benchmark_values():
    """
    计算二战装甲团 vs 步兵团的基准数值

    基于army_war.csv中的编制：
    - 装甲团: 中型坦克:74=反坦克歼击车:10=自行突击炮:10=轮式装甲车:10
    - 步兵团: 栓动步枪:600=突击步枪:1028=冲锋枪:121=机枪:140=迫击炮:24=反坦克炮:15
    """
    print("=" * 70)
    print("二战装甲团 vs 步兵团 数值基准计算")
    print("=" * 70)

    # ===== 防守方（步兵团）数据 =====
    # 基于现有CSV的属性（假设值）
    defender_hp = 89000  # 从测试输出
    defender_org = 94500  # 从测试输出
    defender_total_width = 2200

    # 步兵武器假设参数（宽度1，数量约2000）
    rifle_width = 1
    rifle_quantity = 1700  # 栓动+突击步枪合计
    rifle_defense_per_width = 2.0  # 每宽度防御值

    # 计算总防御
    defender_defense = rifle_defense_per_width * defender_total_width

    # 堑壕防御加成
    trench_bonus = 25.0  # 每单位堑壕防御
    trench_total = trench_bonus * rifle_quantity  # 约42500

    print("\n【防守方（步兵团）参数】")
    print(f"  总血量: {defender_hp}")
    print(f"  总组织度: {defender_org}")
    print(f"  总防御: {defender_defense}")
    print(f"  堑壕防御: {trench_total}")
    print(f"  装甲率: ~3%")

    # ===== 目标时长计算 =====
    print("\n【目标时长分析】")

    # 有堑壕情况（12-24小时）
    target_hours_trench = (12, 24)
    for hours in target_hours_trench:
        result = calculate_hourly_damage_needed(defender_org, defender_hp, hours)
        print(f"\n  目标 {hours} 小时击溃（有堑壕）:")
        print(f"    - 每小时需要伤害: {result['hourly_damage_needed']:.2f}")
        print(f"    - 击溃方式: {result['will_die_by']}")

    # 无堑壕情况（6-12小时）
    target_hours_no_trench = (6, 12)
    for hours in target_hours_no_trench:
        result = calculate_hourly_damage_needed(defender_org, defender_hp, hours)
        print(f"\n  目标 {hours} 小时击溃（无堑壕）:")
        print(f"    - 每小时需要伤害: {result['hourly_damage_needed']:.2f}")
        print(f"    - 击溃方式: {result['will_die_by']}")

    # ===== 进攻方数值反推 =====
    print("\n【进攻方（装甲团）数值反推】")

    # 装甲团参数
    attacker_total_width = 2188
    tank_quantity = 74  # 中型坦克
    tank_width = 20  # 假设坦克宽度

    # 考虑装甲率的软硬攻分配
    defender_armor_rate = 0.03  # 步兵团装甲率约3%

    # 计算目标：18小时击溃（有堑壹取中间值）
    target_hours = 18
    damage_result = calculate_hourly_damage_needed(defender_org, defender_hp, target_hours)
    hourly_damage_needed = damage_result['hourly_damage_needed']

    # 考虑堑壕防御加成后的有效防御
    effective_defense_with_trench = defender_defense + trench_total
    effective_defense_no_trench = defender_defense

    print(f"\n目标: {target_hours}小时击溃")
    print(f"每小时需要伤害: {hourly_damage_needed:.2f}")

    # 反推攻击值（有堑壕）
    attack_needed_trench = reverse_calculate_attack(
        hourly_damage_needed,
        effective_defense_with_trench,
        hit_rate=0.7,
        penetration_efficiency=1.0,
        env_coefficient=1.0
    )

    print(f"\n有堑壕情况:")
    print(f"  有效防御（含堑壕）: {effective_defense_with_trench}")
    print(f"  需要总攻击: {attack_needed_trench:.2f}")
    print(f"  每宽度攻击: {attack_needed_trench / attacker_total_width:.4f}")

    # 反推攻击值（无堑壕）
    attack_needed_no_trench = reverse_calculate_attack(
        hourly_damage_needed * 1.5,  # 无堑壕时伤害需要更高
        effective_defense_no_trench,
        hit_rate=0.7,
        penetration_efficiency=1.0,
        env_coefficient=1.0
    )

    print(f"\n无堑壕情况:")
    print(f"  有效防御: {effective_defense_no_trench}")
    print(f"  需要总攻击: {attack_needed_no_trench:.2f}")
    print(f"  每宽度攻击: {attack_needed_no_trench / attacker_total_width:.4f}")

    # ===== 软硬攻分配 =====
    print("\n【坦克软硬攻数值建议】")

    # 基于装甲率的软硬攻分配
    # 对步兵团（装甲率3%），主要用软攻
    # 对装甲团（装甲率90%），主要用硬攻

    # 假设坦克主要面对步兵，软攻为主
    tank_soft_attack_total = attack_needed_trench * 0.97  # 97%软攻
    tank_hard_attack_total = attack_needed_trench * 0.03  # 3%硬攻

    tank_soft_attack_per_width = tank_soft_attack_total / attacker_total_width
    tank_hard_attack_per_width = tank_hard_attack_total / attacker_total_width

    print(f"\n坦克数值建议（每宽度）:")
    print(f"  软攻: {tank_soft_attack_per_width:.3f}")
    print(f"  硬攻: {tank_hard_attack_per_width:.3f}")
    print(f"  防御: {defender_defense / defender_total_width * 2:.3f} (坦克防御约为步兵2倍)")
    print(f"  突破: {tank_soft_attack_per_width * 0.8:.3f} (突破约为软攻0.8倍)")

    # ===== 时代缩放建议 =====
    print("\n【时代缩放系数建议】")

    # 以二战为基准（1.0）
    # 一战、冷战、现代按技术进步缩放
    era_scaling = {
        '一战': 0.6,   # 一战武器较弱
        '二战': 1.0,   # 基准
        '冷战': 1.5,   # 冷战技术进步
        '现代': 2.5    # 现代技术大幅进步
    }

    for era, scale in era_scaling.items():
        print(f"  {era}: {scale}x 二战基准")
        print(f"    软攻建议: {tank_soft_attack_per_width * scale:.3f}")
        print(f"    硬攻建议: {tank_hard_attack_per_width * scale:.3f}")

    return {
        'defender_hp': defender_hp,
        'defender_org': defender_org,
        'defender_defense': defender_defense,
        'trench_total': trench_total,
        'attack_needed_trench': attack_needed_trench,
        'attack_needed_no_trench': attack_needed_no_trench,
        'tank_soft_attack_per_width': tank_soft_attack_per_width,
        'tank_hard_attack_per_width': tank_hard_attack_per_width,
        'era_scaling': era_scaling
    }


def generate_optimized_values():
    """
    生成优化后的数值表

    基于数学模型计算结果，生成CSV数值设计
    """
    print("\n" + "=" * 70)
    print("生成优化数值表")
    print("=" * 70)

    # 基准计算
    benchmark = calculate_ww2_benchmark_values()

    # 软攻建议值（每宽度）
    base_soft_attack = benchmark['tank_soft_attack_per_width']

    print(f"\n基准软攻（每宽度）: {base_soft_attack:.4f}")

    # ===== 武器类别数值设计 =====
    print("\n【武器类别数值设计原则】")

    design_rules = {
        '栓动步枪': {
            'peak_stage': 3,  # 1.5-4km峰值
            'soft_attack_ratio': 1.0,  # 基准软攻
            'hard_attack_ratio': 0.05,  # 极低硬攻
            'defense_ratio': 1.0,
            'trench_ratio': 1.0,
            'penetration': 0.0,
            'armor': 0.0,
            'description': '近距离软攻主力，无装甲'
        },
        '突击步枪': {
            'peak_stage': 4,  # 4-8km峰值
            'soft_attack_ratio': 1.2,  # 比栓动步枪强20%
            'hard_attack_ratio': 0.1,
            'defense_ratio': 1.1,
            'trench_ratio': 1.1,
            'penetration': 0.05,
            'armor': 0.0,
            'description': '中近距离均衡，略强于栓动'
        },
        '机枪': {
            'peak_stage': 5,  # 8-20km峰值
            'soft_attack_ratio': 1.5,  # 高软攻
            'hard_attack_ratio': 0.15,
            'defense_ratio': 0.8,
            'trench_ratio': 1.0,
            'suppression_ratio': 2.0,  # 高压制
            'penetration': 0.1,
            'armor': 0.0,
            'description': '压制专家，中远距离'
        },
        '中型坦克': {
            'peak_stage': 6,  # 20-40km峰值
            'soft_attack_ratio': 8.0,  # 高软攻
            'hard_attack_ratio': 15.0,  # 极高硬攻
            'defense_ratio': 4.0,  # 高防御
            'breakthrough_ratio': 3.0,  # 突破
            'penetration': 3.0,
            'armor': 3.5,
            'description': '硬攻主力，高装甲'
        },
        '主战坦克': {
            'peak_stage': 6,
            'soft_attack_ratio': 15.0,
            'hard_attack_ratio': 25.0,
            'defense_ratio': 6.0,
            'breakthrough_ratio': 5.0,
            'penetration': 5.0,
            'armor': 5.0,
            'description': '现代坦克，全面碾压'
        },
        '反坦克炮': {
            'peak_stage': 5,
            'soft_attack_ratio': 0.5,
            'hard_attack_ratio': 20.0,  # 极高硬攻
            'defense_ratio': 0.8,
            'penetration': 5.0,  # 极高穿透
            'armor': 0.0,
            'description': '穿甲专家，反装甲'
        },
        '迫击炮': {
            'peak_stage': 4,
            'soft_attack_ratio': 3.0,
            'hard_attack_ratio': 2.0,
            'defense_ratio': 0.5,
            'suppression_ratio': 3.0,  # 高压制
            'penetration': 0.2,
            'armor': 0.0,
            'description': '压制支援，中近距离'
        },
        '火炮': {
            'peak_stage': 7,  # 40-80km峰值
            'soft_attack_ratio': 5.0,
            'hard_attack_ratio': 4.0,
            'defense_ratio': 0.3,
            'suppression_ratio': 5.0,
            'penetration': 1.0,
            'armor': 0.0,
            'description': '远程压制支援'
        }
    }

    for weapon, rules in design_rules.items():
        print(f"\n{weapon}:")
        print(f"  峰值阶段: {rules['peak_stage']} ({DISTANCE_RANGES[rules['peak_stage']-1]}km)")
        print(f"  软攻比例: {rules['soft_attack_ratio']}x基准")
        print(f"  硬攻比例: {rules['hard_attack_ratio']}x基准")
        print(f"  描述: {rules['description']}")

    return {
        'benchmark': benchmark,
        'design_rules': design_rules
    }


# =============================================================================
# 执行
# =============================================================================

if __name__ == "__main__":
    # 从combat_logic导入距离定义
    from combat_logic import DISTANCE_RANGES

    generate_optimized_values()