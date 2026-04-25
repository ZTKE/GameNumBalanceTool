"""
数值平衡迭代器
==============
用于自动调整武器数值以达到目标战斗时长

核心任务：
- 二战装甲团 vs 二战步兵团
- 有堑壕时：12-24小时击溃防守方
- 无堑壕时：6-12小时击溃防守方

工作流程：
1. 设定初版数值
2. 运行战斗模拟
3. 根据战斗时长调整数值比例
4. 迭代直到符合目标
"""

import copy
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

from combat_logic import (
    WeaponStats, Formation, ForceType, CombatResult,
    run_combat_loop, load_all_weapons,
    ARMY_WIDTH_LIMIT, DISTANCE_RANGES
)
from battle_simulator import (
    CombatStatistics, deep_copy_formation,
    build_formation_from_input, calculate_formation_ic,
    print_battle_report, generate_battle_report
)


# =============================================================================
# 数值设计参数
# =============================================================================

@dataclass
class WeaponDesignParams:
    """武器数值设计参数"""
    # 10阶段软攻（随距离变化）
    soft_attack_stages: List[float] = field(default_factory=lambda: [0.0] * 10)
    # 10阶段硬攻（随距离变化）
    hard_attack_stages: List[float] = field(default_factory=lambda: [0.0] * 10)
    # 10阶段防御
    defense_stages: List[float] = field(default_factory=lambda: [0.0] * 10)
    # 突破（单值格式，进攻时的防御值）
    breakthrough: float = 0.0
    # 10阶段压制
    suppression_stages: List[float] = field(default_factory=lambda: [0.0] * 10)
    # 装甲厚度
    armor_thickness: float = 0.0
    # 10阶段装甲穿透
    penetration_stages: List[float] = field(default_factory=lambda: [0.0] * 10)
    # 10阶段命中
    accuracy_stages: List[float] = field(default_factory=lambda: [0.0] * 10)
    # 组织度
    organization: float = 30.0
    # 血量
    hp: float = 30.0
    # 堑壕防御
    trench_defense: float = 0.0


# =============================================================================
# 数值生成器
# =============================================================================

def generate_distance_profile(
    peak_stage: int,
    peak_value: float,
    decay_rate: float = 0.3,
    min_value: float = 0.0
) -> List[float]:
    """
    生成10阶段距离衰减曲线

    参数:
        peak_stage: 峰值阶段（1-10）
        peak_value: 峰值数值
        decay_rate: 衰减率（每偏离1阶段衰减的比例）
        min_value: 最小值

    返回:
        10阶段数值列表
    """
    result = []
    for stage in range(1, 11):
        distance = abs(stage - peak_stage)
        value = peak_value * (1 - decay_rate * distance)
        value = max(min_value, value)
        result.append(value)
    return result


def generate_weapon_stats(
    weapon_type: str,
    era: str,
    cost: float,
    width: int,
    speed: float,
    params: WeaponDesignParams,
    weapon_position: int = 1,  # 1=步兵，2=装甲，3=火炮，4=支援
    base_template: WeaponStats = None
) -> WeaponStats:
    """
    根据设计参数生成武器属性

    参数:
        weapon_type: 武器种类
        era: 时代
        cost: 成本
        width: 编制宽度
        speed: 速度
        params: 设计参数
        weapon_position: 武器定位
        base_template: 基础模板（用于复制其他属性）

    返回:
        WeaponStats对象
    """
    if base_template:
        # 从模板复制并修改核心数值
        weapon = WeaponStats(
            weapon_type=weapon_type,
            era=era,
            cost=cost,
            width=width,
            speed=speed,
            organization=params.organization,
            hp=params.hp,
            structure=base_template.structure,
            buoyancy=base_template.buoyancy,
            recon=base_template.recon.copy() if base_template.recon else [0.1] * 10,
            defense=params.defense_stages,
            armor_thickness=params.armor_thickness,
            armor_type=base_template.armor_type,
            weapon_position=weapon_position,
            fire_control=base_template.fire_control.copy() if base_template.fire_control else [0.1] * 10,
            electronic_jammer=base_template.electronic_jammer.copy() if base_template.electronic_jammer else [0.0] * 10,
            electronic_resistance=base_template.electronic_resistance.copy() if base_template.electronic_resistance else [0.0] * 10,
            fuel_capacity=base_template.fuel_capacity,
            fuel_per_round=base_template.fuel_per_round,
            nuclear_capacity=base_template.nuclear_capacity,
            nuclear_per_round=base_template.nuclear_per_round,
            ground_friendly_damage=base_template.ground_friendly_damage.copy() if base_template.ground_friendly_damage else [0.0] * 10,
            ground_accuracy=params.accuracy_stages,
            ground_penetration=params.penetration_stages,
            ground_suppression=params.suppression_stages,
            ground_soft_attack=params.soft_attack_stages,
            ground_hard_attack=params.hard_attack_stages,
            ground_damage=base_template.ground_damage.copy() if base_template.ground_damage else [0.0] * 10,
            air_accuracy=base_template.air_accuracy.copy() if base_template.air_accuracy else [0.0] * 10,
            air_damage=base_template.air_damage.copy() if base_template.air_damage else [0.0] * 10,
            air_interception=base_template.air_interception.copy() if base_template.air_interception else [0.0] * 10,
            sea_accuracy=base_template.sea_accuracy.copy() if base_template.sea_accuracy else [0.0] * 10,
            sea_penetration=base_template.sea_penetration.copy() if base_template.sea_penetration else [0.0] * 10,
            breakthrough=params.breakthrough,  # 突破是单值格式
            trench_defense=params.trench_defense,
            environment_adaptations=base_template.environment_adaptations.copy() if base_template.environment_adaptations else {},
        )
    else:
        # 创建全新武器
        weapon = WeaponStats(
            weapon_type=weapon_type,
            era=era,
            cost=cost,
            width=width,
            speed=speed,
            organization=params.organization,
            hp=params.hp,
            recon=[0.1] * 10,
            defense=params.defense_stages,
            armor_thickness=params.armor_thickness,
            weapon_position=weapon_position,
            fire_control=[0.1] * 10,
            ground_accuracy=params.accuracy_stages,
            ground_penetration=params.penetration_stages,
            ground_suppression=params.suppression_stages,
            ground_soft_attack=params.soft_attack_stages,
            ground_hard_attack=params.hard_attack_stages,
            breakthrough=params.breakthrough,  # 突破是单值格式
            trench_defense=params.trench_defense,
            environment_adaptations={},
        )

    return weapon


# =============================================================================
# 战斗时长测试器
# =============================================================================

def test_battle_duration(
    attacker_formation: Formation,
    defender_formation: Formation,
    defender_has_trench: bool = True,
    target_min_hours: float = 12,
    target_max_hours: float = 24,
    num_simulations: int = 5
) -> Dict:
    """
    测试战斗时长是否符合目标

    参数:
        attacker_formation: 进攻方编制
        defender_formation: 防守方编制
        defender_has_trench: 防守方是否有堑壕
        target_min_hours: 目标最小时长
        target_max_hours: 目标最大时长
        num_simulations: 模拟次数（取平均）

    返回:
        测试结果字典
    """
    durations = []

    for i in range(num_simulations):
        # 深拷贝编制以保持独立
        attacker_copy = deep_copy_formation(attacker_formation)
        defender_copy = deep_copy_formation(defender_formation)

        # 设置堑壕防御
        if defender_has_trench:
            defender_copy.trench_defense_bonus = True  # 标记用于计算

        # 设置防守方状态
        defender_copy.is_defending = True

        # 运行战斗
        stats = CombatStatistics()
        result = run_combat_loop(
            attacker_copy, defender_copy,
            ForceType.ARMY, [],
            max_rounds=500,
            stats_collector=stats
        )

        durations.append(result['rounds'])

    avg_duration = sum(durations) / len(durations)
    min_duration = min(durations)
    max_duration = max(durations)

    # 判断是否在目标区间
    in_target = avg_duration >= target_min_hours and avg_duration <= target_max_hours

    return {
        'avg_duration': avg_duration,
        'min_duration': min_duration,
        'max_duration': max_duration,
        'target_min': target_min_hours,
        'target_max': target_max_hours,
        'in_target': in_target,
        'durations': durations
    }


def adjust_attack_ratio(
    current_ratio: float,
    avg_duration: float,
    target_min: float,
    target_max: float
) -> float:
    """
    根据战斗时长调整攻防比例

    逻辑：
    - 战斗太短（<目标）→ 降低攻击或提高防御
    - 战斗太长（>目标）→ 提高攻击或降低防御

    参数:
        current_ratio: 当前攻防比例系数
        avg_duration: 平均战斗时长
        target_min: 目标最小时长
        target_max: 目标最大时长

    返回:
        新的攻防比例系数
    """
    if avg_duration < target_min:
        # 战斗太短，需要延长 → 降低攻击力
        adjustment = 1 - (target_min - avg_duration) / target_min * 0.2
        return current_ratio * adjustment
    elif avg_duration > target_max:
        # 战斗太长，需要缩短 → 提高攻击力
        adjustment = 1 + (avg_duration - target_max) / target_max * 0.2
        return current_ratio * adjustment
    else:
        # 在目标区间，不调整
        return current_ratio


# =============================================================================
# 数值迭代器主函数
# =============================================================================

def iterate_weapon_values(
    base_weapons_db: Dict[str, WeaponStats],
    attacker_spec: str,
    defender_spec: str,
    target_with_trench: Tuple[float, float] = (12, 24),
    target_without_trench: Tuple[float, float] = (6, 12),
    max_iterations: int = 20
) -> Dict:
    """
    迭代调整武器数值直到战斗时长符合目标

    参数:
        base_weapons_db: 基础武器数据库
        attacker_spec: 进攻方编制规格
        defender_spec: 防守方编制规格
        target_with_trench: 有堑壕时的目标时长（最小，最大）
        target_without_trench: 无堑壕时的目标时长
        max_iterations: 最大迭代次数

    返回:
        迭代结果字典，包含调整后的数值
    """
    print("=" * 70)
    print("数值迭代器 - 自动调整武器数值")
    print("=" * 70)

    # 初始攻防比例系数
    attack_ratio = 1.0
    defense_ratio = 1.0

    iteration_history = []

    for iteration in range(max_iterations):
        print(f"\n--- 迭代 {iteration + 1} ---")
        print(f"当前攻防比例: 攻击={attack_ratio:.2f}, 防御={defense_ratio:.2f}")

        # 创建调整后的武器数据库
        adjusted_db = adjust_weapon_database(base_weapons_db, attack_ratio, defense_ratio)

        # 构建编制
        attacker = build_formation_from_input(attacker_spec, ForceType.ARMY, "装甲团", adjusted_db)
        defender = build_formation_from_input(defender_spec, ForceType.ARMY, "步兵团", adjusted_db)

        # 测试有堑壕情况
        print("\n测试有堑壕情况...")
        result_trench = test_battle_duration(
            attacker, defender,
            defender_has_trench=True,
            target_min_hours=target_with_trench[0],
            target_max_hours=target_with_trench[1],
            num_simulations=3
        )
        print(f"  平均时长: {result_trench['avg_duration']:.1f}小时 "
              f"(目标: {target_with_trench[0]}-{target_with_trench[1]}小时)")
        print(f"  是否达标: {'✓' if result_trench['in_target'] else '✗'}")

        # 测试无堑壕情况
        print("\n测试无堑壕情况...")
        result_no_trench = test_battle_duration(
            attacker, defender,
            defender_has_trench=False,
            target_min_hours=target_without_trench[0],
            target_max_hours=target_without_trench[1],
            num_simulations=3
        )
        print(f"  平均时长: {result_no_trench['avg_duration']:.1f}小时 "
              f"(目标: {target_without_trench[0]}-{target_without_trench[1]}小时)")
        print(f"  是否达标: {'✓' if result_no_trench['in_target'] else '✗'}")

        # 记录迭代历史
        iteration_history.append({
            'iteration': iteration + 1,
            'attack_ratio': attack_ratio,
            'defense_ratio': defense_ratio,
            'trench_result': result_trench,
            'no_trench_result': result_no_trench
        })

        # 判断是否都达标
        if result_trench['in_target'] and result_no_trench['in_target']:
            print("\n✓ 两个测试都达标！迭代结束。")
            break

        # 调整比例
        if not result_trench['in_target']:
            # 有堑壕未达标，调整攻击比例
            attack_ratio = adjust_attack_ratio(
                attack_ratio,
                result_trench['avg_duration'],
                target_with_trench[0],
                target_with_trench[1]
            )

        if not result_no_trench['in_target']:
            # 无堑壕未达标，也需要调整
            attack_ratio = adjust_attack_ratio(
                attack_ratio,
                result_no_trench['avg_duration'],
                target_without_trench[0],
                target_without_trench[1]
            )

    return {
        'final_attack_ratio': attack_ratio,
        'final_defense_ratio': defense_ratio,
        'iteration_history': iteration_history,
        'adjusted_db': adjusted_db if 'adjusted_db' in dir() else base_weapons_db
    }


def adjust_weapon_database(
    base_db: Dict[str, WeaponStats],
    attack_ratio: float,
    defense_ratio: float
) -> Dict[str, WeaponStats]:
    """
    根据比例系数调整武器数据库中的攻击和防御数值

    参数:
        base_db: 基础武器数据库
        attack_ratio: 攻击比例系数
        defense_ratio: 防御比例系数

    返回:
        调整后的武器数据库
    """
    adjusted_db = {}

    for weapon_name, weapon in base_db.items():
        adjusted = deep_copy_weapon(weapon)

        # 调整软攻和硬攻
        for i in range(len(adjusted.ground_soft_attack)):
            adjusted.ground_soft_attack[i] *= attack_ratio
        for i in range(len(adjusted.ground_hard_attack)):
            adjusted.ground_hard_attack[i] *= attack_ratio

        # 调整防御
        for i in range(len(adjusted.defense)):
            adjusted.defense[i] *= defense_ratio

        # 调整突破（进攻时的防御）
        adjusted.breakthrough *= defense_ratio * 0.8  # 突破应略低于防御

        adjusted_db[weapon_name] = adjusted

    return adjusted_db


def deep_copy_weapon(weapon: WeaponStats) -> WeaponStats:
    """深拷贝武器对象"""
    return WeaponStats(
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
        fuel_capacity=weapon.fuel_capacity,
        fuel_per_round=weapon.fuel_per_round,
        nuclear_capacity=weapon.nuclear_capacity,
        nuclear_per_round=weapon.nuclear_per_round,
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
        ground_detection=weapon.ground_detection,
        radar_strength=weapon.radar_strength.copy() if weapon.radar_strength else [],
        radar_radius=weapon.radar_radius,
        breakthrough=weapon.breakthrough,
        trench_defense=weapon.trench_defense,
        environment_adaptations=weapon.environment_adaptations.copy() if weapon.environment_adaptations else {},
        quantity=weapon.quantity
    )


# =============================================================================
# 数值设计模板生成器
# =============================================================================

def generate_ww2_weapon_templates() -> Dict[str, WeaponDesignParams]:
    """
    生成二战时期武器数值模板

    基于设计原则：
    - 坦克：硬攻强，装甲厚，远距离有效
    - 步枪：软攻强，近距离有效，无装甲
    - 机枪：压制强，中近距离
    - 反坦克炮：硬攻极强，装甲穿透高
    """
    templates = {}

    # ===== 步兵武器 =====

    # 栓动步枪 - 近距离软攻主力
    rifle_params = WeaponDesignParams(
        soft_attack_stages=generate_distance_profile(
            peak_stage=3,  # 1.5-4km峰值
            peak_value=0.5,
            decay_rate=0.25,
            min_value=0.1
        ),
        hard_attack_stages=[0.05] * 10,  # 几乎无硬攻
        defense_stages=generate_distance_profile(
            peak_stage=3,
            peak_value=2.0,
            decay_rate=0.3,
            min_value=0.5
        ),
        breakthrough=0.5,
        suppression_stages=generate_distance_profile(
            peak_stage=4,
            peak_value=0.3,
            decay_rate=0.2,
            min_value=0.1
        ),
        armor_thickness=0.0,
        penetration_stages=[0.0] * 10,
        accuracy_stages=generate_distance_profile(
            peak_stage=3,
            peak_value=0.8,
            decay_rate=0.2,
            min_value=0.4
        ),
        organization=32.0,
        hp=33.0,
        trench_defense=25.0
    )
    templates['栓动步枪-二战'] = rifle_params

    # 突击步枪 - 近中距离均衡
    assault_rifle_params = WeaponDesignParams(
        soft_attack_stages=generate_distance_profile(
            peak_stage=4,  # 4-8km峰值
            peak_value=0.7,
            decay_rate=0.25,
            min_value=0.2
        ),
        hard_attack_stages=[0.1] * 10,
        defense_stages=generate_distance_profile(
            peak_stage=4,
            peak_value=2.1,
            decay_rate=0.3,
            min_value=0.6
        ),
        breakthrough=0.6,
        suppression_stages=generate_distance_profile(
            peak_stage=4,
            peak_value=0.5,
            decay_rate=0.2,
            min_value=0.15
        ),
        armor_thickness=0.0,
        penetration_stages=[0.05] * 10,
        accuracy_stages=generate_distance_profile(
            peak_stage=4,
            peak_value=0.85,
            decay_rate=0.2,
            min_value=0.45
        ),
        organization=33.0,
        hp=33.0,
        trench_defense=28.0
    )
    templates['突击步枪-二战'] = assault_rifle_params

    # 机枪 - 压制专家
    mg_params = WeaponDesignParams(
        soft_attack_stages=generate_distance_profile(
            peak_stage=5,  # 8-20km峰值
            peak_value=0.9,
            decay_rate=0.3,
            min_value=0.2
        ),
        hard_attack_stages=[0.15] * 10,
        defense_stages=generate_distance_profile(
            peak_stage=4,
            peak_value=1.8,
            decay_rate=0.25,
            min_value=0.5
        ),
        breakthrough=0.4,
        suppression_stages=generate_distance_profile(
            peak_stage=5,
            peak_value=1.2,  # 高压制
            decay_rate=0.25,
            min_value=0.3
        ),
        armor_thickness=0.0,
        penetration_stages=[0.1] * 10,
        accuracy_stages=generate_distance_profile(
            peak_stage=5,
            peak_value=0.7,
            decay_rate=0.25,
            min_value=0.3
        ),
        organization=33.0,
        hp=33.0,
        trench_defense=25.0
    )
    templates['机枪-二战'] = mg_params

    # ===== 装甲武器 =====

    # 中型坦克 - 硬攻主力，装甲厚
    tank_params = WeaponDesignParams(
        soft_attack_stages=generate_distance_profile(
            peak_stage=6,  # 20-40km峰值
            peak_value=0.8,
            decay_rate=0.3,
            min_value=0.2
        ),
        hard_attack_stages=generate_distance_profile(
            peak_stage=6,
            peak_value=1.5,  # 硬攻是软攻的近2倍
            decay_rate=0.3,
            min_value=0.4
        ),
        defense_stages=generate_distance_profile(
            peak_stage=6,
            peak_value=8.0,  # 高防御
            decay_rate=0.2,
            min_value=4.0
        ),
        breakthrough=6.0,  # 突破略低于防御（单值格式）
        suppression_stages=generate_distance_profile(
            peak_stage=6,
            peak_value=0.5,
            decay_rate=0.3,
            min_value=0.1
        ),
        armor_thickness=3.5,  # 高装甲
        penetration_stages=generate_distance_profile(
            peak_stage=5,
            peak_value=3.0,  # 高穿透
            decay_rate=0.3,
            min_value=1.0
        ),
        accuracy_stages=generate_distance_profile(
            peak_stage=5,
            peak_value=0.7,
            decay_rate=0.25,
            min_value=0.35
        ),
        organization=40.0,
        hp=40.0,
        trench_defense=0.0  # 坦克无堑壕防御
    )
    templates['中型坦克-二战'] = tank_params

    # 反坦克炮 - 穿甲专家
    at_gun_params = WeaponDesignParams(
        soft_attack_stages=[0.2] * 10,  # 低软攻
        hard_attack_stages=generate_distance_profile(
            peak_stage=5,
            peak_value=2.0,  # 极高硬攻
            decay_rate=0.35,
            min_value=0.5
        ),
        defense_stages=generate_distance_profile(
            peak_stage=6,
            peak_value=1.5,
            decay_rate=0.3,
            min_value=0.5
        ),
        breakthrough=0.3,
        suppression_stages=[0.2] * 10,
        armor_thickness=0.0,
        penetration_stages=generate_distance_profile(
            peak_stage=5,
            peak_value=4.0,  # 极高穿透
            decay_rate=0.35,
            min_value=1.0
        ),
        accuracy_stages=generate_distance_profile(
            peak_stage=5,
            peak_value=0.8,
            decay_rate=0.25,
            min_value=0.4
        ),
        organization=35.0,
        hp=35.0,
        trench_defense=20.0
    )
    templates['反坦克炮-二战'] = at_gun_params

    # ===== 支援武器 =====

    # 迫击炮 - 中近距离压制
    mortar_params = WeaponDesignParams(
        soft_attack_stages=generate_distance_profile(
            peak_stage=4,
            peak_value=0.6,
            decay_rate=0.4,
            min_value=0.1
        ),
        hard_attack_stages=generate_distance_profile(
            peak_stage=4,
            peak_value=0.4,
            decay_rate=0.4,
            min_value=0.1
        ),
        defense_stages=[0.5] * 10,
        breakthrough=0.2,
        suppression_stages=generate_distance_profile(
            peak_stage=4,
            peak_value=0.8,  # 高压制
            decay_rate=0.35,
            min_value=0.2
        ),
        armor_thickness=0.0,
        penetration_stages=[0.1] * 10,
        accuracy_stages=generate_distance_profile(
            peak_stage=4,
            peak_value=0.6,
            decay_rate=0.35,
            min_value=0.2
        ),
        organization=35.0,
        hp=35.0,
        trench_defense=15.0
    )
    templates['迫击炮-二战'] = mortar_params

    return templates


# =============================================================================
# 测试与验证
# =============================================================================

def run_iteration_test():
    """运行数值迭代测试"""
    print("=" * 70)
    print("数值平衡迭代器 - 二战装甲团 vs 步兵团测试")
    print("=" * 70)

    # 加载基础武器数据库
    base_path = "d:/游戏策划相关/战争模块"
    army_db, air_db, navy_db = load_all_weapons(base_path)

    print(f"\n基础武器数量: 陆军={len(army_db)}, 空军={len(air_db)}, 海军={len(navy_db)}")

    # 二战装甲团编制（来自army_war.csv）
    attacker_spec = "中型坦克:74=反坦克歼击车:10=自行突击炮:10=轮式装甲车:10"

    # 二战步兵团编制
    defender_spec = "栓动步枪:600=突击步枪:1028=冲锋枪:121=机枪:140=迫击炮:24=反坦克炮:15"

    # 运行迭代
    result = iterate_weapon_values(
        army_db,
        attacker_spec,
        defender_spec,
        target_with_trench=(12, 24),
        target_without_trench=(6, 12),
        max_iterations=10
    )

    print("\n" + "=" * 70)
    print("迭代结果汇总")
    print("=" * 70)
    print(f"最终攻击比例系数: {result['final_attack_ratio']:.3f}")
    print(f"最终防御比例系数: {result['final_defense_ratio']:.3f}")
    print(f"迭代次数: {len(result['iteration_history'])}")

    return result


def analyze_current_values():
    """分析当前CSV数值的战斗时长"""
    print("=" * 70)
    print("分析当前CSV数值的战斗表现")
    print("=" * 70)

    base_path = "d:/游戏策划相关/战争模块"
    army_db, air_db, navy_db = load_all_weapons(base_path)

    # 二战后期装甲团
    attacker_spec = "中型坦克:74=反坦克歼击车:10=自行突击炮:10=轮式装甲车:10"

    # 二战后期步兵团
    defender_spec = "栓动步枪:600=突击步枪:1028=冲锋枪:121=机枪:140=迫击炮:24=反坦克炮:15"

    # 构建编制
    attacker = build_formation_from_input(attacker_spec, ForceType.ARMY, "装甲团", army_db)
    defender = build_formation_from_input(defender_spec, ForceType.ARMY, "步兵团", army_db)

    print(f"\n进攻方（装甲团）:")
    print(f"  总宽度: {attacker.total_width}")
    print(f"  血量: {attacker.current_hp:.2f}")
    print(f"  组织度: {attacker.current_organization:.2f}")
    print(f"  装甲率: {attacker.get_armor_rate():.2%}")

    print(f"\n防守方（步兵团）:")
    print(f"  总宽度: {defender.total_width}")
    print(f"  血量: {defender.current_hp:.2f}")
    print(f"  组织度: {defender.current_organization:.2f}")
    print(f"  装甲率: {defender.get_armor_rate():.2%}")

    # 测试有堑壕
    print("\n--- 测试有堑壕情况（目标12-24小时） ---")
    result_trench = test_battle_duration(
        attacker, defender,
        defender_has_trench=True,
        target_min_hours=12,
        target_max_hours=24,
        num_simulations=5
    )
    print(f"平均时长: {result_trench['avg_duration']:.1f}小时")
    print(f"范围: {result_trench['min_duration']}-{result_trench['max_duration']}小时")
    print(f"是否达标: {'是' if result_trench['in_target'] else '否'}")

    # 测试无堑壕
    print("\n--- 测试无堑壕情况（目标6-12小时） ---")
    result_no_trench = test_battle_duration(
        attacker, defender,
        defender_has_trench=False,
        target_min_hours=6,
        target_max_hours=12,
        num_simulations=5
    )
    print(f"平均时长: {result_no_trench['avg_duration']:.1f}小时")
    print(f"范围: {result_no_trench['min_duration']}-{result_no_trench['max_duration']}小时")
    print(f"是否达标: {'是' if result_no_trench['in_target'] else '否'}")

    return {
        'trench_result': result_trench,
        'no_trench_result': result_no_trench
    }


if __name__ == "__main__":
    # 先分析当前数值
    analyze_current_values()

    # 运行迭代测试
    # run_iteration_test()