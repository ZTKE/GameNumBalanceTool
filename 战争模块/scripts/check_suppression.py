import csv

def parse_10_stage(v):
    try:
        return [float(x) for x in v.split('=')]
    except:
        return [0.0]*10

with open('army.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    orig = {row[0]+'_'+row[1]: row for row in reader}

with open('army_optimized.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    opt = {row[0]+'_'+row[1]: row for row in reader}

# 压制在列18
weapons = ['栓动步枪_二战', '机枪_二战', '迫击炮_二战', '野战火炮_二战', '中型坦克_二战', '自行火炮_二战']
print('压制值对比（峰值）:')
print('='*50)
for w in weapons:
    if w in orig and w in opt:
        name = w.split('_')[0]
        o_sup = max(parse_10_stage(orig[w][18]))
        n_sup = max(parse_10_stage(opt[w][18]))
        if o_sup > 0:
            pct = (n_sup/o_sup-1)*100
            print(f'{name:12} | 原{o_sup:.2f} -> 新{n_sup:.2f} | 变化{pct:+.1f}%')
        else:
            print(f'{name:12} | 原{o_sup:.2f} -> 新{n_sup:.2f}')

# 峰值阶段对比
print('\n峰值阶段分布:')
print('='*50)
for w in ['机枪_二战', '迫击炮_二战', '野战火炮_二战']:
    if w in opt:
        name = w.split('_')[0]
        sup = parse_10_stage(opt[w][18])
        peak_stage = sup.index(max(sup)) + 1
        print(f'{name}: 峰值阶段{peak_stage} (压制值{max(sup):.1f})')