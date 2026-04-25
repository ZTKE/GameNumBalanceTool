"""
测试二战德国陆军编制之间的战斗
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from combat_logic import load_army_csv, ForceType
from battle_simulator import run_battle_simulation, print_battle_report


def test_ww2_german_battles():
    """测试二战德国各编制之间的战斗"""
    print("=" * 70)
    print("二战德国陆军编制战斗测试")
    print("=" * 70)

    # 加载优化后的数值
    weapons = load_army_csv("army_optimized.csv")

    # 二战德国编制（来自army_war.csv）
    formations = {
        '步兵团前期': '栓动步枪:1636=冲锋枪:140=机枪:130=迫击炮:24=反坦克步枪:18=反坦克炮:10',
        '步兵团后期': '栓动步枪:600=突击步枪:1028=冲锋枪:121=机枪:140=迫击炮:24=反坦克炮:15',
        '装甲掷弹兵团前期': '栓动步枪:1036=冲锋枪:280=机枪:190=迫击炮:30=反坦克步枪:24=反坦克炮:16=轮式装甲车:20',
        '装甲掷弹兵团后期': '栓动步枪:280=突击步枪:874=冲锋枪:223=机枪:180=迫击炮:24=反坦克炮:23=轮式装甲车:18',
        '炮兵团前期': '野战火炮:45=步兵炮:20=防空炮:11',
        '炮兵团后期': '野战火炮:42=步兵炮:16=防空炮:20',
        '装甲团前期': '中型坦克:61=轻型坦克:30=反坦克歼击车:6=自行突击炮:6=轮式装甲车:9',
        '装甲团后期': '中型坦克:74=反坦克歼击车:10=自行突击炮:10=轮式装甲车:10',
    }

    # 测试组合
    test_cases = [
        # 装甲团 vs 步兵团
        ('装甲团后期', '步兵团后期', '装甲进攻步兵'),
        ('装甲团前期', '步兵团前期', '装甲进攻步兵（前期）'),
        ('步兵团后期', '装甲团后期', '步兵进攻装甲'),

        # 装甲团 vs 装甲掷弹兵团
        ('装甲团后期', '装甲掷弹兵团后期', '装甲进攻装甲掷弹兵'),

        # 装甲掷弹兵团 vs 步兵团
        ('装甲掷弹兵团后期', '步兵团后期', '装甲掷弹兵进攻步兵'),

        # 装甲团 vs 装甲团
        ('装甲团后期', '装甲团前期', '装甲对装甲'),

        # 炮兵团测试
        ('炮兵团后期', '步兵团后期', '炮兵进攻步兵'),
        ('装甲团后期', '炮兵团后期', '装甲进攻炮兵'),
    ]

    results = []

    for attacker_name, defender_name, desc in test_cases:
        print(f"\n{'='*70}")
        print(f"测试: {desc}")
        print(f"攻击方: {attacker_name} - {formations[attacker_name]}")
        print(f"防守方: {defender_name} - {formations[defender_name]}")
        print("=" * 70)

        try:
            report = run_battle_simulation(
                formations[attacker_name],
                formations[defender_name],
                ForceType.ARMY,
                weapons
            )
            print_battle_report(report)

            results.append({
                'test': desc,
                'attacker': attacker_name,
                'defender': defender_name,
                'duration': report.battle_duration_hours,
                'winner': report.winner,
                'ic_ratio': report.ic_exchange_ratio,
            })
        except Exception as e:
            print(f"错误: {e}")
            results.append({
                'test': desc,
                'error': str(e),
            })

    # 总结表格
    print("\n" + "=" * 70)
    print("战斗结果汇总")
    print("=" * 70)
    print(f"{'测试场景':<30} {'时长(h)':<10} {'胜方':<10} {'IC比':<10}")
    print("-" * 70)

    for r in results:
        if 'error' in r:
            print(f"{r['test']:<30} 错误: {r['error']}")
        else:
            winner = '攻击方' if r['winner'] == 'attacker' else '防守方'
            print(f"{r['test']:<30} {r['duration']:<10} {winner:<10} {r['ic_ratio']:<10.2f}")

    # 分析结论
    print("\n" + "=" * 70)
    print("数值平衡分析")
    print("=" * 70)

    successful = [r for r in results if 'error' not in r]
    if successful:
        # 检查时长范围
        durations = [r['duration'] for r in successful]
        print(f"战斗时长范围: {min(durations)}-{max(durations)} 小时")
        print(f"平均战斗时长: {sum(durations)/len(durations):.1f} 小时")

        # 检查IC交换比
        ic_ratios = [r['ic_ratio'] for r in successful]
        print(f"IC交换比范围: {min(ic_ratios):.2f}-{max(ic_ratios):.2f}")

        # 判断平衡性
        print("\n平衡性评估:")
        if min(durations) >= 6 and max(durations) <= 30:
            print("  时长范围合理 (6-30小时区间)")
        else:
            print(f"  时长异常: 最短{min(durations)}h, 最长{max(durations)}h")

        # 检查克制关系
        armor_vs_infantry = [r for r in successful if '装甲进攻步兵' in r['test']]
        if armor_vs_infantry:
            for r in armor_vs_infantry:
                if r['winner'] == 'attacker' and r['ic_ratio'] > 2:
                    print("  装甲克制步兵: 正常 (装甲方胜，IC优势)")
                else:
                    print(f"  装甲克制步兵异常: {r}")

    return results


if __name__ == "__main__":
    test_ww2_german_battles()