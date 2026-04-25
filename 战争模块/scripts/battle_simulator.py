"""
战斗数值模拟器
==============
本模块提供战斗模拟和报表生成功能，用于验证游戏数值平衡性。

主要功能：
- BattleReport：战斗报表数据类，包含胜负、IC交换比、击穿率等指标
- CombatStatistics：战斗统计收集器，收集回合内的详细数据
- run_battle_simulation：模拟器主入口函数
- print_battle_report：格式化打印战斗报表

使用示例：
    from battle_simulator import run_battle_simulation, print_battle_report
    from combat_logic import load_all_weapons, ForceType

    army_db, air_db, navy_db = load_all_weapons("path/to/csv")
    report = run_battle_simulation(
        attacker_spec="栓动步枪:1830=机枪:120",
        defender_spec="栓动步枪:2000=机枪:150",
        force_type=ForceType.ARMY,
        weapons_db=army_db
    )
    print_battle_report(report)
"""

import copy
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Union, Callable
from enum import Enum

# 导入核心战斗逻辑模块
from combat_logic import (
    WeaponStats, Formation, CombatResult, ForceType,
    run_combat_loop, determine_first_strike,
    calculate_penetration_efficiency,
    ARMY_WIDTH_LIMIT, AIR_WIDTH_LIMIT, NAVY_WIDTH_LIMIT,
    ENVIRONMENT_TYPES, DISTANCE_RANGES
)


# =============================================================================
# 数据类定义
# =============================================================================

@dataclass
class BattleReport:
    """
    战斗报表数据类
    存储战斗结束后生成的所有统计数据和效能指标
    """
    # 基础信息
    winner: str                          # "attacker" 或 "defender"
    battle_duration_hours: float         # 战斗时长（小时）
    total_rounds: int                    # 总回合数

    # IC交换比
    ic_exchange_ratio: float             # 攻击方IC损失 / 防守方IC损失
    attacker_ic_loss: float              # 攻击方损失的IC总值
    defender_ic_loss: float              # 防守方损失的IC总值
    attacker_initial_ic: float           # 攻击方初始IC总值
    defender_initial_ic: float           # 防守方初始IC总值

    # 弹药价值比
    ammo_value_ratio: float              # 总伤害输出 / 燃料与核动力总消耗
    attacker_total_damage: float         # 攻击方总伤害输出
    defender_total_damage: float         # 防守方总伤害输出
    attacker_fuel_consumed: float        # 攻击方燃料消耗总值
    defender_fuel_consumed: float        # 防守方燃料消耗总值
    attacker_nuclear_consumed: float     # 攻击方核动力消耗总值
    defender_nuclear_consumed: float     # 防守方核动力消耗总值

    # 各阶段伤害分布（10阶段）
    attacker_stage_damage: Dict[int, float]  # 攻击方各阶段伤害 {阶段: 伤害}
    defender_stage_damage: Dict[int, float]  # 防守方各阶段伤害
    stage_damage_percentage: Dict[int, float]  # 各阶段伤害占比

    # 击穿率统计
    attacker_full_penetration_rate: float  # 攻击方完全击穿率
    defender_full_penetration_rate: float  # 防守方完全击穿率
    attacker_penetration_rounds: int       # 攻击方完全击穿回合数
    defender_penetration_rounds: int       # 防守方完全击穿回合数
    attacker_total_attack_rounds: int      # 攻击方总攻击回合数
    defender_total_attack_rounds: int      # 防守方总攻击回合数

    # 残存状态
    attacker_remaining_hp_pct: float       # 攻击方剩余血量百分比
    defender_remaining_hp_pct: float       # 防守方剩余血量百分比
    attacker_remaining_org_pct: float      # 攻击方剩余组织度百分比
    defender_remaining_org_pct: float      # 防守方剩余组织度百分比

    # 编制信息
    attacker_formation_name: str
    defender_formation_name: str
    force_type: ForceType
    active_environments: List[str]


@dataclass
class CombatStatistics:
    """
    战斗统计收集器
    用于在战斗循环中收集每回合的详细数据
    """
    # 各阶段伤害累计
    attacker_stage_damage: Dict[int, float] = field(
        default_factory=lambda: {i: 0.0 for i in range(1, 11)}
    )
    defender_stage_damage: Dict[int, float] = field(
        default_factory=lambda: {i: 0.0 for i in range(1, 11)}
    )

    # 击穿判定记录
    attacker_penetration_results: List[bool] = field(default_factory=list)  # True=完全击穿
    defender_penetration_results: List[bool] = field(default_factory=list)

    # 燃料/核动力消耗累计
    attacker_fuel_consumed: float = 0.0
    defender_fuel_consumed: float = 0.0
    attacker_nuclear_consumed: float = 0.0
    defender_nuclear_consumed: float = 0.0

    # 总伤害累计
    attacker_total_damage: float = 0.0
    defender_total_damage: float = 0.0

    # 总组织度伤害累计
    attacker_total_org_damage: float = 0.0
    defender_total_org_damage: float = 0.0

    def record_round(
        self,
        stage: int,
        attacker_damage: float,
        defender_damage: float,
        attacker_org_damage: float = 0,
        defender_org_damage: float = 0,
        attacker_penetrated: bool = False,
        defender_penetrated: bool = False,
        attacker_fuel: float = 0,
        defender_fuel: float = 0,
        attacker_nuclear: float = 0,
        defender_nuclear: float = 0
    ):
        """
        记录单回合数据

        参数:
            stage: 当前交战阶段（1-10）
            attacker_damage: 攻击方造成的血量伤害
            defender_damage: 防守方造成的血量伤害
            attacker_org_damage: 攻击方造成的组织度伤害
            defender_org_damage: 防守方造成的组织度伤害
            attacker_penetrated: 攻击方是否完全击穿
            defender_penetrated: 防守方是否完全击穿
            attacker_fuel: 攻击方燃料消耗
            defender_fuel: 防守方燃料消耗
            attacker_nuclear: 攻击方核动力消耗
            defender_nuclear: 防守方核动力消耗
        """
        # 记录阶段伤害
        self.attacker_stage_damage[stage] += attacker_damage
        self.defender_stage_damage[stage] += defender_damage

        # 记录总伤害
        self.attacker_total_damage += attacker_damage
        self.defender_total_damage += defender_damage
        self.attacker_total_org_damage += attacker_org_damage
        self.defender_total_org_damage += defender_org_damage

        # 记录击穿判定（只在有伤害时记录）
        if attacker_damage > 0:
            self.attacker_penetration_results.append(attacker_penetrated)
        if defender_damage > 0:
            self.defender_penetration_results.append(defender_penetrated)

        # 记录消耗
        self.attacker_fuel_consumed += attacker_fuel
        self.defender_fuel_consumed += defender_fuel
        self.attacker_nuclear_consumed += attacker_nuclear
        self.defender_nuclear_consumed += defender_nuclear


@dataclass
class FormationSpec:
    """
    编制规格数据类
    用于描述武器组合输入
    """
    force_type: ForceType
    name: str
    weapon_specs: List[Tuple[str, int]]  # [(武器ID, 数量), ...]

    def to_dict_string(self) -> str:
        """
        转换为字典字符串格式
        格式: "武器ID:数量=武器ID:数量..."
        """
        return "=" .join(f"{w}:{n}" for w, n in self.weapon_specs)


# =============================================================================
# 辅助函数
# =============================================================================

def deep_copy_formation(formation: Formation) -> Formation:
    """
    深拷贝编制对象

    用于保存初始状态以便计算IC损失

    参数:
        formation: 原始编制对象

    返回:
        新的编制对象（独立副本）
    """
    # 深拷贝武器列表
    weapons_copy = []
    for weapon in formation.weapons:
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
            recon=weapon.recon.copy() if weapon.recon else [],
            defense=weapon.defense.copy() if weapon.defense else [],
            armor_thickness=weapon.armor_thickness,
            armor_type=weapon.armor_type,
            weapon_position=weapon.weapon_position,
            fire_control=weapon.fire_control.copy() if weapon.fire_control else [],
            electronic_jammer=weapon.electronic_jammer.copy() if weapon.electronic_jammer else [],
            electronic_resistance=weapon.electronic_resistance.copy() if weapon.electronic_resistance else [],
            ground_friendly_damage=weapon.ground_friendly_damage.copy() if weapon.ground_friendly_damage else [],
            ground_accuracy=weapon.ground_accuracy.copy() if weapon.ground_accuracy else [],
            ground_penetration=weapon.ground_penetration.copy() if weapon.ground_penetration else [],
            ground_suppression=weapon.ground_suppression.copy() if weapon.ground_suppression else [],
            ground_soft_attack=weapon.ground_soft_attack.copy() if weapon.ground_soft_attack else [],
            ground_hard_attack=weapon.ground_hard_attack.copy() if weapon.ground_hard_attack else [],
            ground_damage=weapon.ground_damage.copy() if weapon.ground_damage else [],
            air_accuracy=weapon.air_accuracy.copy() if weapon.air_accuracy else [],
            air_damage=weapon.air_damage.copy() if weapon.air_damage else [],
            air_interception=weapon.air_interception.copy() if weapon.air_interception else [],
            sea_accuracy=weapon.sea_accuracy.copy() if weapon.sea_accuracy else [],
            sea_penetration=weapon.sea_penetration.copy() if weapon.sea_penetration else [],
            sea_damage=weapon.sea_damage.copy() if weapon.sea_damage else [],
            light_cannon_damage=weapon.light_cannon_damage.copy() if weapon.light_cannon_damage else [],
            heavy_cannon_damage=weapon.heavy_cannon_damage.copy() if weapon.heavy_cannon_damage else [],
            torpedo_damage=weapon.torpedo_damage.copy() if weapon.torpedo_damage else [],
            missile_damage=weapon.missile_damage.copy() if weapon.missile_damage else [],
            anti_sub_damage=weapon.anti_sub_damage.copy() if weapon.anti_sub_damage else [],
            sonar_strength=weapon.sonar_strength.copy() if weapon.sonar_strength else [],
            submarine_stealth=weapon.submarine_stealth.copy() if weapon.submarine_stealth else [],
            stealth=weapon.stealth.copy() if weapon.stealth else [],
            ground_detection=weapon.ground_detection.copy() if weapon.ground_detection else [],
            radar_strength=weapon.radar_strength.copy() if weapon.radar_strength else [],
            radar_radius=weapon.radar_radius,
            fuel_capacity=weapon.fuel_capacity,
            fuel_per_round=weapon.fuel_per_round,
            nuclear_capacity=weapon.nuclear_capacity,
            nuclear_per_round=weapon.nuclear_per_round,
            breakthrough=weapon.breakthrough,
            trench_defense=weapon.trench_defense,
            environment_adaptations=weapon.environment_adaptations.copy(),
            quantity=weapon.quantity
        )
        weapons_copy.append(weapon_copy)

    # 创建新的编制对象
    new_formation = Formation(
        force_type=formation.force_type,
        name=formation.name,
        weapons=weapons_copy
    )

    # 复制状态属性
    new_formation.current_hp = formation.current_hp
    new_formation.current_organization = formation.current_organization
    new_formation.current_structure = formation.current_structure
    new_formation.current_buoyancy = formation.current_buoyancy
    new_formation.is_defending = formation.is_defending
    new_formation.current_distance_stage = formation.current_distance_stage

    return new_formation


def copy_weapon(weapon_template: WeaponStats, quantity: int) -> WeaponStats:
    """
    从武器模板创建副本并设置数量

    参数:
        weapon_template: 武器模板（从数据库加载）
        quantity: 武器数量

    返回:
        新的武器对象（设置指定数量）
    """
    weapon_copy = WeaponStats(
        weapon_type=weapon_template.weapon_type,
        era=weapon_template.era,
        cost=weapon_template.cost,
        width=weapon_template.width,
        speed=weapon_template.speed,
        organization=weapon_template.organization,
        hp=weapon_template.hp,
        structure=weapon_template.structure,
        buoyancy=weapon_template.buoyancy,
        recon=weapon_template.recon.copy() if weapon_template.recon else [],
        defense=weapon_template.defense.copy() if weapon_template.defense else [],
        armor_thickness=weapon_template.armor_thickness,
        armor_type=weapon_template.armor_type,
        weapon_position=weapon_template.weapon_position,
        fire_control=weapon_template.fire_control.copy() if weapon_template.fire_control else [],
        electronic_jammer=weapon_template.electronic_jammer.copy() if weapon_template.electronic_jammer else [],
        electronic_resistance=weapon_template.electronic_resistance.copy() if weapon_template.electronic_resistance else [],
        ground_friendly_damage=weapon_template.ground_friendly_damage.copy() if weapon_template.ground_friendly_damage else [],
        ground_accuracy=weapon_template.ground_accuracy.copy() if weapon_template.ground_accuracy else [],
        ground_penetration=weapon_template.ground_penetration.copy() if weapon_template.ground_penetration else [],
        ground_suppression=weapon_template.ground_suppression.copy() if weapon_template.ground_suppression else [],
        ground_soft_attack=weapon_template.ground_soft_attack.copy() if weapon_template.ground_soft_attack else [],
        ground_hard_attack=weapon_template.ground_hard_attack.copy() if weapon_template.ground_hard_attack else [],
        ground_damage=weapon_template.ground_damage.copy() if weapon_template.ground_damage else [],
        air_accuracy=weapon_template.air_accuracy.copy() if weapon_template.air_accuracy else [],
        air_damage=weapon_template.air_damage.copy() if weapon_template.air_damage else [],
        air_interception=weapon_template.air_interception.copy() if weapon_template.air_interception else [],
        sea_accuracy=weapon_template.sea_accuracy.copy() if weapon_template.sea_accuracy else [],
        sea_penetration=weapon_template.sea_penetration.copy() if weapon_template.sea_penetration else [],
        sea_damage=weapon_template.sea_damage.copy() if weapon_template.sea_damage else [],
        light_cannon_damage=weapon_template.light_cannon_damage.copy() if weapon_template.light_cannon_damage else [],
        heavy_cannon_damage=weapon_template.heavy_cannon_damage.copy() if weapon_template.heavy_cannon_damage else [],
        torpedo_damage=weapon_template.torpedo_damage.copy() if weapon_template.torpedo_damage else [],
        missile_damage=weapon_template.missile_damage.copy() if weapon_template.missile_damage else [],
        anti_sub_damage=weapon_template.anti_sub_damage.copy() if weapon_template.anti_sub_damage else [],
        sonar_strength=weapon_template.sonar_strength.copy() if weapon_template.sonar_strength else [],
        submarine_stealth=weapon_template.submarine_stealth.copy() if weapon_template.submarine_stealth else [],
        stealth=weapon_template.stealth.copy() if weapon_template.stealth else [],
        ground_detection=weapon_template.ground_detection.copy() if weapon_template.ground_detection else [],
        radar_strength=weapon_template.radar_strength.copy() if weapon_template.radar_strength else [],
        radar_radius=weapon_template.radar_radius,
        fuel_capacity=weapon_template.fuel_capacity,
        fuel_per_round=weapon_template.fuel_per_round,
        nuclear_capacity=weapon_template.nuclear_capacity,
        nuclear_per_round=weapon_template.nuclear_per_round,
        breakthrough=weapon_template.breakthrough,
        trench_defense=weapon_template.trench_defense,
        environment_adaptations=weapon_template.environment_adaptations.copy(),
        quantity=quantity
    )
    return weapon_copy


def find_weapon(weapon_id: str, weapons_db: Dict[str, WeaponStats]) -> Optional[WeaponStats]:
    """
    在武器数据库中查找武器

    支持多种查找方式:
    1. 精确匹配: "轻型战斗机_二战"
    2. 带时代后缀匹配: "轻型战斗机" + "_二战"
    3. 部分匹配: 搜索包含weapon_id的所有key

    参数:
        weapon_id: 武器标识
        weapons_db: 武器数据库

    返回:
        WeaponStats或None
    """
    # 1. 精确匹配
    if weapon_id in weapons_db:
        return weapons_db[weapon_id]

    # 2. 常见时代后缀尝试
    for era in ['二战', '一战', '冷战', '现代']:
        key = f"{weapon_id}_{era}"
        if key in weapons_db:
            return weapons_db[key]

    # 3. 部分匹配（搜索包含weapon_id的key）
    for key in weapons_db:
        if weapon_id in key or key.startswith(weapon_id):
            return weapons_db[key]

    return None


def build_formation_from_input(
    weapon_input: str,
    force_type: ForceType,
    formation_name: str,
    weapons_db: Dict[str, WeaponStats]
) -> Formation:
    """
    从输入字符串构建编制

    支持两种输入格式:
    - 格式1: "武器ID:数量=武器ID:数量..." (army_war.csv格式)
    - 格式2: "武器ID 数量, 武器ID 数量..." (逗号分隔格式)

    参数:
        weapon_input: 武器输入字符串
        force_type: 军种类型
        formation_name: 编制名称
        weapons_db: 武器数据库（从CSV加载）

    返回:
        Formation对象
    """
    weapons_list = []

    # 解析输入格式
    if ':' in weapon_input and '=' in weapon_input:
        # 格式1: "武器ID:数量=武器ID:数量..."
        entries = weapon_input.split('=')
        for entry in entries:
            entry = entry.strip()
            if ':' in entry:
                parts = entry.split(':')
                if len(parts) >= 2:
                    weapon_id = parts[0].strip()
                    try:
                        quantity = int(parts[1].strip())
                    except ValueError:
                        continue

                    if weapon_id in weapons_db:
                        weapon_copy = copy_weapon(weapons_db[weapon_id], quantity)
                        weapons_list.append(weapon_copy)
                    else:
                        weapon = find_weapon(weapon_id, weapons_db)
                        if weapon:
                            weapon_copy = copy_weapon(weapon, quantity)
                            weapons_list.append(weapon_copy)
                        else:
                            print(f"警告: 未找到武器 '{weapon_id}'")

    elif ',' in weapon_input:
        # 格式2: "武器ID 数量, 武器ID 数量..."
        entries = weapon_input.split(',')
        for entry in entries:
            entry = entry.strip()
            parts = entry.split()
            if len(parts) >= 2:
                weapon_id = parts[0].strip()
                try:
                    quantity = int(parts[1].strip())
                except ValueError:
                    continue

                if weapon_id in weapons_db:
                    weapon_copy = copy_weapon(weapons_db[weapon_id], quantity)
                    weapons_list.append(weapon_copy)
                else:
                    print(f"警告: 未找到武器 '{weapon_id}'")

    else:
        # 单一武器输入
        parts = weapon_input.strip().split()
        if len(parts) >= 2:
            weapon_id = parts[0].strip()
            try:
                quantity = int(parts[1].strip())
            except ValueError:
                quantity = 1

            if weapon_id in weapons_db:
                weapon_copy = copy_weapon(weapons_db[weapon_id], quantity)
                weapons_list.append(weapon_copy)

    if not weapons_list:
        raise ValueError(f"无法解析输入或找不到武器: {weapon_input}")

    return Formation(
        force_type=force_type,
        name=formation_name,
        weapons=weapons_list
    )


def calculate_round_fuel_cost(formation: Formation) -> Tuple[float, float]:
    """
    计算单回合燃料和核动力消耗

    参数:
        formation: 编制对象

    返回:
        (燃料消耗总值, 核动力消耗总值)
    """
    fuel_cost = 0.0
    nuclear_cost = 0.0

    for weapon in formation.weapons:
        # 燃料消耗（基于数量）
        fuel_cost += weapon.fuel_per_round * weapon.quantity

        # 核动力消耗（海军）
        nuclear_cost += weapon.nuclear_per_round * weapon.quantity

    return fuel_cost, nuclear_cost


def calculate_formation_ic(formation: Formation) -> float:
    """
    计算编制的总IC值

    IC = Σ(武器成本 × 编制宽度 × 数量)

    参数:
        formation: 编制对象

    返回:
        IC总值
    """
    total_ic = 0.0
    for weapon in formation.weapons:
        total_ic += weapon.cost * weapon.width * weapon.quantity
    return total_ic


def calculate_ic_loss(
    final_formation: Formation,
    initial_formation: Formation
) -> float:
    """
    计算编制的IC损失

    基于血量/结构值的损失比例计算

    参数:
        final_formation: 战斗后的编制
        initial_formation: 战斗前的编制

    返回:
        IC损失值
    """
    initial_ic = calculate_formation_ic(initial_formation)

    # 根据军种计算损失比例
    if initial_formation.force_type == ForceType.NAVY:
        # 海军基于结构值计算
        initial_structure = initial_formation.current_structure
        final_structure = final_formation.current_structure
        if initial_structure > 0:
            loss_ratio = 1.0 - (final_structure / initial_structure)
        else:
            loss_ratio = 1.0
    else:
        # 陆军/空军基于血量计算
        initial_hp = initial_formation.current_hp
        final_hp = final_formation.current_hp
        if initial_hp > 0:
            loss_ratio = 1.0 - (final_hp / initial_hp)
        else:
            loss_ratio = 1.0

    return initial_ic * loss_ratio


# =============================================================================
# 报表生成
# =============================================================================

def generate_battle_report(
    combat_result: Dict,
    statistics: CombatStatistics,
    attacker_initial: Formation,
    defender_initial: Formation,
    attacker_final: Formation,
    defender_final: Formation,
    force_type: ForceType,
    active_environments: List[str]
) -> BattleReport:
    """
    生成完整战斗报表

    参数:
        combat_result: 战斗循环返回的结果字典
        statistics: 统计收集器
        attacker_initial: 攻击方初始状态
        defender_initial: 防守方初始状态
        attacker_final: 攻击方最终状态
        defender_final: 防守方最终状态
        force_type: 军种类型
        active_environments: 生效的环境列表

    返回:
        BattleReport战斗报表
    """
    # 计算IC损失
    attacker_ic_loss = calculate_ic_loss(attacker_final, attacker_initial)
    defender_ic_loss = calculate_ic_loss(defender_final, defender_initial)

    attacker_initial_ic = calculate_formation_ic(attacker_initial)
    defender_initial_ic = calculate_formation_ic(defender_initial)

    # IC交换比（攻击方损失/防守方损失）
    if defender_ic_loss > 0:
        ic_exchange_ratio = attacker_ic_loss / defender_ic_loss
    else:
        ic_exchange_ratio = float('inf') if attacker_ic_loss > 0 else 0.0

    # 计算击穿率
    attacker_pen_rate = 0.0
    defender_pen_rate = 0.0

    if statistics.attacker_penetration_results:
        attacker_pen_rate = (
            sum(statistics.attacker_penetration_results) /
            len(statistics.attacker_penetration_results)
        )

    if statistics.defender_penetration_results:
        defender_pen_rate = (
            sum(statistics.defender_penetration_results) /
            len(statistics.defender_penetration_results)
        )

    # 计算各阶段伤害占比
    total_damage = statistics.attacker_total_damage + statistics.defender_total_damage
    stage_percentage = {}
    for stage in range(1, 11):
        stage_total = (
            statistics.attacker_stage_damage[stage] +
            statistics.defender_stage_damage[stage]
        )
        stage_percentage[stage] = (
            stage_total / total_damage if total_damage > 0 else 0.0
        )

    # 计算弹药价值比
    total_consumption = (
        statistics.attacker_fuel_consumed +
        statistics.defender_fuel_consumed +
        statistics.attacker_nuclear_consumed +
        statistics.defender_nuclear_consumed
    )

    if total_consumption > 0:
        ammo_value_ratio = total_damage / total_consumption
    else:
        ammo_value_ratio = 0.0

    # 计算残存百分比
    attacker_remaining_hp_pct = (
        combat_result.get('attacker_remaining_hp', 0) /
        attacker_initial.current_hp if attacker_initial.current_hp > 0 else 0.0
    )
    defender_remaining_hp_pct = (
        combat_result.get('defender_remaining_hp', 0) /
        defender_initial.current_hp if defender_initial.current_hp > 0 else 0.0
    )
    attacker_remaining_org_pct = (
        combat_result.get('attacker_remaining_org', 0) /
        attacker_initial.current_organization if attacker_initial.current_organization > 0 else 0.0
    )
    defender_remaining_org_pct = (
        combat_result.get('defender_remaining_org', 0) /
        defender_initial.current_organization if defender_initial.current_organization > 0 else 0.0
    )

    return BattleReport(
        winner=combat_result.get('winner', 'unknown'),
        battle_duration_hours=combat_result.get('rounds', 0),
        total_rounds=combat_result.get('rounds', 0),

        ic_exchange_ratio=ic_exchange_ratio,
        attacker_ic_loss=attacker_ic_loss,
        defender_ic_loss=defender_ic_loss,
        attacker_initial_ic=attacker_initial_ic,
        defender_initial_ic=defender_initial_ic,

        ammo_value_ratio=ammo_value_ratio,
        attacker_total_damage=statistics.attacker_total_damage,
        defender_total_damage=statistics.defender_total_damage,
        attacker_fuel_consumed=statistics.attacker_fuel_consumed,
        defender_fuel_consumed=statistics.defender_fuel_consumed,
        attacker_nuclear_consumed=statistics.attacker_nuclear_consumed,
        defender_nuclear_consumed=statistics.defender_nuclear_consumed,

        attacker_stage_damage=statistics.attacker_stage_damage.copy(),
        defender_stage_damage=statistics.defender_stage_damage.copy(),
        stage_damage_percentage=stage_percentage,

        attacker_full_penetration_rate=attacker_pen_rate,
        defender_full_penetration_rate=defender_pen_rate,
        attacker_penetration_rounds=sum(statistics.attacker_penetration_results),
        defender_penetration_rounds=sum(statistics.defender_penetration_results),
        attacker_total_attack_rounds=len(statistics.attacker_penetration_results),
        defender_total_attack_rounds=len(statistics.defender_penetration_results),

        attacker_remaining_hp_pct=attacker_remaining_hp_pct,
        defender_remaining_hp_pct=defender_remaining_hp_pct,
        attacker_remaining_org_pct=attacker_remaining_org_pct,
        defender_remaining_org_pct=defender_remaining_org_pct,

        attacker_formation_name=attacker_initial.name,
        defender_formation_name=defender_initial.name,
        force_type=force_type,
        active_environments=active_environments
    )


def print_battle_report(report: BattleReport):
    """
    打印格式化的战斗报表

    参数:
        report: BattleReport对象
    """
    print("=" * 70)
    print("战斗报表 - Battle Report")
    print("=" * 70)

    # 胜负结果
    print(f"\n【胜负结果】")
    winner_str = "攻击方" if report.winner == "attacker" else "防守方"
    print(f"  胜方: {winner_str}")
    print(f"  战斗时长: {report.battle_duration_hours:.0f} 小时 ({report.total_rounds} 回合)")

    # IC交换比
    print(f"\n【IC交换比】")
    print(f"  攻击方IC损失: {report.attacker_ic_loss:.2f}")
    print(f"    - 初始IC: {report.attacker_initial_ic:.2f}")
    print(f"    - 损失比例: {report.attacker_ic_loss/report.attacker_initial_ic*100:.1f}%")
    print(f"  防守方IC损失: {report.defender_ic_loss:.2f}")
    print(f"    - 初始IC: {report.defender_initial_ic:.2f}")
    print(f"    - 损失比例: {report.defender_ic_loss/report.defender_initial_ic*100:.1f}%")

    if report.ic_exchange_ratio == float('inf'):
        print(f"  IC交换比: ∞ (攻击方全损，防守方无损)")
    else:
        print(f"  IC交换比: {report.ic_exchange_ratio:.2f}")
        if report.ic_exchange_ratio < 1:
            print(f"    - 攻击方优势（损失更少）")
        elif report.ic_exchange_ratio > 1:
            print(f"    - 防守方优势（损失更少）")
        else:
            print(f"    - 均衡")

    # 弹药价值比
    print(f"\n【弹药价值比】")
    print(f"  总伤害输出: {report.attacker_total_damage + report.defender_total_damage:.2f}")
    print(f"    - 攻击方伤害: {report.attacker_total_damage:.2f}")
    print(f"    - 防守方伤害: {report.defender_total_damage:.2f}")
    print(f"  总消耗:")
    print(f"    - 燃料消耗: {report.attacker_fuel_consumed + report.defender_fuel_consumed:.2f}")
    print(f"    - 核动力消耗: {report.attacker_nuclear_consumed + report.defender_nuclear_consumed:.2f}")
    print(f"  弹药价值比: {report.ammo_value_ratio:.2f}")

    # 各阶段伤害分布
    print(f"\n【各阶段伤害分布】")
    print("  阶段   距离(km)      攻击方伤害   防守方伤害   占比")
    stage_names = [
        "0-0.5", "0.5-1.5", "1.5-4", "4-8", "8-20",
        "20-40", "40-80", "80-120", "120-240", "240-480"
    ]
    for stage in range(1, 11):
        dist_str = stage_names[stage-1]
        att_dmg = report.attacker_stage_damage[stage]
        def_dmg = report.defender_stage_damage[stage]
        pct = report.stage_damage_percentage[stage] * 100
        print(f"  {stage:2d}    {dist_str:12s}  {att_dmg:10.2f}   {def_dmg:10.2f}   {pct:6.2f}%")

    # 击穿率统计
    print(f"\n【击穿率统计】")
    print(f"  攻击方:")
    print(f"    - 完全击穿率: {report.attacker_full_penetration_rate*100:.1f}%")
    print(f"    - 完全击穿回合: {report.attacker_penetration_rounds}/{report.attacker_total_attack_rounds}")
    print(f"  防守方:")
    print(f"    - 完全击穿率: {report.defender_full_penetration_rate*100:.1f}%")
    print(f"    - 完全击穿回合: {report.defender_penetration_rounds}/{report.defender_total_attack_rounds}")

    # 残存状态
    print(f"\n【残存状态】")
    print(f"  攻击方:")
    print(f"    - 血量: {report.attacker_remaining_hp_pct*100:.1f}%")
    print(f"    - 组织度: {report.attacker_remaining_org_pct*100:.1f}%")
    print(f"  防守方:")
    print(f"    - 血量: {report.defender_remaining_hp_pct*100:.1f}%")
    print(f"    - 组织度: {report.defender_remaining_org_pct*100:.1f}%")

    # 编制信息
    print(f"\n【编制信息】")
    print(f"  攻击方: {report.attacker_formation_name}")
    print(f"  防守方: {report.defender_formation_name}")
    print(f"  军种: {report.force_type.value}")
    if report.active_environments:
        print(f"  环境: {', '.join(report.active_environments)}")

    print("=" * 70)


# =============================================================================
# 模拟器主入口
# =============================================================================

def run_battle_simulation(
    attacker_spec: Union[str, FormationSpec],
    defender_spec: Union[str, FormationSpec],
    force_type: ForceType,
    weapons_db: Dict[str, WeaponStats],
    active_environments: List[str] = [],
    max_hours: int = 1000,
    verbose: bool = False
) -> BattleReport:
    """
    战斗模拟器主入口函数

    参数:
        attacker_spec: 攻击方编制规格（字符串或FormationSpec）
        defender_spec: 防守方编制规格
        force_type: 军种类型（ARMY/AIR/NAVY）
        weapons_db: 武器数据库（从CSV加载）
        active_environments: 生效的环境列表
        max_hours: 最大战斗时长（小时）
        verbose: 是否输出详细过程

    返回:
        BattleReport战斗报表
    """
    # 解析编制规格
    if isinstance(attacker_spec, str):
        attacker = build_formation_from_input(
            attacker_spec, force_type, "攻击方", weapons_db
        )
    else:
        attacker = build_formation_from_input(
            attacker_spec.to_dict_string(), force_type, "攻击方", weapons_db
        )

    if isinstance(defender_spec, str):
        defender = build_formation_from_input(
            defender_spec, force_type, "防守方", weapons_db
        )
    else:
        defender = build_formation_from_input(
            defender_spec.to_dict_string(), force_type, "防守方", weapons_db
        )

    # 保存初始状态用于IC计算
    attacker_initial = deep_copy_formation(attacker)
    defender_initial = deep_copy_formation(defender)

    # 创建统计收集器
    stats = CombatStatistics()

    # 设置防守方状态
    defender.is_defending = True

    if verbose:
        print(f"战斗开始: {attacker.name} vs {defender.name}")
        print(f"军种: {force_type.value}")
        print(f"攻击方总宽度: {attacker.total_width}")
        print(f"防守方总宽度: {defender.total_width}")
        print(f"攻击方初始血量: {attacker.current_hp:.2f}")
        print(f"防守方初始血量: {defender.current_hp:.2f}")
        print("-" * 50)

    # 运行战斗循环（带统计收集）
    result = run_combat_loop(
        attacker, defender, force_type,
        active_environments, max_hours,
        stats  # 传递统计收集器
    )

    if verbose:
        print(f"战斗结束: {result.get('winner', 'unknown')}获胜")
        print(f"战斗时长: {result.get('rounds', 0)}小时")

    # 生成报表
    report = generate_battle_report(
        result, stats,
        attacker_initial, defender_initial,
        attacker, defender,
        force_type, active_environments
    )

    if verbose:
        print_battle_report(report)

    return report


# =============================================================================
# 批量模拟功能
# =============================================================================

def run_multiple_simulations(
    attacker_spec: Union[str, FormationSpec],
    defender_spec: Union[str, FormationSpec],
    force_type: ForceType,
    weapons_db: Dict[str, WeaponStats],
    active_environments: List[str] = [],
    num_simulations: int = 100,
    max_hours: int = 1000
) -> Dict:
    """
    运行多次模拟并汇总统计结果

    用于分析数值平衡性，减少随机波动影响

    参数:
        attacker_spec: 攻击方编制规格
        defender_spec: 防守方编制规格
        force_type: 军种类型
        weapons_db: 武器数据库
        active_environments: 生效的环境列表
        num_simulations: 模拟次数
        max_hours: 每次最大战斗时长

    返回:
        汇总统计结果字典
    """
    results = {
        'attacker_wins': 0,
        'defender_wins': 0,
        'avg_duration': 0,
        'avg_ic_ratio': 0,
        'avg_attacker_pen_rate': 0,
        'avg_defender_pen_rate': 0,
        'reports': []
    }

    total_duration = 0
    total_ic_ratio = 0
    total_attacker_pen = 0
    total_defender_pen = 0

    for i in range(num_simulations):
        report = run_battle_simulation(
            attacker_spec, defender_spec, force_type,
            weapons_db, active_environments, max_hours
        )

        results['reports'].append(report)

        if report.winner == 'attacker':
            results['attacker_wins'] += 1
        else:
            results['defender_wins'] += 1

        total_duration += report.battle_duration_hours
        if report.ic_exchange_ratio != float('inf'):
            total_ic_ratio += report.ic_exchange_ratio
        total_attacker_pen += report.attacker_full_penetration_rate
        total_defender_pen += report.defender_full_penetration_rate

    # 计算平均值
    results['avg_duration'] = total_duration / num_simulations
    results['avg_ic_ratio'] = total_ic_ratio / num_simulations
    results['avg_attacker_pen_rate'] = total_attacker_pen / num_simulations
    results['avg_defender_pen_rate'] = total_defender_pen / num_simulations
    results['attacker_win_rate'] = results['attacker_wins'] / num_simulations

    return results


def print_multiple_simulation_summary(results: Dict):
    """
    打印多次模拟的汇总结果

    参数:
        results: run_multiple_simulations返回的结果字典
    """
    print("=" * 70)
    print("批量模拟汇总结果")
    print("=" * 70)

    print(f"\n【胜负统计】")
    print(f"  模拟次数: {len(results['reports'])}")
    print(f"  攻击方胜率: {results['attacker_win_rate']*100:.1f}%")
    print(f"  攻击方胜场: {results['attacker_wins']}")
    print(f"  防守方胜场: {results['defender_wins']}")

    print(f"\n【平均值指标】")
    print(f"  平均战斗时长: {results['avg_duration']:.1f}小时")
    print(f"  平均IC交换比: {results['avg_ic_ratio']:.2f}")
    print(f"  平均攻击方击穿率: {results['avg_attacker_pen_rate']*100:.1f}%")
    print(f"  平均防守方击穿率: {results['avg_defender_pen_rate']*100:.1f}%")

    print("=" * 70)


# =============================================================================
# 测试代码
# =============================================================================

def test_simulator():
    """测试模拟器功能"""
    print("=== 测试战斗数值模拟器 ===")

    # 需要先加载武器数据库
    from combat_logic import load_all_weapons

    base_path = "d:/游戏策划相关/战争模块"
    army_db, air_db, navy_db = load_all_weapons(base_path)

    print(f"陆军武器数量: {len(army_db)}")
    print(f"空军武器数量: {len(air_db)}")
    print(f"海军武器数量: {len(navy_db)}")

    if army_db:
        print("\n--- 测试陆军战斗模拟 ---")

        # 测试编制字符串
        attacker_input = "栓动步枪:1830=冲锋枪:30=机枪:120=迫击炮:20=反坦克炮:4"
        defender_input = "栓动步枪:2000=机枪:150=迫击炮:30"

        report = run_battle_simulation(
            attacker_spec=attacker_input,
            defender_spec=defender_input,
            force_type=ForceType.ARMY,
            weapons_db=army_db,
            active_environments=["平原适应性"],
            verbose=True
        )

        # 测试批量模拟
        print("\n--- 测试批量模拟（10次） ---")
        batch_results = run_multiple_simulations(
            attacker_input, defender_input,
            ForceType.ARMY, army_db,
            ["平原适应性"],
            num_simulations=10
        )
        print_multiple_simulation_summary(batch_results)


if __name__ == "__main__":
    test_simulator()