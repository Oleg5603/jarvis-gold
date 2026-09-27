-- Wyckoff Phases TrendUp v1.6
-- Оптимизировано: последние события кэшируются, история повторно не сканируется.
Settings = {
    Name = "Wyckoff - range or WAIT",
    range_bars = 30,
    range_min_bars = 18,
    range_max_bars = 160,
    max_calculation_bars = 1500,
    volume_bars = 20,
    volume_factor = 1.45,
    retest_bars = 16,
    retest_volume_ratio = 0.85,
    close_inside_ratio = 0.60,
    event_cooldown_bars = 18,
    structural_cooldown_bars = 30,
    structural_volume_factor = 1.80,
    phase_cooldown_bars = 7,
    chart_tag = "WyckoffSber",
    label_history_bars = 80,
    cleanup_bars = 600,
    label_font_height = 11,
    line = {
        {Name="ICE: нижняя граница диапазона", Color=RGB(70,130,210), Type=TYPE_LINE, Width=2},
        {Name="Creek: сопротивление / поддержка после SOS", Color=RGB(235,125,55), Type=TYPE_LINE, Width=2},
        {Name="Триггер: Spring / LPS", Color=RGB(20,185,155), Type=TYPE_DASH, Width=4},
        {Name="Резервный уровень 4", Color=RGB(180,180,180), Type=TYPE_DASH, Width=1},
        {Name="Резервный уровень 5", Color=RGB(180,180,180), Type=TYPE_DASH, Width=1},
        {Name="Резервный уровень 6", Color=RGB(180,180,180), Type=TYPE_DASH, Width=1},
        {Name="SC: кульминация продаж", Color=RGB(110,110,110), Type=TYPE_POINT, Width=6},
        {Name="AR: автоматическое ралли", Color=RGB(110,110,110), Type=TYPE_POINT, Width=6},
        {Name="ST: вторичный тест", Color=RGB(30,155,205), Type=TYPE_POINT, Width=6},
        {Name="Spring: прокол ICE и возврат", Color=RGB(0,220,110), Type=TYPE_TRIANGLE_UP, Width=8},
        {Name="LPS: тест после SOS", Color=RGB(0,220,110), Type=TYPE_TRIANGLE_UP, Width=8},
        {Name="UTAD / Upthrust: прокол Creek", Color=RGB(235,115,55), Type=TYPE_TRIANGLE_DOWN, Width=7},
        {Name="LPSY: тест после SOW", Color=RGB(205,45,55), Type=TYPE_TRIANGLE_DOWN, Width=7},
        {Name="SOS: сила вверх", Color=RGB(0,220,110), Type=TYPE_TRIANGLE_UP, Width=8},
        {Name="SOW: слабость вниз", Color=RGB(205,45,55), Type=TYPE_TRIANGLE_DOWN, Width=7},
        {Name="EXT вниз: объёмный экстремум без фазы", Color=RGB(105,105,105), Type=TYPE_TRIANGLE_UP, Width=3},
        {Name="EXT вверх: объёмный экстремум без фазы", Color=RGB(105,105,105), Type=TYPE_TRIANGLE_DOWN, Width=3},
        {Name="Фаза A: остановка движения", Color=RGB(235,180,30), Type=TYPE_POINT, Width=14},
        {Name="Фаза B: диапазон подтверждён", Color=RGB(70,130,210), Type=TYPE_POINT, Width=12},
        {Name="Фаза C: Spring / UT", Color=RGB(145,85,205), Type=TYPE_POINT, Width=12},
        {Name="Фаза D: сила после SOS", Color=RGB(80,90,155), Type=TYPE_POINT, Width=14},
        {Name="Фаза D: слабость после SOW", Color=RGB(145,85,150), Type=TYPE_POINT, Width=14},
        {Name="Фаза E: рост", Color=RGB(75,85,135), Type=TYPE_POINT, Width=15},
        {Name="Фаза E: снижение", Color=RGB(130,75,125), Type=TYPE_POINT, Width=15},
        {Name="LONG: latest confirmed event", Color=RGB(0,255,95), Type=TYPE_TRIANGLE_UP, Width=11},
        {Name="SHORT: latest confirmed event", Color=RGB(255,45,55), Type=TYPE_TRIANGLE_DOWN, Width=11}
    }
}

local indicator_line_count = #Settings.line

local state, last_event = {}, {}
local phase_state = {code="WAIT", direction="", index=0, range_low=nil, range_high=nil, range_started=0, a_low=nil, a_high=nil, c_used=false, st_shown=false, lps_shown=false, lpsy_shown=false}
local calculation_from, display_from = 1, 1
local label_keys = {}
local rendered_range_from = nil
local current_range_key = nil
local live_label_ids = {}
local last_struct_low, last_struct_high = nil, nil
local legacy_chart_tag = Settings.chart_tag

-- Labels are global by tag in QUIK. Keep each security and interval independent.
local function configure_chart_tag(index)
    local tag, source_key = "Wyckoff", nil
    if type(getDataSourceInfo) == "function" then
        local ok, source = pcall(getDataSourceInfo)
        if ok and type(source) == "table" then
            local class = source.class_code or source.CLASS_CODE
            local security = source.sec_code or source.SEC_CODE
            local interval = source.interval or source.INTERVAL
            local data_id = source.ds_id or source.DS_ID or source.data_source_id
            if class and class ~= "" and security and security ~= "" and interval then
                source_key = tostring(class) .. "_" .. tostring(security) .. "_" .. tostring(interval)
                if data_id and data_id ~= "" then source_key = source_key .. "_" .. tostring(data_id) end
            end
        end
    end
    -- Some QUIK builds expose datasource data only after chart startup.  This
    -- candle fingerprint prevents a shared fallback tag across different charts.
    if not source_key then
        local candle = type(T) == "function" and T(index or 1) or nil
        local date = candle and candle.year and (candle.year * 10000 + candle.month * 100 + candle.day) or 0
        local time = candle and ((candle.hour or 0) * 10000 + (candle.min or 0) * 100 + (candle.sec or 0)) or 0
        local price = type(C) == "function" and (C(index or 1) or 0) or 0
        source_key = tostring(date) .. "_" .. tostring(time) .. "_" .. tostring(price) .. "_" .. tostring(type(Size) == "function" and Size() or 0)
    end
    Settings.chart_tag = string.sub(string.gsub(tag .. "_" .. source_key, "[^%w_]", "_"), 1, 60)
end

local function new_phase_state()
    return {code="WAIT", direction="", index=0, range_low=nil, range_high=nil, range_started=0, a_low=nil, a_high=nil, c_used=false, st_shown=false, lps_shown=false, lpsy_shown=false}
end

local function empty_values()
    return nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil
end

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

local function latest_event(i, name)
    local event = last_event[name]
    if event and i - event.index <= Settings.retest_bars then return event end
    if event then last_event[name] = nil end
    return nil
end

local function remember_events(i, s)
    for name, enabled in pairs({sc=s.sc, spring=s.spring, ar=s.ar, st=s.st, sos=s.sos, sow=s.sow, lps=s.lps, lpsy=s.lpsy, upthrust=s.upthrust, ut=s.ut, ext_low=s.ext_low, ext_high=s.ext_high}) do
        if enabled then s.index = i; last_event[name] = s end
    end
end

local function active_level(i, name, field)
    local event = latest_event(i, name)
    return event and event[field] or nil
end

-- Only the currently active range is drawn. Completed ranges are erased so they
-- cannot be mistaken for a live support or resistance level.
local function clear_rendered_levels(last_bar)
    current_range_key = nil
end

local function label_parameters(i, text, y, alignment, r, g, b, hint)
    local t = T(i)
    if not t or not t.year or not t.month or not t.day then return nil end
    return {
        TEXT = text, HINT = hint or text, ALIGNMENT = alignment,
        YVALUE = y, DATE = t.year * 10000 + t.month * 100 + t.day,
        TIME = (t.hour or 0) * 10000 + (t.min or 0) * 100 + (t.sec or 0),
        R = r, G = g, B = b, TRANSPARENCY = 0, TRANSPARENT_BACKGROUND = 1,
        FONT_FACE_NAME = "Arial", FONT_HEIGHT = Settings.label_font_height
    }
end

local function sync_chart_label(slot, i, text, y, alignment, r, g, b, hint)
    if not Settings.chart_tag or Settings.chart_tag == "" or type(AddLabel) ~= "function" then return end
    local params = label_parameters(i, text, y, alignment, r, g, b, hint)
    if not params then return end
    local id = live_label_ids[slot]
    -- QUIK may update a label successfully but return nil. Calling AddLabel
    -- afterwards duplicated the same logical label on every recalculation.
    if id and type(SetLabelParams) == "function" then
        SetLabelParams(Settings.chart_tag, id, params)
        return
    end
    id = AddLabel(Settings.chart_tag, params)
    if id and id ~= -1 then live_label_ids[slot] = id end
end

local function drop_chart_label(slot)
    local id = live_label_ids[slot]
    if id and type(DelLabel) == "function" then DelLabel(Settings.chart_tag, id) end
    live_label_ids[slot] = nil
end

local function phase_label(phase, direction)
    if phase == "A" or phase == "B" then return phase end
    if phase == "C" then return direction == "up" and "C+" or "C-" end
    if phase == "D" then return direction == "up" and "D+" or "D-" end
    if phase == "E" then return direction == "up" and "E+" or "E-" end
    return "WAIT"
end
local function latest_range_event(names, start_index)
    local found_name, found_event = nil, nil
    for _, name in ipairs(names) do
        local event = last_event[name]
        if event and event.index >= start_index and (not found_event or event.index > found_event.index) then
            found_name, found_event = name, event
        end
    end
    return found_name, found_event
end

local function clear_live_levels(total)
    -- QUIK indicator bars are 1-based; index 0 aborts OnChangeSettings.
    local first, last = 1, math.max(1, total - 1)
    if type(SetRangeValue) == "function" then
        for line = 1, 6 do SetRangeValue(line, first, last, nil) end
        SetRangeValue(25, first, last, nil); SetRangeValue(26, first, last, nil)
    end
    -- QUIK may retain explicit SetValue points after SetRangeValue(nil).
    if type(SetValue) == "function" then
        local first = math.max(1, total - Settings.cleanup_bars)
        for point = first, total - 1 do
            for line = 1, 6 do SetValue(point, line, nil) end
            SetValue(point, 25, nil); SetValue(point, 26, nil)
        end
    end
end

local function render_trader_view(bar, phase, direction)
    local total = type(Size) == "function" and Size() or bar
    if bar < total - 1 then return nil, nil, nil end
    local locked = phase_state.range_low and phase_state.range_high and phase_state.range_started > 0
    local ice, creek, trigger = nil, nil, nil
    local trigger_name, trigger_event = nil, nil
    if locked then
        ice, creek = phase_state.range_low, phase_state.range_high
        if direction == "up" then
            trigger_name, trigger_event = latest_range_event({"lps", "spring", "sos"}, phase_state.range_started)
            trigger = trigger_event and trigger_event.event_low or nil
        elseif direction == "down" then
            trigger_name, trigger_event = latest_range_event({"lpsy", "upthrust", "sow"}, phase_state.range_started)
            trigger = trigger_event and trigger_event.event_high or nil
        end
        -- Current decision panel only: completed ranges are not live levels.
        local key = tostring(phase_state.range_started) .. ":" .. tostring(ice) .. ":" .. tostring(creek) .. ":" .. tostring(trigger) .. ":" .. tostring(total)
        if current_range_key ~= key and type(SetRangeValue) == "function" then
            clear_live_levels(total)
            local visible_bars = math.max(24, math.min(Settings.label_history_bars, 80))
            local first = math.max(1, total - visible_bars)
            SetRangeValue(1, first, total - 1, ice)
            SetRangeValue(2, first, total - 1, creek)
            if trigger then SetRangeValue(3, first, total - 1, trigger) end
            -- Also set every visible point explicitly: some QUIK builds do not
            -- repaint a range written only after the final OnCalculate call.
            if type(SetValue) == "function" then
                for point = first, total - 1 do
                    SetValue(point, 1, ice)
                    SetValue(point, 2, creek)
                    if trigger then SetValue(point, 3, trigger) end
                end
            end
            current_range_key = key
        end
    elseif current_range_key then
        clear_live_levels(total)
        current_range_key = nil
    end

    -- Put labels before the chart edge and at different bars so they never overlap.
    local label_anchor = math.max(4, bar - 2)
    if locked then
        sync_chart_label("ice", label_anchor - 2, "ICE", ice, "BOTTOM", 70, 130, 210, "ICE: invalidation level for a Long scenario")
        sync_chart_label("creek", label_anchor - 1, "CREEK", creek, "TOP", 235, 125, 55, C(bar) > creek and "Creek: support after breakout" or "Creek: resistance before breakout")
    else
        drop_chart_label("ice"); drop_chart_label("creek")
    end
    if trigger then
        local long_side = direction == "up"
        sync_chart_label("trigger", label_anchor, "TRIGGER: " .. (long_side and "LONG? " or "SHORT? ") .. string.upper(trigger_name), trigger, long_side and "TOP" or "BOTTOM", long_side and 20 or 205, long_side and 185 or 45, long_side and 155 or 55, "Candidate only after candle confirmation")
    else
        drop_chart_label("trigger")
    end
    -- Entry events alone use bright arrows and explicit labels; phases are dots.
    local entry_name, entry_event = nil, nil
    if locked and direction == "up" then
        entry_name, entry_event = latest_range_event({"lps", "spring", "sos"}, phase_state.range_started)
    elseif locked and direction == "down" then
        entry_name, entry_event = latest_range_event({"lpsy", "upthrust", "sow"}, phase_state.range_started)
    end
    -- Clear then draw one dedicated, high-contrast arrow at the latest confirmed event.
    if type(SetRangeValue) == "function" then SetRangeValue(25, 1, total - 1, nil); SetRangeValue(26, 1, total - 1, nil) end
    if entry_event then
        local e_atr = entry_event.atr or atr(entry_event.index, 14) or 0
        local is_long = direction == "up"
        local e_y = is_long and entry_event.event_low - e_atr * 0.48 or entry_event.event_high + e_atr * 0.48
        if type(SetValue) == "function" then SetValue(entry_event.index, is_long and 25 or 26, e_y) end
        sync_chart_label("entry", entry_event.index, (is_long and "LONG: " or "SHORT: ") .. string.upper(entry_name), e_y, is_long and "TOP" or "BOTTOM", is_long and 0 or 255, is_long and 255 or 45, is_long and 95 or 55, "Confirmed event marker, not an order")
    else
        drop_chart_label("entry")
    end
    if phase ~= "WAIT" then
        local text = "PHASE " .. phase_label(phase, direction)
        sync_chart_label("phase", phase_state.index, text, direction == "down" and H(phase_state.index) + atr(phase_state.index, 14) * 0.7 or L(phase_state.index) - atr(phase_state.index, 14) * 0.7, direction == "down" and "BOTTOM" or "TOP", 145, 85, 205, "Current Wyckoff phase")
    else
        drop_chart_label("phase")
    end
    -- A blank chart is not actionable.  Explain why there is no entry instead.
    local status, status_y, status_color = nil, nil, nil
    if not locked then
        status, status_y, status_color = "WAIT: range not confirmed", C(bar) + (atr(bar, 14) or 0) * 1.6, {150, 55, 55}
    elseif not trigger then
        status, status_y, status_color = "WAIT: no confirmed Trigger", math.max(C(bar), creek or C(bar)) + (atr(bar, 14) or 0) * 1.3, {150, 105, 25}
    elseif phase == "C" then
        status, status_y, status_color = "WATCH: confirmation", C(bar) + (atr(bar, 14) or 0) * 0.8, {125, 85, 175}
    elseif phase == "D" or phase == "E" then
        status, status_y, status_color = direction == "up" and "LONG: wait LPS hold" or "SHORT: wait LPSY hold", C(bar) + (atr(bar, 14) or 0) * 0.8, {20, 125, 85}
    end
    if status then
        sync_chart_label("status", math.max(2, bar - 5), status, status_y, "BOTTOM", status_color[1], status_color[2], status_color[3], "No order until the stated condition is met")
    else
        drop_chart_label("status")
    end
    return ice, creek, trigger
end
-- Оставляем первую точку события и не повторяем одинаковую метку рядом.
local function keep_new_events(i, s)
    for name, enabled in pairs({sc=s.sc, spring=s.spring, sos=s.sos, sow=s.sow, upthrust=s.upthrust, ut=s.ut, ar=s.ar, st=s.st, lps=s.lps, lpsy=s.lpsy, ext_low=s.ext_low, ext_high=s.ext_high}) do
        local previous = last_event[name]
        if enabled and previous and i - previous.index < Settings.event_cooldown_bars then s[name] = false end
    end
end

local function calculate(i)
    local rolling_low, rolling_high = range_bounds(i, math.max(12, Settings.range_bars))
    local low, high = rolling_low, rolling_high
    if phase_state.range_low and phase_state.range_high then
        low, high = phase_state.range_low, phase_state.range_high
    end
    local avg_volume, a = mean_volume(i - Settings.volume_bars, i - 1), atr(i, 14)
    if not low or not high or not avg_volume or not a then return nil end
    local pos = close_position(i)
    local high_volume = V(i) >= avg_volume * Settings.volume_factor
    local quiet = V(i) <= avg_volume * Settings.retest_volume_ratio
    local buffer = math.max(a * 0.08, (high - low) * 0.01)
    local ext_low = high_volume and L(i) < rolling_low - buffer
    local ext_high = high_volume and H(i) > rolling_high + buffer
    local spring = L(i) < low - buffer and C(i) > low and pos >= Settings.close_inside_ratio and high_volume
    local upthrust = H(i) > high + buffer and C(i) < high and pos <= 1 - Settings.close_inside_ratio and high_volume
    local sc = not spring and high_volume and C(i) < O(i) and pos <= 0.35 and L(i) <= rolling_low + buffer
    local ut = not upthrust and high_volume and C(i) > O(i) and pos >= 0.65 and H(i) >= rolling_high - buffer
    local previous_support = latest_event(i, "sc") or latest_event(i, "spring")
    local previous_resistance = latest_event(i, "ut") or latest_event(i, "upthrust")
    local ar = (previous_support and C(i) > O(i) and C(i) >= previous_support.event_close + a * 0.75)
        or (previous_resistance and C(i) < O(i) and C(i) <= previous_resistance.event_close - a * 0.75)
    local st = (previous_support and quiet and math.abs(L(i) - previous_support.event_low) <= a * 0.35)
        or (previous_resistance and quiet and math.abs(H(i) - previous_resistance.event_high) <= a * 0.35)
    local sos, sow = C(i) > high + buffer and C(i) > O(i) and high_volume, C(i) < low - buffer and C(i) < O(i) and high_volume
    -- Structural pivots are confirmed two candles later; they are visual arrows, not entry signals.
    local pivot, swing_low, swing_high = i - 2, false, false
    if valid(pivot - 2) and valid(pivot - 1) and valid(pivot) and valid(pivot + 1) and valid(pivot + 2) then
        local pivot_avg_volume = mean_volume(pivot - Settings.volume_bars, pivot - 1)
        local pivot_high_volume = pivot_avg_volume and V(pivot) >= pivot_avg_volume * Settings.structural_volume_factor
        swing_low = pivot_high_volume and L(pivot) < L(pivot - 1) and L(pivot) <= L(pivot - 2) and L(pivot) <= L(pivot + 1) and L(pivot) < L(pivot + 2)
        swing_high = pivot_high_volume and H(pivot) > H(pivot - 1) and H(pivot) >= H(pivot - 2) and H(pivot) >= H(pivot + 1) and H(pivot) > H(pivot + 2)
    end
    local prior_sos, prior_sow = latest_event(i, "sos"), latest_event(i, "sow")
    local lps = prior_sos and quiet and L(i) <= prior_sos.range_high + buffer and C(i) > prior_sos.range_high
    local lpsy = prior_sow and quiet and H(i) >= prior_sow.range_low - buffer and C(i) < prior_sow.range_low
    return {low=low, high=high, rolling_low=rolling_low, rolling_high=rolling_high, atr=a, range_low=low, range_high=high, spring=spring, upthrust=upthrust,
        sc=sc, ut=ut, ar=ar, st=st, sos=sos, sow=sow, lps=lps, lpsy=lpsy, ext_low=ext_low, ext_high=ext_high, swing_low=swing_low, swing_high=swing_high, swing_index=pivot,
        event_low=L(i), event_high=H(i), event_close=C(i)}
end

-- Фаза определяется только по уже закрытым свечам. Это разметка контекста,
-- а не прогноз и не команда совершать сделку.
local function update_phase(i, s)
    local before_code, before_direction = phase_state.code, phase_state.direction
    local function set_phase(code, direction)
        if phase_state.code == code and phase_state.direction == (direction or "") then return end
        if i - phase_state.index < Settings.phase_cooldown_bars then return end
        phase_state.code, phase_state.direction, phase_state.index = code, direction or "", i
    end
    local function start_a(direction)
        if i - phase_state.index < Settings.phase_cooldown_bars then return end
        clear_rendered_levels(i)
        phase_state.code, phase_state.direction, phase_state.index = "A", direction, i
        phase_state.range_low, phase_state.range_high, phase_state.range_started = nil, nil, 0
        phase_state.a_low, phase_state.a_high = s.event_low, s.event_high
        phase_state.c_used, phase_state.st_shown, phase_state.lps_shown, phase_state.lpsy_shown = false, false, false, false
    end
    local function start_b()
        if not s.rolling_low or not s.rolling_high then return end
        phase_state.code, phase_state.index = "B", i
        if phase_state.direction == "up" then
            phase_state.range_low = phase_state.a_low or s.rolling_low
            phase_state.range_high = s.ar and s.event_high or s.rolling_high
        else
            phase_state.range_low = s.ar and s.event_low or s.rolling_low
            phase_state.range_high = phase_state.a_high or s.rolling_high
        end
        phase_state.range_started, phase_state.c_used = i, false
        rendered_range_from = i
    end

    local stale = phase_state.range_started > 0 and i - phase_state.range_started >= Settings.range_max_bars
    local reverse_sc = phase_state.direction == "down" and s.sc
    local reverse_ut = phase_state.direction == "up" and s.ut
    if stale and s.sc then
        start_a("up")
    elseif stale and s.ut then
        start_a("down")
    elseif (phase_state.code == "D" or phase_state.code == "E") and reverse_sc then
        start_a("up")
    elseif (phase_state.code == "D" or phase_state.code == "E") and reverse_ut then
        start_a("down")
    elseif phase_state.code == "WAIT" and s.sc then
        start_a("up")
    elseif phase_state.code == "WAIT" and s.ut then
        start_a("down")
    elseif phase_state.code == "A" and ((s.ar or s.st) or i - phase_state.index >= Settings.retest_bars) then
        start_b()
    elseif phase_state.code == "B" and phase_state.range_low and not phase_state.c_used
        and i - phase_state.range_started >= Settings.range_min_bars and s.spring then
        set_phase("C", "up")
        phase_state.c_used = true
    elseif phase_state.code == "B" and phase_state.range_low and not phase_state.c_used
        and i - phase_state.range_started >= Settings.range_min_bars and s.upthrust then
        set_phase("C", "down")
        phase_state.c_used = true
    elseif (s.sos or s.lps) and phase_state.code == "C" and phase_state.direction == "up" then
        set_phase("D", "up")
    elseif (s.sow or s.lpsy) and phase_state.code == "C" and phase_state.direction == "down" then
        set_phase("D", "down")
    elseif phase_state.code == "D" and phase_state.direction == "up" and C(i) > s.high then
        set_phase("E", "up")
    elseif phase_state.code == "D" and phase_state.direction == "down" and C(i) < s.low then
        set_phase("E", "down")
    elseif phase_state.code == "C" and i - phase_state.index >= Settings.retest_bars then
        -- C failed to confirm D: the range is invalidated, never return C -> B.
        phase_state = new_phase_state()
        phase_state.index = i
    elseif stale then
        clear_rendered_levels(i)
        phase_state = new_phase_state()
        phase_state.index = i
    end
    return phase_state.code, phase_state.direction, before_code ~= phase_state.code or before_direction ~= phase_state.direction
end

function Init() return indicator_line_count end

function OnCalculate(index)
    local warmup = math.max(Settings.range_bars, Settings.volume_bars) + 3
    if index == 1 then
        -- Datasource details become reliable only when chart calculation starts.
        -- Each window has its own chart_tag, so only its own old labels are cleared.
        if Settings.chart_tag and Settings.chart_tag ~= "" and type(DelAllLabels) == "function" then DelAllLabels(Settings.chart_tag) end
        state, last_event, phase_state, current_range_key, live_label_ids, last_struct_low, last_struct_high = {}, {}, new_phase_state(), nil, {}, nil, nil
        local total = type(Size) == "function" and Size() or 1
        -- Clear previous visible output before rendering the current decision state.
        clear_live_levels(total)
        display_from = math.max(1, total - Settings.max_calculation_bars + 1)
        calculation_from = math.max(1, display_from - warmup)
    end
    if index < calculation_from or index <= warmup or not valid(index - 1) then return empty_values() end
    local bar, s = index - 1, calculate(index - 1)
    if not s then return empty_values() end
    keep_new_events(bar, s)
    state[bar] = s
    -- Draw confirmed structural arrows at the actual pivot candle.
    if type(SetValue) == "function" and s.swing_index and s.swing_index > 0 then
        -- One structural arrow of each direction per cooldown window: no micro-noise.
        if s.swing_low and (not last_struct_low or s.swing_index - last_struct_low >= Settings.structural_cooldown_bars) then
            SetValue(s.swing_index, 16, L(s.swing_index) - s.atr * 0.28)
            last_struct_low = s.swing_index
        end
        if s.swing_high and (not last_struct_high or s.swing_index - last_struct_high >= Settings.structural_cooldown_bars) then
            SetValue(s.swing_index, 17, H(s.swing_index) + s.atr * 0.28)
            last_struct_high = s.swing_index
        end
    end
    remember_events(bar, s)
    local phase, direction, changed = update_phase(bar, s)
    s.phase, s.direction = phase, direction
    local locked = phase_state.range_low and phase_state.range_high
    local ice, creek = locked and phase_state.range_low or nil, locked and phase_state.range_high or nil
    local spring_floor = locked and (active_level(bar, "spring", "event_low") or active_level(bar, "sc", "event_low")) or nil
    local ut_ceiling = locked and (active_level(bar, "upthrust", "event_high") or active_level(bar, "ut", "event_high")) or nil
    local sos_level = locked and active_level(bar, "sos", "range_high") or nil
    local sow_level = locked and active_level(bar, "sow", "range_low") or nil
    local sc_mark = s.sc and phase == "A" and L(bar) - s.atr * 0.22 or nil
    local ar_mark = s.ar and changed and phase == "B" and L(bar) - s.atr * 0.12 or nil
    local st_mark = s.st and phase == "B" and not phase_state.st_shown and L(bar) - s.atr * 0.07 or nil
    local spring_mark = s.spring and changed and phase == "C" and direction == "up" and L(bar) - s.atr * 0.25 or nil
    local lps_mark = s.lps and (phase == "D" or phase == "E") and direction == "up" and not phase_state.lps_shown and L(bar) - s.atr * 0.10 or nil
    local utad_mark = s.upthrust and changed and phase == "C" and direction == "down" and H(bar) + s.atr * 0.25 or nil
    local lpsy_mark = s.lpsy and (phase == "D" or phase == "E") and direction == "down" and not phase_state.lpsy_shown and H(bar) + s.atr * 0.10 or nil
    local sos_mark = s.sos and changed and phase == "D" and direction == "up" and L(bar) - s.atr * 0.15 or nil
    local sow_mark = s.sow and changed and phase == "D" and direction == "down" and H(bar) + s.atr * 0.15 or nil
    local ext_low_mark = nil -- structural arrows are rendered only by the filtered pivot path
    local ext_high_mark = nil -- structural arrows are rendered only by the filtered pivot path
    if st_mark then phase_state.st_shown = true end
    if lps_mark then phase_state.lps_shown = true end
    if lpsy_mark then phase_state.lpsy_shown = true end
    s.confirmed = {sc=sc_mark, ar=ar_mark, st=st_mark, spring=spring_mark, lps=lps_mark,
        utad=utad_mark, lpsy=lpsy_mark, sos=sos_mark, sow=sow_mark, ext_low=ext_low_mark, ext_high=ext_high_mark}
    local marker = changed and (direction == "down" and H(bar) + s.atr * 0.58 or L(bar) - s.atr * 0.58) or nil
    local phase_a = changed and phase == "A" and marker or nil
    local phase_b = changed and phase == "B" and marker or nil
    local phase_c = changed and phase == "C" and marker or nil
    local phase_d_up = changed and phase == "D" and direction == "up" and marker or nil
    local phase_d_down = changed and phase == "D" and direction == "down" and marker or nil
    local phase_e_up = changed and phase == "E" and direction == "up" and marker or nil
    local phase_e_down = changed and phase == "E" and direction == "down" and marker or nil
    local live_ice, live_creek, live_trigger = render_trader_view(bar, phase, direction)
    if index < display_from then return empty_values() end
    return live_ice, live_creek, live_trigger, nil, nil, nil,
        sc_mark, ar_mark, st_mark, spring_mark, lps_mark, utad_mark, lpsy_mark, sos_mark, sow_mark, ext_low_mark, ext_high_mark,
        phase_a, phase_b, phase_c, phase_d_up, phase_d_down, phase_e_up, phase_e_down
end

function ExplainSignal(index)
    local s = state[index - 1] or state[index]
    if not s then return "Недостаточно данных" end
    local items = {}
    local phase_names = {
        A="Фаза A: остановка предыдущего движения",
        B="Фаза B: диапазон — сделку не ищем",
        C="Фаза C: проверка границы (Spring / Upthrust)",
        D=s.direction == "up" and "Фаза D: подтверждение силы после SOS" or "Фаза D: подтверждение слабости после SOW",
        E=s.direction == "up" and "Фаза E: рост после SOS" or "Фаза E: снижение после SOW"
    }
    items[#items + 1] = phase_names[s.phase or "B"]
    local c = s.confirmed or {}
    if c.sc then items[#items + 1] = "SC: остановка падения" end
    if c.ar then items[#items + 1] = "AR: автоматическое ралли" end
    if c.st then items[#items + 1] = "ST: вторичный тест" end
    if c.spring then items[#items + 1] = "Spring: прокол ICE и возврат" end
    if c.sos then items[#items + 1] = "SOS: сила выше Creek" end
    if c.lps then items[#items + 1] = "LPS: тест после SOS" end
    if c.utad then items[#items + 1] = "UTAD: прокол Creek и возврат" end
    if c.sow then items[#items + 1] = "SOW: слабость ниже ICE" end
    if c.lpsy then items[#items + 1] = "LPSY: тест после SOW" end
    if c.ext_low then items[#items + 1] = "EXT вниз: объёмный экстремум без фазы" end
    if c.ext_high then items[#items + 1] = "EXT вверх: объёмный экстремум без фазы" end
    return table.concat(items, "; ")
end

function OnChangeSettings() state, last_event, phase_state, calculation_from, display_from, rendered_range_from = {}, {}, new_phase_state(), 1, 1, nil; return indicator_line_count end
