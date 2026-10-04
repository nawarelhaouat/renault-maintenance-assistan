import math
import os
import random
from datetime import date, datetime, timedelta

import psycopg2
from psycopg2.extras import execute_values

rng = random.Random(7)
DSN = os.getenv("DATABASE_URL", "postgresql://gmao:gmao@localhost:5432/gmao")
START, END = date(2022, 1, 1), date(2026, 10, 1)

BASE = {"Robot": 0.0035, "Presse": 0.0045, "Visseuse": 0.0030, "Automate": 0.0028, "Robot peinture": 0.0050}
PM_DAYS = {"Robot": 90, "Presse": 60, "Visseuse": 30, "Automate": 180, "Robot peinture": 14}
COMPLIANCE = {1: 0.60, 2: 0.80, 3: 0.95}    # probabilité de faire la préventive à l'échéance
CAT_FAILURES = {
    "Robot": ["E101", "E102", "E202", "E401", "E501", "E601"],
    "Robot peinture": ["E101", "E102", "E202", "E301", "E402", "E501"],
    "Presse": ["E201", "E202", "E402", "E501", "E601"],
    "Visseuse": ["E302", "E402", "E501"],
    "Automate": ["E301", "E402", "E501"],
}
FAIL_PARTS = {"E101": ["RF-MOT-210"], "E102": ["RF-ENC-045"], "E201": ["RF-JNT-310", "RF-FIL-050"],
              "E202": ["RF-VAL-205"], "E301": ["RF-CAB-330"], "E302": [], "E401": ["RF-RED-120"],
              "E402": ["RF-SEN-077"], "E501": [], "E601": ["RF-GRS-010"]}
SPEC = {"E101": "Robotique", "E102": "Robotique", "E201": "Hydraulique", "E202": "Mécanique",
        "E301": "Automatisme", "E302": "Électrique", "E401": "Mécanique", "E402": "Électrique",
        "E501": "Électrique", "E601": "Mécanique"}
DOWNTIME = {1: (30, 150), 2: (60, 320), 3: (180, 600)}   # par sévérité du code
PM_PARTS = {"Robot": ["RF-GRS-010"], "Presse": ["RF-GRS-010", "RF-FIL-050"],
            "Robot peinture": ["RF-GRS-010"], "Visseuse": [], "Automate": []}
DESC = {
    "preventive": ["Maintenance préventive planifiée", "Graissage et contrôle périodique"],
    "inspection": ["Inspection visuelle et mesures", "Contrôle de sécurité"],
    "corrective": ["Dépannage suite à arrêt machine", "Remplacement de composant défaillant"],
}
LABOR_PER_MIN = 1.2

conn = psycopg2.connect(DSN)
cur = conn.cursor()
cur.execute("""SELECT m.machine_id, m.install_date, m.criticality, mm.category
               FROM machines m JOIN machine_models mm ON mm.model_id = m.model_id ORDER BY m.machine_id""")
machines = cur.fetchall()
cur.execute("SELECT code, severity FROM failure_codes")
sev = dict(cur.fetchall())
cur.execute("SELECT reference, part_id, unit_cost_mad FROM spare_parts")
parts = {r: (pid, float(c)) for r, pid, c in cur.fetchall()}
cur.execute("SELECT technician_id, specialty FROM technicians")
techs = cur.fetchall()

wos = []


def pick_tech(code):
    pool = [t for t, s in techs if s == SPEC.get(code)] or [t for t, _ in techs]
    return rng.choice(pool)


def add(mid, wo_type, code, d, downtime, refs):
    opened = datetime(d.year, d.month, d.day, rng.randint(6, 20), rng.choice([0, 15, 30, 45]))
    cost = 250 + LABOR_PER_MIN * downtime + sum(parts[r][1] for r in refs)
    wos.append({"mid": mid, "type": wo_type, "code": code, "desc": rng.choice(DESC[wo_type]),
                "opened": opened, "closed": opened + timedelta(minutes=downtime + 20),
                "tech": pick_tech(code), "downtime": downtime, "cost": round(cost, 2), "refs": refs})


for mid, install, crit, cat in machines:
    d = max(START, install)
    pm_days = PM_DAYS[cat]
    last_pm, next_pm = d, d + timedelta(pm_days)
    next_insp = d + timedelta(rng.randint(60, 150))
    last_fail, last_code = None, None
    while d < END:
        if d >= next_pm:
            if rng.random() > COMPLIANCE[crit]:
                next_pm = d + timedelta(rng.randint(10, 45))          # préventive reportée
            else:
                add(mid, "preventive", None, d, rng.randint(15, 90), list(PM_PARTS[cat]))
                last_pm, next_pm = d, d + timedelta(pm_days + rng.randint(-5, 5))
        elif d >= next_insp:
            add(mid, "inspection", None, d, rng.randint(10, 30), [])
            next_insp = d + timedelta(rng.randint(90, 180))

        wear = min((d - last_pm).days / pm_days, 2.5)                 # usure depuis la dernière préventive
        age = (d - install).days / 365.25
        shock = 1 + math.exp(-(d - last_fail).days / 10) if last_fail else 1   # pannes en cascade
        h = BASE[cat] * (1 + 0.12 * age) * (0.6 + 0.8 * wear) * shock
        if rng.random() < h:
            code = last_code if last_code and rng.random() < 0.3 else rng.choice(CAT_FAILURES[cat])
            lo, hi = DOWNTIME[sev[code]]
            refs = [r for r in FAIL_PARTS[code] if rng.random() < 0.85]
            add(mid, "corrective", code, d, rng.randint(lo, hi), refs)
            last_fail, last_code = d, code
            last_pm += (d - last_pm) // 3                              # la réparation réduit l'usure
        d += timedelta(days=1)

wos.sort(key=lambda w: w["opened"])
cur.execute("TRUNCATE work_order_parts, work_orders RESTART IDENTITY")
execute_values(cur, """INSERT INTO work_orders(wo_id, machine_id, wo_type, failure_code, description,
    opened_at, closed_at, technician_id, downtime_minutes, status, cost_mad) VALUES %s""",
               [(i, w["mid"], w["type"], w["code"], w["desc"], w["opened"], w["closed"], w["tech"],
                 w["downtime"], "closed", w["cost"]) for i, w in enumerate(wos, 1)])
wp = [(i, parts[r][0], 1) for i, w in enumerate(wos, 1) for r in w["refs"]]
if wp:
    execute_values(cur, "INSERT INTO work_order_parts(wo_id, part_id, quantity) VALUES %s", wp)
cur.execute("SELECT setval(pg_get_serial_sequence('work_orders','wo_id'), (SELECT MAX(wo_id) FROM work_orders))")
conn.commit()

cur.execute("""SELECT mm.category, COUNT(DISTINCT m.machine_id),
                      COUNT(*) FILTER (WHERE w.wo_type = 'corrective')
               FROM work_orders w JOIN machines m ON m.machine_id = w.machine_id
               JOIN machine_models mm ON mm.model_id = m.model_id GROUP BY 1 ORDER BY 1""")
print(f"OK : {len(wos)} ordres de travail")
for cat, n, c in cur.fetchall():
    print(f"  {cat:15s} {n:2d} machines · {c:4d} pannes · {c / n / 4.75:.1f} pannes/machine/an")