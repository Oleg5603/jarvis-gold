Settings = {
    Name = "Wyckoff Phases TrendUp v1.0",
    range_bars = 30,
    volume_bars = 20,
    volume_factor = 1.30,
    retest_bars = 12,
    retest_volume_ratio = 0.85,
    close_inside_ratio = 0.60,
    line = {
        {Name="Range low", Color=RGB(65,125,205), Type=TYPE_LINE, Width=1},
        {Name="Range high", Color=RGB(65,125,205), Type=TYPE_LINE, Width=1},
        {Name="Spring", Color=RGB(25,190,95), Type=TYPE_TRIANGLE_UP, Width=4},
        {Name="Upthrust", Color=RGB(230,65,65), Type=TYPE_TRIANGLE_DOWN, Width=4},
        {Name="SOS / JOC", Color=RGB(20,150,80), Type=TYPE_TRIANGLE_UP, Width=3},
        {Name="SOW", Color=RGB(205,40,55), Type=TYPE_TRIANGLE_DOWN, Width=3},
        {Name="LPS", Color=RGB(110,200,145), Type=TYPE_POINT, Width=4},
        {Name="LPSY / BUI", Color=RGB(245,145,105), Type=TYPE_POINT, Width=4}
    }
}

local state = {}

local function valid(i)
    return i and i > 0 and CandleExist(i) and O(i) and H(i) and L(i) and C(i) and V(i)
end

local function mean_volume(first, last)
    local sum, count = 0, 0
    for j = math.max(1, first), last do
        if valid(j) then sum = sum + V(j); count = count + 1 end
    end
    return count > 0 and sum / count or nil
end

local function range_bounds(i, bars)
    local low, high = nil, nil
    for j = math.max(1, i - bars), i - 1 do
        if valid(j) then
            low = low and math.min(low, L(j)) or L(j)
            high = high and math.max(high, H(j)) or H(j)
        end
    end
    return low, high
end

local function atr(i, bars)
    local sum, count = 0, 0
    for j = math.max(2, i - bars + 1), i do
        if valid(j) and C(j - 1) then
            local tr = math.max(H(j) - L(j), math.abs(H(j) - C(j - 1)), math.abs(L(j) - C(j - 1)))
            sum = sum + tr; count = count + 1
        end
    end
    return count > 0 and sum / count or nil
end

local function close_position(i)
    local size = math.max(H(i) - L(i), 0.00000001)
    return (C(i) - L(i)) / size
end

local function recent_breakout(i, side)
    for j = i - 1, math.max(1, i - Settings.retest_bars) , -1 do
        local s = state[j]
        if s and s.breakout_side == side then return s end
    end
    return nil
end

local function calculate(i)
    local low, high = range_bounds(i, math.max(12, Settings.range_bars))
    local avg_volume = mean_volume(i - Settings.volume_bars, i - 1)
    local a = atr(i, 14)
    if not low or not high or not avg_volume or not a then return nil end

    local pos = close_position(i)
    local high_volume = V(i) >= avg_volume * Settings.volume_factor
    local buffer = math.max(a * 0.08, (high - low) * 0.01)
    local spring = L(i) < low - buffer and C(i) > low and pos >= Settings.close_inside_ratio and high_volume
    local upthrust = H(i) > high + buffer and C(i) < high and pos <= 1 - Settings.close_inside_ratio and high_volume
    local sos = C(i) > high + buffer and C(i) > O(i) and high_volume
    local sow = C(i) < low - buffer and C(i) < O(i) and high_volume
    local prior_long = recent_breakout(i, 1)
    local prior_short = recent_breakout(i, -1)
    local quiet = V(i) <= avg_volume * Settings.retest_volume_ratio
    local lps = prior_long and L(i) <= prior_long.range_high + buffer and C(i) > prior_long.range_high and quiet
    local lpsy = prior_short and H(i) >= prior_short.range_low - buffer and C(i) < prior_short.range_low and quiet
    return {
        low = low, high = high, atr = a, spring = spring, upthrust = upthrust,
        sos = sos, sow = sow, lps = lps, lpsy = lpsy,
        breakout_side = sos and 1 or (sow and -1 or nil), range_low = low, range_high = high
    }
end

function Init()
    return #Settings.line
end

function OnCalculate(index)
    if index == 1 then state = {} end
    local warmup = math.max(Settings.range_bars, Settings.volume_bars) + 3
    if index <= warmup or not valid(index - 1) then return nil,nil,nil,nil,nil,nil,nil,nil end
    local s = calculate(index - 1)
    if not s then return nil,nil,nil,nil,nil,nil,nil,nil end
    state[index - 1] = s
    local spring = s.spring and L(index - 1) - s.atr * 0.20 or nil
    local upthrust = s.upthrust and H(index - 1) + s.atr * 0.20 or nil
    local sos = s.sos and L(index - 1) - s.atr * 0.10 or nil
    local sow = s.sow and H(index - 1) + s.atr * 0.10 or nil
    local lps = s.lps and L(index - 1) - s.atr * 0.08 or nil
    local lpsy = s.lpsy and H(index - 1) + s.atr * 0.08 or nil
    return s.low, s.high, spring, upthrust, sos, sow, lps, lpsy
end

function ExplainSignal(index)
    local s = state[index - 1] or state[index]
    if not s then return "Недостаточно данных для диапазона" end
    local items = {}
    if s.spring then items[#items + 1] = "Spring: прокол вниз и возврат в диапазон" end
    if s.upthrust then items[#items + 1] = "Upthrust: прокол вверх и возврат в диапазон" end
    if s.sos then items[#items + 1] = "SOS/JOC: пробой верхней границы на объёме" end
    if s.sow then items[#items + 1] = "SOW: пробой нижней границы на объёме" end
    if s.lps then items[#items + 1] = "LPS: тихий тест после SOS/JOC" end
    if s.lpsy then items[#items + 1] = "LPSY/BUI: тихий тест после SOW" end
    if #items == 0 then return "Диапазон B: подтверждённого события нет" end
    return table.concat(items, "; ")
end

function OnChangeSettings()
    state = {}
    return #Settings.line
end
