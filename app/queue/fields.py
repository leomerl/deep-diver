DEDUP_KEY_FIELD = "dedup_key"  # every job carries its own marker, so dead-lettering can free it without parsing
ORIGINAL_ID_FIELD = "original_id"  # on a dead-lettered entry: its id in the source stream
