#!/usr/bin/env python3
"""Generate realistic API traffic so logs, Prometheus and Grafana have something to show.

Standard library only (no pip install needed).

Examples
  python3 scripts/generate_traffic.py                       # 3-minute "demo" profile
  python3 scripts/generate_traffic.py --profile steady --rps 10 --duration 60
  python3 scripts/generate_traffic.py --url http://localhost:18080 --profile spike

Profiles (requests/second over time)
  demo    warm-up -> ramp -> spike -> cool-down        (best for a Grafana screenshot)
  steady  constant --rps for --duration seconds
  spike   low load with a sudden 10x burst in the middle

Traffic mix: valid patients (sampled from data/heart_disease_clean.csv when present),
plus --invalid-ratio of bad payloads (HTTP 422) and a few 404s, so the error panels light up.
"""
import argparse
import csv
import json
import random
import statistics
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

FEATURES = ["age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
            "thalach", "exang", "oldpeak", "slope", "ca", "thal"]
CLEAN_CSV = Path(__file__).resolve().parent.parent / "data" / "heart_disease_clean.csv"


def load_patients():
    """Real rows from the cleaned dataset (missing ca/thal replaced by common values)."""
    patients = []
    if CLEAN_CSV.exists():
        with CLEAN_CSV.open() as fh:
            for row in csv.DictReader(fh):
                rec = {k: (float(row[k]) if row[k] != "" else None) for k in FEATURES}
                rec["ca"] = 0.0 if rec["ca"] is None else rec["ca"]
                rec["thal"] = 3.0 if rec["thal"] is None else rec["thal"]
                patients.append(rec)
    return patients


def random_patient(rng):
    return {"age": rng.randint(29, 77), "sex": rng.randint(0, 1), "cp": rng.randint(1, 4),
            "trestbps": rng.randint(94, 200), "chol": rng.randint(126, 564), "fbs": rng.randint(0, 1),
            "restecg": rng.randint(0, 2), "thalach": rng.randint(71, 202), "exang": rng.randint(0, 1),
            "oldpeak": round(rng.uniform(0, 6.2), 1), "slope": rng.randint(1, 3),
            "ca": rng.randint(0, 3), "thal": rng.choice([3, 6, 7])}


def bad_payload(rng):
    rec = random_patient(rng)
    kind = rng.choice(["missing", "range", "type"])
    if kind == "missing":
        del rec[rng.choice(FEATURES)]
    elif kind == "range":
        rec["age"] = rng.choice([-5, 500])
    else:
        rec["chol"] = "abc"
    return rec


def call(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except Exception:
        status = 0
    return status, (time.perf_counter() - start) * 1000


def schedule(profile, rps, duration):
    """Yield (seconds, target_rps) phases."""
    if profile == "steady":
        return [(duration, rps)]
    if profile == "spike":
        third = duration / 3
        return [(third, max(1, rps // 5)), (third, rps * 2), (third, max(1, rps // 5))]
    return [(20, 2), (60, 8), (40, 25), (30, 8), (30, 2)]   # demo, 180 s


def main():
    ap = argparse.ArgumentParser(description="Generate API traffic")
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--profile", choices=["demo", "steady", "spike"], default="demo")
    ap.add_argument("--rps", type=int, default=10, help="target requests/second (steady, spike)")
    ap.add_argument("--duration", type=int, default=60, help="seconds (steady, spike)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--invalid-ratio", type=float, default=0.08)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    patients = load_patients() or [random_patient(rng) for _ in range(100)]
    base = args.url.rstrip("/")
    codes, latencies, lock = Counter(), [], threading.Lock()

    def one_request():
        r = rng.random()
        if r < args.invalid_ratio:
            status, ms = call(f"{base}/predict", bad_payload(rng))
        elif r < args.invalid_ratio + 0.02:
            status, ms = call(f"{base}/does-not-exist")
        elif r < args.invalid_ratio + 0.05:
            status, ms = call(f"{base}/health")
        else:
            status, ms = call(f"{base}/predict", rng.choice(patients))
        with lock:
            codes[status] += 1
            latencies.append(ms)

    print(f"Traffic -> {base}  profile={args.profile}")
    sem = threading.Semaphore(args.workers)
    threads, t0 = [], time.time()
    for seconds, target in schedule(args.profile, args.rps, args.duration):
        print(f"  phase: {target:>3} req/s for {seconds:.0f}s   (elapsed {time.time() - t0:.0f}s)")
        end = time.time() + seconds
        while time.time() < end:
            tick = time.time()
            for _ in range(target):
                sem.acquire()
                t = threading.Thread(target=lambda: (one_request(), sem.release()), daemon=True)
                t.start()
                threads.append(t)
            time.sleep(max(0, 1 - (time.time() - tick)))
    for t in threads:
        t.join(timeout=15)

    n = len(latencies)
    if not n:
        raise SystemExit("No requests completed - is the API running?")
    lat = sorted(latencies)
    print("\n=== Summary ===")
    print(f"requests : {n}  in {time.time() - t0:.0f}s")
    print(f"status   : {dict(sorted(codes.items()))}   (0 = connection error)")
    print(f"latency  : p50={statistics.median(lat):.1f} ms  p95={lat[int(n * .95) - 1]:.1f} ms  max={lat[-1]:.1f} ms")
    raise SystemExit(0 if codes.get(0, 0) == 0 else 1)


if __name__ == "__main__":
    main()
