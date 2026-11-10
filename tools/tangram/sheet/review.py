import json, sys
from preview import sheet
import tg45
res=json.load(open(sys.argv[1]))
keys=sys.argv[3:] or sorted(res, key=lambda k: tuple(map(int,k.split(','))))
figs=[]
for k in keys:
    if k not in res: continue
    r,c=k.split(',')
    figs.append(tg45.fig_from_solution('f_%s_%s'%(r,c), k, res[k]['solution']))
sheet(figs, sys.argv[2])
