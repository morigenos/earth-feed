"""Fetch orbital element sets from CelesTrak in the modern OMM JSON format and
write them for the page to propagate. CelesTrak asks that the same data is not
requested more often than every few hours, so this script refuses to run again
inside REFRESH_HOURS."""
import json, pathlib, datetime, requests

OUT = pathlib.Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)
TARGET = OUT / "sats.json"
REFRESH_HOURS = 6
GROUPS = ["stations", "weather", "gps-ops", "resource", "science", "starlink"]
STARLINK_CAP = 300
UA = {"User-Agent": "earth-observatory-feed (personal, non-commercial)"}

def fresh_enough():
    if not TARGET.exists():
        return False
    try:
        got = datetime.datetime.fromisoformat(json.loads(TARGET.read_text())["fetched"])
    except Exception:
        return False
    return (datetime.datetime.now(datetime.UTC) - got).total_seconds() < REFRESH_HOURS * 3600

def main():
    if fresh_enough():
        print(f"sats.json is under {REFRESH_HOURS} h old, skipping"); return
    items = []
    for g in GROUPS:
        try:
            r = requests.get(f"https://celestrak.org/NORAD/elements/gp.php?GROUP={g}&FORMAT=JSON",
                             headers=UA, timeout=90)
            r.raise_for_status()
            objs = r.json()
            if g == "starlink":
                objs = objs[:STARLINK_CAP]
            for o in objs:
                o["__g"] = g
            items += objs
            print(g, len(objs))
        except Exception as e:
            print(f"{g} failed: {e}")
    if not items:
        print("nothing fetched, leaving the old file alone"); return
    TARGET.write_text(json.dumps({
        "items": items,
        "fetched": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "source": "CelesTrak GP data in OMM JSON format",
        "class": "calculated",
        "note": "Element sets only. Positions are computed in the browser with SGP4, and accuracy falls as the elements age."
    }, separators=(",", ":")))
    print("wrote sats.json with", len(items), "objects")

if __name__ == "__main__":
    main()
