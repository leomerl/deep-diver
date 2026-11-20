import os

# The gateway is its own service: it reads its own environment, not app.config.
# Empty: no auth (local dev). The Anthropic SDK reads ANTHROPIC_API_KEY itself.
GATEWAY_KEY = os.getenv("GATEWAY_KEY", "")
