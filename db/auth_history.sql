CREATE TABLE IF NOT EXISTS users (
    user_id        SERIAL PRIMARY KEY,
    username       VARCHAR(50) NOT NULL UNIQUE,
    full_name      VARCHAR(100) NOT NULL DEFAULT '',
    password_hash  TEXT NOT NULL,
    role           VARCHAR(20) NOT NULL CHECK (role IN ('operator', 'technician', 'manager', 'admin')),
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id  SERIAL PRIMARY KEY,
    user_id          INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title            VARCHAR(120) NOT NULL DEFAULT 'Nouvelle discussion',
    asset_tag        VARCHAR(30) REFERENCES machines(asset_tag) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    message_id       BIGSERIAL PRIMARY KEY,
    conversation_id  INT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    role             VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant')),
    content          TEXT NOT NULL,
    asset_tag        VARCHAR(30),
    meta             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, message_id);