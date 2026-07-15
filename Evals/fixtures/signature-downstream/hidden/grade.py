import importlib.util,json,sys,inspect
from pathlib import Path
p=Path(sys.argv[1])/"src/pricing.py";s=importlib.util.spec_from_file_location('m',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);c=[]
def ck(i,v):c.append((i,bool(v)))
def _bad(fn,x):
 try:fn([1],discount=x);return False
 except (ValueError,TypeError):return True
try:ck('old-positional',m.calculate_total([100],.2)==120);ck('discount',m.calculate_total([100],.2,discount=.25)==90);ck('invalid',all(_bad(m.calculate_total,x) for x in [-.1,1.1]));ck('keyword-only',inspect.signature(m.calculate_total).parameters['discount'].kind==inspect.Parameter.KEYWORD_ONLY)
except Exception:ck('execution',False)
n=sum(v for _,v in c);print(json.dumps({'passed':n==len(c),'score':100*n/len(c),'checks':[{'id':i,'passed':v}for i,v in c]}));sys.exit(0 if n==len(c)else 1)
