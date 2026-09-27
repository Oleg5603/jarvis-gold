Settings = {
    Name="Purnov Context Signals v2", period=30, trend_period=34,
    volume_factor=1.25, zone_atr=0.30, setup_bars=8,
    weakening_bars=6, weakening_progress=0.35, min_rr=3.0,
    line={
        {Name="Support", Color=RGB(65,125,205), Type=TYPE_LINE, Width=1},
        {Name="Resistance", Color=RGB(65,125,205), Type=TYPE_LINE, Width=1},
        {Name="BUY ready", Color=RGB(110,190,145), Type=TYPE_POINT, Width=3},
        {Name="BUY confirmed", Color=RGB(20,200,95), Type=TYPE_TRIANGLE_UP, Width=4},
        {Name="SELL ready", Color=RGB(225,145,145), Type=TYPE_POINT, Width=3},
        {Name="SELL confirmed", Color=RGB(235,55,55), Type=TYPE_TRIANGLE_DOWN, Width=4},
        {Name="Stage (-2..2)", Color=RGB(235,175,45), Type=TYPE_HISTOGRAM, Width=2},
        {Name="Risk/reward", Color=RGB(145,95,210), Type=TYPE_HISTOGRAM, Width=1}
    }
}

-- Cache API reads only within one calculation; history corrections remain visible.
local sourceO, sourceH, sourceL, sourceC, sourceV, sourceExists = O,H,L,C,V,CandleExist
local reads
local function memo(source)
    return function(i)
        local values = reads[source]
        if not values then values = {}; reads[source] = values end
        local item = values[i]
        if item == nil then item = {source(i)}; values[i] = item end
        return item[1]
    end
end
local O,H,L,C,V,CandleExist = memo(sourceO),memo(sourceH),memo(sourceL),
    memo(sourceC),memo(sourceV),memo(sourceExists)

local cache={}

local function valid(i)
    return i and i>0 and CandleExist(i) and O(i)~=nil and C(i)~=nil
        and H(i)~=nil and L(i)~=nil and V(i)~=nil
end

local function mean(first,last,fn)
    local sum,n=0,0
    for i=math.max(1,first),last do
        if valid(i) then sum=sum+fn(i); n=n+1 end
    end
    return n>0 and sum/n or nil
end

local function bounds(i,p)
    local lo,hi=nil,nil
    for j=math.max(1,i-p),i-1 do
        if valid(j) then
            lo=lo and math.min(lo,L(j)) or L(j)
            hi=hi and math.max(hi,H(j)) or H(j)
        end
    end
    return lo,hi
end

local function atr(i,p)
    return mean(i-p+1,i,function(j)
        local prev=C(j-1) or C(j)
        return math.max(H(j)-L(j),math.abs(H(j)-prev),math.abs(L(j)-prev))
    end)
end

local function context(i,p)
    local recent=mean(i-p+1,i,C)
    local prior=mean(i-p*2+1,i-p,C)
    if not recent or not prior then return 0 end
    return recent>prior and 1 or (recent<prior and -1 or 0)
end

local function bar(i,av,ar)
    local range=math.max(H(i)-L(i),0.0000001)
    return {range=range, close_pos=(C(i)-L(i))/range,
        high_volume=V(i)>=av*Settings.volume_factor,
        wide=range>=ar*1.15, bull=C(i)>O(i), bear=C(i)<O(i)}
end

-- Two same-direction high-volume attacks with little new price progress
-- represent Purnov's "effort without result".
local function weakening(i,side,av,a)
    local latest,prior=nil,nil
    for j=i,math.max(2,i-Settings.weakening_bars+1),-1 do
        local directional=valid(j) and ((side=="sell" and C(j)<O(j))
            or (side=="buy" and C(j)>O(j)))
        if directional and V(j)>=av*Settings.volume_factor then
            if not latest then latest=j else prior=j; break end
        end
    end
    if not latest or not prior then return false end
    if side=="sell" then
        local progress=math.max(0,L(prior)-L(latest))
        local rejection=C(latest)>=L(latest)+(H(latest)-L(latest))*0.45
        return progress<=a*Settings.weakening_progress and rejection
    end
    local progress=math.max(0,H(latest)-H(prior))
    local rejection=C(latest)<=L(latest)+(H(latest)-L(latest))*0.55
    return progress<=a*Settings.weakening_progress and rejection
end

local function old(since,i)
    return not since or i-since>Settings.setup_bars
end

local function rewardRisk(entry,stop,target,long)
    local risk=long and entry-stop or stop-entry
    local reward=long and target-entry or entry-target
    return risk>0 and math.max(0,reward/risk) or 0
end

local function evaluate(i)
    local p=math.max(12,Settings.period)
    local support,resistance=bounds(i,p)
    local a=atr(i,14)
    local av=mean(i-p,i-1,V)
    local ar=mean(i-p,i-1,function(j) return H(j)-L(j) end)
    if not support or not resistance or not a or not av or not ar then
        return support,resistance,nil,nil,nil,nil,0,0
    end

    local b=bar(i,av,ar)
    local zone=a*Settings.zone_atr
    local prev=cache[i-1] or {}
    local s={long_stage=prev.long_stage or 0, short_stage=prev.short_stage or 0,
        long_since=prev.long_since, short_since=prev.short_since,
        breakout_side=prev.breakout_side, breakout_level=prev.breakout_level,
        breakout_since=prev.breakout_since}

    if old(s.long_since,i) then s.long_stage=0; s.long_since=nil end
    if old(s.short_since,i) then s.short_stage=0; s.short_since=nil end
    if old(s.breakout_since,i) then
        s.breakout_side=nil; s.breakout_level=nil; s.breakout_since=nil
    end

    local at_support=L(i)<=support+zone and H(i)>=support-zone
    local at_resistance=H(i)>=resistance-zone and L(i)<=resistance+zone
    local spring=L(i)<support-zone and C(i)>support and b.close_pos>=0.60
    local upthrust=H(i)>resistance+zone and C(i)<resistance and b.close_pos<=0.40
    local joc=C(i)>resistance+zone and b.bull and b.wide and b.high_volume
    local sow=C(i)<support-zone and b.bear and b.wide and b.high_volume

    if at_support and s.long_stage==0 then s.long_stage=1; s.long_since=i end
    if at_resistance and s.short_stage==0 then s.short_stage=1; s.short_since=i end
    s.seller_weak=s.long_stage>=1 and weakening(i,"sell",av,a)
    s.buyer_weak=s.short_stage>=1 and weakening(i,"buy",av,a)
    if s.seller_weak then s.long_stage=2 end
    if s.buyer_weak then s.short_stage=2 end

    if joc then s.breakout_side=1; s.breakout_level=resistance; s.breakout_since=i end
    if sow then s.breakout_side=-1; s.breakout_level=support; s.breakout_since=i end

    local trend=context(i,Settings.trend_period)
    s.buyer_appears=b.bull and b.close_pos>=0.65 and (b.high_volume or spring) and trend>=0
    s.seller_appears=b.bear and b.close_pos<=0.35 and (b.high_volume or upthrust) and trend<=0
    local btc=s.breakout_side==1 and i>(s.breakout_since or i)
        and L(i)<=s.breakout_level+zone and C(i)>s.breakout_level and s.buyer_appears
    local bti=s.breakout_side==-1 and i>(s.breakout_since or i)
        and H(i)>=s.breakout_level-zone and C(i)<s.breakout_level and s.seller_appears

    local long_ready=s.long_stage>=2
    local short_ready=s.short_stage>=2
    local long_candidate=(long_ready and s.buyer_appears) or spring or btc
    local short_candidate=(short_ready and s.seller_appears) or upthrust or bti
    local long_stop=btc and (s.breakout_level-zone) or math.min(L(i),support-zone)
    local short_stop=bti and (s.breakout_level+zone) or math.max(H(i),resistance+zone)
    local long_target=btc and C(i)+(resistance-support) or resistance
    local short_target=bti and C(i)-(resistance-support) or support
    local long_rr=rewardRisk(C(i),long_stop,long_target,true)
    local short_rr=rewardRisk(C(i),short_stop,short_target,false)

    local buy,sell,rr=nil,nil,0
    if long_candidate and long_rr>=Settings.min_rr and not short_candidate then
        buy=L(i)-a*0.25; rr=long_rr
        s.long_stage=0; s.long_since=nil
        s.breakout_side=nil; s.breakout_level=nil; s.breakout_since=nil
    elseif short_candidate and short_rr>=Settings.min_rr and not long_candidate then
        sell=H(i)+a*0.25; rr=-short_rr
        s.short_stage=0; s.short_since=nil
        s.breakout_side=nil; s.breakout_level=nil; s.breakout_since=nil
    end

    s.spring=spring; s.upthrust=upthrust; s.btc=btc; s.bti=bti
    s.trend=trend; s.rr=rr
    cache[i]=s
    local stage=s.long_stage>0 and s.long_stage or (s.short_stage>0 and -s.short_stage or 0)
    local buy_ready=long_ready and not buy and L(i)-a*0.12 or nil
    local sell_ready=short_ready and not sell and H(i)+a*0.12 or nil
    return support,resistance,buy_ready,buy,sell_ready,sell,stage,rr
end

function Init() return #Settings.line end

function OnCalculate(index)
    reads = {}
    local needed=math.max(Settings.period*2,Settings.trend_period*2)
    if index==1 then cache={} end
    if index<=needed or not valid(index-1) then
        return nil,nil,nil,nil,nil,nil,nil,nil
    end
    -- Evaluate only the previous closed candle: signals do not repaint.
    return evaluate(index-1)
end

function ExplainSignal(index)
    local s=cache[index-1] or cache[index]
    if not s then return "Недостаточно данных" end
    local p={}
    if s.long_stage==1 then p[#p+1]="цена в зоне поддержки" end
    if s.long_stage==2 then p[#p+1]="продавец ослаб; ожидание покупателя" end
    if s.short_stage==1 then p[#p+1]="цена в зоне сопротивления" end
    if s.short_stage==2 then p[#p+1]="покупатель ослаб; ожидание продавца" end
    if s.spring then p[#p+1]="Spring: возврат над поддержкой" end
    if s.upthrust then p[#p+1]="Upthrust: возврат под сопротивление" end
    if s.btc then p[#p+1]="BTC: тест пробоя вверх" end
    if s.bti then p[#p+1]="BTI: тест пробоя вниз" end
    if s.seller_weak then p[#p+1]="усилие продавца без результата" end
    if s.buyer_weak then p[#p+1]="усилие покупателя без результата" end
    if s.buyer_appears then p[#p+1]="появился покупатель" end
    if s.seller_appears then p[#p+1]="появился продавец" end
    if s.rr and s.rr~=0 then p[#p+1]=string.format("R/R %.1f",math.abs(s.rr)) end
    return #p>0 and table.concat(p,"; ") or "Подтвержденного сетапа нет"
end

function OnChangeSettings() cache={}; return #Settings.line end
