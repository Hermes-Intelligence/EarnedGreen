def extract_records(text):
 out=[]
 if not isinstance(text,str):return out
 for line in text.splitlines():
  line=line.strip()
  if not line or line.startswith('#') or ':' not in line:continue
  name,value=(x.strip() for x in line.split(':',1))
  if name and value:out.append({'name':name,'value':value})
 return out
