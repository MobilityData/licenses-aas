-- Unified license table
CREATE TABLE licenses (
    id UUID PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('standard', 'custom')),
    spdx_id TEXT UNIQUE, -- for standard
    code TEXT UNIQUE, -- for custom
    name TEXT NOT NULL,
    url TEXT,
    summary TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Custom building blocks
CREATE TABLE permissions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE conditions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE limitations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

-- Join tables for rule composition
CREATE TABLE license_permissions (
    license_id UUID REFERENCES licenses(id) ON DELETE CASCADE,
    permission_id TEXT REFERENCES permissions(id),
    PRIMARY KEY (license_id, permission_id)
);

CREATE TABLE license_conditions (
    license_id UUID REFERENCES licenses(id) ON DELETE CASCADE,
    condition_id TEXT REFERENCES conditions(id),
    PRIMARY KEY (license_id, condition_id)
);

CREATE TABLE license_limitations (
    license_id UUID REFERENCES licenses(id) ON DELETE CASCADE,
    limitation_id TEXT REFERENCES limitations(id),
    PRIMARY KEY (license_id, limitation_id)
);