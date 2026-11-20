-- KEYS[1] = stream; ARGV[1] = group, ARGV[2] = consumer, ARGV[3] = entry id
-- Renews only while this consumer still owns the entry: once the reaper has handed it to another worker,
-- a plain XCLAIM would steal it back.
local pending = redis.call('XPENDING', KEYS[1], ARGV[1], ARGV[3], ARGV[3], 1)
if pending[1] and pending[1][2] == ARGV[2] then
  -- min-idle 0 + JUSTID: resets the idle time without bumping the delivery count
  redis.call('XCLAIM', KEYS[1], ARGV[1], ARGV[2], 0, ARGV[3], 'JUSTID')
  return 1
end
return 0
