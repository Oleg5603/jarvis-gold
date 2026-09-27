-- Add this indicator once to the chart tagged WyckoffSber, then remove it.
Settings = {
    Name = "Wyckoff - clear Lua labels (one time)",
    chart_tag = "WyckoffSber",
    line = {
        {Name="Service line (hidden)", Color=RGB(255,255,255), Type=TYPE_LINE, Width=1}
    }
}

local cleared = false

function Init()
    return #Settings.line
end

function OnCalculate(index)
    if index == 1 and not cleared then
        DelAllLabels(Settings.chart_tag)
        cleared = true
        message("WyckoffSber: Lua labels cleared. Remove this one-time indicator.")
    end
    return nil
end
