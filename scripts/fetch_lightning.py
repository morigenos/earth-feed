"""Read recent GOES-East GLM lightning files from NOAA's public S3 bucket and write
a small JSON of flash positions. GLM sees optical flashes from orbit: these include
in-cloud lightning and are not all ground strikes, and coverage is the Americas only."""
import json, pathlib, datetime, tempfile, requests
import numpy as np
from netCDF4 import Dataset

OUT = pathlib.Path(__file__).resolve().parents[1] / "data"
BUCKET = "https://noaa-goes16.s3.amazonaws.com"
FILES = 60
MAX_FLASHES = 20000

def list_keys(prefix):
    r = requests.get(f"{BUCKET}/?list-type=2&prefix={prefix}&max-keys=1000", timeout=60)
    r.raise_for_status()
    return [k.split("</Key>")[0] for k in r.text.split("<Key>")[1:]]

def main():
    now = datetime.datetime.now(datetime.UTC)
    flashes = []
    for back in (0, 1):
        t = now - datetime.timedelta(hours=back)
        prefix = f"GLM-L2-LCFA/{t.year}/{t.timetuple().tm_yday:03d}/{t.hour:02d}/"
        try:
            keys = sorted(list_keys(prefix))[-FILES:]
        except Exception as e:
            print("listing failed:", e); continue
        for k in keys:
            try:
                blob = requests.get(f"{BUCKET}/{k}", timeout=60).content
                with tempfile.NamedTemporaryFile(suffix=".nc") as f:
                    f.write(blob); f.flush()
                    with Dataset(f.name) as nc:
                        lat = np.array(nc["flash_lat"][:], dtype=float)
                        lon = np.array(nc["flash_lon"][:], dtype=float)
                ts = int(datetime.datetime.strptime(k.split("_s")[1][:13], "%Y%j%H%M%S")
                         .replace(tzinfo=datetime.UTC).timestamp())
                flashes += [[round(float(lo), 2), round(float(la), 2), ts]
                            for la, lo in zip(lat, lon) if np.isfinite(la) and np.isfinite(lo)]
            except Exception as e:
                print("file failed:", k, e)
        if flashes:
            break
    flashes = flashes[-MAX_FLASHES:]
    (OUT / "lightning.json").write_text(json.dumps({
        "items": flashes,
        "fetched": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "source": "NOAA GOES-16 GLM level 2 flash data (public S3 bucket)",
        "class": "observed",
        "coverage": "GOES-East field of view: the Americas and neighbouring ocean, not global.",
        "note": "Optical flashes seen from orbit, including in-cloud lightning. Not every flash reaches the ground."
    }, separators=(",", ":")))
    print("wrote lightning.json with", len(flashes), "flashes")

if __name__ == "__main__":
    main()
