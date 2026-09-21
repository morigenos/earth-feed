"""Recent GOES-East GLM flashes. No readable files is failure, not zero activity."""
import datetime, math, os, xml.etree.ElementTree as ET, requests
from feed_health import publish, record, run
BUCKET='https://noaa-goes19.s3.amazonaws.com'
FILES=60
MAX_FLASHES=20000

def list_keys(prefix):
    r=requests.get(BUCKET+'/',params={'list-type':2,'prefix':prefix,'max-keys':1000},timeout=30)
    r.raise_for_status()
    return [n.text for n in ET.fromstring(r.content).iter() if n.tag.split('}')[-1]=='Key']

def main():
    from netCDF4 import Dataset
    now=datetime.datetime.now(datetime.UTC)
    keys=[]
    listing_failures=0
    for back in (0,1):
        t=now-datetime.timedelta(hours=back)
        try: keys+=list_keys(f'GLM-L2-LCFA/{t.year}/{t.timetuple().tm_yday:03d}/{t.hour:02d}/')
        except Exception: listing_failures+=1
    keys=sorted(set(keys))[-int(os.environ.get('LIGHTNING_FILES',FILES)):]
    if not keys: raise ValueError('No recent GLM files')
    flashes,times,loaded=[],[],0
    for key in keys:
        try:
            r=requests.get(BUCKET+'/'+key,timeout=30)
            r.raise_for_status()
            timestamp=int(datetime.datetime.strptime(key.split('_s')[1][:13],'%Y%j%H%M%S').replace(tzinfo=datetime.UTC).timestamp())
            with Dataset('glm.nc',memory=r.content) as nc:
                lat,lon=nc['flash_lat'][:],nc['flash_lon'][:]
                for la,lo in zip(lat,lon):
                    if getattr(la,'mask',False) or getattr(lo,'mask',False): continue
                    if math.isfinite(float(la)) and math.isfinite(float(lo)): flashes.append([round(float(lo),2),round(float(la),2),timestamp])
            loaded+=1
            times.append(timestamp)
        except Exception: continue
    if not loaded: raise ValueError('No readable GLM files')
    flashes.sort(key=lambda x:x[2])
    raw_count=len(flashes)
    latest={}
    for lo,la,t in flashes:                                 # sorted by time, so later flashes overwrite earlier ones
        latest[(round(lo*20),round(la*20))]=[lo,la,t]
    flashes=sorted(latest.values(),key=lambda x:x[2])
    truncated=max(0,len(flashes)-MAX_FLASHES)
    publish('lightning',{'items':flashes[-MAX_FLASHES:],'rawFlashes':raw_count,'droppedOldest':truncated,
        'thinning':'newest flash kept per 0.05-degree cell','filesRead':loaded,'filesRequested':len(keys),
        'validTime':datetime.datetime.fromtimestamp(max(times),datetime.UTC).isoformat(),
        'coverage':'GOES-East Americas and neighbouring oceans, not global'},
        'NOAA GOES-19 GLM level 2','observed','Optical flashes, including in-cloud events. Timestamps use file start times.')
    if loaded<len(keys) or listing_failures: record('lightning','partial',f'Read {loaded} of {len(keys)} selected files; some requests failed')

if __name__=='__main__': run('lightning',main)
