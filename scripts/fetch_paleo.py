"""Precompute plate reconstructions for the Deep Time view.

Asks the GPlates Web Service (EarthByte, University of Sydney) for reconstructed
coastlines at a series of ages and stores them as small GeoJSON files. The service
does the science; this script only caches the answers so the globe does not have to
call it every time. Run it once: it skips ages that are already on disk.

Models offered here, with the age range each one supports:
  MERDITH2021  0-1000 Ma   Merdith et al. 2021, paleomagnetic reference frame
  MULLER2022   0-1000 Ma   Muller et al. 2022, mantle reference frame
  CAO2024      0-1800 Ma   Cao et al. 2024, longest range
Cite the model you display. The service is GPL software run by EarthByte; be polite
with request rates.
"""
import json, pathlib, time, requests

OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "paleo"
MAX_NEW = 40          # fetch at most this many new ages per run, so a first run cannot hog the job
OUT.mkdir(parents=True, exist_ok=True)
GWS = "https://gws.gplates.org/reconstruct/coastlines/"
PLAN = {"MERDITH2021": list(range(0, 1001, 10)),
        "CAO2024": list(range(0, 1801, 50))}
PRECISION = 2          # decimal places kept for each coordinate

def thin(geom):
    """Round coordinates and drop tiny rings; the globe is 2048 px wide, so
    centimetre precision is wasted bytes."""
    def ring(r):
        out, last = [], None
        for x, y in r:
            p = [round(x, PRECISION), round(y, PRECISION)]
            if p != last:
                out.append(p); last = p
        return out
    if geom["type"] == "Polygon":
        rings = [ring(r) for r in geom["coordinates"]]
        return {"type": "Polygon", "coordinates": [r for r in rings if len(r) > 3]}
    if geom["type"] == "MultiPolygon":
        polys = [[ring(r) for r in poly] for poly in geom["coordinates"]]
        polys = [[r for r in poly if len(r) > 3] for poly in polys]
        return {"type": "MultiPolygon", "coordinates": [p for p in polys if p]}
    return geom

def fetch(model, age):
    target = OUT / f"{model}_{age}.json"
    if target.exists():
        return False
    r = requests.get(GWS, params={"time": age, "model": model}, timeout=180,
                     headers={"User-Agent": "earth-observatory-feed (personal, non-commercial)"})
    r.raise_for_status()
    gj = r.json()
    feats = []
    for f in gj.get("features", []):
        g = thin(f["geometry"])
        if g.get("coordinates"):
            feats.append({"type": "Feature", "geometry": g, "properties": {}})
    target.write_text(json.dumps({
        "age": age, "model": model, "features": feats,
        "source": "GPlates Web Service, EarthByte group, University of Sydney",
        "class": "modelled",
        "note": "Reconstructed present-day coastlines moved to their modelled past positions. "
                "They are not ancient shorelines: sea level, erosion and deposition are not modelled."
    }, separators=(",", ":")))
    return True

def main():
    index = {}
    fetched_now = 0
    for model, ages in PLAN.items():
        done = []
        for age in ages:
            if fetched_now >= MAX_NEW:
                done.append(age) if (OUT / f"{model}_{age}.json").exists() else None
                continue
            try:
                if fetch(model, age):
                    fetched_now += 1
                    print(model, age, "fetched"); time.sleep(1.5)
                done.append(age)
            except Exception as e:
                print(f"{model} {age} failed: {e}")
        index[model] = done
    (OUT / "index.json").write_text(json.dumps({
        "models": index,
        "ranges": {"MERDITH2021": [0, 1000], "CAO2024": [0, 1800]},
        "source": "GPlates Web Service, EarthByte group, University of Sydney", "class": "modelled"
    }, separators=(",", ":")))
    print("wrote paleo index")

if __name__ == "__main__":
    main()
