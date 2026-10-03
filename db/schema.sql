-- Lignes de production
CREATE TABLE production_lines (
    line_id   SERIAL PRIMARY KEY,
    name      VARCHAR(100) NOT NULL UNIQUE,
    workshop  VARCHAR(50)  NOT NULL  -- Emboutissage, Ferrage, Peinture, Montage
);

-- Modèles de machines (lien avec les manuels pour le RAG)
CREATE TABLE machine_models (
    model_id      SERIAL PRIMARY KEY,
    manufacturer  VARCHAR(100) NOT NULL,
    model_name    VARCHAR(100) NOT NULL,
    category      VARCHAR(50)  NOT NULL,
    manual_file   VARCHAR(255),
    UNIQUE (manufacturer, model_name)
);

-- Machines physiques (asset_tag = contenu du QR code / plaque)
CREATE TABLE machines (
    machine_id     SERIAL PRIMARY KEY,
    asset_tag      VARCHAR(30) NOT NULL UNIQUE,
    serial_number  VARCHAR(50) NOT NULL UNIQUE,
    model_id       INT NOT NULL REFERENCES machine_models(model_id),
    line_id        INT NOT NULL REFERENCES production_lines(line_id),
    install_date   DATE NOT NULL,
    status         VARCHAR(20) NOT NULL DEFAULT 'running'
                   CHECK (status IN ('running','stopped','maintenance','decommissioned')),
    criticality    SMALLINT NOT NULL CHECK (criticality BETWEEN 1 AND 3)
);

-- Codes de panne
CREATE TABLE failure_codes (
    code         VARCHAR(20) PRIMARY KEY,
    description  TEXT NOT NULL,
    severity     SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 3)
);

-- Techniciens
CREATE TABLE technicians (
    technician_id  SERIAL PRIMARY KEY,
    full_name      VARCHAR(100) NOT NULL,
    specialty      VARCHAR(50)  NOT NULL
);

-- Pièces de rechange
CREATE TABLE spare_parts (
    part_id        SERIAL PRIMARY KEY,
    reference      VARCHAR(50) NOT NULL UNIQUE,
    name           VARCHAR(150) NOT NULL,
    stock_qty      INT NOT NULL DEFAULT 0,
    unit_cost_mad  NUMERIC(10,2) NOT NULL
);

-- Plans de maintenance préventive (par modèle)
CREATE TABLE maintenance_plans (
    plan_id         SERIAL PRIMARY KEY,
    model_id        INT NOT NULL REFERENCES machine_models(model_id),
    task            TEXT NOT NULL,
    frequency_days  INT NOT NULL
);

-- Ordres de travail = interventions de maintenance
CREATE TABLE work_orders (
    wo_id             SERIAL PRIMARY KEY,
    machine_id        INT NOT NULL REFERENCES machines(machine_id),
    wo_type           VARCHAR(20) NOT NULL
                      CHECK (wo_type IN ('preventive','corrective','predictive','inspection')),
    failure_code      VARCHAR(20) REFERENCES failure_codes(code),
    description       TEXT NOT NULL,
    opened_at         TIMESTAMP NOT NULL,
    closed_at         TIMESTAMP,
    technician_id     INT REFERENCES technicians(technician_id),
    downtime_minutes  INT NOT NULL DEFAULT 0,
    status            VARCHAR(20) NOT NULL DEFAULT 'closed'
                      CHECK (status IN ('open','in_progress','closed')),
    cost_mad          NUMERIC(10,2) NOT NULL DEFAULT 0
);

CREATE TABLE work_order_parts (
    wo_id     INT NOT NULL REFERENCES work_orders(wo_id) ON DELETE CASCADE,
    part_id   INT NOT NULL REFERENCES spare_parts(part_id),
    quantity  INT NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (wo_id, part_id)
);

CREATE INDEX idx_wo_machine ON work_orders(machine_id, opened_at DESC);
CREATE INDEX idx_wo_type    ON work_orders(wo_type);
CREATE INDEX idx_machines_model ON machines(model_id);

-- Vue utilisée par l'agent : fiche complète d'une machine
CREATE VIEW machine_summary AS
SELECT
    m.machine_id,
    m.asset_tag,
    m.serial_number,
    mm.manufacturer,
    mm.model_name,
    mm.category,
    mm.manual_file,
    pl.name       AS line_name,
    pl.workshop,
    m.install_date,
    m.status,
    m.criticality,
    COUNT(w.wo_id)                                         AS total_interventions,
    COUNT(w.wo_id) FILTER (WHERE w.wo_type = 'preventive') AS preventive_count,
    COUNT(w.wo_id) FILTER (WHERE w.wo_type = 'corrective') AS corrective_count,
    MAX(w.opened_at)                                       AS last_intervention,
    COALESCE(SUM(w.downtime_minutes), 0)                   AS total_downtime_min,
    ROUND(AVG(w.downtime_minutes) FILTER (WHERE w.wo_type = 'corrective'), 1) AS mttr_min
FROM machines m
JOIN machine_models mm    ON mm.model_id = m.model_id
JOIN production_lines pl  ON pl.line_id = m.line_id
LEFT JOIN work_orders w   ON w.machine_id = m.machine_id
GROUP BY m.machine_id, mm.manufacturer, mm.model_name, mm.category,
         mm.manual_file, pl.name, pl.workshop;