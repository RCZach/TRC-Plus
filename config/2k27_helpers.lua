-- NBA 2K27 roster helpers for Cheat Engine
-- Load: Table -> Show Cheat Table Lua Script -> paste -> Execute (attach to NBA2K27.exe first)

TWOK = {
  BASE_PTR    = 'NBA2K27.exe+ABEBDA0', -- pointer to start of player array (survives restarts)
  SIZE        = 0x4F8,                 -- bytes per player record
  OFF_LAST    = 0x00,                  -- UTF-16, 20 chars
  OFF_FIRST   = 0x28,                  -- UTF-16, 24 chars
  MAX_PLAYERS = 6000,
  ATTR = { DrivingLayup = 0x43C },     -- full list in offsets_2k27.json
}

-- returns recordAddress, index
function rec2K(first, last)
  local base = readQword(getAddress('NBA2K27.exe') + 0xABEBDA0)
  for i = 0, TWOK.MAX_PLAYERS - 1 do
    local r = base + i * TWOK.SIZE
    local ln = readString(r + TWOK.OFF_LAST, 20, true)
    if ln == nil or ln == '' then break end
    if ln:lower() == last:lower() and (readString(r + TWOK.OFF_FIRST, 24, true) or ''):lower() == first:lower() then
      return r, i
    end
  end
end

-- ratings are stored as (rating - 25) * 3
function get2KRating(first, last, attr)
  local rec = rec2K(first, last)
  if not rec then return nil, 'not found' end
  return readBytes(rec + TWOK.ATTR[attr], 1) // 3 + 25
end

function set2KRating(first, last, attr, rating)
  local rec = rec2K(first, last)
  if not rec then return nil, 'not found' end
  rating = math.max(25, math.min(99, math.floor(rating)))
  writeBytes(rec + TWOK.ATTR[attr], (rating - 25) * 3)
  return rating
end

-- adds a pointer-based entry to the cheat table
function add2KPlayer(first, last, attr)
  attr = attr or 'DrivingLayup'
  local rec, i = rec2K(first, last)
  if not rec then return nil, 'not found' end
  local mr = getAddressList().createMemoryRecord()
  mr.Description = string.format('%s %s - %s (#%d)', first, last, attr, i)
  mr.Address = string.format('[%s]+%X', TWOK.BASE_PTR, i * TWOK.SIZE + TWOK.ATTR[attr])
  if getCustomType and getCustomType('2K Rating') then
    mr.Type = vtCustom
    mr.CustomTypeName = '2K Rating'
  else
    mr.Type = vtByte
  end
  return i
end

-- custom type so table entries show / accept real ratings
registerCustomTypeLua('2K Rating', 1,
  function(b) return math.floor(b / 3) + 25 end,
  function(v)
    v = math.max(25, math.min(99, math.floor(v)))
    return (v - 25) * 3
  end,
  false)

---------------------------------------------------------------------------
-- Offset-mapping tools (snapshot a record, edit in game, diff)
---------------------------------------------------------------------------
local function get(bytes, pos, len)
  local o, sb = pos // 8, pos % 8
  local v = 0
  for j = 3, 0, -1 do v = (v << 8) | (bytes[o + 1 + j] or 0) end
  return (v >> sb) & ((1 << len) - 1)
end

function snap2K(first, last)
  SNAP_REC, SNAP_IDX = rec2K(first, last)
  SNAP = readBytes(SNAP_REC, TWOK.SIZE, true)
  return SNAP_REC, SNAP_IDX
end

-- before/after bits of every changed byte.
-- 0xE8-0xEF looks like a per-edit hash; 0x1AA-0x1BA a recalculated cache.
function diffRaw()
  local now = readBytes(SNAP_REC, TWOK.SIZE, true)
  local function b(x) local s = '' for i = 7, 0, -1 do s = s .. ((x >> i) & 1) end return s end
  local out = {}
  for o = 0x50, TWOK.SIZE - 1 do
    if SNAP[o + 1] ~= now[o + 1] then
      local tag = ((o >= 0xE8 and o <= 0xEF) or (o >= 0x1AA and o <= 0x1BA)) and '  (hash/cache?)' or ''
      out[#out + 1] = string.format('0x%X  before %s  now %s%s', o, b(SNAP[o + 1]), b(now[o + 1]), tag)
    end
  end
  return #out > 0 and table.concat(out, '\n') or 'no change'
end

-- windows of `width` bits that now hold one of `targets` (used for tendencies / badges)
function diff2K(targets, width)
  width = width or 7
  local now = readBytes(SNAP_REC, TWOK.SIZE, true)
  local changed = {}
  for k = 1, TWOK.SIZE do
    local x = SNAP[k] ~ now[k]
    for bit = 0, 7 do if (x >> bit) & 1 == 1 then changed[#changed + 1] = (k - 1) * 8 + bit end end
  end
  local out = {}
  for _, t in ipairs(targets or {}) do
    local hits, seen = {}, {}
    for _, bit in ipairs(changed) do
      for st = bit - width + 1, bit do
        if st >= 0 and not seen[st] and get(now, st, width) == t and get(SNAP, st, width) ~= t then
          seen[st] = true
          hits[#hits + 1] = string.format('0x%X bit %d', st // 8, st % 8)
        end
      end
    end
    out[#out + 1] = string.format('value %d -> %s', t, table.concat(hits, ', '))
  end
  return table.concat(out, '\n')
end
