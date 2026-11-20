-- KEYS[1] = dedup key, KEYS[2] = stream; ARGV = field, value, field, value, ...
-- One script so the marker and the job are written together or not at all.
if redis.call('SET', KEYS[1], '1', 'NX') then
  redis.call('XADD', KEYS[2], '*', unpack(ARGV))
  return 1
end
return 0
