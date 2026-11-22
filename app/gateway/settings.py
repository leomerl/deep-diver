import os

# The gateway is its own service: it reads its own environment, not app.config.
# Empty: no auth (local dev). The Anthropic SDK reads ANTHROPIC_API_KEY itself.
GATEWAY_KEY = os.getenv("GATEWAY_KEY", "")
# Where each paid call is recorded (the llm_calls table, migrated by the app's Alembic).
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://dd:dd@localhost:5432/dd")
