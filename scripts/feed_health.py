"""Atomic data and public health reports; never expose credential-bearing errors."""
import datetime, json, os, pathlib, tempfile
OUT = pathlib.Path(__file__).resolve().parents[1] / 'data'
EXPECTED = ('quakes','storms','alerts','space','fires','flights','sats','lightning','ships','fishing','outages')

def now():
    return datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds')

def read(path, fallback):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return fallback

def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    text=json.dumps(payload,separators=(',',':'),allow_nan=False)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,suffix='.tmp',delete=False) as f:
        f.write(text)
        tmp=f.name
    os.replace(tmp,path)

def record(name,status,message='',payload=None):
    path=OUT/'health.json'
    health=read(path,{'schemaVersion':1,'datasets':{}})
    entry=dict(health['datasets'].get(name,{}),status=status,lastAttempt=now(),message=message)
    cached=payload if payload is not None else read(OUT/(name+'.json'),{})
    if cached:
        entry.update(lastSuccess=cached.get('fetched'),recordCount=len(cached.get('items',cached.get('aurora',[]))),validTime=cached.get('validTime',cached.get('auroraTime')))
    health['datasets'][name]=entry
    health['generated']=now()
    atomic_json(path,health)

def publish(name,payload,source,kind,note=''):
    data=dict(payload,fetched=now(),source=source,**{'class':kind},note=note)
    atomic_json(OUT/(name+'.json'),data)
    record(name,'ok',payload=data)

class NotConfigured(Exception): pass

def run(name,fn):
    record(name,'running','Update in progress')
    try:
        fn()
        return True
    except NotConfigured:
        record(name,'not_configured','Required provider credentials are not configured')
        print(name,'not configured')
    except Exception as error:
        status=getattr(getattr(error,'response',None),'status_code',None)
        message='Provider HTTP '+str(status) if status else 'Provider request or data validation failed'
        record(name,'failed',message)
        print(name,message)
    return False

def manifest():
    health=read(OUT/'health.json',{'datasets':{}})
    for name in EXPECTED:
        if name not in health['datasets']:
            record(name,'not_configured' if name=='ships' else 'missing','No ship collector configured' if name=='ships' else 'No successful update recorded')
    files=sorted(p.name for p in OUT.glob('*.json') if p.name not in ('index.json','health.json'))
    atomic_json(OUT/'index.json',{'files':files,'fetched':now(),'health':'health.json','source':'feed manifest','class':'reference'})

if __name__=='__main__': manifest()
