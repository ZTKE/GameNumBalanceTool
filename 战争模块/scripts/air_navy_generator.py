"""
空军海军数值生成器
==================

设计原则：
- 空军：防御填0，高爆发性（1-2小时结算），高伤低防
- 海军：装甲厚度重要，轻炮/重炮/鱼雷/导弹分类，鱼雷近程致命
- 时代缩放：一战0.6x, 二战1.0x, 冷战1.5x, 现代2.5x
- 战斗节奏：空战高爆发(1-2小时)，海战决战(6-8小时)
- 跨维度：空对地/海一波次(1小时)显著伤害，地对空3-6小时重创空军
"""

import csv
import copy
from typing import Dict, List, Tuple
from pathlib import Path
from dataclasses import dataclass, field


# =============================================================================
# 基准数值
# =============================================================================

# 空军基准值（每宽度）- 基于高爆发目标设计
# 目标时长：空战1-2小时（高爆发结算）
# 特性：高伤害、低生存（血量35、防御0）
#
# 验证历程：
# - 25.0 → 32小时（太慢）
# - 400.0 → 5小时（仍慢）
# - 需要提高到约1000才能达到1-2小时目标
# 调整到1000.0 → 预期空战约1小时
BASE_AIR_HP = 35.0                 # 空军血量基准（脆弱设计）
BASE_AIR_ORGANIZATION = 35.0       # 空军组织度基准
BASE_AIR_TO_GROUND_DAMAGE = 200.0  # 空对地伤害基准（高爆发，一波次6%组织度损伤）
BASE_AIR_TO_AIR_DAMAGE = 1200.0    # 空对空伤害基准（高爆发，缩短空战到1-2h）
BASE_AIR_TO_SEA_DAMAGE = 150.0     # 空对海伤害基准（对舰高爆发）
BASE_AIR_SPEED = 500               # 空军速度基准(km/h)

# 海军基准值（每宽度）- 基于舰队决战目标设计
# 目标时长：6-8小时决战
# 特性：鱼雷近程致命，导弹远程压制
#
# 验证历程：
# - 50.0鱼雷/100结构 → 3小时（太快）
# - 25.0鱼雷/150结构 → 2小时（仍快）
# 调整：进一步降低伤害，大幅提高结构值
BASE_NAVY_LIGHT_GUN_DAMAGE = 4.5    # 轻炮对海伤害（提高缩短战斗）
BASE_NAVY_HEAVY_GUN_DAMAGE = 9.0    # 重炮对海伤害（提高缩短战斗）
BASE_NAVY_TORPEDO_DAMAGE = 25.0     # 鱼雷对海伤害（提高缩短战斗）
BASE_NAVY_MISSILE_DAMAGE = 15.0     # 导弹对海伤害（提高缩短战斗）
BASE_NAVY_DEFENSE = 25.0            # 海军防御基准
BASE_NAVY_STRUCTURE = 120.0         # 结构值基准（调整到目标6-8h）
BASE_NAVY_SPEED = 30                # 海军速度基准(km/h)

# 时代缩放
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
    (20, 40),      # 阶段6：中远
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
    """生成10阶段距离曲线"""
    values = []
    for stage in range(1, 11):
        distance = abs(stage - peak_stage)
        if decay_type == 'linear':
            ratio = 1 - decay_rate * distance
        else:
            ratio = (1 - decay_rate) ** distance
        ratio = max(min_ratio, ratio)
        values.append(peak_value * ratio)
    return values


def format_10_stage_value(values: List[float]) -> str:
    """格式化10阶段数值为CSV字符串"""
    return '='.join([f"{v:.4f}" for v in values])


# =============================================================================
# 空军武器设计规则
# =============================================================================

def find_air_rules(weapon_type: str) -> dict:
    """根据武器类型查找匹配的设计规则"""
    # 精确匹配
    if weapon_type in AIR_WEAPON_DESIGN_RULES:
        return AIR_WEAPON_DESIGN_RULES[weapon_type]

    # 部分匹配 - 按关键词匹配
    keywords_map = {
        '战斗机': '轻型战斗机',
        '轰炸机': '战术轰炸机',
        '强击机': '强击机',
        '喷气机': '早期喷气机',
        '侦察机': '侦察机',
        '直升机': '直升机',
        '运输机': '运输机'
    }

    for keyword, fallback_key in keywords_map.items():
        if keyword in weapon_type:
            if fallback_key in AIR_WEAPON_DESIGN_RULES:
                return AIR_WEAPON_DESIGN_RULES[fallback_key]

    # 默认返回轻型战斗机规则
    return AIR_WEAPON_DESIGN_RULES['轻型战斗机']


AIR_WEAPON_DESIGN_RULES = {
    # ===== 战斗机类 =====
    '轻型战斗机': {
        'category': 'fighter',
        'peak_stage': 5,
        'air_to_air_mult': 1.0,        # 空对空基准
        'air_to_ground_mult': 0.3,     # 空对地较弱
        'air_to_sea_mult': 0.2,        # 空对海较弱
        'intercept_mult': 1.2,         # 拦截能力强
        'speed_mult': 1.0,
        'accuracy_peak': 0.85,
        'fire_control_mult': 1.0,
        'radar_strength': 0.2,         # 战斗机雷达（二战0.2→冷战0.3→现代0.5）
        'radar_radius': 50,            # 雷达探测半径
        'range_km': 500,
        'altitude_peak': 5,            # 中高空
        'hp_mult': 1.0,                # 战斗机血量基准
        'org_mult': 1.0,               # 战斗机组织度基准
        'decay_rate': 0.25,
        'description': '轻型战斗机'
    },
    '多用途战斗机': {
        'category': 'fighter',
        'peak_stage': 6,
        'air_to_air_mult': 0.8,
        'air_to_ground_mult': 0.8,
        'air_to_sea_mult': 0.5,
        'intercept_mult': 1.0,
        'speed_mult': 1.2,
        'accuracy_peak': 0.85,
        'fire_control_mult': 1.2,
        'radar_strength': 0.4,         # 多用途战斗机雷达更强
        'radar_radius': 80,
        'range_km': 800,
        'altitude_peak': 6,
        'decay_rate': 0.25,
        'description': '多用途战斗机'
    },
    '早期喷气机': {
        'category': 'fighter',
        'peak_stage': 6,
        'air_to_air_mult': 1.5,
        'air_to_ground_mult': 0.4,
        'air_to_sea_mult': 0.3,
        'intercept_mult': 1.3,
        'speed_mult': 1.5,
        'accuracy_peak': 0.8,
        'fire_control_mult': 1.0,
        'radar_strength': 0.3,         # 早期喷气机雷达
        'radar_radius': 60,
        'range_km': 600,
        'altitude_peak': 7,
        'decay_rate': 0.2,
        'description': '早期喷气机'
    },
    '对海战斗机': {
        'category': 'fighter',
        'peak_stage': 5,
        'air_to_air_mult': 0.6,
        'air_to_ground_mult': 0.2,
        'air_to_sea_mult': 1.0,
        'intercept_mult': 0.8,
        'speed_mult': 1.0,
        'accuracy_peak': 0.75,
        'fire_control_mult': 1.0,
        'radar_strength': 0.35,        # 对海战斗机雷达偏向海面探测
        'radar_radius': 70,
        'range_km': 400,
        'altitude_peak': 4,
        'decay_rate': 0.3,
        'description': '对海战斗机'
    },

    # ===== 轰炸机类 =====
    '战术轰炸机': {
        'category': 'bomber',
        'peak_stage': 6,
        'air_to_air_mult': 0.1,
        'air_to_ground_mult': 1.0,
        'air_to_sea_mult': 0.5,
        'intercept_mult': 0.2,
        'speed_mult': 0.8,
        'accuracy_peak': 0.7,
        'fire_control_mult': 0.8,
        'radar_strength': 0.3,         # 战术轰炸机雷达
        'radar_radius': 60,
        'range_km': 1000,
        'altitude_peak': 6,
        'ground_damage_mult': 2.0,     # 对地伤害高
        'penetration_mult': 1.5,
        'decay_rate': 0.2,
        'description': '战术轰炸机'
    },
    '战略轰炸机': {
        'category': 'bomber',
        'peak_stage': 8,
        'air_to_air_mult': 0.05,
        'air_to_ground_mult': 0.8,
        'air_to_sea_mult': 0.3,
        'intercept_mult': 0.1,
        'speed_mult': 0.6,
        'accuracy_peak': 0.5,
        'fire_control_mult': 0.6,
        'radar_strength': 0.4,         # 战略轰炸机雷达较强
        'radar_radius': 100,
        'range_km': 2000,
        'altitude_peak': 8,
        'ground_damage_mult': 5.0,     # 对地伤害极高
        'penetration_mult': 2.0,
        'suppression_mult': 3.0,
        'decay_rate': 0.15,
        'description': '战略轰炸机'
    },
    '强击机': {
        'category': 'bomber',
        'peak_stage': 4,
        'air_to_air_mult': 0.2,
        'air_to_ground_mult': 1.5,
        'air_to_sea_mult': 0.3,
        'intercept_mult': 0.3,
        'speed_mult': 0.9,
        'accuracy_peak': 0.9,          # 近距离高命中
        'fire_control_mult': 1.0,
        'radar_strength': 0.15,        # 强击机雷达较弱（低空突防为主）
        'radar_radius': 30,
        'range_km': 500,
        'altitude_peak': 3,            # 低空突防
        'ground_damage_mult': 2.5,
        'penetration_mult': 2.0,
        'decay_rate': 0.35,
        'description': '强击机/攻击机'
    },
    '对海轰炸机': {
        'category': 'bomber',
        'peak_stage': 5,
        'air_to_air_mult': 0.1,
        'air_to_ground_mult': 0.2,
        'air_to_sea_mult': 1.5,
        'intercept_mult': 0.2,
        'speed_mult': 0.7,
        'accuracy_peak': 0.75,
        'fire_control_mult': 0.8,
        'radar_strength': 0.35,        # 对海轰炸机雷达偏向海面
        'radar_radius': 70,
        'range_km': 800,
        'altitude_peak': 5,
        'sea_damage_mult': 2.0,
        'decay_rate': 0.25,
        'description': '对海轰炸机'
    },

    # ===== 支援飞机 =====
    '侦察机': {
        'category': 'support',
        'peak_stage': 7,
        'air_to_air_mult': 0.0,
        'air_to_ground_mult': 0.0,
        'recon_mult': 2.0,             # 高侦察
        'radar_strength': 0.8,         # 侦察机雷达最强
        'radar_radius': 200,
        'ground_detection': 0.7,
        'speed_mult': 1.1,
        'range_km': 1500,
        'altitude_peak': 7,
        'decay_rate': 0.15,
        'description': '侦察机'
    },
    '运输机': {
        'category': 'support',
        'peak_stage': 5,
        'air_to_air_mult': 0.0,
        'air_to_ground_mult': 0.0,
        'radar_strength': 0.1,         # 运输机雷达较弱
        'radar_radius': 20,
        'speed_mult': 0.5,
        'range_km': 2000,
        'altitude_peak': 6,
        'decay_rate': 0.2,
        'description': '运输机'
    },
    '电子战飞机': {
        'category': 'support',
        'peak_stage': 6,
        'air_to_air_mult': 0.0,
        'air_to_ground_mult': 0.0,
        'electronic_jammer_mult': 2.0,
        'radar_strength': 0.6,         # 电子战飞机雷达强
        'radar_radius': 150,
        'electronic_resistance_mult': 2.0,
        'speed_mult': 0.8,
        'range_km': 1000,
        'altitude_peak': 6,
        'decay_rate': 0.2,
        'description': '电子战飞机'
    },
    '空中加油机': {
        'category': 'support',
        'peak_stage': 5,
        'air_to_air_mult': 0.0,
        'air_to_ground_mult': 0.0,
        'radar_strength': 0.1,         # 加油机雷达较弱
        'radar_radius': 30,
        'speed_mult': 0.6,
        'range_km': 3000,
        'altitude_peak': 6,
        'decay_rate': 0.2,
        'description': '空中加油机'
    },
    '海军直升机': {
        'category': 'support',
        'peak_stage': 4,
        'air_to_air_mult': 0.0,
        'air_to_ground_mult': 0.2,
        'air_to_sea_mult': 0.5,
        'sub_detection_mult': 1.5,     # 反潜能力强
        'radar_strength': 0.25,        # 直升机雷达（海面探测）
        'radar_radius': 40,
        'speed_mult': 0.2,
        'range_km': 200,
        'altitude_peak': 2,
        'decay_rate': 0.4,
        'description': '海军直升机'
    },

    # ===== 导弹 =====
    '地对地导弹': {
        'category': 'missile',
        'peak_stage': 9,
        'ground_damage_mult': 10.0,
        'penetration_mult': 5.0,
        'accuracy_peak': 0.6,
        'decay_rate': 0.1,
        'description': '地对地导弹'
    },
    '地对空导弹': {
        'category': 'missile',
        'peak_stage': 8,
        'air_damage_mult': 8.0,
        'accuracy_peak': 0.8,
        'decay_rate': 0.15,
        'description': '地对空导弹'
    },
}


# =============================================================================
# 海军武器设计规则
# =============================================================================

NAVY_WEAPON_DESIGN_RULES = {
    # ===== 主力舰 =====
    '战列舰': {
        'category': 'capital',
        'peak_stage': 6,
        'heavy_gun_mult': 3.0,         # 重炮主力
        'light_gun_mult': 1.0,
        'torpedo_mult': 0.5,
        'missile_mult': 0.0,
        'defense_mult': 3.0,           # 高防御
        'armor_thickness': 300,        # 重甲
        'structure_mult': 5.0,
        'speed_mult': 0.7,
        'fire_control_mult': 1.0,
        'accuracy_peak': 0.6,
        'armor_type': 1,               # 重甲船
        'radar_strength': 0.5,         # 战列舰雷达
        'radar_radius': 100,
        'ground_detection': 0.2,       # 对地探测较弱
        'decay_rate': 0.2,
        'description': '战列舰'
    },
    '战列巡洋舰': {
        'category': 'capital',
        'peak_stage': 6,
        'heavy_gun_mult': 2.5,
        'light_gun_mult': 1.5,
        'torpedo_mult': 0.8,
        'missile_mult': 0.0,
        'defense_mult': 2.5,
        'armor_thickness': 200,
        'structure_mult': 4.0,
        'speed_mult': 1.0,             # 比战列舰快
        'fire_control_mult': 1.2,
        'accuracy_peak': 0.65,
        'armor_type': 1,
        'radar_strength': 0.4,         # 战列巡洋舰雷达
        'radar_radius': 80,
        'ground_detection': 0.15,
        'decay_rate': 0.2,
        'description': '战列巡洋舰'
    },
    '航空母舰': {
        'category': 'carrier',
        'peak_stage': 7,
        'heavy_gun_mult': 0.5,
        'light_gun_mult': 0.5,
        'torpedo_mult': 0.0,
        'missile_mult': 0.5,
        'defense_mult': 1.5,
        'armor_thickness': 50,
        'structure_mult': 4.0,
        'speed_mult': 0.9,
        'fire_control_mult': 1.5,
        'accuracy_peak': 0.5,
        'armor_type': 1,
        'radar_strength': 1.0,         # 航母雷达最强
        'radar_radius': 300,
        'ground_detection': 0.5,       # 航母对地探测较强
        'decay_rate': 0.15,
        'description': '航空母舰'
    },
    '轻型航空母舰': {
        'category': 'carrier',
        'peak_stage': 6,
        'heavy_gun_mult': 0.3,
        'light_gun_mult': 0.5,
        'torpedo_mult': 0.0,
        'missile_mult': 0.3,
        'defense_mult': 1.0,
        'armor_thickness': 30,
        'structure_mult': 2.5,
        'speed_mult': 0.8,
        'fire_control_mult': 1.2,
        'accuracy_peak': 0.5,
        'armor_type': 1,
        'radar_strength': 0.8,
        'radar_radius': 200,
        'ground_detection': 0.4,
        'decay_rate': 0.2,
        'description': '轻型航空母舰'
    },
    '导弹巡洋舰': {
        'category': 'cruiser',
        'peak_stage': 7,
        'heavy_gun_mult': 1.0,
        'light_gun_mult': 1.0,
        'torpedo_mult': 0.5,
        'missile_mult': 3.0,           # 导弹主力
        'defense_mult': 2.0,
        'armor_thickness': 80,
        'structure_mult': 3.0,
        'speed_mult': 1.2,
        'fire_control_mult': 2.0,
        'accuracy_peak': 0.8,
        'armor_type': 1,
        'radar_strength': 0.9,         # 导弹巡洋舰雷达强
        'radar_radius': 250,
        'ground_detection': 0.6,       # 导弹需要强对地探测
        'decay_rate': 0.15,
        'description': '导弹巡洋舰'
    },

    # ===== 巡洋舰 =====
    '重型巡洋舰': {
        'category': 'cruiser',
        'peak_stage': 6,
        'heavy_gun_mult': 2.0,
        'light_gun_mult': 1.0,
        'torpedo_mult': 1.0,
        'missile_mult': 0.0,
        'defense_mult': 2.0,
        'armor_thickness': 100,
        'structure_mult': 2.5,
        'speed_mult': 1.0,
        'fire_control_mult': 1.2,
        'accuracy_peak': 0.65,
        'armor_type': 1,
        'radar_strength': 0.5,
        'radar_radius': 100,
        'ground_detection': 0.2,
        'decay_rate': 0.2,
        'description': '重型巡洋舰'
    },
    '轻型巡洋舰': {
        'category': 'cruiser',
        'peak_stage': 5,
        'heavy_gun_mult': 0.5,
        'light_gun_mult': 2.0,         # 炮主力
        'torpedo_mult': 1.5,
        'missile_mult': 0.0,
        'defense_mult': 1.5,
        'armor_thickness': 50,
        'structure_mult': 2.0,
        'speed_mult': 1.2,
        'fire_control_mult': 1.3,
        'accuracy_peak': 0.7,
        'armor_type': 0,               # 轻甲船
        'radar_strength': 0.4,
        'radar_radius': 80,
        'ground_detection': 0.15,
        'decay_rate': 0.25,
        'description': '轻型巡洋舰'
    },

    # ===== 驱逐舰/护卫舰 =====
    '驱逐舰': {
        'category': 'destroyer',
        'peak_stage': 5,
        'heavy_gun_mult': 0.3,
        'light_gun_mult': 1.5,
        'torpedo_mult': 2.0,           # 鱼雷主力
        'missile_mult': 0.5,
        'defense_mult': 1.0,
        'armor_thickness': 20,
        'structure_mult': 1.0,
        'speed_mult': 1.5,             # 高速
        'fire_control_mult': 1.5,
        'accuracy_peak': 0.75,
        'armor_type': 0,
        'radar_strength': 0.3,
        'radar_radius': 60,
        'ground_detection': 0.1,
        'sub_detection_mult': 1.0,
        'decay_rate': 0.25,
        'description': '驱逐舰'
    },
    '护卫舰': {
        'category': 'destroyer',
        'peak_stage': 5,
        'heavy_gun_mult': 0.0,
        'light_gun_mult': 1.0,
        'torpedo_mult': 0.5,
        'missile_mult': 1.0,
        'defense_mult': 0.8,
        'armor_thickness': 10,
        'structure_mult': 0.8,
        'speed_mult': 1.3,
        'fire_control_mult': 1.5,
        'accuracy_peak': 0.75,
        'armor_type': 0,
        'radar_strength': 0.25,
        'radar_radius': 50,
        'ground_detection': 0.1,
        'sub_detection_mult': 1.5,     # 反潜强
        'decay_rate': 0.25,
        'description': '护卫舰'
    },

    # ===== 潜艇 =====
    '常规潜艇': {
        'category': 'submarine',
        'peak_stage': 4,               # 近程峰值（0.5-4km）
        'torpedo_mult': 4.0,           # 鱼雷极高（近程致命）
        'missile_mult': 0.0,
        'defense_mult': 0.3,
        'armor_thickness': 0,
        'structure_mult': 0.5,
        'speed_mult': 0.3,             # 潜艇慢
        'fire_control_mult': 0.8,
        'accuracy_peak': 0.85,         # 近程高命中
        'sub_stealth': 0.8,            # 高隐身
        'armor_type': 0,
        'radar_strength': 0.0,         # 潜艇无雷达（用声呐）
        'radar_radius': 0,
        'ground_detection': 0.0,
        'decay_rate': 0.35,            # 近程衰减快
        'description': '常规潜艇（近程致命）'
    },
    '攻击核潜艇': {
        'category': 'submarine',
        'peak_stage': 5,
        'torpedo_mult': 4.0,
        'missile_mult': 1.5,
        'defense_mult': 0.5,
        'armor_thickness': 0,
        'structure_mult': 1.0,
        'speed_mult': 0.6,             # 核潜艇较快
        'fire_control_mult': 1.5,
        'accuracy_peak': 0.85,
        'sub_stealth': 0.9,
        'armor_type': 0,
        'decay_rate': 0.25,
        'description': '攻击核潜艇'
    },
    '战略核潜艇': {
        'category': 'submarine',
        'peak_stage': 6,
        'torpedo_mult': 2.0,
        'missile_mult': 5.0,           # 导弹极高
        'defense_mult': 0.5,
        'armor_thickness': 0,
        'structure_mult': 1.5,
        'speed_mult': 0.5,
        'fire_control_mult': 2.0,
        'accuracy_peak': 0.7,
        'sub_stealth': 0.95,           # 最高隐身
        'armor_type': 0,
        'decay_rate': 0.2,
        'description': '战略核潜艇'
    },

    # ===== 支援舰 =====
    '补给舰': {
        'category': 'support',
        'peak_stage': 4,
        'defense_mult': 0.3,
        'armor_thickness': 0,
        'structure_mult': 0.5,
        'speed_mult': 0.4,
        'decay_rate': 0.3,
        'description': '补给舰'
    },
    '两栖攻击舰': {
        'category': 'support',
        'peak_stage': 5,
        'light_gun_mult': 0.5,
        'missile_mult': 0.5,
        'defense_mult': 1.0,
        'armor_thickness': 30,
        'structure_mult': 2.0,
        'speed_mult': 0.6,
        'accuracy_peak': 0.5,
        'armor_type': 1,
        'decay_rate': 0.25,
        'description': '两栖攻击舰'
    },
    '两栖登陆舰': {
        'category': 'support',
        'peak_stage': 4,
        'defense_mult': 0.8,
        'armor_thickness': 20,
        'structure_mult': 1.5,
        'speed_mult': 0.5,
        'armor_type': 0,
        'decay_rate': 0.3,
        'description': '两栖登陆舰'
    },
}


# =============================================================================
# 空军数值生成
# =============================================================================

def generate_air_weapon_values(
    weapon_type: str,
    era: str,
    cost: float,
    width: int,
    speed: float,
    organization: float,
    hp: float
) -> Dict:
    """生成空军武器数值"""

    rules = AIR_WEAPON_DESIGN_RULES.get(weapon_type)
    if not rules:
        rules = {
            'category': 'fighter',
            'peak_stage': 5,
            'air_to_air_mult': 0.5,
            'air_to_ground_mult': 0.5,
            'speed_mult': 1.0,
            'accuracy_peak': 0.75,
            'decay_rate': 0.25,
        }

    era_scale = ERA_SCALING.get(era, 1.0)

    # 基准计算
    base_damage = BASE_AIR_TO_GROUND_DAMAGE * era_scale * width

    # 血量和组织度计算（使用基准值和倍率）
    base_hp = BASE_AIR_HP * width * era_scale * rules.get('hp_mult', 1.0)
    base_org = BASE_AIR_ORGANIZATION * width * era_scale * rules.get('org_mult', 1.0)

    # 峰值数值
    peak_air_to_ground = base_damage * rules.get('air_to_ground_mult', 0.5)
    peak_air_to_air = BASE_AIR_TO_AIR_DAMAGE * era_scale * width * rules.get('air_to_air_mult', 0.5)
    peak_air_to_sea = BASE_AIR_TO_SEA_DAMAGE * era_scale * width * rules.get('air_to_sea_mult', 0.3)
    peak_ground_damage = base_damage * rules.get('ground_damage_mult', 1.0)
    peak_intercept = base_damage * rules.get('intercept_mult', 0.5) * 0.1

    # 生成曲线
    air_to_ground_stages = generate_distance_curve(
        rules['peak_stage'], peak_air_to_ground, decay_rate=rules.get('decay_rate', 0.25)
    )

    air_to_air_stages = generate_distance_curve(
        rules['peak_stage'], peak_air_to_air, decay_rate=rules.get('decay_rate', 0.25)
    )

    air_to_sea_stages = generate_distance_curve(
        rules['peak_stage'], peak_air_to_sea, decay_rate=rules.get('decay_rate', 0.25)
    )

    ground_damage_stages = generate_distance_curve(
        rules['peak_stage'], peak_ground_damage, decay_rate=rules.get('decay_rate', 0.25)
    )

    intercept_stages = generate_distance_curve(
        rules['peak_stage'], peak_intercept, decay_rate=0.2, min_ratio=0.3
    )

    accuracy_stages = generate_distance_curve(
        rules['peak_stage'], rules.get('accuracy_peak', 0.75), decay_rate=0.2, min_ratio=0.4
    )

    # 侦察
    recon_stages = generate_distance_curve(
        rules['peak_stage'],
        0.1 * era_scale * rules.get('recon_mult', 1.0),
        decay_rate=0.15
    )

    # 火控
    fire_control_stages = [0.1 * era_scale * rules.get('fire_control_mult', 1.0)] * 10

    # 防御填0（空军无防御）
    defense_stages = [0.0] * 10

    # 雷达相关
    radar_strength = rules.get('radar_strength', 0.0) * era_scale
    radar_radius = rules.get('radar_radius', 0)
    ground_detection = rules.get('ground_detection', 0.0) * era_scale

    return {
        'weapon_type': weapon_type,
        'era': era,
        'cost': cost,
        'width': width,
        'speed': speed * rules.get('speed_mult', 1.0),
        'organization': base_org,      # 使用计算的基准组织度
        'hp': base_hp,                 # 使用计算的基准血量

        # 10阶段数值
        'recon': recon_stages,
        'defense': defense_stages,
        'fire_control': fire_control_stages,
        'air_accuracy': accuracy_stages,
        'air_to_ground': air_to_ground_stages,
        'air_to_air': air_to_air_stages,
        'air_to_sea': air_to_sea_stages,
        'ground_damage': ground_damage_stages,
        'intercept': intercept_stages,

        # 电子战
        'electronic_jammer': [0.05 * era_scale * rules.get('electronic_jammer_mult', 1.0)] * 10,
        'electronic_resistance': [0.05 * era_scale * rules.get('electronic_resistance_mult', 1.0)] * 10,

        # 雷达
        'radar_strength': radar_strength,
        'radar_radius': radar_radius,
        'ground_detection': ground_detection,

        # 其他
        'armor_thickness': 0.0,
        'range_km': rules.get('range_km', 500),
        'altitude_peak': rules.get('altitude_peak', 5),
    }


# =============================================================================
# 海军数值生成
# =============================================================================

def generate_navy_weapon_values(
    weapon_type: str,
    era: str,
    cost: float,
    width: int,
    speed: float,
    organization: float,
    structure: float,
    buoyancy: float
) -> Dict:
    """生成海军武器数值"""

    rules = NAVY_WEAPON_DESIGN_RULES.get(weapon_type)
    if not rules:
        rules = {
            'category': 'destroyer',
            'peak_stage': 5,
            'light_gun_mult': 1.0,
            'heavy_gun_mult': 0.5,
            'torpedo_mult': 1.0,
            'defense_mult': 1.0,
            'armor_thickness': 20,
            'structure_mult': 1.0,
            'accuracy_peak': 0.7,
            'decay_rate': 0.25,
            'armor_type': 0,
        }

    era_scale = ERA_SCALING.get(era, 1.0)

    # 基准计算
    base_damage = BASE_NAVY_HEAVY_GUN_DAMAGE * era_scale * width

    # 峰值数值
    peak_light_gun = BASE_NAVY_LIGHT_GUN_DAMAGE * era_scale * width * rules.get('light_gun_mult', 1.0)
    peak_heavy_gun = BASE_NAVY_HEAVY_GUN_DAMAGE * era_scale * width * rules.get('heavy_gun_mult', 1.0)
    peak_torpedo = BASE_NAVY_TORPEDO_DAMAGE * era_scale * width * rules.get('torpedo_mult', 1.0)
    peak_missile = BASE_NAVY_MISSILE_DAMAGE * era_scale * width * rules.get('missile_mult', 0.0)
    peak_defense = BASE_NAVY_DEFENSE * era_scale * width * rules.get('defense_mult', 1.0)
    peak_structure = BASE_NAVY_STRUCTURE * era_scale * width * rules.get('structure_mult', 1.0)

    # 潜艇伤害
    peak_sub_damage = peak_torpedo * rules.get('torpedo_mult', 1.0) * 0.5

    # 生成曲线
    light_gun_stages = generate_distance_curve(
        rules['peak_stage'], peak_light_gun, decay_rate=rules.get('decay_rate', 0.25)
    )

    heavy_gun_stages = generate_distance_curve(
        rules['peak_stage'], peak_heavy_gun, decay_rate=rules.get('decay_rate', 0.25)
    )

    torpedo_stages = generate_distance_curve(
        rules['peak_stage'], peak_torpedo, decay_rate=rules.get('decay_rate', 0.3), min_ratio=0.1
    )

    missile_stages = generate_distance_curve(
        rules['peak_stage'], peak_missile, decay_rate=0.15, min_ratio=0.3
    )

    defense_stages = generate_distance_curve(
        rules['peak_stage'], peak_defense, decay_rate=0.15, min_ratio=0.5
    )

    sub_damage_stages = generate_distance_curve(
        rules['peak_stage'], peak_sub_damage, decay_rate=rules.get('decay_rate', 0.3)
    )

    accuracy_stages = generate_distance_curve(
        rules['peak_stage'], rules.get('accuracy_peak', 0.7), decay_rate=0.2, min_ratio=0.4
    )

    # 侦察
    recon_stages = generate_distance_curve(
        rules['peak_stage'],
        0.1 * era_scale * width,
        decay_rate=0.15
    )

    # 火控
    fire_control_stages = [0.1 * era_scale * rules.get('fire_control_mult', 1.0)] * 10

    # 潜艇隐身
    sub_stealth = rules.get('sub_stealth', 0.0) * era_scale

    # 雷达
    radar_strength = rules.get('radar_strength', 0.0) * era_scale
    radar_radius = rules.get('radar_radius', 0)
    ground_detection = rules.get('ground_detection', 0.0) * era_scale

    # 雷达强度10阶段（峰值在阶段5-6）
    radar_strength_stages = [radar_strength * (1 - 0.1 * abs(s - 6)) for s in range(1, 11)]

    # 对地探测10阶段（峰值在阶段5-6）
    ground_detection_stages = [ground_detection * (1 - 0.1 * abs(s - 6)) for s in range(1, 11)]

    return {
        'weapon_type': weapon_type,
        'era': era,
        'cost': cost,
        'width': width,
        'speed': speed * rules.get('speed_mult', 1.0),
        'organization': organization,
        'structure': peak_structure,
        'buoyancy': buoyancy,

        # 10阶段数值
        'recon': recon_stages,
        'defense': defense_stages,
        'fire_control': fire_control_stages,
        'sea_accuracy': accuracy_stages,
        'light_gun_damage': light_gun_stages,
        'heavy_gun_damage': heavy_gun_stages,
        'torpedo_damage': torpedo_stages,
        'missile_damage': missile_stages,
        'sub_damage': sub_damage_stages,

        # 电子战
        'electronic_jammer': [0.02 * era_scale] * 10,
        'electronic_resistance': [0.05 * era_scale] * 10,

        # 装甲
        'armor_thickness': rules.get('armor_thickness', 0) * era_scale,
        'armor_type': rules.get('armor_type', 0),

        # 雷达（10阶段格式）
        'radar_strength': radar_strength_stages,
        'radar_radius': radar_radius,
        'ground_detection': ground_detection_stages,

        # 潜艇隐身
        'sub_stealth': [sub_stealth] * 10,

        # 对地
        'ground_damage': [peak_light_gun * 0.2] * 10,
        'ground_accuracy': accuracy_stages,
    }


# =============================================================================
# CSV生成
# =============================================================================

def generate_new_air_csv(input_csv: str, output_csv: str) -> Dict:
    """生成新的air.csv"""
    stats = {'total_weapons': 0, 'weapons_by_era': {}}

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    new_rows = [header]

    for row in rows:
        weapon_type = row[0]
        era = row[1]
        cost = float(row[2]) if row[2] else 1.0
        width = int(row[5]) if row[5] else 2
        speed = float(row[47]) if len(row) > 47 and row[47] else 500.0  # 速度在列48(index 47)
        org = float(row[6]) if row[6] else 30.0
        hp = float(row[48]) if len(row) > 48 and row[48] else 30.0  # 血量在列49(index 48)

        values = generate_air_weapon_values(weapon_type, era, cost, width, speed, org, hp)
        rules = find_air_rules(weapon_type)

        stats['total_weapons'] += 1
        stats['weapons_by_era'][era] = stats['weapons_by_era'].get(era, 0) + 1

        new_row = row.copy()

        # 更新组织度和血量（使用计算的基准值）
        new_row[6] = f"{values['organization']:.3f}"
        if len(new_row) > 48:
            new_row[48] = f"{values['hp']:.3f}"

        # 更新10阶段数值列
        # 列8: 侦查
        new_row[7] = format_10_stage_value(values['recon'])
        # 列9: 防御 (填0)
        new_row[8] = format_10_stage_value(values['defense'])
        # 列10: 装甲厚度 (0)
        new_row[9] = "0"
        # 列11-13: 火控/电子干扰/电子抗性
        new_row[10] = format_10_stage_value(values['fire_control'])
        new_row[11] = format_10_stage_value(values['electronic_jammer'])
        new_row[12] = format_10_stage_value(values['electronic_resistance'])
        # 列17: 对地命中
        new_row[16] = format_10_stage_value(values['air_accuracy'])
        # 列18: 对地穿透
        new_row[17] = format_10_stage_value(values['air_to_ground'])
        # 列19: 对地压制
        new_row[18] = "0=0=0=0=0=0=0=0=0=0"
        # 列20: 对空命中
        new_row[19] = format_10_stage_value(values['air_accuracy'])
        # 列21: 对空伤害
        new_row[20] = format_10_stage_value(values['air_to_air'])
        # 列22: 对空装甲穿透 (填0)
        new_row[21] = "0=0=0=0=0=0=0=0=0=0"
        # 列23: 对海命中
        new_row[22] = format_10_stage_value(values['air_accuracy'])
        # 列24: 对海装甲穿透
        new_row[23] = format_10_stage_value(values['air_to_sea'])
        # 列50: 拦截
        new_row[49] = format_10_stage_value(values['intercept'])
        # 列51: 隐身
        new_row[50] = "0=0=0=0=0=0=0=0=0=0"
        # 列52: 雷达强度（10阶段格式）
        radar_strength_values = [values['radar_strength'] * (1 - 0.1 * abs(s - 5)) for s in range(1, 11)]
        new_row[51] = format_10_stage_value(radar_strength_values)
        # 列53: 雷达半径（单值）
        new_row[52] = f"{values['radar_radius']}"
        # 列54: 声呐强度（10阶段，普通飞机填0，反潜飞机有值）
        if '反潜' in weapon_type or '直升机' in weapon_type:
            sonar_values = [values.get('sonar_strength', 0.1) * (1 - 0.05 * abs(s - 4)) for s in range(1, 11)]
            new_row[53] = format_10_stage_value(sonar_values)
        else:
            new_row[53] = "0=0=0=0=0=0=0=0=0=0"
        # 列55: 飞行距离（单值）
        new_row[54] = f"{values['range_km']}"
        # 列56: 飞行高度（10阶段）
        altitude_values = [values['altitude_peak'] * (1 - 0.1 * abs(s - values['altitude_peak'])) for s in range(1, 11)]
        new_row[55] = format_10_stage_value(altitude_values)
        # 列57: 对地伤害（10阶段）
        new_row[56] = format_10_stage_value(values['ground_damage'])
        # 列58: 对地探测（10阶段，仅侦察机/预警机有值）
        if '侦察机' in weapon_type or '预警机' in weapon_type:
            detection_values = [values['ground_detection'] * (1 - 0.1 * abs(s - 6)) for s in range(1, 11)]
            new_row[57] = format_10_stage_value(detection_values)
        else:
            new_row[57] = "0=0=0=0=0=0=0=0=0=0"
        # 列59: 对海伤害（10阶段）
        new_row[58] = format_10_stage_value(values['air_to_sea'])
        # 列60: 对潜伤害（10阶段，仅反潜飞机有值）
        if '反潜' in weapon_type or '直升机' in weapon_type:
            anti_sub_values = [values.get('anti_sub_damage', 20) * (1 - 0.1 * abs(s - 5)) for s in range(1, 11)]
            new_row[59] = format_10_stage_value(anti_sub_values)
        else:
            new_row[59] = "0=0=0=0=0=0=0=0=0=0"

        # 空军战斗使用陆军逻辑，软攻硬攻已在combat_logic.py的load_air_csv中
        # 从对地伤害列读取并设置，不需要在CSV中额外写入

        new_rows.append(new_row)

    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)

    return stats


def generate_new_navy_csv(input_csv: str, output_csv: str) -> Dict:
    """生成新的navy.csv"""
    stats = {'total_weapons': 0, 'weapons_by_era': {}}

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    new_rows = [header]

    for row in rows:
        weapon_type = row[0]
        era = row[1]
        cost = float(row[2]) if row[2] else 1.0
        width = int(row[5]) if row[5] else 2
        speed = float(row[47]) if len(row) > 47 and row[47] else 30.0
        org = float(row[6]) if row[6] else 30.0
        structure = float(row[48]) if len(row) > 48 and row[48] else 100.0
        buoyancy = float(row[49]) if len(row) > 49 and row[49] else 100.0

        values = generate_navy_weapon_values(weapon_type, era, cost, width, speed, org, structure, buoyancy)

        stats['total_weapons'] += 1
        stats['weapons_by_era'][era] = stats['weapons_by_era'].get(era, 0) + 1

        new_row = row.copy()

        # 更新10阶段数值列
        # 列8: 侦查
        new_row[7] = format_10_stage_value(values['recon'])
        # 列9: 防御
        new_row[8] = format_10_stage_value(values['defense'])
        # 列10: 装甲厚度
        new_row[9] = f"{values['armor_thickness']:.1f}"
        # 列11-13: 火控/电子干扰/电子抗性
        new_row[10] = format_10_stage_value(values['fire_control'])
        new_row[11] = format_10_stage_value(values['electronic_jammer'])
        new_row[12] = format_10_stage_value(values['electronic_resistance'])
        # 列17: 对地命中
        new_row[16] = format_10_stage_value(values['ground_accuracy'])
        # 列18: 对地穿透
        new_row[17] = "0=0=0=0=0=0=0=0=0=0"
        # 列19: 对地压制
        new_row[18] = "0=0=0=0=0=0=0=0=0=0"
        # 列23: 对海命中
        new_row[22] = format_10_stage_value(values['sea_accuracy'])
        # 列24: 对海装甲穿透
        new_row[23] = format_10_stage_value(values['heavy_gun_damage'])
        # 列51: 装甲类型
        new_row[50] = f"{values['armor_type']}"
        # 列52: 拦截
        new_row[51] = "0=0=0=0=0=0=0=0=0=0"
        # 列53: 潜艇隐身
        new_row[52] = format_10_stage_value(values['sub_stealth'])
        # 列54: 雷达强度（10阶段）
        new_row[53] = format_10_stage_value(values['radar_strength'])
        # 列55: 雷达半径
        new_row[54] = f"{values['radar_radius']}"
        # 列56: 声呐强度
        new_row[55] = "0=0=0=0=0=0=0=0=0=0"
        # 列60: 对地伤害
        new_row[59] = format_10_stage_value(values['ground_damage'])
        # 列61: 对地探测（10阶段）
        new_row[60] = format_10_stage_value(values['ground_detection'])
        # 列62: 轻炮对海伤害
        new_row[61] = format_10_stage_value(values['light_gun_damage'])
        # 列63: 重炮对海伤害
        new_row[62] = format_10_stage_value(values['heavy_gun_damage'])
        # 列64: 鱼雷对海伤害
        new_row[63] = format_10_stage_value(values['torpedo_damage'])
        # 列65: 导弹对海伤害
        new_row[64] = format_10_stage_value(values['missile_damage'])
        # 列66: 对潜伤害
        new_row[65] = format_10_stage_value(values['sub_damage'])

        # 更新单值属性
        new_row[48] = f"{values['structure']:.1f}"  # 结构值
        new_row[49] = f"{buoyancy:.1f}"  # 浮力值

        new_rows.append(new_row)

    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)

    return stats


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("空军海军数值生成器测试")
    print("=" * 70)

    # 测试空军
    print("\n[空军测试]")
    air_stats = generate_new_air_csv("air.csv", "air_optimized.csv")
    print(f"生成: {air_stats['total_weapons']} 种武器")
    for era, count in air_stats['weapons_by_era'].items():
        print(f"  {era}: {count} 种")

    # 测试海军
    print("\n[海军测试]")
    navy_stats = generate_new_navy_csv("navy.csv", "navy_optimized.csv")
    print(f"生成: {navy_stats['total_weapons']} 种武器")
    for era, count in navy_stats['weapons_by_era'].items():
        print(f"  {era}: {count} 种")

    # 显示关键武器数值
    print("\n[空军关键武器示例]")
    for weapon in ['战术轰炸机', '轻型战斗机', '战略轰炸机']:
        values = generate_air_weapon_values(weapon, '二战', 100, 2, 500, 30, 30)
        print(f"\n{weapon}（二战）:")
        print(f"  对地伤害峰值: {max(values['ground_damage']):.1f}")
        print(f"  对空伤害峰值: {max(values['air_to_air']):.1f}")
        print(f"  飞行距离: {values['range_km']} km")

    print("\n[海军关键武器示例]")
    for weapon in ['战列舰', '驱逐舰', '常规潜艇']:
        values = generate_navy_weapon_values(weapon, '二战', 100, 10, 30, 30, 100, 100)
        print(f"\n{weapon}（二战）:")
        print(f"  重炮伤害峰值: {max(values['heavy_gun_damage']):.1f}")
        print(f"  鱼雷伤害峰值: {max(values['torpedo_damage']):.1f}")
        print(f"  防御峰值: {max(values['defense']):.1f}")
        print(f"  装甲厚度: {values['armor_thickness']:.1f}")