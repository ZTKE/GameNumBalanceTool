"""
战争模块战斗逻辑实现
=====================
本模块实现了完整的战争数值计算系统，包括：
- 陆军、海军、空军三军的伤害判定逻辑
- 10阶段距离推进系统
- 环境适应系数计算
- 先手判定与血量影响
- CSV数据加载功能

基于需求.md文档中的规则实现
"""

import random
import math
import csv
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
from pathlib import Path


# =============================================================================
# 常量定义
# =============================================================================

# 10阶段距离区间定义（km）
DISTANCE_RANGES = [
    (0, 0.5),      # 阶段1：贴脸距离
    (0.5, 1.5),    # 阶段2：超近距离
    (1.5, 4),      # 阶段3：近距离
    (4, 8),        # 阶段4：中近距离
    (8, 20),       # 阶段5：中距离
    (20, 40),      # 阶段6：中远距离（陆战开局距离、循环重置距离）
    (40, 80),      # 阶段7：远距离
    (80, 120),     # 阶段8：超远距离
    (120, 240),    # 阶段9：极远距离
    (240, 480),    # 阶段10：超极远距离
]

# 环境适应性变量列表
ENVIRONMENT_TYPES = [
    "海洋适应性", "平原适应性", "城市适应性", "丘陵适应性",
    "森林适应性", "丛林适应性", "山地适应性", "沙漠适应性",
    "沼泽适应性", "可通行冰面湖泊适应性", "酷暑适应性", "炎热适应性",
    "温和适应性", "严寒适应性", "极寒适应性", "晴朗适应性",
    "小雨适应性", "暴雨适应性", "小雪适应性", "暴风雪适应性",
    "沙尘暴适应性", "大雾适应性"
]

# 编制宽度上限
ARMY_WIDTH_LIMIT = 2200   # 陆军团上限
AIR_WIDTH_LIMIT = 24      # 空军大队上限
NAVY_WIDTH_LIMIT = 60     # 海军舰队上限


# =============================================================================
# 枚举类型定义
# =============================================================================

class ForceType(Enum):
    """军种类型"""
    ARMY = "army"    # 陆军
    AIR = "air"      # 空军
    NAVY = "navy"    # 海军


class CombatType(Enum):
    """战斗类型"""
    GROUND_TO_GROUND = "地对地"
    GROUND_TO_AIR = "地对空"
    GROUND_TO_SEA = "地对海"
    AIR_TO_AIR = "空对空"
    AIR_TO_GROUND = "空对地"
    AIR_TO_SEA = "空对海"
    SEA_TO_SEA = "海对海"


class ArmorType(Enum):
    """装甲类型"""
    LIGHT = 0    # 轻甲（轻甲船、非装甲单位）
    HEAVY = 1    # 重甲（重甲船、装甲单位如坦克）


class WeaponPositionType(Enum):
    """武器定位类型（用于判断装甲类武器）"""
    INFANTRY = 1      # 步兵类
    ARMORED = 2       # 装甲类（坦克、步兵战车等）
    ARTILLERY = 3     # 火炮类
    SUPPORT = 4       # 支援类


# =============================================================================
# 数据类定义
# =============================================================================

@dataclass
class WeaponStats:
    """
    武器属性数据类
    存储单个武器的所有数值属性

    注意：带有（10阶段）标记的属性需要使用get_stage_value()方法获取特定阶段的值
    """
    # 基础信息（不可修改）
    weapon_type: str              # 武器种类
    era: str                      # 时代
    cost: float                   # 成本
    width: int                    # 编制宽度
    speed: float                  # 速度（km/h）

    # 组织度与血量
    organization: float           # 组织度
    hp: float                     # 血量（陆军/空军）
    structure: float = 0          # 结构值（海军）
    buoyancy: float = 0           # 浮力值（海军）

    # 侦查与防御（10阶段）
    recon: List[float] = field(default_factory=list)      # 侦查（10阶段）
    defense: List[float] = field(default_factory=list)    # 防御（10阶段）

    # 装甲属性
    armor_thickness: float = 0    # 装甲厚度
    armor_type: int = 0            # 装甲类型（0=轻甲，1=重甲）
    weapon_position: int = 1       # 武器定位编号（1=步兵，2=装甲，3=火炮，4=支援）

    # 电子战属性（10阶段）
    fire_control: List[float] = field(default_factory=list)        # 火控（10阶段）
    electronic_jammer: List[float] = field(default_factory=list)   # 电子干扰（10阶段）
    electronic_resistance: List[float] = field(default_factory=list)  # 电子抗性（10阶段）

    # 对地属性（10阶段）
    ground_friendly_damage: List[float] = field(default_factory=list)   # 对地友伤（10阶段）
    ground_accuracy: List[float] = field(default_factory=list)          # 对地命中（10阶段）
    ground_penetration: List[float] = field(default_factory=list)       # 对地装甲穿透（10阶段）
    ground_suppression: List[float] = field(default_factory=list)       # 对地压制（10阶段）
    ground_soft_attack: List[float] = field(default_factory=list)       # 对地软攻（10阶段）
    ground_hard_attack: List[float] = field(default_factory=list)       # 对地硬攻（10阶段）
    ground_damage: List[float] = field(default_factory=list)            # 对地伤害（10阶段）

    # 对空属性（10阶段）
    air_accuracy: List[float] = field(default_factory=list)      # 对空命中（10阶段）
    air_damage: List[float] = field(default_factory=list)        # 对空伤害（10阶段）
    air_interception: List[float] = field(default_factory=list)  # 拦截（10阶段）

    # 对海属性（10阶段）
    sea_accuracy: List[float] = field(default_factory=list)           # 对海命中（10阶段）
    sea_penetration: List[float] = field(default_factory=list)        # 对海装甲穿透（10阶段）
    sea_damage: List[float] = field(default_factory=list)             # 对海伤害（10阶段）- 空军专用
    light_cannon_damage: List[float] = field(default_factory=list)    # 轻炮对海伤害（10阶段）
    heavy_cannon_damage: List[float] = field(default_factory=list)    # 重炮对海伤害（10阶段）
    torpedo_damage: List[float] = field(default_factory=list)         # 鱼雷对海伤害（10阶段）
    missile_damage: List[float] = field(default_factory=list)         # 导弹对海伤害（10阶段）
    anti_sub_damage: List[float] = field(default_factory=list)        # 对潜伤害（10阶段）

    # 特殊属性
    sonar_strength: List[float] = field(default_factory=list)   # 声呐强度（10阶段）
    submarine_stealth: List[float] = field(default_factory=list) # 潜艇隐身（10阶段）
    stealth: List[float] = field(default_factory=list)          # 隐身（10阶段）
    ground_detection: List[float] = field(default_factory=list) # 对地探测（10阶段，空军专用）
    radar_strength: List[float] = field(default_factory=list)   # 雷达强度（10阶段）
    radar_radius: float = 0                                      # 雷达半径（km，单值）

    # 燃料与核动力属性
    fuel_capacity: float = 0         # 燃料容量
    fuel_per_round: float = 0        # 燃料每轮消耗
    nuclear_capacity: float = 0      # 核动力能容量（海军专用）
    nuclear_per_round: float = 0     # 核动力能每轮消耗（海军专用）

    # 突破与堑壕
    breakthrough: float = 0      # 突破（进攻时防御）
    trench_defense: float = 0    # 堑壕防御

    # 环境适应性（22种环境）
    environment_adaptations: Dict[str, float] = field(default_factory=dict)

    # 数量
    quantity: int = 1            # 武器数量

    def get_stage_value(self, stage_values: List[float], stage: int) -> float:
        """
        获取10阶段属性的特定阶段值

        参数:
            stage_values: 10阶段数值列表
            stage: 阶段编号（1-10）

        返回:
            对应阶段的数值

        注意:
            阶段编号从1开始，但列表索引从0开始，需要转换
        """
        if not stage_values or len(stage_values) == 0:
            return 0
        # 阶段1对应索引0，阶段10对应索引9
        index = min(stage - 1, len(stage_values) - 1)
        return stage_values[index] if index >= 0 else 0


@dataclass
class Formation:
    """
    编制数据类
    存储一个编制（团/大队/舰队）的所有武器组合
    """
    force_type: ForceType                    # 军种类型
    name: str                                 # 编制名称
    weapons: List[WeaponStats] = field(default_factory=list)  # 武器列表
    total_width: int = 0                      # 总编制宽度

    # 状态属性
    current_hp: float = 0                     # 当前血量（陆军/空军）
    current_organization: float = 0           # 当前组织度
    current_structure: float = 0              # 当前结构值（海军）
    current_buoyancy: float = 0               # 当前浮力值（海军）

    # 战斗状态
    is_defending: bool = False                # 是否处于防御状态
    current_distance_stage: int = 6           # 当前交战距离阶段（默认6=20-40km）
    damage_penalty_ratio: float = 1.0         # 血量损失导致的面板惩罚系数（1.0=无惩罚）

    def __post_init__(self):
        """初始化后计算总宽度"""
        self._calculate_total_width()
        self._initialize_stats()

    def _calculate_total_width(self):
        """计算总编制宽度"""
        self.total_width = sum(w.width * w.quantity for w in self.weapons)

    def _initialize_stats(self):
        """初始化总血量和组织度"""
        # 计算加权平均的组织度和血量
        if self.total_width > 0:
            total_org = sum(w.organization * w.width * w.quantity for w in self.weapons)
            total_hp = sum(w.hp * w.width * w.quantity for w in self.weapons)

            # 如果编制宽度不足上限，组织度按比例折算（仅陆军）
            if self.force_type == ForceType.ARMY and self.total_width < ARMY_WIDTH_LIMIT:
                self.current_organization = total_org / self.total_width * ARMY_WIDTH_LIMIT
            else:
                self.current_organization = total_org

            self.current_hp = total_hp

            # 海军还需要计算结构值和浮力值
            if self.force_type == ForceType.NAVY:
                self.current_structure = sum(w.structure * w.width * w.quantity for w in self.weapons)
                self.current_buoyancy = sum(w.buoyancy * w.width * w.quantity for w in self.weapons)

    def get_armor_rate(self) -> float:
        """
        计算装甲率

        装甲率 = 装甲类武器编制宽度总和 / 部队总编制宽度
        装甲类武器判定：武器定位编号=2的单位

        返回:
            装甲率（0-1之间）
        """
        if self.total_width <= 0:
            return 0

        armored_width = sum(
            w.width * w.quantity
            for w in self.weapons
            if w.weapon_position == WeaponPositionType.ARMORED.value
        )

        return armored_width / self.total_width

    def get_total_panel_at_stage(self, stage: int, panel_name: str) -> float:
        """
        计算编制在特定阶段的某项面板总值

        参数:
            stage: 阶段编号（1-10）
            panel_name: 面板属性名称

        返回:
            加权面板总值（已应用血量惩罚）
        """
        total = 0
        for weapon in self.weapons:
            # 获取10阶段属性的值
            stage_attr = getattr(weapon, panel_name, [])
            if isinstance(stage_attr, list):
                value = weapon.get_stage_value(stage_attr, stage)
            else:
                value = stage_attr
            total += value * weapon.quantity

        # 应用血量损失的面板惩罚
        return total * self.damage_penalty_ratio

    def get_recon_value(self) -> float:
        """
        获取当前阶段的侦查值

        返回:
            当前交战距离阶段的侦查值
        """
        return self.get_total_panel_at_stage(self.current_distance_stage, 'recon')

    def is_defeated(self) -> bool:
        """
        判断编制是否失去战斗力

        陆军/空军：组织度或血量归零
        海军：浮力值、结构值或组织度归零

        返回:
            是否失去战斗力
        """
        if self.force_type == ForceType.NAVY:
            # 海军：任一项归零即失去战斗力
            return (self.current_buoyancy <= 0 or
                    self.current_structure <= 0 or
                    self.current_organization <= 0)
        else:
            # 陆军/空军：组织度或血量归零
            return self.current_organization <= 0 or self.current_hp <= 0

    def apply_damage_penalty(self):
        """
        应用血量损失的面板惩罚

        规则：血量每损失1%，所有面板属性下降1%
        实现方式：计算当前血量/初始血量的比例作为面板系数
        """
        if self.force_type == ForceType.NAVY:
            # 海军用结构值计算损失比例
            if self.current_structure <= 0:
                self.damage_penalty_ratio = 0
            else:
                initial_structure = sum(w.structure * w.width * w.quantity for w in self.weapons)
                self.damage_penalty_ratio = self.current_structure / initial_structure if initial_structure > 0 else 0
        else:
            # 陆军/空军用血量计算损失比例
            if self.current_hp <= 0:
                self.damage_penalty_ratio = 0
            else:
                initial_hp = sum(w.hp * w.width * w.quantity for w in self.weapons)
                self.damage_penalty_ratio = self.current_hp / initial_hp if initial_hp > 0 else 0


@dataclass
class CombatResult:
    """
    战斗结果数据类
    存储单次战斗的结果数据
    """
    attacker_damage: float       # 攻击方造成的伤害
    defender_damage: float       # 防守方造成的伤害
    attacker_first: bool         # 攻击方是否先手
    distance_change: int = 0      # 距离变化（正数缩短，负数延长）
    stage: int = 0               # 战斗发生的阶段
    # 新增字段（用于统计收集）
    attacker_penetrated: bool = False   # 攻击方是否完全击穿（击穿效率>=1.0）
    defender_penetrated: bool = False   # 防守方是否完全击穿
    attacker_fuel_cost: float = 0       # 攻击方本回合燃料消耗
    defender_fuel_cost: float = 0       # 防守方本回合燃料消耗
    attacker_nuclear_cost: float = 0    # 攻击方本回合核动力消耗
    defender_nuclear_cost: float = 0    # 防守方本回合核动力消耗
    attacker_org_damage: float = 0      # 攻击方造成的组织度伤害
    defender_org_damage: float = 0      # 防守方造成的组织度伤害


# =============================================================================
# 全局基础公式
# =============================================================================

def calculate_base_damage(attack: float, defense: float) -> float:
    """
    计算基础伤害（全局基础公式）

    这是所有伤害计算的底层逻辑：
    - 若 攻击 <= 防御：基础伤害 = 攻击 * 0.1
    - 若 攻击 > 防御：基础伤害 = 防御 * 0.1 + (攻击 - 防御) * 0.4

    这个公式的特点：
    - 当攻击小于等于防御时，伤害被大幅压制（仅10%转化率）
    - 当攻击溢出防御时，溢出部分获得更高的转化率（40%）
    - 这鼓励玩家追求"击穿"效果，而非单纯堆攻击

    参数:
        attack: 有效攻击值
        defense: 有效防御值

    返回:
        基础伤害值
    """
    if attack <= defense:
        # 攻击不足以突破防御，伤害转化率低
        return attack * 0.1
    else:
        # 攻击溢出防御，溢出部分获得更高转化
        return defense * 0.1 + (attack - defense) * 0.4


def calculate_penetration_efficiency(penetration: float, armor_thickness: float) -> float:
    """
    计算击穿效率

    规则：
    - 若穿透 > 装甲厚度，击穿效率 = 1（完全击穿）
    - 若穿透 <= 装甲厚度，击穿效率 = max(0.1, 穿透 / (装甲厚度 + 1))

    这个设计确保：
    - 完全击穿时伤害最大化
    - 未击穿时伤害大幅降低，但仍有最低10%的基础伤害
    - 分母加1是为了避免装甲厚度为0时的除零问题

    参数:
        penetration: 装甲穿透值
        armor_thickness: 装甲厚度

    返回:
        击穿效率（0.1-1之间）
    """
    if penetration > armor_thickness:
        return 1.0
    else:
        # 未击穿时按比例衰减，最低10%
        return max(0.1, penetration / (armor_thickness + 1))


def calculate_accuracy(base_accuracy: float, min_val: float = 0.05, max_val: float = 1.0) -> float:
    """
    计算命中率（限制在合理范围内）

    规则：命中率 = min(1.0, max(0.05, 计算值))

    这个设计确保：
    - 命中率永远不会低于5%（避免完全无法命中）
    - 命中率永远不会超过100%

    参数:
        base_accuracy: 计算得出的基础命中率
        min_val: 最小命中率（默认5%）
        max_val: 最大命中率（默认100%）

    返回:
        限制后的命中率
    """
    return min(max_val, max(min_val, base_accuracy))


# =============================================================================
# 环境适应系数计算
# =============================================================================

def calculate_environment_coefficient(
    formation: Formation,
    active_environments: List[str],
    stage: int
) -> float:
    """
    计算环境适应系数

    计算逻辑：
    1. 单环境：部队环境适应系数 = Σ(武器数量 × 编制宽度 × 环境适应性) / 总编制宽度
    2. 多环境叠加：综合适应系数 = 所有环境适应性的平均值

    示例：
    - 单环境（平原0.9）：直接计算加权平均
    - 双环境（暴雨0.8 + 平原0.9）：(0.8 + 0.9) / 2 = 0.85
    - 三环境（暴雨0.8 + 平原0.9 + 夜间0.7）：(0.8 + 0.9 + 0.7) / 3 = 0.8

    参数:
        formation: 编制对象
        active_environments: 当前生效的环境列表
        stage: 当前阶段（10阶段属性可能随距离变化，但环境适应性通常是固定值）

    返回:
        综合环境适应系数
    """
    if not active_environments:
        return 1.0  # 无环境修正时系数为1

    if formation.total_width <= 0:
        return 1.0

    # 计算每个环境的加权适应系数
    env_coefficients = []

    for env_name in active_environments:
        if env_name not in ENVIRONMENT_TYPES:
            continue

        # 计算该环境的加权适应系数
        total_adaptation = 0
        for weapon in formation.weapons:
            adaptation = weapon.environment_adaptations.get(env_name, 1.0)
            total_adaptation += weapon.quantity * weapon.width * adaptation

        env_coefficient = total_adaptation / formation.total_width
        env_coefficients.append(env_coefficient)

    if not env_coefficients:
        return 1.0

    # 多环境叠加：取平均值
    return sum(env_coefficients) / len(env_coefficients)


# =============================================================================
# 距离推进逻辑
# =============================================================================

def calculate_army_advance_progress(
    attacker_speed: float,
    attacker_breakthrough: float,
    attacker_suppression: float,
    defender_suppression: float
) -> float:
    """
    计算陆军推进度

    公式：
    推进度 = 速度/(速度+8) * 0.25 +
             (突破-敌方压制+己方压制/2)/(己方压制/2+突破+敌方压制) * 0.75 +
             [-0.2~0.3]随机数

    公式解析：
    - 第一项（速度因素）：速度越快推进度越高，但权重仅25%
    - 第二项（战斗因素）：突破与压制对比，权重75%
      - 进攻方突破高 → 推进快
      - 防守方压制高 → 推进受阻
    - 第三项（随机因素）：模拟战场不确定性

    参数:
        attacker_speed: 进攻方速度
        attacker_breakthrough: 进攻方突破值
        attacker_suppression: 进攻方压制值
        defender_suppression: 防守方压制值

    返回:
        推进度值
    """
    # 速度因素（25%权重）
    speed_factor = attacker_speed / (attacker_speed + 8) * 0.25

    # 战斗因素（75%权重）
    # 分子：进攻方突破 - 防守方压制 + 进攻方压制/2
    numerator = attacker_breakthrough - defender_suppression + attacker_suppression / 2
    # 分母：进攻方压制/2 + 进攻方突破 + 防守方压制
    denominator = attacker_suppression / 2 + attacker_breakthrough + defender_suppression

    if denominator <= 0:
        combat_factor = 0
    else:
        combat_factor = numerator / denominator * 0.75

    # 随机因素（[-0.2, 0.3]范围）
    random_factor = random.uniform(-0.2, 0.3)

    return speed_factor + combat_factor + random_factor


def calculate_navy_air_advance_progress(
    attacker_speed: float,
    defender_speed: float
) -> float:
    """
    计算海军/空军推进度

    公式：
    推进度 = (进攻方速度-防御方速度)/(进攻方速度+防御方速度) + [-0.2~0.3]随机数

    公式解析：
    - 只有速度差决定推进，不考虑火力压制
    - 速度快的部队可以拉近或拉开距离
    - 随机因素模拟战场不确定性

    参数:
        attacker_speed: 进攻方速度
        defender_speed: 防守方速度

    返回:
        推进度值
    """
    # 速度差因素
    total_speed = attacker_speed + defender_speed
    if total_speed <= 0:
        speed_factor = 0
    else:
        speed_factor = (attacker_speed - defender_speed) / total_speed

    # 随机因素
    random_factor = random.uniform(-0.2, 0.3)

    return speed_factor + random_factor


def determine_distance_change(progress: float, current_stage: int, force_type: ForceType) -> int:
    """
    根据推进度确定距离变化

    规则：
    - 推进度 > 0.2 → 缩短距离（前进一个阶段）
    - 推进度 < -0.3 → 延长距离（后退一个阶段）
    - 陆战距离限制在阶段1-6（0-40km）
    - 海空战距离无限制（1-10）

    参数:
        progress: 推进度值
        current_stage: 当前阶段
        force_type: 军种类型

    返回:
        新的阶段编号
    """
    new_stage = current_stage

    if progress > 0.2:
        # 推进成功，缩短距离（阶段编号减小）
        new_stage = current_stage - 1
    elif progress < -0.3:
        # 推进失败，延长距离（阶段编号增大）
        new_stage = current_stage + 1

    # 陆战距离限制（阶段1-6，对应0-40km）
    if force_type == ForceType.ARMY:
        new_stage = max(1, min(6, new_stage))
    else:
        # 海空战无限制（阶段1-10）
        new_stage = max(1, min(10, new_stage))

    return new_stage


def should_reset_distance(current_stage: int, force_type: ForceType) -> bool:
    """
    判断是否应该重置距离

    规则：在阶段1结算完成后自动重置到阶段6

    参数:
        current_stage: 当前阶段
        force_type: 军种类型

    返回:
        是否需要重置
    """
    return current_stage == 1


# =============================================================================
# 先手判定逻辑
# =============================================================================

def determine_first_strike(attacker_recon: float, defender_recon: float) -> bool:
    """
    判断先手方

    规则：
    通过双方侦查值对比决定先手概率
    进攻方先手概率 = 进攻方侦查值 / (进攻方侦查值 + 防守方侦查值)

    示例：
    - 进攻方侦查50，防守方侦查30
    - 进攻方先手概率 = 50/(50+30) = 62.5%

    参数:
        attacker_recon: 进攻方侦查值（取当前阶段的侦查值）
        defender_recon: 防守方侦查值

    返回:
        True表示进攻方先手，False表示防守方先手
    """
    total_recon = attacker_recon + defender_recon

    if total_recon <= 0:
        # 双方都无侦查能力时，进攻方默认先手
        return True

    # 计算进攻方先手概率
    attacker_probability = attacker_recon / total_recon

    # 随机判定
    return random.random() < attacker_probability


# =============================================================================
# 陆军伤害判定
# =============================================================================

def army_ground_to_ground_damage(
    attacker: Formation,
    defender: Formation,
    stage: int,
    active_environments: List[str]
) -> Tuple[float, float]:
    """
    计算陆军地对地伤害

    完整流程：
    1. 命中率 = min(1.0, max(0.05, 对地命中 + 火控 * max(0, 1 - 敌方电子干扰/(1+电子抗性))))
    2. 敌方装甲率 = 敌方装甲类武器编制宽度总和 / 敌方部队总编制宽度
    3. 有效攻击 = 敌方装甲率 * 己方对地硬攻 + (1-敌方装甲率) * 己方对地软攻
    4. 敌方有效防御 = 敌方堑壕防御 + (敌方防御状态 ? 敌方防御 : 敌方突破)
    5. 基础伤害 = 将"有效攻击"与"敌方有效防御"代入全局基础公式
    6. 击穿判定：击穿效率计算
    7. 最终伤害 = 基础伤害 * 击穿效率 * 命中率 * 环境适应系数

    结算：
    - 敌方血量 - 最终伤害 * 0.1
    - 敌方组织度 - 最终伤害

    参数:
        attacker: 进攻方编制
        defender: 防守方编制
        stage: 当前交战阶段
        active_environments: 当前生效的环境

    返回:
        (血量伤害, 组织度伤害)
    """
    # 1. 计算命中率
    # 获取进攻方在当前阶段的对地命中和火控
    attacker_ground_accuracy = attacker.get_total_panel_at_stage(stage, 'ground_accuracy')
    attacker_fire_control = attacker.get_total_panel_at_stage(stage, 'fire_control')

    # 获取防守方的电子干扰和电子抗性
    defender_ecm = defender.get_total_panel_at_stage(stage, 'electronic_jammer')
    defender_eccm = defender.get_total_panel_at_stage(stage, 'electronic_resistance')

    # 命中率计算公式
    ecm_effect = max(0, 1 - defender_ecm / (1 + defender_eccm))
    base_accuracy = attacker_ground_accuracy + attacker_fire_control * ecm_effect
    accuracy = calculate_accuracy(base_accuracy)

    # 2. 计算敌方装甲率
    defender_armor_rate = defender.get_armor_rate()

    # 3. 计算有效攻击（软硬攻混合）
    attacker_soft_attack = attacker.get_total_panel_at_stage(stage, 'ground_soft_attack')
    attacker_hard_attack = attacker.get_total_panel_at_stage(stage, 'ground_hard_attack')
    effective_attack = defender_armor_rate * attacker_hard_attack + \
                       (1 - defender_armor_rate) * attacker_soft_attack

    # 4. 计算敌方有效防御
    # 堑壕防御 + (防御状态?防御:突破)
    defender_trench_defense = sum(w.trench_defense * w.width * w.quantity for w in defender.weapons)

    if defender.is_defending:
        defender_defense = defender.get_total_panel_at_stage(stage, 'defense')
    else:
        defender_defense = sum(w.breakthrough * w.width * w.quantity for w in defender.weapons)

    effective_defense = defender_trench_defense + defender_defense

    # 5. 计算基础伤害（全局公式）
    base_damage = calculate_base_damage(effective_attack, effective_defense)

    # 6. 计算击穿效率
    attacker_penetration = attacker.get_total_panel_at_stage(stage, 'ground_penetration')
    defender_armor_thickness = sum(
        w.armor_thickness * w.width * w.quantity
        for w in defender.weapons
        if w.weapon_position == WeaponPositionType.ARMORED.value
    )
    # 取装甲单位的平均装甲厚度
    armored_count = sum(w.quantity for w in defender.weapons if w.weapon_position == WeaponPositionType.ARMORED.value)
    if armored_count > 0:
        defender_armor_thickness = defender_armor_thickness / armored_count
    else:
        defender_armor_thickness = 0

    penetration_efficiency = calculate_penetration_efficiency(attacker_penetration, defender_armor_thickness)

    # 7. 计算环境适应系数
    env_coefficient = calculate_environment_coefficient(attacker, active_environments, stage)

    # 8. 计算最终伤害
    final_damage = base_damage * penetration_efficiency * accuracy * env_coefficient

    # 9. 结算
    hp_damage = final_damage * 0.1
    org_damage = final_damage

    return hp_damage, org_damage


def army_ground_to_air_damage(
    attacker: Formation,
    defender: Formation,
    stage: int
) -> Tuple[float, float]:
    """
    计算地对空伤害

    流程：
    1. 基础导引 = 对空命中 + 火控*(1-敌方干扰/(1+电子抗性)) - 敌方拦截
    2. 命中率 = min(1.0, max(0.05, 基础导引))
    3. 最终伤害 = 对空伤害 * 命中率（空对空无击穿判定）
    4. 结算：敌方血量 - 最终伤害*0.3；敌方组织度 - 最终伤害

    注意：
    - 空军没有护甲，所以没有击穿判定
    - 拦截变量代表飞机对敌方火力的拦截率

    参数:
        attacker: 进攻方编制（陆军）
        defender: 防守方编制（空军）
        stage: 当前交战阶段

    返回:
        (血量伤害, 组织度伤害)
    """
    # 1. 计算基础导引
    attacker_air_accuracy = attacker.get_total_panel_at_stage(stage, 'air_accuracy')
    attacker_fire_control = attacker.get_total_panel_at_stage(stage, 'fire_control')

    defender_interference = defender.get_total_panel_at_stage(stage, 'electronic_jammer')
    defender_eccm = defender.get_total_panel_at_stage(stage, 'electronic_resistance')
    defender_interception = defender.get_total_panel_at_stage(stage, 'air_interception')

    base_guidance = attacker_air_accuracy + \
                    attacker_fire_control * (1 - defender_interference / (1 + defender_eccm)) - \
                    defender_interception

    # 2. 计算命中率
    accuracy = calculate_accuracy(base_guidance)

    # 3. 计算最终伤害（对空伤害，无击穿）
    attacker_air_damage = attacker.get_total_panel_at_stage(stage, 'air_damage')
    final_damage = attacker_air_damage * accuracy

    # 4. 结算
    hp_damage = final_damage * 0.3
    org_damage = final_damage

    return hp_damage, org_damage


def army_ground_to_sea_damage(
    attacker: Formation,
    defender: Formation,
    stage: int,
    target_is_submarine: bool = False
) -> Tuple[float, float, float]:
    """
    计算地对海伤害

    流程：
    1. 基础导引计算：
       - 目标军舰：对海命中 + 火控*(1-敌方电子干扰/(1+电子抗性)) - 敌方拦截
       - 目标潜艇：(对海命中 + 火控*(1-敌方电子干扰/(1+电子抗性)) - 敌方拦截) * 声呐强度/(敌方潜艇隐身+1)
    2. 命中率 = min(1.0, max(0.05, 基础导引))
    3. 有效攻击 = 目标军舰 ? 对海伤害 : 对潜伤害
    4. 基础伤害 = 全局公式计算
    5. 击穿判定
    6. 最终伤害 = 基础伤害 * 击穿效率 * 命中率
    7. 结算：结构值、浮力值、组织度

    注意：
    - 陆军武器无声呐强度变量，所以对潜艇的基础导引为0

    参数:
        attacker: 进攻方编制
        defender: 防守方编制（海军）
        stage: 当前交战阶段
        target_is_submarine: 目标是否为潜艇

    返回:
        (结构值伤害, 浮力值伤害, 组织度伤害)
    """
    # 1. 计算基础导引
    attacker_sea_accuracy = attacker.get_total_panel_at_stage(stage, 'sea_accuracy')
    attacker_fire_control = attacker.get_total_panel_at_stage(stage, 'fire_control')

    defender_ecm = defender.get_total_panel_at_stage(stage, 'electronic_jammer')
    defender_eccm = defender.get_total_panel_at_stage(stage, 'electronic_resistance')
    defender_interception = defender.get_total_panel_at_stage(stage, 'air_interception')  # 船只拦截

    base_guidance_base = attacker_sea_accuracy + \
                         attacker_fire_control * (1 - defender_ecm / (1 + defender_eccm)) - \
                         defender_interception

    if target_is_submarine:
        # 潜艇目标：需要声呐强度
        attacker_sonar = attacker.get_total_panel_at_stage(stage, 'sonar_strength')
        defender_submarine_stealth = defender.get_total_panel_at_stage(stage, 'submarine_stealth')

        # 陆军无声呐，基础导引为0
        if attacker_sonar <= 0:
            base_guidance = 0
        else:
            base_guidance = base_guidance_base * attacker_sonar / (defender_submarine_stealth + 1)
    else:
        base_guidance = base_guidance_base

    # 2. 计算命中率
    accuracy = calculate_accuracy(base_guidance)

    # 3. 计算有效攻击
    if target_is_submarine:
        effective_attack = attacker.get_total_panel_at_stage(stage, 'anti_sub_damage')
    else:
        effective_attack = attacker.get_total_panel_at_stage(stage, 'sea_damage')  # 对海伤害

    # 4. 计算敌方防御
    defender_defense = defender.get_total_panel_at_stage(stage, 'defense')

    # 5. 计算基础伤害
    base_damage = calculate_base_damage(effective_attack, defender_defense)

    # 6. 计算击穿效率
    attacker_penetration = attacker.get_total_panel_at_stage(stage, 'sea_penetration')
    defender_armor = defender.get_total_panel_at_stage(stage, 'armor_thickness')

    penetration_efficiency = calculate_penetration_efficiency(attacker_penetration, defender_armor)

    # 7. 计算最终伤害
    final_damage = base_damage * penetration_efficiency * accuracy

    # 8. 结算
    structure_damage = final_damage
    buoyancy_damage = final_damage * 0.3
    org_damage = final_damage

    return structure_damage, buoyancy_damage, org_damage


# =============================================================================
# 空军伤害判定
# =============================================================================

def air_to_ground_damage(
    attacker: Formation,
    defender: Formation,
    stage: int,
    active_environments: List[str],
    has_friendly_ground: bool = True
) -> Tuple[float, float]:
    """
    计算空对地伤害

    流程：
    1. 基础导引 = 对地命中 + 火控 * max(0, 1-敌方电子干扰/(1+电子抗性))
    2. 命中率 = min(1.0, max(0.05, 基础导引 * 对地探测))
       - 同地块有己方部队：基础导引 * 对地探测
       - 同地块无己方部队：基础导引 * 对地探测 * 对地探测（平方惩罚）
    3. 伤害逻辑同陆军地对地（包括击穿判定）
    4. 结算：敌方血量 - 最终伤害*0.1；敌方组织度 - 最终伤害

    注意：
    - 空军使用"对地装甲穿透"变量进行击穿判定
    - 敌方装甲厚度取地面单位的装甲厚度

    参数:
        attacker: 进攻方编制（空军）
        defender: 防守方编制（陆军）
        stage: 当前交战阶段
        active_environments: 当前生效的环境
        has_friendly_ground: 同地块是否有己方部队

    返回:
        (血量伤害, 组织度伤害)
    """
    # 1. 计算基础导引
    attacker_ground_accuracy = attacker.get_total_panel_at_stage(stage, 'ground_accuracy')
    attacker_fire_control = attacker.get_total_panel_at_stage(stage, 'fire_control')

    defender_ecm = defender.get_total_panel_at_stage(stage, 'electronic_jammer')
    defender_eccm = defender.get_total_panel_at_stage(stage, 'electronic_resistance')

    ecm_effect = max(0, 1 - defender_ecm / (1 + defender_eccm))
    base_guidance = attacker_ground_accuracy + attacker_fire_control * ecm_effect

    # 2. 计算命中率（考虑对地探测）
    # 对地探测是10阶段格式，需要取当前阶段的值
    ground_detection = attacker.get_total_panel_at_stage(stage, 'ground_detection') or 1.0

    if has_friendly_ground:
        accuracy = calculate_accuracy(base_guidance * ground_detection)
    else:
        # 无己方部队时，探测效果平方惩罚
        accuracy = calculate_accuracy(base_guidance * ground_detection * ground_detection)

    # 3. 计算有效攻击（软硬攻）
    defender_armor_rate = defender.get_armor_rate()
    attacker_soft_attack = attacker.get_total_panel_at_stage(stage, 'ground_soft_attack')
    attacker_hard_attack = attacker.get_total_panel_at_stage(stage, 'ground_hard_attack')

    effective_attack = defender_armor_rate * attacker_hard_attack + \
                       (1 - defender_armor_rate) * attacker_soft_attack

    # 4. 计算敌方有效防御
    defender_trench_defense = sum(w.trench_defense * w.width * w.quantity for w in defender.weapons)

    if defender.is_defending:
        defender_defense = defender.get_total_panel_at_stage(stage, 'defense')
    else:
        defender_defense = sum(w.breakthrough * w.width * w.quantity for w in defender.weapons)

    effective_defense = defender_trench_defense + defender_defense

    # 5. 计算基础伤害
    base_damage = calculate_base_damage(effective_attack, effective_defense)

    # 6. 计算击穿效率
    # 空军使用对地装甲穿透
    attacker_penetration = attacker.get_total_panel_at_stage(stage, 'ground_penetration')
    defender_armor_thickness = sum(
        w.armor_thickness * w.width * w.quantity
        for w in defender.weapons
        if w.weapon_position == WeaponPositionType.ARMORED.value
    )
    armored_count = sum(w.quantity for w in defender.weapons if w.weapon_position == WeaponPositionType.ARMORED.value)
    if armored_count > 0:
        defender_armor_thickness = defender_armor_thickness / armored_count
    else:
        defender_armor_thickness = 0

    penetration_efficiency = calculate_penetration_efficiency(attacker_penetration, defender_armor_thickness)

    # 7. 计算环境适应系数
    env_coefficient = calculate_environment_coefficient(attacker, active_environments, stage)

    # 8. 计算最终伤害
    final_damage = base_damage * penetration_efficiency * accuracy * env_coefficient

    # 9. 结算
    hp_damage = final_damage * 0.1
    org_damage = final_damage

    return hp_damage, org_damage


def air_to_sea_damage(
    attacker: Formation,
    defender: Formation,
    stage: int,
    target_is_submarine: bool = False
) -> Tuple[float, float, float]:
    """
    计算空对海伤害

    流程：同地对海
    结算差异：浮力值损耗 = 最终伤害 * 0.5（空军对船只浮力伤害更高）

    参数:
        attacker: 进攻方编制（空军）
        defender: 防守方编制（海军）
        stage: 当前交战阶段
        target_is_submarine: 目标是否为潜艇

    返回:
        (结构值伤害, 浮力值伤害, 组织度伤害)
    """
    # 使用地对海的计算逻辑
    structure_damage, buoyancy_damage, org_damage = army_ground_to_sea_damage(
        attacker, defender, stage, target_is_submarine
    )

    # 空对海结算差异：浮力值损耗加倍
    buoyancy_damage = buoyancy_damage * (0.5 / 0.3)  # 从0.3修正到0.5

    return structure_damage, buoyancy_damage, org_damage


# =============================================================================
# 海军伤害判定
# =============================================================================

def navy_to_navy_damage(
    attacker: Formation,
    defender: Formation,
    stage: int,
    target_is_submarine: bool = False
) -> Tuple[float, float, float]:
    """
    计算海对海伤害

    流程：
    1. 命中率：同地对海
    2. 伤害修正：
       - 目标轻甲船：轻炮*1，重炮*1.2，导弹*1
       - 目标重甲船：轻炮*0.8，重炮*1，导弹*0.9
       - 目标潜艇：有效攻击 = 对潜伤害
    3. 击穿判定
    4. 结算：
       - 目标非潜艇：
         * 浮力值损耗 = 击穿效率 * 命中率 *
           (轻炮*0.05 + 重炮*0.4 + 鱼雷*3 + 导弹*0.2)与敌方防御代入全局公式
         * 结构值损耗 = 击穿效率 * 命中率 *
           (轻炮*1 + 重炮*1 + 鱼雷*0.3 + 导弹*1.5)与敌方防御代入全局公式
       - 目标潜艇：
         * 浮力值损耗 = 击穿效率 * 命中率 * 对潜伤害与敌方防御代入全局公式
         * 结构值损耗 = 击穿效率 * 命中率 * 对潜伤害与敌方防御代入全局公式

    注意：
    - 海战是每船独立开火敌方随机船只
    - 此函数计算的是单船对单船的伤害

    参数:
        attacker: 进攻方编制（海军）
        defender: 防守方编制（海军）
        stage: 当前交战阶段
        target_is_submarine: 目标是否为潜艇

    返回:
        (结构值伤害, 浮力值伤害, 组织度伤害)
    """
    # 1. 计算命中率（同地对海）
    attacker_sea_accuracy = attacker.get_total_panel_at_stage(stage, 'sea_accuracy')
    attacker_fire_control = attacker.get_total_panel_at_stage(stage, 'fire_control')

    defender_ecm = defender.get_total_panel_at_stage(stage, 'electronic_jammer')
    defender_eccm = defender.get_total_panel_at_stage(stage, 'electronic_resistance')
    defender_interception = defender.get_total_panel_at_stage(stage, 'air_interception')

    if target_is_submarine:
        attacker_sonar = attacker.get_total_panel_at_stage(stage, 'sonar_strength')
        defender_submarine_stealth = defender.get_total_panel_at_stage(stage, 'submarine_stealth')

        base_guidance_base = attacker_sea_accuracy + \
                             attacker_fire_control * (1 - defender_ecm / (1 + defender_eccm)) - \
                             defender_interception

        if attacker_sonar <= 0:
            base_guidance = 0
        else:
            base_guidance = base_guidance_base * attacker_sonar / (defender_submarine_stealth + 1)
    else:
        base_guidance = attacker_sea_accuracy + \
                        attacker_fire_control * (1 - defender_ecm / (1 + defender_eccm)) - \
                        defender_interception

    accuracy = calculate_accuracy(base_guidance)

    # 2. 计算击穿效率
    attacker_penetration = attacker.get_total_panel_at_stage(stage, 'sea_penetration')
    defender_armor = defender.get_total_panel_at_stage(stage, 'armor_thickness')
    penetration_efficiency = calculate_penetration_efficiency(attacker_penetration, defender_armor)

    # 3. 获取敌方防御
    defender_defense = defender.get_total_panel_at_stage(stage, 'defense')

    # 4. 计算伤害
    if target_is_submarine:
        # 潜艇目标
        anti_sub_damage = attacker.get_total_panel_at_stage(stage, 'anti_sub_damage')

        # 对潜伤害与敌方防御代入全局公式
        base_damage = calculate_base_damage(anti_sub_damage, defender_defense)
        final_damage = penetration_efficiency * accuracy * base_damage

        structure_damage = final_damage
        buoyancy_damage = final_damage
        org_damage = final_damage
    else:
        # 非潜艇目标（军舰）
        # 判断目标装甲类型
        target_armor_type = defender.weapons[0].armor_type if defender.weapons else ArmorType.LIGHT.value

        # 获取各类武器伤害
        light_cannon = attacker.get_total_panel_at_stage(stage, 'light_cannon_damage')
        heavy_cannon = attacker.get_total_panel_at_stage(stage, 'heavy_cannon_damage')
        torpedo = attacker.get_total_panel_at_stage(stage, 'torpedo_damage')
        missile = attacker.get_total_panel_at_stage(stage, 'missile_damage')

        # 根据目标装甲类型修正伤害
        if target_armor_type == ArmorType.LIGHT.value:
            # 轻甲船
            light_cannon_mod = light_cannon * 1
            heavy_cannon_mod = heavy_cannon * 1.2
            missile_mod = missile * 1
        else:
            # 重甲船
            light_cannon_mod = light_cannon * 0.8
            heavy_cannon_mod = heavy_cannon * 1
            missile_mod = missile * 0.9

        # 计算浮力值攻击（轻炮*0.05 + 重炮*0.4 + 鱼雷*3 + 导弹*0.2）
        buoyancy_attack = light_cannon_mod * 0.05 + heavy_cannon_mod * 0.4 + torpedo * 3 + missile_mod * 0.2

        # 计算结构值攻击（轻炮*1 + 重炮*1 + 鱼雷*0.3 + 导弹*1.5）
        structure_attack = light_cannon_mod * 1 + heavy_cannon_mod * 1 + torpedo * 0.3 + missile_mod * 1.5

        # 代入全局公式计算基础伤害
        buoyancy_base_damage = calculate_base_damage(buoyancy_attack, defender_defense)
        structure_base_damage = calculate_base_damage(structure_attack, defender_defense)

        # 计算最终损耗
        buoyancy_damage = penetration_efficiency * accuracy * buoyancy_base_damage
        structure_damage = penetration_efficiency * accuracy * structure_base_damage
        # 组织度损耗：根据需求，敌方组织度 - 最终伤害
        # "最终伤害"在此处指的是结构伤害计算后的值
        org_damage = structure_damage

    return structure_damage, buoyancy_damage, org_damage


def navy_to_ground_damage(
    attacker: Formation,
    defender: Formation,
    stage: int,
    active_environments: List[str]
) -> Tuple[float, float]:
    """
    计算海军岸轰对地面单位伤害

    流程：
    1. 基础导引 = 对地命中 + 火控 * max(0, 1-敌方电子干扰/(1+电子抗性))
    2. 命中率 = min(1.0, max(0.05, 基础导引))
    3. 有效攻击 = 轻炮+重炮的总和（对地岸轰）
    4. 基础伤害 = 全局公式计算
    5. 击穿判定
    6. 最终伤害 = 基础伤害 * 击穿效率 * 命中率 * 环境系数
    7. 结算：敌方血量 - 最终伤害 * 0.1；敌方组织度 - 最终伤害

    注意：
    - 海军岸轰主要使用轻炮和重炮对地伤害
    - 陆军的堑壕防御对岸轰无效（海军火力无法被堑壕阻挡）

    参数:
        attacker: 进攻方编制（海军）
        defender: 防守方编制（陆军）
        stage: 当前交战阶段
        active_environments: 当前生效的环境

    返回:
        (血量伤害, 组织度伤害)
    """
    # 1. 计算基础导引
    attacker_ground_accuracy = attacker.get_total_panel_at_stage(stage, 'ground_accuracy')
    attacker_fire_control = attacker.get_total_panel_at_stage(stage, 'fire_control')

    defender_ecm = defender.get_total_panel_at_stage(stage, 'electronic_jammer')
    defender_eccm = defender.get_total_panel_at_stage(stage, 'electronic_resistance')

    ecm_effect = max(0, 1 - defender_ecm / (1 + defender_eccm))
    base_guidance = attacker_ground_accuracy + attacker_fire_control * ecm_effect

    # 2. 计算命中率
    accuracy = calculate_accuracy(base_guidance)

    # 3. 计算有效攻击（轻炮+重炮岸轰）
    light_cannon = attacker.get_total_panel_at_stage(stage, 'light_cannon_damage')
    heavy_cannon = attacker.get_total_panel_at_stage(stage, 'heavy_cannon_damage')
    missile = attacker.get_total_panel_at_stage(stage, 'missile_damage')

    # 岸轰攻击值：轻炮+重炮+导弹（导弹对地也有效）
    effective_attack = light_cannon * 0.8 + heavy_cannon * 1.5 + missile * 0.5

    # 4. 计算敌方防御（岸轰无视堑壕）
    if defender.is_defending:
        defender_defense = defender.get_total_panel_at_stage(stage, 'defense')
    else:
        defender_defense = sum(w.breakthrough * w.width * w.quantity for w in defender.weapons)

    # 堑壕对岸轰无效，不加入计算

    # 5. 计算基础伤害
    base_damage = calculate_base_damage(effective_attack, defender_defense)

    # 6. 计算击穿效率（海军岸轰穿透）
    attacker_penetration = attacker.get_total_panel_at_stage(stage, 'ground_penetration')
    defender_armor_thickness = sum(
        w.armor_thickness * w.width * w.quantity
        for w in defender.weapons
        if w.weapon_position == WeaponPositionType.ARMORED.value
    )
    armored_count = sum(w.quantity for w in defender.weapons if w.weapon_position == WeaponPositionType.ARMORED.value)
    if armored_count > 0:
        defender_armor_thickness = defender_armor_thickness / armored_count
    else:
        defender_armor_thickness = 0

    penetration_efficiency = calculate_penetration_efficiency(attacker_penetration, defender_armor_thickness)

    # 7. 计算环境适应系数
    env_coefficient = calculate_environment_coefficient(attacker, active_environments, stage)

    # 8. 计算最终伤害
    final_damage = base_damage * penetration_efficiency * accuracy * env_coefficient

    # 9. 结算（地对地系数）
    hp_damage = final_damage * 0.1
    org_damage = final_damage

    return hp_damage, org_damage


# =============================================================================
# 战斗执行逻辑
# =============================================================================

def execute_army_combat_round(
    attacker: Formation,
    defender: Formation,
    stage: int,
    active_environments: List[str]
) -> CombatResult:
    """
    执行陆军战斗回合

    流程：
    1. 判定先手方（侦查值对比）
    2. 先手方攻击
    3. 后手方反击（使用扣血后的面板）
    4. 应用血量惩罚（每损失1%血量，面板下降1%）

    参数:
        attacker: 进攻方编制
        defender: 防守方编制
        stage: 当前交战阶段
        active_environments: 当前生效的环境

    返回:
        战斗结果
    """
    # 获取侦查值
    attacker_recon = attacker.get_recon_value()
    defender_recon = defender.get_recon_value()

    # 判定先手
    attacker_first = determine_first_strike(attacker_recon, defender_recon)

    attacker_damage = 0
    defender_damage = 0

    if attacker_first:
        # 进攻方先手
        hp_damage, org_damage = army_ground_to_ground_damage(attacker, defender, stage, active_environments)
        attacker_damage = org_damage

        # 应用伤害
        defender.current_hp -= hp_damage
        defender.current_organization -= org_damage

        # 应用血量惩罚
        defender.apply_damage_penalty()

        # 防守方反击（使用扣血后的面板）
        if not defender.is_defeated():
            hp_damage, org_damage = army_ground_to_ground_damage(defender, attacker, stage, active_environments)
            defender_damage = org_damage

            attacker.current_hp -= hp_damage
            attacker.current_organization -= org_damage
            attacker.apply_damage_penalty()
    else:
        # 防守方先手（防守方反击）
        hp_damage, org_damage = army_ground_to_ground_damage(defender, attacker, stage, active_environments)
        defender_damage = org_damage

        attacker.current_hp -= hp_damage
        attacker.current_organization -= org_damage
        attacker.apply_damage_penalty()

        # 进攻方反击
        if not attacker.is_defeated():
            hp_damage, org_damage = army_ground_to_ground_damage(attacker, defender, stage, active_environments)
            attacker_damage = org_damage

            defender.current_hp -= hp_damage
            defender.current_organization -= org_damage
            defender.apply_damage_penalty()

    # 计算推进度并确定距离变化
    attacker_speed = sum(w.speed * w.quantity for w in attacker.weapons) / attacker.total_width
    attacker_breakthrough = sum(w.breakthrough * w.quantity for w in attacker.weapons)
    attacker_suppression = attacker.get_total_panel_at_stage(stage, 'ground_suppression')
    defender_suppression = defender.get_total_panel_at_stage(stage, 'ground_suppression')

    progress = calculate_army_advance_progress(attacker_speed, attacker_breakthrough,
                                                attacker_suppression, defender_suppression)

    new_stage = determine_distance_change(progress, stage, ForceType.ARMY)

    return CombatResult(
        attacker_damage=attacker_damage,
        defender_damage=defender_damage,
        attacker_first=attacker_first,
        distance_change=new_stage - stage,
        stage=stage
    )


def execute_navy_combat_round(
    attacker: Formation,
    defender: Formation,
    stage: int
) -> CombatResult:
    """
    执行海军战斗回合

    流程：
    1. 每个船只独立开火敌方随机船只
    2. 双方所有船都会开火一次
    3. 判定先手方决定开火顺序

    注意：
    海战有一方一半以上船只失去战斗力则战役结束

    参数:
        attacker: 进攻方舰队
        defender: 防守方舰队

    返回:
        战斗结果
    """
    # 判定先手
    attacker_recon = attacker.get_recon_value()
    defender_recon = defender.get_recon_value()
    attacker_first = determine_first_strike(attacker_recon, defender_recon)

    total_attacker_damage = 0
    total_defender_damage = 0

    # 海战：每船独立开火
    # 修正：navy_to_navy_damage计算整个编制的伤害，需要按武器类型数量分摊
    # 避免伤害被武器类型数量倍增
    attacker_weapon_types = len(attacker.weapons)
    defender_weapon_types = len(defender.weapons) if defender.weapons else 1

    if attacker_first:
        # 进攻方先开火
        for attacker_ship in attacker.weapons:
            # 随机选择防守方船只
            if defender.weapons:
                target_ship = random.choice(defender.weapons)

                # 判断目标类型
                target_is_submarine = '潜艇' in target_ship.weapon_type.lower() if hasattr(target_ship, 'weapon_type') else False

                # 计算伤害（单船对单船）
                # 修正：将整个编制的伤害分摊到每个武器类型
                structure_damage, buoyancy_damage, org_damage = navy_to_navy_damage(
                    attacker, defender, stage, target_is_submarine
                )

                # 分摊伤害到单个武器类型
                structure_damage /= attacker_weapon_types
                buoyancy_damage /= attacker_weapon_types
                org_damage /= attacker_weapon_types

                # 应用伤害
                defender.current_structure -= structure_damage
                defender.current_buoyancy -= buoyancy_damage
                defender.current_organization -= org_damage

                total_attacker_damage += org_damage

        # 应用血量惩罚
        defender.apply_damage_penalty()

        # 防守方反击
        if not defender.is_defeated():
            for defender_ship in defender.weapons:
                if attacker.weapons:
                    target_ship = random.choice(attacker.weapons)

                    target_is_submarine = '潜艇' in target_ship.weapon_type.lower() if hasattr(target_ship, 'weapon_type') else False

                    structure_damage, buoyancy_damage, org_damage = navy_to_navy_damage(
                        defender, attacker, stage, target_is_submarine
                    )

                    # 分摊伤害到单个武器类型
                    structure_damage /= defender_weapon_types
                    buoyancy_damage /= defender_weapon_types
                    org_damage /= defender_weapon_types

                    attacker.current_structure -= structure_damage
                    attacker.current_buoyancy -= buoyancy_damage
                    attacker.current_organization -= org_damage

                    total_defender_damage += org_damage

            attacker.apply_damage_penalty()
    else:
        # 防守方先开火
        if defender.weapons:
            for defender_ship in defender.weapons:
                if attacker.weapons:
                    target_ship = random.choice(attacker.weapons)

                    target_is_submarine = '潜艇' in target_ship.weapon_type.lower() if hasattr(target_ship, 'weapon_type') else False

                    structure_damage, buoyancy_damage, org_damage = navy_to_navy_damage(
                        defender, attacker, stage, target_is_submarine
                    )

                    # 分摊伤害到单个武器类型
                    structure_damage /= defender_weapon_types
                    buoyancy_damage /= defender_weapon_types
                    org_damage /= defender_weapon_types

                    attacker.current_structure -= structure_damage
                    attacker.current_buoyancy -= buoyancy_damage
                    attacker.current_organization -= org_damage

                    total_defender_damage += org_damage

            attacker.apply_damage_penalty()

        # 进攻方反击
        if not attacker.is_defeated():
            for attacker_ship in attacker.weapons:
                if defender.weapons:
                    target_ship = random.choice(defender.weapons)

                    target_is_submarine = '潜艇' in target_ship.weapon_type.lower() if hasattr(target_ship, 'weapon_type') else False

                    structure_damage, buoyancy_damage, org_damage = navy_to_navy_damage(
                        attacker, defender, stage, target_is_submarine
                    )

                    # 分摊伤害到单个武器类型
                    structure_damage /= attacker_weapon_types
                    buoyancy_damage /= attacker_weapon_types
                    org_damage /= attacker_weapon_types

                    defender.current_structure -= structure_damage
                    defender.current_buoyancy -= buoyancy_damage
                    defender.current_organization -= org_damage

                    total_attacker_damage += org_damage

            defender.apply_damage_penalty()

    # 计算推进度
    attacker_speed = sum(w.speed * w.quantity for w in attacker.weapons) / attacker.total_width
    defender_speed = sum(w.speed * w.quantity for w in defender.weapons) / defender.total_width

    progress = calculate_navy_air_advance_progress(attacker_speed, defender_speed)
    new_stage = determine_distance_change(progress, stage, ForceType.NAVY)

    return CombatResult(
        attacker_damage=total_attacker_damage,
        defender_damage=total_defender_damage,
        attacker_first=attacker_first,
        distance_change=new_stage - stage,
        stage=stage
    )


def execute_air_combat_round(
    attacker: Formation,
    defender: Formation,
    stage: int,
    active_environments: List[str]
) -> CombatResult:
    """
    执行空军战斗回合

    流程：
    1. 判定先手方（侦查值对比）
    2. 空对空伤害计算（无击穿判定）
    3. 结算：敌方血量 - 最终伤害 * 0.3；敌方组织度 - 最终伤害
    4. 应用血量惩罚

    注意：
    - 空战没有击穿判定
    - 空军防御值固定为0
    - 血量伤害系数是0.3而非陆军的0.1

    参数:
        attacker: 进攻方编制（空军）
        defender: 防守方编制（空军）
        stage: 当前交战阶段
        active_environments: 当前生效的环境

    返回:
        战斗结果
    """
    # 获取侦查值
    attacker_recon = attacker.get_recon_value()
    defender_recon = defender.get_recon_value()

    # 判定先手
    attacker_first = determine_first_strike(attacker_recon, defender_recon)

    attacker_damage = 0
    defender_damage = 0

    def calculate_air_to_air_damage(attacker: Formation, defender: Formation, stage: int) -> Tuple[float, float]:
        """
        计算空对空伤害（无击穿判定）

        流程：
        1. 基础导引 = 对空命中 + 火控*(1-敌方干扰/(1+电子抗性)) - 敌方拦截
        2. 命中率 = min(1.0, max(0.05, 基础导引))
        3. 最终伤害 = 对空伤害 * 命中率
        4. 结算：敌方血量 - 最终伤害*0.3；敌方组织度 - 最终伤害

        返回:
            (血量伤害, 组织度伤害)
        """
        # 1. 计算基础导引
        attacker_air_accuracy = attacker.get_total_panel_at_stage(stage, 'air_accuracy')
        attacker_fire_control = attacker.get_total_panel_at_stage(stage, 'fire_control')

        defender_interference = defender.get_total_panel_at_stage(stage, 'electronic_jammer')
        defender_eccm = defender.get_total_panel_at_stage(stage, 'electronic_resistance')
        defender_interception = defender.get_total_panel_at_stage(stage, 'air_interception')

        # 电子干扰效果
        ecm_effect = max(0, 1 - defender_interference / (1 + defender_eccm))
        base_guidance = attacker_air_accuracy + \
                        attacker_fire_control * ecm_effect - \
                        defender_interception

        # 2. 计算命中率
        accuracy = calculate_accuracy(base_guidance)

        # 3. 计算最终伤害（对空伤害，无击穿）
        attacker_air_damage = attacker.get_total_panel_at_stage(stage, 'air_damage')
        final_damage = attacker_air_damage * accuracy

        # 4. 结算（空军血量系数为0.3）
        hp_damage = final_damage * 0.3
        org_damage = final_damage

        return hp_damage, org_damage

    if attacker_first:
        # 进攻方先手
        hp_damage, org_damage = calculate_air_to_air_damage(attacker, defender, stage)
        attacker_damage = org_damage

        # 应用伤害
        defender.current_hp -= hp_damage
        defender.current_organization -= org_damage

        # 应用血量惩罚
        defender.apply_damage_penalty()

        # 防守方反击（使用扣血后的面板）
        if not defender.is_defeated():
            hp_damage, org_damage = calculate_air_to_air_damage(defender, attacker, stage)
            defender_damage = org_damage

            attacker.current_hp -= hp_damage
            attacker.current_organization -= org_damage
            attacker.apply_damage_penalty()
    else:
        # 防守方先手
        hp_damage, org_damage = calculate_air_to_air_damage(defender, attacker, stage)
        defender_damage = org_damage

        attacker.current_hp -= hp_damage
        attacker.current_organization -= org_damage
        attacker.apply_damage_penalty()

        # 进攻方反击
        if not attacker.is_defeated():
            hp_damage, org_damage = calculate_air_to_air_damage(attacker, defender, stage)
            attacker_damage = org_damage

            defender.current_hp -= hp_damage
            defender.current_organization -= org_damage
            defender.apply_damage_penalty()

    # 计算推进度（空军用速度差）
    attacker_speed = sum(w.speed * w.quantity for w in attacker.weapons) / attacker.total_width
    defender_speed = sum(w.speed * w.quantity for w in defender.weapons) / defender.total_width

    progress = calculate_navy_air_advance_progress(attacker_speed, defender_speed)
    new_stage = determine_distance_change(progress, stage, ForceType.AIR)

    return CombatResult(
        attacker_damage=attacker_damage,
        defender_damage=defender_damage,
        attacker_first=attacker_first,
        distance_change=new_stage - stage,
        stage=stage
    )


def run_combat_loop(
    attacker: Formation,
    defender: Formation,
    force_type: ForceType,
    active_environments: List[str] = [],
    max_rounds: int = 1000,
    stats_collector: Optional[Any] = None  # 统计收集器（CombatStatistics对象）
) -> Dict:
    """
    运行完整战斗循环

    流程：
    1. 从阶段6（20-40km）开始交战
    2. 每回合执行战斗判定
    3. 根据推进度调整距离
    4. 在阶段1结算完成后重置到阶段6循环
    5. 直到一方溃败

    参数:
        attacker: 进攻方编制
        defender: 防守方编制
        force_type: 军种类型
        active_environments: 当前生效的环境
        max_rounds: 最大回合数（防止无限循环）
        stats_collector: 统计收集器对象（用于收集详细战斗数据）

    返回:
        战斗结果字典
    """
    # 初始化战斗状态
    current_stage = 6  # 开局从20-40km开始

    round_count = 0
    total_attacker_damage = 0
    total_defender_damage = 0

    # 记录每个阶段的战斗次数
    stage_combat_count = {i: 0 for i in range(1, 11)}

    while round_count < max_rounds:
        round_count += 1

        # 检查是否需要重置距离
        if should_reset_distance(current_stage, force_type):
            current_stage = 6  # 重置到阶段6

        # 记录阶段战斗次数
        stage_combat_count[current_stage] += 1

        # 根据军种执行战斗
        if force_type == ForceType.ARMY:
            result = execute_army_combat_round(attacker, defender, current_stage, active_environments)
        elif force_type == ForceType.NAVY:
            result = execute_navy_combat_round(attacker, defender, current_stage)
        else:  # AIR - 使用独立的空战逻辑
            result = execute_air_combat_round(attacker, defender, current_stage, active_environments)

        total_attacker_damage += result.attacker_damage
        total_defender_damage += result.defender_damage

        # 收集统计数据（如果提供了收集器）
        if stats_collector is not None:
            # 计算本回合燃料消耗
            attacker_fuel = sum(w.fuel_per_round * w.quantity for w in attacker.weapons)
            defender_fuel = sum(w.fuel_per_round * w.quantity for w in defender.weapons)
            attacker_nuclear = sum(w.nuclear_per_round * w.quantity for w in attacker.weapons)
            defender_nuclear = sum(w.nuclear_per_round * w.quantity for w in defender.weapons)

            # 调用统计收集器的记录方法
            stats_collector.record_round(
                stage=current_stage,
                attacker_damage=result.attacker_damage,
                defender_damage=result.defender_damage,
                attacker_org_damage=result.attacker_org_damage if hasattr(result, 'attacker_org_damage') else result.attacker_damage,
                defender_org_damage=result.defender_org_damage if hasattr(result, 'defender_org_damage') else result.defender_damage,
                attacker_penetrated=result.attacker_penetrated if hasattr(result, 'attacker_penetrated') else False,
                defender_penetrated=result.defender_penetrated if hasattr(result, 'defender_penetrated') else False,
                attacker_fuel=attacker_fuel,
                defender_fuel=defender_fuel,
                attacker_nuclear=attacker_nuclear,
                defender_nuclear=defender_nuclear
            )

        # 更新距离阶段
        current_stage = current_stage + result.distance_change

        # 检查战斗结束条件
        if attacker.is_defeated() or defender.is_defeated():
            break

    # 返回战斗结果
    winner = "defender" if attacker.is_defeated() else "attacker"

    return {
        "winner": winner,
        "rounds": round_count,
        "total_attacker_damage": total_attacker_damage,
        "total_defender_damage": total_defender_damage,
        "stage_combat_count": stage_combat_count,
        "attacker_remaining_hp": attacker.current_hp,
        "attacker_remaining_org": attacker.current_organization,
        "defender_remaining_hp": defender.current_hp,
        "defender_remaining_org": defender.current_organization
    }


# =============================================================================
# 测试代码
# =============================================================================

def test_base_damage_formula():
    """测试全局基础伤害公式"""
    print("=== 测试全局基础伤害公式 ===")

    # 测试1：攻击小于等于防御
    attack, defense = 50, 100
    damage = calculate_base_damage(attack, defense)
    print(f"攻击={attack}, 防御={defense} → 伤害={damage}")
    # 预期：50 * 0.1 = 5

    # 测试2：攻击大于防御
    attack, defense = 150, 100
    damage = calculate_base_damage(attack, defense)
    print(f"攻击={attack}, 防御={defense} → 伤害={damage}")
    # 预期：100 * 0.1 + (150-100) * 0.4 = 10 + 20 = 30

    # 测试3：攻击远超防御
    attack, defense = 500, 100
    damage = calculate_base_damage(attack, defense)
    print(f"攻击={attack}, 防御={defense} → 伤害={damage}")
    # 预期：100 * 0.1 + (500-100) * 0.4 = 10 + 160 = 170


def test_penetration_efficiency():
    """测试击穿效率计算"""
    print("\n=== 测试击穿效率计算 ===")

    # 测试1：完全击穿
    penetration, armor = 100, 50
    efficiency = calculate_penetration_efficiency(penetration, armor)
    print(f"穿透={penetration}, 装甲={armor} → 击穿效率={efficiency}")
    # 预期：1.0

    # 测试2：部分击穿
    penetration, armor = 50, 100
    efficiency = calculate_penetration_efficiency(penetration, armor)
    print(f"穿透={penetration}, 装甲={armor} → 击穿效率={efficiency}")
    # 预期：max(0.1, 50/101) ≈ 0.495

    # 测试3：完全无法击穿
    penetration, armor = 5, 100
    efficiency = calculate_penetration_efficiency(penetration, armor)
    print(f"穿透={penetration}, 装甲={armor} → 击穿效率={efficiency}")
    # 预期：max(0.1, 5/101) ≈ 0.1


def test_environment_coefficient():
    """测试环境适应系数计算"""
    print("\n=== 测试环境适应系数计算 ===")

    # 创建测试编制
    weapon1 = WeaponStats(
        weapon_type="步枪",
        era="二战",
        cost=100,
        width=1,
        speed=5,
        organization=30,
        hp=100,
        environment_adaptations={"平原适应性": 0.9, "城市适应性": 0.7}
    )
    weapon1.quantity = 100

    formation = Formation(
        force_type=ForceType.ARMY,
        name="步兵团",
        weapons=[weapon1]
    )

    # 测试单环境
    coefficient = calculate_environment_coefficient(formation, ["平原适应性"], 6)
    print(f"单环境（平原0.9）→ 适应系数={coefficient}")

    # 测试双环境
    coefficient = calculate_environment_coefficient(formation, ["平原适应性", "城市适应性"], 6)
    print(f"双环境（平原0.9 + 城市0.7）→ 适应系数={coefficient}")
    # 预期：(0.9 + 0.7) / 2 = 0.8


def test_distance_system():
    """测试距离推进系统"""
    print("\n=== 测试距离推进系统 ===")

    # 测试陆军推进度计算
    progress = calculate_army_advance_progress(
        attacker_speed=20,
        attacker_breakthrough=100,
        attacker_suppression=50,
        defender_suppression=30
    )
    print(f"陆军推进度（速度20, 突破100, 攻方压制50, 守方压制30）→ {progress:.3f}")

    # 测试海军推进度计算
    progress = calculate_navy_air_advance_progress(
        attacker_speed=30,
        defender_speed=20
    )
    print(f"海军推进度（攻方速度30, 守方速度20）→ {progress:.3f}")

    # 测试距离变化判定
    new_stage = determine_distance_change(0.5, 6, ForceType.ARMY)
    print(f"推进度0.5 > 0.2 → 新阶段={new_stage}（从6缩短到5）")

    new_stage = determine_distance_change(-0.5, 3, ForceType.ARMY)
    print(f"推进度-0.5 < -0.3 → 新阶段={new_stage}（从3延长到4）")


if __name__ == "__main__":
    """主函数：运行所有测试"""
    test_base_damage_formula()
    test_penetration_efficiency()
    test_environment_coefficient()
    test_distance_system()

    print("\n所有测试完成！")


# =============================================================================
# CSV数据加载功能
# =============================================================================

def parse_10_stage_value(value_str: str) -> List[float]:
    """
    解析10阶段数值字符串

    CSV中的10阶段数值使用"="分隔，如: "0.003=0.008=0.014=..."

    参数:
        value_str: "="分隔的数值字符串

    返回:
        10个浮点数的列表
    """
    if not value_str or value_str.strip() == "":
        return [0.0] * 10

    parts = value_str.strip().split('=')
    result = []
    for part in parts:
        try:
            result.append(float(part.strip()))
        except ValueError:
            result.append(0.0)

    # 确保10个数值
    while len(result) < 10:
        result.append(0.0)

    return result[:10]


def parse_single_value(value_str: str) -> float:
    """
    解析单个数值

    参数:
        value_str: 数值字符串

    返回:
        浮点数
    """
    if not value_str or value_str.strip() == "":
        return 0.0
    try:
        return float(value_str.strip())
    except ValueError:
        return 0.0


def parse_single_int(value_str: str) -> int:
    """
    解析单个整数

    参数:
        value_str: 数值字符串

    返回:
        整数
    """
    if not value_str or value_str.strip() == "":
        return 0
    try:
        return int(float(value_str.strip()))
    except ValueError:
        return 0


def load_army_csv(csv_path: str) -> Dict[str, WeaponStats]:
    """
    加载陆军CSV文件

    参数:
        csv_path: army.csv文件路径

    返回:
        武器名称到WeaponStats的字典映射
    """
    weapons = {}

    # 陆军CSV列映射
    ARMY_COLUMNS = {
        'weapon_type': 0,       # 武器种类
        'era': 1,               # 时代
        'cost': 2,              # 成本
        'width': 5,             # 编制宽度
        'organization': 6,      # 组织度
        'recon': 7,             # 侦查（10阶段）
        'defense': 8,           # 防御（10阶段）
        'armor_thickness': 9,   # 装甲厚度
        'fire_control': 10,     # 火控（10阶段）
        'electronic_jammer': 11,    # 电子干扰（10阶段）
        'electronic_resistance': 12, # 电子抗性（10阶段）
        'fuel_capacity': 13,        # 燃料容量
        'fuel_per_round': 14,       # 燃料每轮消耗
        'ground_friendly_damage': 15,  # 对地友伤（10阶段）
        'ground_accuracy': 16,     # 对地命中（10阶段）
        'ground_penetration': 17,  # 对地穿甲穿透（10阶段）
        'ground_suppression': 18,  # 对地压制（10阶段）
        'air_accuracy': 19,        # 对空命中（10阶段）
        'air_damage': 20,          # 对空伤害（10阶段）
        'sea_accuracy': 22,        # 对海命中（10阶段）
        'sea_penetration': 23,     # 对海装甲穿透（10阶段）
        'speed': 47,               # 速度
        'hp': 50,                  # 血量
        'breakthrough': 51,        # 突破（10阶段）
        'trench_defense': 52,      # 堑壕防御
        'ground_hard_attack': 53,  # 对地硬攻（10阶段）
        'ground_soft_attack': 54,  # 对地软攻（10阶段）
        'ground_damage': 55,       # 对地伤害（10阶段）
        'weapon_position': 56,     # 武器定位
    }

    # 环境适应性列索引（24-45，共22个）
    ENV_START_COL = 24

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # 跳过标题行

        for row in reader:
            if len(row) < 57:
                continue

            weapon_name = row[ARMY_COLUMNS['weapon_type']].strip()
            if not weapon_name:
                continue

            # 解析环境适应性
            env_adaptations = {}
            for i, env_name in enumerate(ENVIRONMENT_TYPES):
                col_idx = ENV_START_COL + i
                if col_idx < len(row):
                    env_adaptations[env_name] = parse_single_value(row[col_idx])

            # 创建WeaponStats对象
            weapon = WeaponStats(
                weapon_type=weapon_name,
                era=row[ARMY_COLUMNS['era']].strip(),
                cost=parse_single_value(row[ARMY_COLUMNS['cost']]),
                width=parse_single_int(row[ARMY_COLUMNS['width']]),
                speed=parse_single_value(row[ARMY_COLUMNS['speed']]),
                organization=parse_single_value(row[ARMY_COLUMNS['organization']]),
                hp=parse_single_value(row[ARMY_COLUMNS['hp']]),
                recon=parse_10_stage_value(row[ARMY_COLUMNS['recon']]),
                defense=parse_10_stage_value(row[ARMY_COLUMNS['defense']]),
                armor_thickness=parse_single_value(row[ARMY_COLUMNS['armor_thickness']]),
                fire_control=parse_10_stage_value(row[ARMY_COLUMNS['fire_control']]),
                electronic_jammer=parse_10_stage_value(row[ARMY_COLUMNS['electronic_jammer']]),
                electronic_resistance=parse_10_stage_value(row[ARMY_COLUMNS['electronic_resistance']]),
                fuel_capacity=parse_single_value(row[ARMY_COLUMNS['fuel_capacity']]),
                fuel_per_round=parse_single_value(row[ARMY_COLUMNS['fuel_per_round']]),
                ground_friendly_damage=parse_10_stage_value(row[ARMY_COLUMNS['ground_friendly_damage']]),
                ground_accuracy=parse_10_stage_value(row[ARMY_COLUMNS['ground_accuracy']]),
                ground_penetration=parse_10_stage_value(row[ARMY_COLUMNS['ground_penetration']]),
                ground_suppression=parse_10_stage_value(row[ARMY_COLUMNS['ground_suppression']]),
                air_accuracy=parse_10_stage_value(row[ARMY_COLUMNS['air_accuracy']]),
                air_damage=parse_10_stage_value(row[ARMY_COLUMNS['air_damage']]),
                sea_accuracy=parse_10_stage_value(row[ARMY_COLUMNS['sea_accuracy']]),
                sea_penetration=parse_10_stage_value(row[ARMY_COLUMNS['sea_penetration']]),
                ground_hard_attack=parse_10_stage_value(row[ARMY_COLUMNS['ground_hard_attack']]),
                ground_soft_attack=parse_10_stage_value(row[ARMY_COLUMNS['ground_soft_attack']]),
                ground_damage=parse_10_stage_value(row[ARMY_COLUMNS['ground_damage']]),
                trench_defense=parse_single_value(row[ARMY_COLUMNS['trench_defense']]),
                breakthrough=parse_single_value(row[ARMY_COLUMNS['breakthrough']]),
                weapon_position=parse_single_int(row[ARMY_COLUMNS['weapon_position']]),
                environment_adaptations=env_adaptations,
            )

            # 使用 "武器名_时代" 作为key，避免同名武器覆盖
            era = row[ARMY_COLUMNS['era']]
            weapons[f"{weapon_name}_{era}"] = weapon

    return weapons


def load_air_csv(csv_path: str) -> Dict[str, WeaponStats]:
    """
    加载空军CSV文件

    参数:
        csv_path: air.csv文件路径

    返回:
        武器名称到WeaponStats的字典映射
    """
    weapons = {}

    # 空军CSV列映射（基于air.csv结构）
    # 列索引: 0=武器种类, 1=时代, 2=成本, 5=编制宽度, 6=组织度...
    AIR_COLUMNS = {
        'weapon_type': 0,       # 武器种类
        'era': 1,               # 时代
        'cost': 2,              # 成本
        'width': 5,             # 编制宽度
        'organization': 6,      # 组织度
        'recon': 7,             # 侦查（10阶段）
        'armor_thickness': 9,   # 装甲厚度
        'fire_control': 10,     # 火控（10阶段）
        'electronic_jammer': 11,    # 电子干扰（10阶段）
        'electronic_resistance': 12, # 电子抗性（10阶段）
        'fuel_capacity': 13,        # 燃料容量
        'fuel_per_round': 14,       # 燃料每轮消耗
        'ground_friendly_damage': 15,  # 对地友伤（10阶段）
        'ground_accuracy': 16,     # 对地命中（10阶段）
        'ground_penetration': 17,  # 对地穿甲穿透（10阶段）
        'ground_suppression': 18,  # 对地压制（10阶段）
        'air_accuracy': 19,        # 对空命中（10阶段）
        'air_damage': 20,          # 对空伤害（10阶段）
        'sea_accuracy': 22,        # 对海命中（10阶段）
        'sea_penetration': 23,     # 对海装甲穿透（10阶段）
        'speed': 47,               # 速度（km/h）
        'hp': 48,                  # 血量
        'air_interception': 49,    # 拦截（10阶段）
        'stealth': 50,             # 隐身（10阶段）
        'radar_strength': 51,      # 雷达强度（10阶段）
        'radar_radius': 52,        # 雷达半径(km)
        'sonar_strength': 53,      # 声呐强度（10阶段）
        'ground_damage': 56,       # 对地伤害（10阶段）
        'ground_detection': 57,    # 对地探测（10阶段）- 侦察机/预警机专用
        'sea_damage': 58,          # 对海伤害（10阶段）
        'anti_sub_damage': 59,     # 对潜伤害（10阶段）
    }

    # 环境适应性列索引（24-45，共22个）
    ENV_START_COL = 24

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # 跳过标题行

        for row in reader:
            if len(row) < 60:
                continue

            weapon_name = row[AIR_COLUMNS['weapon_type']].strip()
            if not weapon_name:
                continue

            # 解析环境适应性
            env_adaptations = {}
            for i, env_name in enumerate(ENVIRONMENT_TYPES):
                col_idx = ENV_START_COL + i
                if col_idx < len(row):
                    env_adaptations[env_name] = parse_single_value(row[col_idx])

            # 空军防御填0
            defense = [0.0] * 10

            # 解析ground_damage用于soft/hard attack
            ground_damage_values = parse_10_stage_value(row[AIR_COLUMNS['ground_damage']])
            # 空军使用ground_damage作为soft_attack（对地伤害）
            ground_soft_attack = ground_damage_values
            # 空军hard_attack = ground_damage * 1.5（对装甲目标更强）
            ground_hard_attack = [v * 1.5 for v in ground_damage_values]

            # 创建WeaponStats对象
            weapon = WeaponStats(
                weapon_type=weapon_name,
                era=row[AIR_COLUMNS['era']].strip(),
                cost=parse_single_value(row[AIR_COLUMNS['cost']]),
                width=parse_single_int(row[AIR_COLUMNS['width']]),
                speed=parse_single_value(row[AIR_COLUMNS['speed']]),
                organization=parse_single_value(row[AIR_COLUMNS['organization']]),
                hp=parse_single_value(row[AIR_COLUMNS['hp']]),
                recon=parse_10_stage_value(row[AIR_COLUMNS['recon']]),
                defense=defense,  # 空军防御为0
                armor_thickness=parse_single_value(row[AIR_COLUMNS['armor_thickness']]),
                fire_control=parse_10_stage_value(row[AIR_COLUMNS['fire_control']]),
                electronic_jammer=parse_10_stage_value(row[AIR_COLUMNS['electronic_jammer']]),
                electronic_resistance=parse_10_stage_value(row[AIR_COLUMNS['electronic_resistance']]),
                fuel_capacity=parse_single_value(row[AIR_COLUMNS['fuel_capacity']]),
                fuel_per_round=parse_single_value(row[AIR_COLUMNS['fuel_per_round']]),
                ground_friendly_damage=parse_10_stage_value(row[AIR_COLUMNS['ground_friendly_damage']]),
                ground_accuracy=parse_10_stage_value(row[AIR_COLUMNS['ground_accuracy']]),
                ground_penetration=parse_10_stage_value(row[AIR_COLUMNS['ground_penetration']]),
                ground_suppression=parse_10_stage_value(row[AIR_COLUMNS['ground_suppression']]),
                ground_soft_attack=ground_soft_attack,  # 空军soft_attack = ground_damage
                ground_hard_attack=ground_hard_attack,  # 空军hard_attack = ground_damage * 1.5
                air_accuracy=parse_10_stage_value(row[AIR_COLUMNS['air_accuracy']]),
                air_damage=parse_10_stage_value(row[AIR_COLUMNS['air_damage']]),
                air_interception=parse_10_stage_value(row[AIR_COLUMNS['air_interception']]),
                sea_accuracy=parse_10_stage_value(row[AIR_COLUMNS['sea_accuracy']]),
                sea_penetration=parse_10_stage_value(row[AIR_COLUMNS['sea_penetration']]),
                stealth=parse_10_stage_value(row[AIR_COLUMNS['stealth']]),
                radar_strength=parse_10_stage_value(row[AIR_COLUMNS['radar_strength']]),
                radar_radius=parse_single_value(row[AIR_COLUMNS['radar_radius']]),
                sonar_strength=parse_10_stage_value(row[AIR_COLUMNS['sonar_strength']]),
                ground_detection=parse_10_stage_value(row[AIR_COLUMNS['ground_detection']]),
                ground_damage=ground_damage_values,
                sea_damage=parse_10_stage_value(row[AIR_COLUMNS['sea_damage']]),
                anti_sub_damage=parse_10_stage_value(row[AIR_COLUMNS['anti_sub_damage']]),
                environment_adaptations=env_adaptations,
            )

            # 使用 "武器名_时代" 作为key，避免同名武器覆盖
            era = row[AIR_COLUMNS['era']]
            weapons[f"{weapon_name}_{era}"] = weapon

    return weapons


def load_navy_csv(csv_path: str) -> Dict[str, WeaponStats]:
    """
    加载海军CSV文件

    参数:
        csv_path: navy.csv文件路径

    返回:
        武器名称到WeaponStats的字典映射
    """
    weapons = {}

    # 海军CSV列映射（基于navy.csv结构）
    # 列索引: 0=武器种类, 1=时代, 2=成本, 5=编制宽度, 6=组织度...
    NAVY_COLUMNS = {
        'weapon_type': 0,       # 武器种类
        'era': 1,               # 时代
        'cost': 2,              # 成本
        'width': 5,             # 编制宽度
        'organization': 6,      # 组织度
        'recon': 7,             # 侦查（10阶段）
        'defense': 8,           # 防御（10阶段）
        'armor_thickness': 9,   # 装甲厚度
        'fire_control': 10,     # 火控（10阶段）
        'electronic_jammer': 11,    # 电子干扰（10阶段）
        'electronic_resistance': 12, # 电子抗性（10阶段）
        'fuel_capacity': 13,        # 燃料容量
        'fuel_per_round': 14,       # 燃料每轮消耗
        'ground_friendly_damage': 15,  # 对地友伤（10阶段）
        'ground_accuracy': 16,     # 对地命中（10阶段）
        'ground_penetration': 17,  # 对地穿甲穿透（10阶段）
        'ground_suppression': 18,  # 对地压制（10阶段）
        'air_accuracy': 19,        # 对空命中（10阶段）
        'air_damage': 20,          # 对空伤害（10阶段）
        'sea_accuracy': 22,        # 对海命中（10阶段）
        'sea_penetration': 23,     # 对海装甲穿透（10阶段）
        'speed': 47,               # 速度（km/h）
        'structure': 48,           # 结构值
        'buoyancy': 49,            # 浮力值
        'armor_type': 50,          # 装甲类型（0=轻甲，1=重甲）
        'air_interception': 51,    # 拦截
        'submarine_stealth': 52,   # 潜艇隐身（10阶段）
        'radar_strength': 53,      # 雷达强度（10阶段）
        'radar_radius': 54,        # 雷达半径(km)
        'sonar_strength': 55,      # 声呐强度（10阶段）
        'nuclear_capacity': 56,    # 核动力能容量
        'nuclear_per_round': 57,   # 核动力能每轮消耗
        'light_cannon_damage': 61, # 轻炮对海伤害（10阶段）
        'heavy_cannon_damage': 62, # 重炮对海伤害（10阶段）
        'torpedo_damage': 63,      # 鱼雷对海伤害（10阶段）
        'missile_damage': 64,      # 导弹对海伤害（10阶段）
        'anti_sub_damage': 65,     # 对潜伤害（10阶段）
    }

    # 环境适应性列索引（24-45，共22个）
    ENV_START_COL = 24

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # 跳过标题行

        for row in reader:
            if len(row) < 66:
                continue

            weapon_name = row[NAVY_COLUMNS['weapon_type']].strip()
            if not weapon_name:
                continue

            # 解析环境适应性
            env_adaptations = {}
            for i, env_name in enumerate(ENVIRONMENT_TYPES):
                col_idx = ENV_START_COL + i
                if col_idx < len(row):
                    env_adaptations[env_name] = parse_single_value(row[col_idx])

            # 创建WeaponStats对象
            weapon = WeaponStats(
                weapon_type=weapon_name,
                era=row[NAVY_COLUMNS['era']].strip(),
                cost=parse_single_value(row[NAVY_COLUMNS['cost']]),
                width=parse_single_int(row[NAVY_COLUMNS['width']]),
                speed=parse_single_value(row[NAVY_COLUMNS['speed']]),
                organization=parse_single_value(row[NAVY_COLUMNS['organization']]),
                hp=0,  # 海军不使用hp
                structure=parse_single_value(row[NAVY_COLUMNS['structure']]),
                buoyancy=parse_single_value(row[NAVY_COLUMNS['buoyancy']]),
                recon=parse_10_stage_value(row[NAVY_COLUMNS['recon']]),
                defense=parse_10_stage_value(row[NAVY_COLUMNS['defense']]),
                armor_thickness=parse_single_value(row[NAVY_COLUMNS['armor_thickness']]),
                armor_type=parse_single_int(row[NAVY_COLUMNS['armor_type']]),
                fire_control=parse_10_stage_value(row[NAVY_COLUMNS['fire_control']]),
                electronic_jammer=parse_10_stage_value(row[NAVY_COLUMNS['electronic_jammer']]),
                electronic_resistance=parse_10_stage_value(row[NAVY_COLUMNS['electronic_resistance']]),
                fuel_capacity=parse_single_value(row[NAVY_COLUMNS['fuel_capacity']]),
                fuel_per_round=parse_single_value(row[NAVY_COLUMNS['fuel_per_round']]),
                nuclear_capacity=parse_single_value(row[NAVY_COLUMNS['nuclear_capacity']]),
                nuclear_per_round=parse_single_value(row[NAVY_COLUMNS['nuclear_per_round']]),
                ground_friendly_damage=parse_10_stage_value(row[NAVY_COLUMNS['ground_friendly_damage']]),
                ground_accuracy=parse_10_stage_value(row[NAVY_COLUMNS['ground_accuracy']]),
                ground_penetration=parse_10_stage_value(row[NAVY_COLUMNS['ground_penetration']]),
                ground_suppression=parse_10_stage_value(row[NAVY_COLUMNS['ground_suppression']]),
                air_accuracy=parse_10_stage_value(row[NAVY_COLUMNS['air_accuracy']]),
                air_damage=parse_10_stage_value(row[NAVY_COLUMNS['air_damage']]),
                air_interception=parse_10_stage_value(row[NAVY_COLUMNS['air_interception']]),
                sea_accuracy=parse_10_stage_value(row[NAVY_COLUMNS['sea_accuracy']]),
                sea_penetration=parse_10_stage_value(row[NAVY_COLUMNS['sea_penetration']]),
                sonar_strength=parse_10_stage_value(row[NAVY_COLUMNS['sonar_strength']]),
                submarine_stealth=parse_10_stage_value(row[NAVY_COLUMNS['submarine_stealth']]),
                radar_strength=parse_10_stage_value(row[NAVY_COLUMNS['radar_strength']]),
                radar_radius=parse_single_value(row[NAVY_COLUMNS['radar_radius']]),
                light_cannon_damage=parse_10_stage_value(row[NAVY_COLUMNS['light_cannon_damage']]),
                heavy_cannon_damage=parse_10_stage_value(row[NAVY_COLUMNS['heavy_cannon_damage']]),
                torpedo_damage=parse_10_stage_value(row[NAVY_COLUMNS['torpedo_damage']]),
                missile_damage=parse_10_stage_value(row[NAVY_COLUMNS['missile_damage']]),
                anti_sub_damage=parse_10_stage_value(row[NAVY_COLUMNS['anti_sub_damage']]),
                environment_adaptations=env_adaptations,
            )

            # 使用 "武器名_时代" 作为key，避免同名武器覆盖
            era = row[NAVY_COLUMNS['era']]
            weapons[f"{weapon_name}_{era}"] = weapon

    return weapons


def load_all_weapons(base_path: str) -> Tuple[Dict[str, WeaponStats], Dict[str, WeaponStats], Dict[str, WeaponStats]]:
    """
    加载所有武器数据

    参数:
        base_path: CSV文件所在目录路径

    返回:
        (陆军武器字典, 空军武器字典, 海军武器字典)
    """
    army_path = Path(base_path) / "army.csv"
    air_path = Path(base_path) / "air.csv"
    navy_path = Path(base_path) / "navy.csv"

    army_weapons = {}
    air_weapons = {}
    navy_weapons = {}

    if army_path.exists():
        army_weapons = load_army_csv(str(army_path))

    if air_path.exists():
        air_weapons = load_air_csv(str(air_path))

    if navy_path.exists():
        navy_weapons = load_navy_csv(str(navy_path))

    return army_weapons, air_weapons, navy_weapons


def create_formation_from_war_csv(
    formation_str: str,
    army_weapons: Dict[str, WeaponStats],
    force_type: ForceType,
    formation_name: str
) -> Formation:
    """
    从army_war.csv格式的编制字符串创建Formation对象

    编制字符串格式: "武器名:数量=武器名:数量=..."
    例如: "栓动步枪:1830=冲锋枪:30=机枪:120=迫击炮:20=反坦克炮:4"

    参数:
        formation_str: 编制字符串
        army_weapons: 陆军武器字典
        force_type: 军种类型
        formation_name: 编制名称

    返回:
        Formation对象
    """
    weapons_list = []

    # 解析编制字符串
    weapon_entries = formation_str.split('=')
    for entry in weapon_entries:
        if ':' not in entry:
            continue

        parts = entry.strip().split(':')
        if len(parts) != 2:
            continue

        weapon_name = parts[0].strip()
        quantity = parse_single_int(parts[1])

        if weapon_name in army_weapons:
            # 复制武器数据并设置数量
            weapon = army_weapons[weapon_name]
            weapon_copy = WeaponStats(
                weapon_type=weapon.weapon_type,
                era=weapon.era,
                cost=weapon.cost,
                width=weapon.width,
                speed=weapon.speed,
                organization=weapon.organization,
                hp=weapon.hp,
                structure=weapon.structure,
                buoyancy=weapon.buoyancy,
                recon=weapon.recon.copy(),
                defense=weapon.defense.copy(),
                armor_thickness=weapon.armor_thickness,
                armor_type=weapon.armor_type,
                weapon_position=weapon.weapon_position,
                fire_control=weapon.fire_control.copy(),
                electronic_jammer=weapon.electronic_jammer.copy(),
                electronic_resistance=weapon.electronic_resistance.copy(),
                ground_friendly_damage=weapon.ground_friendly_damage.copy(),
                ground_accuracy=weapon.ground_accuracy.copy(),
                ground_penetration=weapon.ground_penetration.copy(),
                ground_suppression=weapon.ground_suppression.copy(),
                ground_soft_attack=weapon.ground_soft_attack.copy(),
                ground_hard_attack=weapon.ground_hard_attack.copy(),
                ground_damage=weapon.ground_damage.copy(),
                air_accuracy=weapon.air_accuracy.copy(),
                air_damage=weapon.air_damage.copy(),
                air_interception=weapon.air_interception.copy(),
                sea_accuracy=weapon.sea_accuracy.copy(),
                sea_penetration=weapon.sea_penetration.copy(),
                light_cannon_damage=weapon.light_cannon_damage.copy(),
                heavy_cannon_damage=weapon.heavy_cannon_damage.copy(),
                torpedo_damage=weapon.torpedo_damage.copy(),
                missile_damage=weapon.missile_damage.copy(),
                anti_sub_damage=weapon.anti_sub_damage.copy(),
                sonar_strength=weapon.sonar_strength.copy(),
                submarine_stealth=weapon.submarine_stealth.copy(),
                stealth=weapon.stealth.copy(),
                ground_detection=weapon.ground_detection.copy() if isinstance(weapon.ground_detection, list) else [weapon.ground_detection],
                radar_strength=weapon.radar_strength.copy(),
                radar_radius=weapon.radar_radius,
                breakthrough=weapon.breakthrough,
                trench_defense=weapon.trench_defense,
                environment_adaptations=weapon.environment_adaptations.copy(),
                quantity=quantity
            )
            weapons_list.append(weapon_copy)
        else:
            print(f"警告: 未找到武器 '{weapon_name}'")

    return Formation(
        force_type=force_type,
        name=formation_name,
        weapons=weapons_list
    )


def test_csv_loading():
    """测试CSV加载功能"""
    print("\n=== 测试CSV加载功能 ===")

    base_path = "d:/游戏策划相关/战争模块"

    # 加载所有武器
    army_weapons, air_weapons, navy_weapons = load_all_weapons(base_path)

    print(f"陆军武器数量: {len(army_weapons)}")
    print(f"空军武器数量: {len(air_weapons)}")
    print(f"海军武器数量: {len(navy_weapons)}")

    # 显示几个陆军武器示例
    if army_weapons:
        for name, weapon in list(army_weapons.items())[:3]:
            print(f"\n陆军武器: {name}")
            print(f"  时代: {weapon.era}")
            print(f"  成本: {weapon.cost}")
            print(f"  编制宽度: {weapon.width}")
            print(f"  血量: {weapon.hp}")
            print(f"  组织度: {weapon.organization}")
            print(f"  侦查(10阶段): {weapon.recon}")
            print(f"  防御(10阶段): {weapon.defense}")
            print(f"  武器定位: {weapon.weapon_position}")

    # 显示几个空军武器示例
    if air_weapons:
        for name, weapon in list(air_weapons.items())[:2]:
            print(f"\n空军武器: {name}")
            print(f"  时代: {weapon.era}")
            print(f"  血量: {weapon.hp}")
            print(f"  拦截(10阶段): {weapon.air_interception}")
            print(f"  对地探测: {weapon.ground_detection}")

    # 显示几个海军武器示例
    if navy_weapons:
        for name, weapon in list(navy_weapons.items())[:2]:
            print(f"\n海军武器: {name}")
            print(f"  时代: {weapon.era}")
            print(f"  结构值: {weapon.structure}")
            print(f"  浮力值: {weapon.buoyancy}")
            print(f"  装甲类型: {weapon.armor_type}")
            print(f"  轻炮对海伤害(10阶段): {weapon.light_cannon_damage}")

    # 测试创建编制
    if army_weapons:
        print("\n=== 测试创建编制 ===")
        formation_str = "栓动步枪:1830=冲锋枪:30=机枪:120=迫击炮:20=反坦克炮:4"
        formation = create_formation_from_war_csv(
            formation_str, army_weapons, ForceType.ARMY, "一战德国步兵团"
        )
        print(f"编制名称: {formation.name}")
        print(f"总编制宽度: {formation.total_width}")
        print(f"武器数量: {len(formation.weapons)}")
        print(f"装甲率: {formation.get_armor_rate():.2%}")


if __name__ == "__main__":
    """主函数：运行所有测试"""
    test_base_damage_formula()
    test_penetration_efficiency()
    test_environment_coefficient()
    test_distance_system()
    test_csv_loading()

    print("\n所有测试完成！")