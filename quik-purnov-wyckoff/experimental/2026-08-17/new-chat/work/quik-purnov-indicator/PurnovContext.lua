Settings = {
    Name = "Purnov Context Signals",
    period = 20,
    trend_period = 34,
    volume_factor = 1.35,
    wick_factor = 1.20,
    atr_buffer = 0.15,
    line = {
        {Name="Support", Color=RGB(58,123,213), Type=TYPE_LINE, Width=1},
        {Name="Resistance", Color=RGB(58,123,213), Type=TYPE_LINE, Width=1},
        {Name="BUY: Spring / JOC-BTC", Color=RGB(30,200,110), Type=TYPE_TRIANGLE_UP, Width=3},
        {Name="SELL: Upthrust / SOW-BTI", Color=RGB(235,70,70), Type=TYPE_TRIANGLE_DOWN, Width=3},
        {Name="Signal score (+buy/-sell)", Color=RGB(235,175,45), Type=TYPE_HISTOGRAM, Width=2}
    }
}

local cache = {}

local function valid(i)
    return i and i > 0 and C(i) ~= nil and H(i) ~= nil and L(i) ~= nil and V(i) ~= nil
end

local function mean(from_i, to_i, fn)
    local sum, count = 0, 0
    for i = from_i, to_i do
        if valid(i) then sum = sum + fn(i); count = count + 1 end
    end
    if count == 0 then return nil end
    return sum / count
end

local function bounds(i, period)
    local lo, hi = nil, nil
    for j = math.max(1, i-period), i-1 do
        if valid(j) then
            lo = lo and math.min(lo, L(j)) or L(j)
            hi = hi and math.max(hi, H(j)) or H(j)
        end
    end
    return lo, hi
end

local function atr(i, period)
    return mean(math.max(2, i-period+1), i, function(j)
        local previous = C(j-1) or C(j)
        return math.max(H(j)-L(j), math.abs(H(j)-previous), math.abs(L(j)-previous))
    end)
end

local function context(i, period)
    local recent = mean(math.max(1, i-period+1), i, C)
    local previous = mean(math.max(1, i-period*2+1), i-period, C)
    if not recent or not previous then return 0 end
    if recent > previous then return 1 end
    if recent < previous then return -1 end
    return 0
end

local function evaluate(i)
    local p = math.max(8, Settings.period)
    local support, resistance = bounds(i, p)
    local a = atr(i, 14)
    local avg_volume = mean(math.max(1, i-p), i-1, V)
    local avg_range = mean(math.max(1, i-p), i-1, function(j) return H(j)-L(j) end)
    if not support or not resistance or not a or not avg_volume or not avg_range then
        return support, resistance, nil, nil, 0
    end

    local range = math.max(H(i)-L(i), 0.0000001)
    local body = math.max(math.abs(C(i)-O(i)), range*0.10)
    local lower_wick, upper_wick = math.min(O(i),C(i))-L(i), H(i)-math.max(O(i),C(i))
    local volume_ok = V(i) >= avg_volume * Settings.volume_factor
    local wide = range >= avg_range * 1.15
    local trend = context(i, Settings.trend_period)
    local buy_score, sell_score = 0, 0

    local spring = L(i) < support and C(i) > support and lower_wick >= body * Settings.wick_factor
    local upthrust = H(i) > resistance and C(i) < resistance and upper_wick >= body * Settings.wick_factor
    local joc = C(i) > resistance + a*Settings.atr_buffer and C(i) > O(i) and wide
    local sow = C(i) < support - a*Settings.atr_buffer and C(i) < O(i) and wide

    if spring then buy_score = buy_score + 2 end
    if joc then buy_score = buy_score + 2 end
    if upthrust then sell_score = sell_score + 2 end
    if sow then sell_score = sell_score + 2 end
    if volume_ok then
        if spring or joc then buy_score = buy_score + 1 end
        if upthrust or sow then sell_score = sell_score + 1 end
    end
    if trend >= 0 and (spring or joc) then buy_score = buy_score + 1 end
    if trend <= 0 and (upthrust or sow) then sell_score = sell_score + 1 end

    local buy, sell, score = nil, nil, 0
    if buy_score >= 3 and buy_score > sell_score then buy = L(i)-a*0.25; score = buy_score end
    if sell_score >= 3 and sell_score > buy_score then sell = H(i)+a*0.25; score = -sell_score end
    cache[i] = {spring=spring, upthrust=upthrust, joc=joc, sow=sow, volume=volume_ok, trend=trend, score=score}
    return support, resistance, buy, sell, score
end

function Init()
    return #Settings.line
end

function OnCalculate(index)
    local min_bars = math.max(Settings.period*2, Settings.trend_period*2)
    if index == 1 then cache = {} end
    if index <= min_bars or not CandleExist(index-1) then return nil, nil, nil, nil, nil end
    -- Signal on index uses only the previous, already closed candle.
    local support, resistance, buy, sell, score = evaluate(index-1)
    cache[index] = cache[index-1]
    return support, resistance, buy, sell, score
end

function ExplainSignal(index)
    local s = cache[index]
    if not s or s.score == 0 then return "Нет подтвержденного сигнала" end
    local parts = {}
    if s.spring then parts[#parts+1] = "ложный пробой поддержки (Spring)" end
    if s.upthrust then parts[#parts+1] = "ложный пробой сопротивления (Upthrust)" end
    if s.joc then parts[#parts+1] = "выход выше уровня широким баром (JOC)" end
    if s.sow then parts[#parts+1] = "выход ниже уровня широким баром (SOW)" end
    if s.volume then parts[#parts+1] = "объем выше среднего" end
    parts[#parts+1] = s.trend > 0 and "контекст восходящий" or (s.trend < 0 and "контекст нисходящий" or "контекст боковой")
    return table.concat(parts, "; ")
end

function OnChangeSettings()
    cache = {}
    return #Settings.line
end
