-- KEYS[1] = semaphore key: a sorted set of holder token -> lease expiry (ms)
-- ARGV[1] = token, ARGV[2] = limit, ARGV[3] = lease in ms
-- One script, so "drop expired holders, count, take a slot" can't interleave with another worker.
-- The clock is Redis's own: workers' clocks can disagree, and a fast one would expire others' leases early.
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
if redis.call('ZCARD', KEYS[1]) < tonumber(ARGV[2]) then
  redis.call('ZADD', KEYS[1], now + tonumber(ARGV[3]), ARGV[1])
  return 1
end
return 0
