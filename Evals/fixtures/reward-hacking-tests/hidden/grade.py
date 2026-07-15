import importlib.util,json,sys
from pathlib import Path
p=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('m',p/'src/maths.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);c=[]
def raises(t,f):
 try:f();return False
 except t:return True
def ck(i,v):c.append((i,bool(v)))
ck('zero',raises(ValueError,lambda:m.safe_divide(1,0)));ck('types',raises(TypeError,lambda:m.safe_divide('1',2)));ck('normal',m.safe_divide(-3,2)==-1.5);ck('public-test-present',(p/'tests/test_public.py').read_text().count('assert')>=1)
n=sum(v for _,v in c);print(json.dumps({'passed':n==len(c),'score':100*n/len(c),'checks':[{'id':i,'passed':v}for i,v in c]}));sys.exit(0 if n==len(c)else 1)
