Settings = {
    Name="Purnov Context Signals v3.0", period=30, trend_period=34,
    higher_context_period=80, volume_lookback=55, volume_factor=1.25,
    zone_atr=0.30, volume_zone_atr=0.40, setup_bars=8,
    weakening_bars=6, weakening_progress=0.35, min_rr=3.0,
    line={
        {Name="Support", Color=RGB(65,125,205), Type=TYPE_LINE, Width=1},
        {Name="Resistance", Color=RGB(65,125,205), Type=TYPE_LINE, Width=1},
        {Name="Volume zone 1", Color=RGB(80,165,185), Type=TYPE_LINE, Width=1},
        {Name="Volume zone 2", Color=RGB(125,190,205), Type=TYPE_LINE, Width=1},
        {Name="Confirmed target", Color=RGB(175,115,210), Type=TYPE_LINE, Width=1},
        {Name="BUY ready", Color=RGB(110,190,145), Type=TYPE_POINT, Width=3},
        {Name="BUY confirmed", Color=RGB(20,200,95), Type=TYPE_TRIANGLE_UP, Width=4},
        {Name="SELL ready", Color=RGB(225,145,145), Type=TYPE_POINT, Width=3},
        {Name="SELL confirmed", Color=RGB(235,55,55), Type=TYPE_TRIANGLE_DOWN, Width=4},
        {Name="Stage (-2..2)", Color=RGB(235,175,45), Type=TYPE_HISTOGRAM, Width=2},
        {Name="Risk/reward", Color=RGB(145,95,210), Type=TYPE_HISTOGRAM, Width=1},
        {Name="Senior context (-1..1)", Color=RGB(110,110,110), Type=TYPE_HISTOGRAM, Width=1}
    }
}

local cache={}
local function valid(i)
    return i and i>0 and CandleExist(i) and O(i)~=nil and C(i)~=nil
        and H(i)~=nil and L(i)~=nil and V(i)~=nil
end
local function mean(first,last,fn)
    local sum,n=0,0
    for i=math.max(1,first),last do if valid(i) then sum=sum+fn(i); n=n+1 end end
    return n>0 and sum/n or nil
end
local function bounds(i,p)
    local lo,hi=nil,nil
    for j=math.max(1,i-p),i-1 do if valid(j) then
        lo=lo and math.min(lo,L(j)) or L(j); hi=hi and math.max(hi,H(j)) or H(j)
    end end
    return lo,hi
end
local function atr(i,p)
    return mean(i-p+1,i,function(j)
        local prev=C(j-1) or C(j)
        return math.max(H(j)-L(j),math.abs(H(j)-prev),math.abs(L(j)-prev))
    end)
end
local function context(i,p)
    local recent=mean(i-p+1,i,C); local prior=mean(i-p*2+1,i-p,C)
    if not recent or not prior then return 0 end
    return recent>prior and 1 or (recent<prior and -1 or 0)
end
local function bar(i,av,ar)
    local range=math.max(H(i)-L(i),0.0000001)
    return {range=range,close_pos=(C(i)-L(i))/range,high_volume=V(i)>=av*Settings.volume_factor,
        wide=range>=ar*1.15,bull=C(i)>O(i),bear=C(i)<O(i)}
end
-- Approximate two nearest high-volume nodes on the active chart timeframe.
-- They are guides, not a replacement for a manually drawn Volume Profile.
local function volumeZones(i,low,a)
    local width=math.max(a*Settings.volume_zone_atr,0.0000001); local bins={}
    for j=math.max(1,i-Settings.volume_lookback),i-1 do if valid(j) then
        local price=(H(j)+L(j)+C(j))/3; local key=math.floor((price-low)/width)
        bins[key]=(bins[key] or 0)+V(j)
    end end
    local candidates={}; local current=C(i)
    for key,volume in pairs(bins) do
        local price=low+(key+0.5)*width
        if price<=current then candidates[#candidates+1]={price=price,volume=volume} end
    end
    table.sort(candidates,function(x,y) return x.volume>y.volume end)
    local first,second=nil,nil
    for _,node in ipairs(candidates) do
        if not first then first=node.price
        elseif math.abs(node.price-first)>=width then second=node.price; break end
    end
    return first,second
end
local function weakening(i,side,av,a)
    local latest,prior=nil,nil
    for j=i,math.max(2,i-Settings.weakening_bars+1),-1 do
        local directional=valid(j) and ((side=="sell" and C(j)<O(j)) or (side=="buy" and C(j)>O(j)))
        if directional and V(j)>=av*Settings.volume_factor then if not latest then latest=j else prior=j; break end end
    end
    if not latest or not prior then return false end
    if side=="sell" then
        return math.max(0,L(prior)-L(latest))<=a*Settings.weakening_progress
            and C(latest)>=L(latest)+(H(latest)-L(latest))*0.45
    end
    return math.max(0,H(latest)-H(prior))<=a*Settings.weakening_progress
        and C(latest)<=L(latest)+(H(latest)-L(latest))*0.55
end
local function old(since,i) return not since or i-since>Settings.setup_bars end
local function rewardRisk(entry,stop,target,long)
    local risk=long and entry-stop or stop-entry; local reward=long and target-entry or entry-target
    return risk>0 and math.max(0,reward/risk) or 0
end
local function evaluate(i)
    local p=math.max(12,Settings.period); local support,resistance=bounds(i,p)
    local a=atr(i,14); local av=mean(i-p,i-1,V); local ar=mean(i-p,i-1,function(j) return H(j)-L(j) end)
    if not support or not resistance or not a or not av or not ar then return nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil end
    local b=bar(i,av,ar); local zone=a*Settings.zone_atr; local v1,v2=volumeZones(i,support,a)
    local prev=cache[i-1] or {}; local s={long_stage=prev.long_stage or 0,short_stage=prev.short_stage or 0,
        long_since=prev.long_since,short_since=prev.short_since,breakout_side=prev.breakout_side,
        breakout_level=prev.breakout_level,breakout_since=prev.breakout_since}
    if old(s.long_since,i) then s.long_stage=0;s.long_since=nil end
    if old(s.short_since,i) then s.short_stage=0;s.short_since=nil end
    if old(s.breakout_since,i) then s.breakout_side=nil;s.breakout_level=nil;s.breakout_since=nil end
    local at_support=L(i)<=support+zone and H(i)>=support-zone; local at_resistance=H(i)>=resistance-zone and L(i)<=resistance+zone
    local spring=L(i)<support-zone and C(i)>support and b.close_pos>=0.60; local upthrust=H(i)>resistance+zone and C(i)<resistance and b.close_pos<=0.40
    local joc=C(i)>resistance+zone and b.bull and b.wide and b.high_volume; local sow=C(i)<support-zone and b.bear and b.wide and b.high_volume
    if at_support and s.long_stage==0 then s.long_stage=1;s.long_since=i end
    if at_resistance and s.short_stage==0 then s.short_stage=1;s.short_since=i end
    s.seller_weak=s.long_stage>=1 and weakening(i,"sell",av,a); s.buyer_weak=s.short_stage>=1 and weakening(i,"buy",av,a)
    if s.seller_weak then s.long_stage=2 end; if s.buyer_weak then s.short_stage=2 end
    if joc then s.breakout_side=1;s.breakout_level=resistance;s.breakout_since=i end
    if sow then s.breakout_side=-1;s.breakout_level=support;s.breakout_since=i end
    local trend=context(i,Settings.trend_period); local senior=context(i,Settings.higher_context_period)
    s.buyer_appears=b.bull and b.close_pos>=0.65 and (b.high_volume or spring) and trend>=0 and senior>=0
    s.seller_appears=b.bear and b.close_pos<=0.35 and (b.high_volume or upthrust) and trend<=0 and senior<=0
    local btc=s.breakout_side==1 and i>(s.breakout_since or i) and L(i)<=s.breakout_level+zone and C(i)>s.breakout_level and s.buyer_appears
    local bti=s.breakout_side==-1 and i>(s.breakout_since or i) and H(i)>=s.breakout_level-zone and C(i)<s.breakout_level and s.seller_appears
    local long_candidate=(s.long_stage>=2 and s.buyer_appears) or spring or btc; local short_candidate=(s.short_stage>=2 and s.seller_appears) or upthrust or bti
    local long_stop=btc and s.breakout_level-zone or math.min(L(i),support-zone); local short_stop=bti and s.breakout_level+zone or math.max(H(i),resistance+zone)
    local long_target=btc and C(i)+(resistance-support) or resistance; local short_target=bti and C(i)-(resistance-support) or support
    local long_rr=rewardRisk(C(i),long_stop,long_target,true); local short_rr=rewardRisk(C(i),short_stop,short_target,false)
    local buy,sell,target,rr=nil,nil,nil,0
    if long_candidate and long_rr>=Settings.min_rr and not short_candidate then buy=L(i)-a*0.25;target=long_target;rr=long_rr
    elseif short_candidate and short_rr>=Settings.min_rr and not long_candidate then sell=H(i)+a*0.25;target=short_target;rr=-short_rr end
    if buy or sell then s.long_stage=0;s.short_stage=0;s.long_since=nil;s.short_since=nil;s.breakout_side=nil;s.breakout_level=nil;s.breakout_since=nil end
    s.spring=spring;s.upthrust=upthrust;s.btc=btc;s.bti=bti;s.trend=trend;s.senior=senior;s.rr=rr;s.target=target;s.v1=v1;s.v2=v2
    cache[i]=s; local stage=s.long_stage>0 and s.long_stage or (s.short_stage>0 and -s.short_stage or 0)
    local buy_ready=s.long_stage>=2 and not buy and L(i)-a*0.12 or nil; local sell_ready=s.short_stage>=2 and not sell and H(i)+a*0.12 or nil
    return support,resistance,v1,v2,target,buy_ready,buy,sell_ready,sell,stage,rr,senior
end
function Init() return #Settings.line end
function OnCalculate(index)
    local needed=math.max(Settings.period*2,Settings.trend_period*2,Settings.higher_context_period*2)
    if index==1 then cache={} end
    if index<=needed or not valid(index-1) then return nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil end
    return evaluate(index-1)
end
function ExplainSignal(index)
    local s=cache[index-1] or cache[index]; if not s then return "Недостаточно данных" end; local p={}
    if s.long_stage==1 then p[#p+1]="цена в зоне поддержки" end; if s.long_stage==2 then p[#p+1]="продавец ослаб; ожидание покупателя" end
    if s.short_stage==1 then p[#p+1]="цена в зоне сопротивления" end; if s.short_stage==2 then p[#p+1]="покупатель ослаб; ожидание продавца" end
    if s.spring then p[#p+1]="Spring" end; if s.upthrust then p[#p+1]="Upthrust" end; if s.btc then p[#p+1]="BTC" end; if s.bti then p[#p+1]="BTI" end
    if s.senior==1 then p[#p+1]="старший контекст вверх" elseif s.senior==-1 then p[#p+1]="старший контекст вниз" end
    if s.v1 then p[#p+1]=string.format("объемная зона 1 %.4f",s.v1) end; if s.v2 then p[#p+1]=string.format("зона 2 %.4f",s.v2) end
    if s.target then p[#p+1]=string.format("цель %.4f подтверждена R/R %.1f",s.target,math.abs(s.rr)) end
    return #p>0 and table.concat(p,"; ") or "Подтвержденного сетапа нет"
end
function OnChangeSettings() cache={}; return #Settings.line end
