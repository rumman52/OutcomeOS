-- outcomeos:up
CREATE TABLE schema_contract (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
-- outcomeos:down
DROP TABLE schema_contract;
