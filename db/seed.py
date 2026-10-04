import os
import random
from datetime import date, datetime, timedelta

import psycopg2
from psycopg2.extras import execute_values

random.seed(42)
DSN = os.getenv("DATABASE_URL", "postgresql://gmao:gmao@localhost:5432/gmao")
conn = psycopg2.connect(DSN)
cur = conn.cursor()

LINES = [
    ("Ligne Emboutissage 1", "Emboutissage"), ("Ligne Emboutissage 2", "Emboutissage"),
    ("Ligne Ferrage 1", "Ferrage"), ("Ligne Ferrage 2", "Ferrage"),
    ("Ligne Peinture 1", "Peinture"), ("Ligne Montage 1", "Montage"),
    ("Ligne Montage 2", "Montage"),
]
MODELS = [
    ("KUKA", "KR 210 R2700", "Robot", "kuka_kr210.pdf"),
    ("FANUC", "R-2000iC/210F", "Robot", "fanuc_r2000ic.pdf"),
    ("ABB", "IRB 6700", "Robot", "abb_irb6700.pdf"),
    ("Schuler", "MSP 2000", "Presse", "schuler_msp2000.pdf"),
    ("Atlas Copco", "Tensor STR", "Visseuse", "atlas_tensor_str.pdf"),
    ("Siemens", "SIMATIC S7-1500", "Automate", "siemens_s7_1500.pdf"),
    ("Dürr", "EcoRP E043i", "Robot peinture", "durr_ecorp.pdf"),
]
PREFIX = {"Robot": "ROB", "Presse": "PRS", "Visseuse": "VIS",
          "Automate": "PLC", "Robot peinture": "RPT"}
FAILURES = [
    ("E101", "Surchauffe moteur axe", 2), ("E102", "Défaut codeur / encodeur", 2),
    ("E201", "Fuite hydraulique", 3), ("E202", "Pression pneumatique insuffisante", 1),
    ("E301", "Défaut de communication réseau (Profinet)", 2),
    ("E302", "Erreur de couple de serrage", 1), ("E401", "Usure réducteur", 3),
    ("E402", "Défaut capteur de proximité", 1), ("E501", "Arrêt d'urgence déclenché", 2),
    ("E601", "Défaut de graissage", 1),  
]
CAT_FAILURES = {
    "Robot": ["E101", "E102", "E202", "E401", "E501", "E601"],
    "Robot peinture": ["E101", "E102", "E202", "E301", "E402", "E501"],
    "Presse": ["E201", "E202", "E402", "E501", "E601"],
    "Visseuse": ["E302", "E402", "E501"],
    "Automate": ["E301", "E402", "E501"],
}
TECHS = [
    ("Youssef Benali", "Mécanique"), ("Karim El Idrissi", "Électrique"),
    ("Samir Ouazzani", "Automatisme"), ("Hamza Tazi", "Hydraulique"),
    ("Imane Chraibi", "Robotique"), ("Reda Fassi", "Mécanique"),
    ("Salma Berrada", "Automatisme"), ("Anas Alaoui", "Électrique"),
]
PARTS = [
    ("RF-MOT-210", "Moteur axe 3", 4, 18500), ("RF-ENC-045", "Codeur absolu", 10, 2300),
    ("RF-RED-120", "Réducteur axe 2", 3, 24000), ("RF-JNT-310", "Kit joints hydrauliques", 25, 450),
    ("RF-SEN-077", "Capteur inductif M18", 60, 120), ("RF-VAL-205", "Électrovanne 5/2", 15, 680),
    ("RF-CAB-330", "Câble Profinet", 30, 210), ("RF-GRS-010", "Cartouche de graisse", 100, 85),
    ("RF-FIL-050", "Filtre hydraulique", 20, 390), ("RF-BAT-002", "Batterie sauvegarde robot", 12, 520),
]
PLANS = {
    "Robot": [("Graissage des axes", 90), ("Contrôle des câbles et batteries", 180)],
    "Presse": [("Contrôle niveau et filtre hydraulique", 60), ("Inspection des glissières", 120)],
    "Visseuse": [("Étalonnage du couple", 30)],
    "Automate": [("Sauvegarde programme et test réseau", 180)],
    "Robot peinture": [("Nettoyage des atomiseurs", 14), ("Contrôle pompes de peinture", 90)],
}
DESC = {
    "preventive": ["Maintenance préventive planifiée", "Graissage et contrôle périodique"],
    "inspection": ["Inspection visuelle et mesures", "Contrôle de sécurité"],
    "predictive": ["Intervention suite à alerte vibration", "Remplacement anticipé d'un composant"],
    "corrective": ["Dépannage suite à arrêt machine", "Remplacement de composant défaillant"],
}

execute_values(cur, "INSERT INTO production_lines(name, workshop) VALUES %s RETURNING line_id", LINES)
line_ids = [r[0] for r in cur.fetchall()] if cur.description else []
cur.execute("SELECT line_id FROM production_lines ORDER BY line_id")
line_ids = [r[0] for r in cur.fetchall()]

execute_values(cur, "INSERT INTO machine_models(manufacturer, model_name, category, manual_file) VALUES %s", MODELS)
cur.execute("SELECT model_id, category FROM machine_models ORDER BY model_id")
models = cur.fetchall()

execute_values(cur, "INSERT INTO failure_codes(code, description, severity) VALUES %s", FAILURES)
execute_values(cur, "INSERT INTO technicians(full_name, specialty) VALUES %s", TECHS)
execute_values(cur, "INSERT INTO spare_parts(reference, name, stock_qty, unit_cost_mad) VALUES %s", PARTS)
cur.execute("SELECT technician_id FROM technicians")
tech_ids = [r[0] for r in cur.fetchall()]
cur.execute("SELECT part_id, unit_cost_mad FROM spare_parts")
parts = cur.fetchall()

plan_rows = [(mid, task, freq) for mid, cat in models for task, freq in PLANS[cat]]
execute_values(cur, "INSERT INTO maintenance_plans(model_id, task, frequency_days) VALUES %s", plan_rows)

# Machines
machines_rows, counters = [], {}
for _ in range(60):
    mid, cat = random.choice(models)
    pref = PREFIX[cat]
    counters[pref] = counters.get(pref, 0) + 1
    machines_rows.append((
        f"TNG-{pref}-{counters[pref]:04d}", f"SN{random.randint(10**7, 10**8 - 1)}",
        mid, random.choice(line_ids),
        date(2012, 1, 1) + timedelta(days=random.randint(0, 4500)),
        random.choices(["running", "maintenance", "stopped"], [85, 10, 5])[0],
        random.choice([1, 2, 3]),
    ))

execute_values(cur, """INSERT INTO machines(asset_tag, serial_number, model_id, line_id,
    install_date, status, criticality) VALUES %s""", machines_rows)
cur.execute("""SELECT m.machine_id, m.install_date, mm.category FROM machines m
               JOIN machine_models mm USING (model_id)""")
machines = cur.fetchall()

# Ordres de travail
NOW = datetime(2026, 10, 1)
START = datetime(2022, 1, 1)
wo_rows = []
for mid, inst, cat in machines:
    t0 = max(START, datetime.combine(inst, datetime.min.time()))
    span = (NOW - t0).days
    for _ in range(random.randint(8, 45)):
        wo_type = random.choices(["preventive", "corrective", "inspection", "predictive"],
                                 [45, 35, 12, 8])[0]
        opened = t0 + timedelta(days=random.randint(0, span), hours=random.randint(6, 20))
        corrective = wo_type == "corrective"
        downtime = random.randint(30, 480) if corrective else random.randint(10, 90)
        wo_rows.append((
            mid, wo_type, random.choice(CAT_FAILURES[cat]) if corrective else None,
            random.choice(DESC[wo_type]), opened, opened + timedelta(minutes=downtime + 20),
            random.choice(tech_ids), downtime, "closed", 0,
        ))
wo_rows.sort(key=lambda r: r[4])
execute_values(cur, """INSERT INTO work_orders(machine_id, wo_type, failure_code, description,
    opened_at, closed_at, technician_id, downtime_minutes, status, cost_mad)
    VALUES %s RETURNING wo_id, wo_type""", wo_rows)
wos = cur.fetchall()

# Pièces utilisées + coût
wop_rows = []
for wo_id, wo_type in wos:
    if wo_type in ("corrective", "predictive"):
        for pid, _ in random.sample(parts, random.randint(1, 3)):
            wop_rows.append((wo_id, pid, random.randint(1, 2)))
execute_values(cur, "INSERT INTO work_order_parts(wo_id, part_id, quantity) VALUES %s", wop_rows)
cur.execute("""UPDATE work_orders w SET cost_mad =
    COALESCE((SELECT SUM(p.unit_cost_mad * wp.quantity) FROM work_order_parts wp
              JOIN spare_parts p USING (part_id) WHERE wp.wo_id = w.wo_id), 0) + 300""")

conn.commit()
cur.close()
conn.close()
print(f"OK: {len(machines)} machines, {len(wos)} ordres de travail")