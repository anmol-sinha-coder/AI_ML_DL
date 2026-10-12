"""Tiny load test: 300 requests, report the percentiles that matter."""
import time, statistics, requests
URL_SINGLE = "http://127.0.0.1:8000/predict"
URL_BATCH = "http://127.0.0.1:8000/predict-batch"

PAYLOAD_SINGLE = {"tenure_months": 24, "monthly_spend": 1500.0, "orders_per_month": 3, "support_tickets": 1,  "uses_discounts": 1, "app_sessions": 10}
PAYLOAD_BATCH = {"customers": [PAYLOAD_SINGLE] * 100}

# Warm-up request
requests.post(URL_SINGLE, json=PAYLOAD_SINGLE)

lat = []
for _ in range(300):
    t0 = time.perf_counter()
    r = requests.post(URL_SINGLE, json=PAYLOAD_SINGLE, timeout=5)
    r.raise_for_status()
    lat.append((time.perf_counter() - t0) * 1000)

lat.sort()
q = lambda p: lat[int(p / 100 * len(lat)) - 1]
print(f"n={len(lat)}  p50={q(50):.1f}ms  p95={q(95):.1f}ms  "
      f"p99={q(99):.1f}ms  max={max(lat):.1f}ms")

###############################################################
# Benchmark 300 Single Calls
t0 = time.perf_counter()
for _ in range(300):
    requests.post(URL_SINGLE, json=PAYLOAD_SINGLE).raise_for_status()
time_single = (time.perf_counter() - t0) * 1000

# Benchmark 3 Batch Calls (100 customers each = 300 total)
t0 = time.perf_counter()
for _ in range(3):
    requests.post(URL_BATCH, json=PAYLOAD_BATCH).raise_for_status()
time_batch = (time.perf_counter() - t0) * 1000

print(f"300 Single Requests Total Time : {time_single:.2f} ms")
print(f"  3 Batch Requests Total Time  : {time_batch:.2f} ms")
print(f"Speedup Factor                 : {time_single / time_batch:.1f}x")
