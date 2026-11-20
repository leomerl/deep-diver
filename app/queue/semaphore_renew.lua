-- KEYS[1] = semaphore key; ARGV[1] = token, ARGV[2] = lease in ms
-- Renews only a lease that hasn't run out: once it has, the slot may already belong to someone else.
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local expires = redis.call('ZSCORE', KEYS[1], ARGV[1])
if expires and tonumber(expires) > now then
  redis.call('ZADD', KEYS[1], 'XX', now + tonumber(ARGV[2]), ARGV[1])
  return 1
end
return 0
