"""
数值表生成器 - 基于数学模型生成CSV数值
========================================

核心原理：
- 基准软攻（每宽度）= 23.42（基于18小时击溃步兵团）
- 基准硬攻（每宽度）= 3.5 × 软攻（坦克对装甲目标）
- 时代缩放：一战0.6x，二战1.0x，冷战1.5x，现代2.5x
- 距离曲线：峰值阶段递减衰减

生成逻辑：
- 步兵武器：软攻主力，硬攻极低，无装甲
- 坦克：硬攻=软攻×2，高装甲，高穿透
- 反坦克炮：硬攻极高，穿透极高
- 机枪/迫击炮：压制高，中近距离
"""

import csv
from typing import Dict, List, Tuple
from pathlib import Path


# =============================================================================
# 数值设计基准
# =============================================================================

# 核心基准值（来自战斗模拟验证）
# 验证历程：
# - 23.42 → 1小时战斗 (太快)
# - 2.93 → 25-28小时战斗 (太慢)
# - 7.5 → 4-5小时战斗 (太快)
# - 4.5 → 17小时战斗 (达标！)
#
# 最终值：4.5，确保装甲团 vs 步兵团战斗时长约17小时
# 符合目标：有堑壕12-24小时区间
BASE_SOFT_ATTACK_PER_WIDTH = 4.5  # 二战基准软攻每宽度（最终验证值）
BASE_HARD_ATTACK_RATIO = 2.0  # 坦克硬攻=软攻×2
BASE_DEFENSE_PER_WIDTH = 3.0  # 二战坦克防御每宽度
BASE_BREAKTHROUGH_RATIO = 0.8  # 突破=防御×0.8

# 时代缩放系数
ERA_SCALING = {
    '一战': 0.6,
    '二战': 1.0,
    '冷战': 1.5,
    '现代': 2.5
}

# 距离区间定义
DISTANCE_RANGES = [
    (0, 0.5),      # 阶段1：贴脸
    (0.5, 1.5),    # 阶段2：超近
    (1.5, 4),      # 阶段3：近
    (4, 8),        # 阶段4：中近
    (8, 20),       # 阶段5：中
    (20, 40),      # 阶段6：中远（开局）
    (40, 80),      # 阶段7：远
    (80, 120),     # 阶段8：超远
    (120, 240),    # 阶段9：极远
    (240, 480),    # 阶段10：超极远
]


# =============================================================================
# 距离曲线生成器
# =============================================================================

def generate_distance_curve(
    peak_stage: int,
    peak_value: float,
    decay_type: str = 'linear',
    decay_rate: float = 0.3,
    min_ratio: float = 0.2
) -> List[float]:
    """
    生成10阶段距离曲线

    参数:
        peak_stage: 峰值阶段（1-10）
        peak_value: 峰值数值
        decay_type: 衰减类型（'linear'线性/'exponential'指数）
        decay_rate: 衰减率
        min_ratio: 最小值比例

    返回:
        10阶段数值列表
    """
    values = []
    for stage in range(1, 11):
        distance = abs(stage - peak_stage)

        if decay_type == 'linear':
            ratio = 1 - decay_rate * distance
        else:  # exponential
            ratio = (1 - decay_rate) ** distance

        ratio = max(min_ratio, ratio)
        values.append(peak_value * ratio)

    return values


def generate_ascending_curve(
    start_stage: int,
    end_stage: int,
    start_value: float,
    end_value: float
) -> List[float]:
    """
    生成递增曲线（从某阶段开始递增）

    用于坦克装甲穿透等远距离有效属性
    """
    values = []
    for stage in range(1, 11):
        if stage < start_stage:
            values.append(start_value * 0.5)
        elif stage > end_stage:
            values.append(end_value)
        else:
            # 线性递增
            progress = (stage - start_stage) / (end_stage - start_stage)
            value = start_value + (end_value - start_value) * progress
            values.append(value)
    return values


# =============================================================================
# 武器数值模板
# =============================================================================

WEAPON_DESIGN_RULES = {
    # ===== 步兵武器 =====
    '栓动步枪': {
        'category': 'infantry',
        'peak_stage': 3,  # 1.5-4km峰值
        'soft_attack_mult': 1.0,  # 基准软攻
        'hard_attack_mult': 0.05,  # 极低硬攻
        'defense_mult': 1.0,
        'breakthrough_mult': 0.3,
        'suppression_mult': 0.5,
        'penetration_mult': 0.0,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.8,
        'trench_defense_mult': 1.0,
        'decay_rate': 0.25,
        'description': '近距离软攻主力'
    },
    '突击步枪': {
        'category': 'infantry',
        'peak_stage': 4,
        'soft_attack_mult': 1.2,
        'hard_attack_mult': 0.1,
        'defense_mult': 1.1,
        'breakthrough_mult': 0.35,
        'suppression_mult': 0.7,
        'penetration_mult': 0.05,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.85,
        'trench_defense_mult': 1.1,
        'decay_rate': 0.25,
        'description': '中近距离均衡'
    },
    '冲锋枪': {
        'category': 'infantry',
        'peak_stage': 2,  # 超近距离峰值
        'soft_attack_mult': 1.3,
        'hard_attack_mult': 0.02,
        'defense_mult': 0.9,
        'breakthrough_mult': 0.25,
        'suppression_mult': 0.4,
        'penetration_mult': 0.0,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.75,
        'trench_defense_mult': 1.0,
        'decay_rate': 0.35,  # 近距离衰减快
        'description': '贴脸战斗专家'
    },
    '机枪': {
        'category': 'support',
        'peak_stage': 5,  # 8-20km峰值
        'soft_attack_mult': 1.5,
        'hard_attack_mult': 0.15,
        'defense_mult': 0.8,
        'breakthrough_mult': 0.2,
        'suppression_mult': 2.5,  # 高压制
        'penetration_mult': 0.1,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.7,
        'trench_defense_mult': 1.0,
        'decay_rate': 0.25,
        'description': '压制专家'
    },

    # ===== 装甲武器 =====
    '轻型坦克': {
        'category': 'armor',
        'peak_stage': 5,
        'soft_attack_mult': 5.0,
        'hard_attack_mult': 8.0,  # 硬攻高于软攻
        'defense_mult': 2.5,
        'breakthrough_mult': 2.0,
        'suppression_mult': 0.8,
        'penetration_mult': 2.0,
        'armor_thickness': 2.0,
        'accuracy_peak': 0.75,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.25,
        'description': '轻装甲侦察'
    },
    '中型坦克': {
        'category': 'armor',
        'peak_stage': 6,
        'soft_attack_mult': 8.0,
        'hard_attack_mult': 15.0,
        'defense_mult': 4.0,
        'breakthrough_mult': 3.2,
        'suppression_mult': 1.0,
        'penetration_mult': 3.0,
        'armor_thickness': 3.5,
        'accuracy_peak': 0.7,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.25,
        'description': '主力坦克'
    },
    '重型坦克': {
        'category': 'armor',
        'peak_stage': 6,
        'soft_attack_mult': 10.0,
        'hard_attack_mult': 20.0,
        'defense_mult': 6.0,
        'breakthrough_mult': 4.8,
        'suppression_mult': 1.2,
        'penetration_mult': 4.0,
        'armor_thickness': 5.0,
        'accuracy_peak': 0.65,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.25,
        'description': '重型突破'
    },
    '主战坦克': {
        'category': 'armor',
        'peak_stage': 6,
        'soft_attack_mult': 15.0,
        'hard_attack_mult': 25.0,
        'defense_mult': 6.0,
        'breakthrough_mult': 5.0,
        'suppression_mult': 1.5,
        'penetration_mult': 5.0,
        'armor_thickness': 5.0,
        'accuracy_peak': 0.8,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.25,
        'description': '现代坦克'
    },

    # ===== 反装甲武器 =====
    '反坦克步枪': {
        'category': 'anti_armor',
        'peak_stage': 3,
        'soft_attack_mult': 0.3,
        'hard_attack_mult': 8.0,
        'defense_mult': 0.8,
        'breakthrough_mult': 0.2,
        'suppression_mult': 0.3,
        'penetration_mult': 5.0,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.85,
        'trench_defense_mult': 0.8,
        'decay_rate': 0.35,
        'description': '早期反坦克'
    },
    '反坦克炮': {
        'category': 'anti_armor',
        'peak_stage': 5,
        'soft_attack_mult': 0.5,
        'hard_attack_mult': 20.0,  # 极高硬攻
        'defense_mult': 0.8,
        'breakthrough_mult': 0.3,
        'suppression_mult': 0.5,
        'penetration_mult': 8.0,  # 极高穿透
        'armor_thickness': 0.0,
        'accuracy_peak': 0.85,
        'trench_defense_mult': 1.0,
        'decay_rate': 0.25,
        'description': '穿甲专家'
    },
    '反坦克歼击车': {
        'category': 'anti_armor',
        'peak_stage': 5,
        'soft_attack_mult': 1.0,
        'hard_attack_mult': 25.0,
        'defense_mult': 1.5,
        'breakthrough_mult': 1.0,
        'suppression_mult': 0.8,
        'penetration_mult': 10.0,
        'armor_thickness': 1.5,
        'accuracy_peak': 0.8,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.25,
        'description': '机动反坦克'
    },

    # ===== 支援武器 =====
    '迫击炮': {
        'category': 'support',
        'peak_stage': 4,
        'soft_attack_mult': 3.0,
        'hard_attack_mult': 2.0,
        'defense_mult': 0.5,
        'breakthrough_mult': 0.15,
        'suppression_mult': 4.0,  # 高压制
        'penetration_mult': 0.2,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.6,
        'trench_defense_mult': 0.6,
        'decay_rate': 0.35,
        'description': '近距离压制'
    },
    '步兵炮': {
        'category': 'support',
        'peak_stage': 5,
        'soft_attack_mult': 4.0,
        'hard_attack_mult': 3.0,
        'defense_mult': 0.5,
        'breakthrough_mult': 0.15,
        'suppression_mult': 3.0,
        'penetration_mult': 0.5,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.65,
        'trench_defense_mult': 0.5,
        'decay_rate': 0.3,
        'description': '步兵支援火炮'
    },
    '野战火炮': {
        'category': 'support',
        'peak_stage': 7,  # 远距离峰值
        'soft_attack_mult': 6.0,
        'hard_attack_mult': 5.0,
        'defense_mult': 0.3,
        'breakthrough_mult': 0.1,
        'suppression_mult': 5.0,
        'penetration_mult': 1.0,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.55,
        'trench_defense_mult': 0.3,
        'decay_rate': 0.2,
        'description': '远程压制'
    },
    '自行火炮': {
        'category': 'support',
        'peak_stage': 7,
        'soft_attack_mult': 8.0,
        'hard_attack_mult': 6.0,
        'defense_mult': 0.8,
        'breakthrough_mult': 0.5,
        'suppression_mult': 6.0,
        'penetration_mult': 1.5,
        'armor_thickness': 0.5,
        'accuracy_peak': 0.6,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.2,
        'description': '机动支援火炮'
    },
    '自行突击炮': {
        'category': 'support',
        'peak_stage': 6,
        'soft_attack_mult': 5.0,
        'hard_attack_mult': 12.0,
        'defense_mult': 2.0,
        'breakthrough_mult': 1.5,
        'suppression_mult': 2.0,
        'penetration_mult': 4.0,
        'armor_thickness': 2.0,
        'accuracy_peak': 0.7,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.25,
        'description': '突击支援'
    },

    # ===== 防空武器 =====
    '防空炮': {
        'category': 'anti_air',
        'peak_stage': 8,  # 远距离防空
        'soft_attack_mult': 0.5,
        'hard_attack_mult': 0.5,
        'defense_mult': 0.5,
        'breakthrough_mult': 0.2,
        'suppression_mult': 0.3,
        'penetration_mult': 0.2,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.5,
        'air_accuracy_peak': 0.7,
        'air_damage_mult': 3.0,
        'trench_defense_mult': 0.5,
        'decay_rate': 0.2,
        'description': '防空火力'
    },
    '防空自行火炮': {
        'category': 'anti_air',
        'peak_stage': 8,
        'soft_attack_mult': 0.8,
        'hard_attack_mult': 0.8,
        'defense_mult': 1.0,
        'breakthrough_mult': 0.3,
        'suppression_mult': 0.5,
        'penetration_mult': 0.3,
        'armor_thickness': 0.3,
        'accuracy_peak': 0.5,
        'air_accuracy_peak': 0.75,
        'air_damage_mult': 5.0,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.2,
        'description': '机动防空'
    },

    # ===== 导弹武器 =====
    '单兵反坦克导弹': {
        'category': 'missile',
        'peak_stage': 4,
        'soft_attack_mult': 1.0,
        'hard_attack_mult': 30.0,  # 极高硬攻
        'defense_mult': 0.3,
        'breakthrough_mult': 0.1,
        'suppression_mult': 0.8,
        'penetration_mult': 15.0,  # 极高穿透
        'armor_thickness': 0.0,
        'accuracy_peak': 0.9,
        'trench_defense_mult': 0.5,
        'decay_rate': 0.3,
        'description': '单兵反坦克导弹'
    },
    '便携式防空导弹': {
        'category': 'anti_air',
        'peak_stage': 5,
        'soft_attack_mult': 0.2,  # 对地攻击能力极低
        'hard_attack_mult': 0.5,
        'defense_mult': 0.3,
        'breakthrough_mult': 0.1,
        'suppression_mult': 0.2,
        'penetration_mult': 0.3,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.6,
        'air_accuracy_peak': 0.9,
        'air_damage_mult': 8.0,
        'trench_defense_mult': 0.5,
        'decay_rate': 0.25,
        'description': '单兵防空导弹'
    },

    # ===== 特殊车辆 =====
    '轮式装甲车': {
        'category': 'armor',
        'peak_stage': 5,
        'soft_attack_mult': 2.0,
        'hard_attack_mult': 3.0,
        'defense_mult': 1.5,
        'breakthrough_mult': 1.2,
        'suppression_mult': 0.6,
        'penetration_mult': 1.0,
        'armor_thickness': 0.8,
        'accuracy_peak': 0.75,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.25,
        'description': '侦察装甲车'
    },
    '履带式步兵战车': {
        'category': 'armor',
        'peak_stage': 5,
        'soft_attack_mult': 4.0,
        'hard_attack_mult': 6.0,
        'defense_mult': 2.5,
        'breakthrough_mult': 2.0,
        'suppression_mult': 1.2,
        'penetration_mult': 2.5,
        'armor_thickness': 2.0,
        'accuracy_peak': 0.8,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.25,
        'description': '步兵战车'
    },
    '无后坐力炮': {
        'category': 'anti_armor',
        'peak_stage': 3,
        'soft_attack_mult': 1.0,
        'hard_attack_mult': 10.0,
        'defense_mult': 0.5,
        'breakthrough_mult': 0.2,
        'suppression_mult': 0.5,
        'penetration_mult': 6.0,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.8,
        'trench_defense_mult': 0.8,
        'decay_rate': 0.35,
        'description': '轻型反装甲'
    },

    # ===== 补充缺失武器 =====
    '支援器材': {
        'category': 'support',
        'peak_stage': 5,
        'soft_attack_mult': 0.2,
        'hard_attack_mult': 0.2,
        'defense_mult': 0.5,
        'breakthrough_mult': 0.1,
        'suppression_mult': 0.3,
        'penetration_mult': 0.0,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.6,
        'trench_defense_mult': 0.5,
        'decay_rate': 0.3,
        'description': '支援器材'
    },
    '无人机': {
        'category': 'support',
        'peak_stage': 7,
        'soft_attack_mult': 1.0,
        'hard_attack_mult': 1.0,
        'defense_mult': 0.2,
        'breakthrough_mult': 0.1,
        'suppression_mult': 2.0,
        'penetration_mult': 0.5,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.9,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.2,
        'description': '无人机侦察打击'
    },
    '火箭炮': {
        'category': 'support',
        'peak_stage': 7,
        'soft_attack_mult': 10.0,
        'hard_attack_mult': 8.0,
        'defense_mult': 0.3,
        'breakthrough_mult': 0.1,
        'suppression_mult': 8.0,
        'penetration_mult': 2.0,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.5,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.15,
        'description': '火箭炮远程压制'
    },
    '通用军车': {
        'category': 'support',
        'peak_stage': 5,
        'soft_attack_mult': 0.1,
        'hard_attack_mult': 0.1,
        'defense_mult': 0.3,
        'breakthrough_mult': 0.1,
        'suppression_mult': 0.1,
        'penetration_mult': 0.0,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.5,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.3,
        'description': '通用军车'
    },
    '重型火炮': {
        'category': 'support',
        'peak_stage': 8,
        'soft_attack_mult': 8.0,
        'hard_attack_mult': 7.0,
        'defense_mult': 0.2,
        'breakthrough_mult': 0.1,
        'suppression_mult': 6.0,
        'penetration_mult': 1.5,
        'armor_thickness': 0.0,
        'accuracy_peak': 0.5,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.15,
        'description': '重型火炮'
    },
    '陆军直升机': {
        'category': 'support',
        'peak_stage': 6,
        'soft_attack_mult': 5.0,
        'hard_attack_mult': 10.0,
        'defense_mult': 0.5,
        'breakthrough_mult': 0.5,
        'suppression_mult': 3.0,
        'penetration_mult': 5.0,
        'armor_thickness': 0.3,
        'accuracy_peak': 0.85,
        'trench_defense_mult': 0.0,
        'decay_rate': 0.25,
        'description': '陆军直升机'
    },
}


# =============================================================================
# CSV数值生成器
# =============================================================================

def generate_weapon_values(
    weapon_type: str,
    era: str,
    cost: float,
    width: int,
    speed: float,
    organization: float,
    hp: float,
    weapon_position: int = 1
) -> Dict:
    """
    生成单个武器的完整数值

    参数:
        weapon_type: 武器种类
        era: 时代
        cost: 成本（不可修改）
        width: 编制宽度（不可修改）
        speed: 速度（不可修改）
        organization: 组织度
        hp: 血量
        weapon_position: 武器定位

    返回:
        包含所有数值的字典
    """
    # 获取武器设计规则
    rules = WEAPON_DESIGN_RULES.get(weapon_type)
    if not rules:
        print(f"DEBUG: 未找到规则: {weapon_type}, 使用默认规则")
        # 默认规则（步兵类）
        rules = {
            'category': 'infantry',
            'peak_stage': 3,
            'soft_attack_mult': 1.0,
            'hard_attack_mult': 0.05,
            'defense_mult': 1.0,
            'breakthrough_mult': 0.3,
            'suppression_mult': 0.5,
            'penetration_mult': 0.0,
            'armor_thickness': 0.0,
            'accuracy_peak': 0.8,
            'trench_defense_mult': 1.0,
            'decay_rate': 0.25,
        }

    # 检查规则是否完整
    required_fields = ['soft_attack_mult', 'hard_attack_mult', 'defense_mult', 'decay_rate', 'peak_stage']
    for field in required_fields:
        if field not in rules:
            print(f"DEBUG: 武器 {weapon_type} 缺少字段 {field}")
            rules[field] = 1.0 if 'mult' in field else 3 if 'stage' in field else 0.25

    # 时代缩放
    era_scale = ERA_SCALING.get(era, 1.0)

    # 计算基准值
    base_soft_attack = BASE_SOFT_ATTACK_PER_WIDTH * era_scale * width
    base_defense = BASE_DEFENSE_PER_WIDTH * era_scale * width

    # 计算峰值数值
    peak_soft_attack = base_soft_attack * rules['soft_attack_mult']
    peak_hard_attack = base_soft_attack * rules['hard_attack_mult']
    peak_defense = base_defense * rules['defense_mult']
    breakthrough_mult = rules.get('breakthrough_mult', 0.5)  # 默认突破倍数
    peak_breakthrough = peak_defense * breakthrough_mult / rules['defense_mult']
    peak_suppression = base_soft_attack * rules.get('suppression_mult', 0.5)
    peak_penetration = base_soft_attack * rules.get('penetration_mult', 0.0) * 0.3  # 穿透值较小

    # 生成10阶段曲线
    soft_attack_stages = generate_distance_curve(
        rules['peak_stage'],
        peak_soft_attack,
        decay_type='linear',
        decay_rate=rules['decay_rate'],
        min_ratio=0.2
    )

    hard_attack_stages = generate_distance_curve(
        rules['peak_stage'],
        peak_hard_attack,
        decay_type='linear',
        decay_rate=rules['decay_rate'],
        min_ratio=0.15
    )

    defense_stages = generate_distance_curve(
        rules['peak_stage'],
        peak_defense,
        decay_type='linear',
        decay_rate=rules.get('defense_decay', 0.15),
        min_ratio=0.5
    )

    breakthrough_stages = generate_distance_curve(
        rules['peak_stage'],
        peak_breakthrough,
        decay_type='linear',
        decay_rate=0.2,
        min_ratio=0.4
    )

    suppression_stages = generate_distance_curve(
        rules['peak_stage'],
        peak_suppression,
        decay_type='linear',
        decay_rate=rules['decay_rate'],
        min_ratio=0.2
    )

    penetration_stages = generate_distance_curve(
        rules['peak_stage'],
        peak_penetration,
        decay_type='linear',
        decay_rate=rules['decay_rate'] * 0.8,
        min_ratio=0.3
    )

    accuracy_peak = rules.get('accuracy_peak', 0.75)  # 默认命中率峰值
    accuracy_stages = generate_distance_curve(
        rules['peak_stage'],
        accuracy_peak,
        decay_type='linear',
        decay_rate=0.2,
        min_ratio=0.4
    )

    # 堑壕防御（仅步兵和支援）
    trench_defense = 0.0
    trench_mult = rules.get('trench_defense_mult', 0.0)
    if rules['category'] in ['infantry', 'anti_armor'] and trench_mult > 0:
        trench_defense = 25.0 * era_scale * trench_mult

    armor_thickness = rules.get('armor_thickness', 0.0) * era_scale

    return {
        'weapon_type': weapon_type,
        'era': era,
        'cost': cost,
        'width': width,
        'speed': speed,
        'organization': organization,
        'hp': hp,
        'weapon_position': weapon_position,

        # 10阶段数值
        'soft_attack': soft_attack_stages,
        'hard_attack': hard_attack_stages,
        'defense': defense_stages,
        'breakthrough': breakthrough_stages,
        'suppression': suppression_stages,
        'penetration': penetration_stages,
        'accuracy': accuracy_stages,

        # 单值属性
        'armor_thickness': armor_thickness,
        'trench_defense': trench_defense,

        # 侦察（基础值）
        'recon': [0.1 * era_scale * (1 - 0.1 * abs(s - 6)) for s in range(1, 11)],

        # 火控（基础值）
        'fire_control': [0.1 * era_scale] * 10,

        # 电子战（基础值）
        'electronic_jammer': [0.0] * 10,
        'electronic_resistance': [0.0] * 10,

        # 环境适应性（全部设为1.0基准）
        'environment_adaptations': {},

        # 对空/对海（默认0）
        'air_accuracy': [0.0] * 10,
        'air_damage': [0.0] * 10,
        'sea_accuracy': [0.0] * 10,
        'sea_penetration': [0.0] * 10,
        'sea_damage': [0.0] * 10,
    }


def format_10_stage_value(values: List[float]) -> str:
    """格式化10阶段数值为CSV字符串"""
    return '='.join([f"{v:.4f}" for v in values])


def generate_new_army_csv(
    input_csv_path: str,
    output_csv_path: str
) -> Dict:
    """
    生成新的army.csv文件

    参数:
        input_csv_path: 原CSV路径
        output_csv_path: 输出CSV路径

    返回:
        生成统计
    """
    stats = {
        'total_weapons': 0,
        'weapons_by_era': {},
        'changes_log': []
    }

    # 读取原始CSV获取不可修改的列
    with open(input_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    # 生成新数值
    new_rows = []
    new_rows.append(header)  # 保持原表头

    for row in rows:
        weapon_type = row[0]
        era = row[1]
        cost = float(row[2]) if row[2] else 1.0
        width = int(row[5]) if row[5] else 1  # 默认宽度1
        speed = float(row[47]) if len(row) > 47 and row[47] else 5.0

        # 获取组织度和血量
        org = float(row[6]) if len(row) > 6 and row[6] else 30.0
        hp = float(row[50]) if len(row) > 50 and row[50] else 30.0
        weapon_pos = int(row[56]) if len(row) > 56 and row[56] else 1

        # 生成新数值
        values = generate_weapon_values(
            weapon_type, era, cost, width, speed, org, hp, weapon_pos
        )

        # 记录统计
        stats['total_weapons'] += 1
        stats['weapons_by_era'][era] = stats['weapons_by_era'].get(era, 0) + 1

        # 构建新行（保持不可修改列不变）
        new_row = row.copy()

        # 更新10阶段数值列
        # 列8: 侦查
        new_row[7] = format_10_stage_value(values['recon'])
        # 列9: 防御
        new_row[8] = format_10_stage_value(values['defense'])
        # 列10: 装甲厚度
        new_row[9] = f"{values['armor_thickness']:.3f}"
        # 列11-13: 火控/电子干扰/电子抗性
        new_row[10] = format_10_stage_value(values['fire_control'])
        new_row[11] = format_10_stage_value(values['electronic_jammer'])
        new_row[12] = format_10_stage_value(values['electronic_resistance'])
        # 列18: 对地命中
        new_row[16] = format_10_stage_value(values['accuracy'])
        # 列19: 对地穿透
        new_row[17] = format_10_stage_value(values['penetration'])
        # 列20: 对地压制
        new_row[18] = format_10_stage_value(values['suppression'])
        # 列52: 堑壕防御
        new_row[52] = f"{values['trench_defense']:.2f}"
        # 列53: 对地硬攻
        new_row[53] = format_10_stage_value(values['hard_attack'])
        # 列54: 对地软攻
        new_row[54] = format_10_stage_value(values['soft_attack'])
        # 列55: 突破（取平均值）
        avg_breakthrough = sum(values['breakthrough']) / 10
        new_row[51] = f"{avg_breakthrough:.3f}"

        new_rows.append(new_row)

        # 记录变更
        stats['changes_log'].append({
            'weapon': weapon_type,
            'era': era,
            'old_soft_avg': '原有值',
            'new_soft_avg': sum(values['soft_attack']) / 10,
            'new_hard_avg': sum(values['hard_attack']) / 10,
        })

    # 写入新CSV
    with open(output_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)

    return stats


# =============================================================================
# 平衡性报告生成器
# =============================================================================

def generate_balance_report(stats: Dict) -> str:
    """生成平衡性报告"""
    report = []
    report.append("=" * 70)
    report.append("数值平衡设计报告")
    report.append("=" * 70)

    report.append("\n【设计基准】")
    report.append(f"- 二战基准软攻（每宽度）: {BASE_SOFT_ATTACK_PER_WIDTH:.2f}")
    report.append(f"- 目标战斗时长: 有堑壕12-24h，无堑壕6-12h")
    report.append(f"- 时代缩放: 一战0.6x → 二战1.0x → 冷战1.5x → 现代2.5x")

    report.append("\n【设计原则】")
    report.append("1. 坦克压制步兵: 硬攻=软攻×2，装甲穿透极高")
    report.append("2. 反坦克炮克制坦克: 硬攻极高，穿透是坦克的2倍")
    report.append("3. 步兵克制步兵: 软攻主力，近距离峰值")
    report.append("4. 机枪压制: 高压制值，影响推进度")
    report.append("5. 火炮支援: 远距离压制，低防御")

    report.append("\n【距离差异化】")
    report.append("- 步枪: 阶段3峰值（1.5-4km），近距离强")
    report.append("- 坦克: 阶段6峰值（20-40km），中远距离强")
    report.append("- 火炮: 阶段7峰值（40-80km），远程压制")
    report.append("- 反坦克炮: 阶段5峰值（8-20km），中距离穿甲")

    report.append("\n【无敌单位排除】")
    report.append("- 坦克: 软攻高但可被反坦克炮硬攻克制")
    report.append("- 反坦克炮: 硬攻极高但软攻极低，无法单独作战")
    report.append("- 步兵: 数量多但无装甲，坦克硬攻可碾压")
    report.append("- 机枪: 压制高但防御低，可被火炮压制")

    report.append("\n【生成统计】")
    report.append(f"- 总武器数量: {stats['total_weapons']}")
    for era, count in stats['weapons_by_era'].items():
        report.append(f"- {era}时期: {count}种武器")

    report.append("\n【成本匹配验证】")
    report.append("- 坦克成本高 → 面板显著强于步枪集群")
    report.append("- 反坦克炮成本低 → 专项克制，不全能")
    report.append("- 步枪成本最低 → 数量弥补面板劣势")

    return '\n'.join(report)


# =============================================================================
# 测试
# =============================================================================

def test_value_generation():
    """测试数值生成"""
    print("=" * 70)
    print("数值生成器测试")
    print("=" * 70)

    # 测试几种关键武器
    test_weapons = ['栓动步枪', '中型坦克', '反坦克炮', '机枪']

    for weapon in test_weapons:
        values = generate_weapon_values(
            weapon, '二战', 100, 5, 20, 35, 35,
            weapon_position=2 if '坦克' in weapon else 1
        )

        print(f"\n【{weapon}】（二战）")
        print(f"  峰值软攻: {max(values['soft_attack']):.2f}")
        print(f"  峰值硬攻: {max(values['hard_attack']):.2f}")
        print(f"  峰值防御: {max(values['defense']):.2f}")
        print(f"  装甲厚度: {values['armor_thickness']:.2f}")
        print(f"  堑壕防御: {values['trench_defense']:.2f}")
        print(f"  软攻曲线: {format_10_stage_value(values['soft_attack'])}")


if __name__ == "__main__":
    test_value_generation()