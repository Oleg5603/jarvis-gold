Settings = {
    Name = "Purnov Effort-Result Context v2.0",
    period = 20,
    trend_period = 34,
    volume_factor = 1.35,
    result_min = 0.55,
    close_location = 0.65,
    activity_lookback = 8,
    wick_factor = 1.20,
    atr_buffer = 0.15,
    min_score = 3,
    line = {
        {Name="Support", Color=RGB(58,123,213), Type=TYPE_LINE, Width=1},
        {Name="Resistance", Color=RGB(58,123,213), Type=TYPE_LINE, Width=1},
        {Name="BUY: Spring / JOC", Color=RGB(30,200,110), Type=TYPE_TRIANGLE_UP, Width=3},
        {Name="SELL: Upthrust / SOW", Color=RGB(235,70,70), Type=TYPE_TRIANGLE_DOWN, Width=3}
    }
}

local cache = {}

local function valid(i)
    return i and i > 0 and CandleExist(i) and O(i) ~= nil and C(i) ~= nil
        and H(i) ~= nil and L(i) ~= nil and V(i) ~= nil
end

local function mean(from_i, to_i, fn)
    local sum, count = 0, 0
    for i = from_i, to_i do
        if valid(i) then
            local value = fn(i)
            if value ~= nil then sum = sum + value; count = count + 1 end
        end
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

local function prior_activity(i, direction, lookback, avg_volume)
    local from_i = math.max(1, i-lookback)
    for j = from_i, i-1 do
        if valid(j) and V(j) >= avg_volume then
            if direction > 0 and C(j) > O(j) then return true end
            if direction < 0 and C(j) < O(j) then return true end
        end
    end
    return false
end

local function evaluate(i)
    local p = math.max(8, Settings.period)
    local support, resistance = bounds(i, p)
    local a = atr(i, 14)
    local avg_volume = mean(math.max(1, i-p), i-1, V)
    local avg_range = mean(math.max(1, i-p), i-1, function(j) return H(j)-L(j) end)
    if not support or not resistance or not a or not avg_volume or not avg_range then
        return support, resistance, nil, nil
    end

    local bar_range = math.max(H(i)-L(i), 0.0000001)
    local body = math.max(math.abs(C(i)-O(i)), bar_range*0.10)
    local lower_wick = math.min(O(i),C(i))-L(i)
    local upper_wick = H(i)-math.max(O(i),C(i))
    local volume_ok = avg_volume > 0 and V(i) >= avg_volume * Settings.volume_factor
    local wide = avg_range > 0 and bar_range >= avg_range * 1.15
    local volume_ratio = avg_volume > 0 and V(i)/avg_volume or 0
    local progress_ratio = avg_range > 0 and math.abs(C(i)-C(i-1))/avg_range or 0
    local close_position = (C(i)-L(i))/bar_range
    local buy_result = progress_ratio >= Settings.result_min
        and close_position >= Settings.close_location
    local sell_result = progress_ratio >= Settings.result_min
        and close_position <= 1-Settings.close_location
    local buy_activity = prior_activity(i, 1, Settings.activity_lookback, avg_volume)
    local sell_activity = prior_activity(i, -1, Settings.activity_lookback, avg_volume)
    local trend = context(i, Settings.trend_period)
    local buy_score, sell_score = 0, 0

    local spring = L(i) < support and C(i) > support and lower_wick >= body * Settings.wick_factor
    local upthrust = H(i) > resistance and C(i) < resistance and upper_wick >= body * Settings.wick_factor
    local joc = C(i) > resistance + a*Settings.atr_buffer and C(i) > O(i) and wide
    local sow = C(i) < support - a*Settings.atr_buffer and C(i) < O(i) and wide

    if spring and sell_activity then buy_score = buy_score + 2 end
    if joc and buy_activity then buy_score = buy_score + 2 end
    if upthrust and buy_activity then sell_score = sell_score + 2 end
    if sow and sell_activity then sell_score = sell_score + 2 end
    if volume_ok then
        if spring or joc then buy_score = buy_score + 1 end
        if upthrust or sow then sell_score = sell_score + 1 end
    end
    if trend >= 0 and (spring or joc) then buy_score = buy_score + 1 end
    if trend <= 0 and (upthrust or sow) then sell_score = sell_score + 1 end
    -- Большое усилие без результата не подтверждает продолжение движения.
    if volume_ok and buy_result and (spring or joc) then buy_score = buy_score + 1 end
    if volume_ok and sell_result and (upthrust or sow) then sell_score = sell_score + 1 end
    if volume_ratio >= Settings.volume_factor and not buy_result then buy_score = 0 end
    if volume_ratio >= Settings.volume_factor and not sell_result then sell_score = 0 end

    local buy, sell, score = nil, nil, 0
    if buy_score >= Settings.min_score and buy_score > sell_score then
        buy = L(i)-a*0.25; score = buy_score
    end
    if sell_score >= Settings.min_score and sell_score > buy_score then
        sell = H(i)+a*0.25; score = -sell_score
    end
    cache[i] = {spring=spring, upthrust=upthrust, joc=joc, sow=sow,
        volume=volume_ok, trend=trend, score=score, volume_ratio=volume_ratio,
        progress_ratio=progress_ratio, buy_result=buy_result,
        sell_result=sell_result, buy_activity=buy_activity,
        sell_activity=sell_activity}
    return support, resistance, buy, sell
end

function Init()
    return #Settings.line
end

function OnCalculate(index)
    local min_bars = math.max(Settings.period*2, Settings.trend_period*2)
    if index == 1 then cache = {} end
    if index <= min_bars or not CandleExist(index-1) then
        return nil, nil, nil, nil
    end
    -- Расчёт текущей точки использует только предыдущий закрытый бар.
    return evaluate(index-1)
end

function ExplainSignal(index)
    local s = cache[index-1]
    if not s or s.score == 0 then return "Нет подтвержденного сигнала" end
    local parts = {}
    if s.spring then parts[#parts+1] = "Spring" end
    if s.upthrust then parts[#parts+1] = "Upthrust" end
    if s.joc then parts[#parts+1] = "JOC" end
    if s.sow then parts[#parts+1] = "SOW" end
    if s.volume then parts[#parts+1] = "объем выше среднего" end
    parts[#parts+1] = "усилие=" .. string.format("%.2f", s.volume_ratio)
    parts[#parts+1] = "результат=" .. string.format("%.2f", s.progress_ratio)
    parts[#parts+1] = s.trend > 0 and "контекст вверх"
        or (s.trend < 0 and "контекст вниз" or "боковой контекст")
    return table.concat(parts, "; ") .. "; score=" .. tostring(math.abs(s.score))
end

function OnChangeSettings()
    cache = {}
    return #Settings.line
end
