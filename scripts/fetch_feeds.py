"""Fetch public feeds, retaining cached data on provider failures."""
import csv, datetime, io, math, os, requests
from feed_health import NotConfigured, publish, run, manifest
UA={'User-Agent':'earth-observatory-feed (personal, non-commercial)'}
GDACS='https://www.gdacs.org/gdacsapi/api/events/geteventlist/events4app'

def get(url):
    r=requests.get(url,headers=UA,timeout=60)
    r.raise_for_status()
    return r

def finite(v): return isinstance(v,(float,int)) and math.isfinite(v)

def quakes():
    data=get('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson').json()
    if not isinstance(data.get('features'),list): raise ValueError('Invalid quake collection')
    items=[]
    for f in data['features']:
        c,p=f['geometry']['coordinates'],f['properties']
        if len(c)<3 or not all(finite(v) for v in c[:3]) or not finite(p.get('mag')): continue
        items.append([round(c[0],3),round(c[1],3),round(c[2],1),p['mag'],p.get('place',''),int(p['time']/1000)])
    publish('quakes',{'items':items},'USGS M4.5+ past 7 days','observed')

def storms():
    data=get('https://www.nhc.noaa.gov/CurrentStorms.json').json()
    if not isinstance(data.get('activeStorms'),list): raise ValueError('Invalid storm collection')
    items=[]
    for s in data['activeStorms']:
        items.append({'n':f'{s.get("classification", "")} {s.get("name", "")}'.strip(),
            'basin':s.get('basin','NHC area'),'lat':float(s['latitudeNumeric']),'lon':float(s['longitudeNumeric']),
            'windKt':float(s.get('intensity') or 0),'pres':float(s.get('pressure') or 0),'status':'active',
            'd':f'Moving {s.get("movementDir", "?")} degrees at {s.get("movementSpeed", "?")} kt.'})
    publish('storms',{'items':items},'NOAA National Hurricane Center','observed','Atlantic, eastern and central Pacific only; empty means no active NHC storms.')

def alerts():
    data=get(GDACS).json()
    if not isinstance(data.get('features'),list): raise ValueError('Invalid alert collection')
    kinds={'FL':'flood','DR':'drought','WF':'fire','TC':'storm','VO':'ash','EQ':'quake'}
    items=[]
    for f in data['features']:
        p,g=f.get('properties',{}),f.get('geometry') or {}
        c=g.get('coordinates',[])
        if g.get('type')!='Point' or len(c)<2 or not all(finite(v) for v in c[:2]): continue
        if p.get('eventtype') not in kinds or str(p.get('iscurrent','true')).lower()=='false': continue
        items.append({'id':f'{p.get("eventtype")}-{p.get("eventid")}','t':kinds[p['eventtype']],
            'n':p.get('name') or p.get('eventname') or p['eventtype'],'lat':c[1],'lon':c[0],
            'validTime':p.get('datemodified'),'d':f'{p.get("alertlevel", "")} alert, {p.get("country", "")}, from {str(p.get("fromdate", ""))[:10]}.'})
    publish('alerts',{'items':items},'GDACS events4app current event collection','reported','Provider collection limited to 100 recent events; not a complete hazard inventory.')

def latest_kp(rows):
    for row in reversed(rows):
        if isinstance(row,dict):
            value,timestamp=row.get('Kp',row.get('kp_index',row.get('estimated_kp'))),row.get('time_tag')
        elif isinstance(row,list) and len(row)>1: timestamp,value=row[:2]
        else: continue
        try:
            value=float(value)
            if math.isfinite(value) and 0<=value<=9: return value,timestamp
        except (TypeError,ValueError): pass
    raise ValueError('No valid Kp record')

def space():
    kp,kp_time=latest_kp(get('https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json').json())
    ov=get('https://services.swpc.noaa.gov/json/ovation_aurora_latest.json').json()
    if not isinstance(ov.get('coordinates'),list) or not ov['coordinates']: raise ValueError('No aurora grid')
    publish('space',{'kp':kp,'kpTime':kp_time,'aurora':ov['coordinates'],'auroraTime':ov.get('Forecast Time'),'validTime':ov.get('Forecast Time')},'NOAA SWPC Kp and OVATION','modelled')

def fires():
    key=os.environ.get('FIRMS_KEY','').strip()
    if not key: raise NotConfigured()
    data=get(f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_NOAA20_NRT/world/1').text
    reader=csv.DictReader(io.StringIO(data))
    if not {'latitude','longitude','acq_date','acq_time'}.issubset(reader.fieldnames or []): raise ValueError('Invalid fire CSV')
    items=[]
    for row in reader:
        timestamp=datetime.datetime.strptime(row['acq_date']+' '+row['acq_time'].zfill(4),'%Y-%m-%d %H%M').replace(tzinfo=datetime.UTC).timestamp()
        items.append([round(float(row['latitude']),3),round(float(row['longitude']),3),round(float(row.get('frp') or 0),1),int(timestamp)])
    publish('fires',{'items':items},'NASA FIRMS VIIRS NOAA-20, past 24 hours','observed','Thermal anomalies, not confirmed fires. Acquisition times are UTC Unix seconds.')

if __name__=='__main__':
    for fn in (quakes,storms,alerts,space,fires): run(fn.__name__,fn)
    manifest()
