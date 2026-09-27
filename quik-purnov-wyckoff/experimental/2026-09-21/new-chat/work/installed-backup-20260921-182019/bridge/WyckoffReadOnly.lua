-- Read-only QUIK collector. NO sendTransaction, no account access, no orders.
-- Run as a QLua script, NOT as a chart indicator.
local root = getScriptPath() .. "\\.."
local config = dofile(getScriptPath() .. "\\config.lua")
local account_reader = dofile(getScriptPath() .. "\\AccountReadOnly.lua")
local running, streams, updated = true, {}, {}
local history_cache, history_cursor = {}, 1
local frames = {D1=INTERVAL_D1,H4=INTERVAL_H4,H1=INTERVAL_H1,M15=INTERVAL_M15,M5=INTERVAL_M5,M1=INTERVAL_M1}
local function utc() return os.date('!%Y-%m-%dT%H:%M:%SZ') end
local function esc(s) return '"'..tostring(s):gsub('\\','\\\\'):gsub('"','\\"'):gsub('[%z\1-\31]',' ')..'"' end
local function json(v)
  if v == nil then return 'null' end
  if type(v)=='boolean' then return v and 'true' or 'false' end
  if type(v)=='number' then if v~=v or v==math.huge or v==-math.huge then return 'null' end return tostring(v) end
  if type(v)=='string' then return esc(v) end
  local out={}
  if #v>0 or v.__array then
    for i=1,#v do out[#out+1]=json(v[i]) end
    return '['..table.concat(out,',')..']'
  end
  for k,x in pairs(v) do out[#out+1]=esc(k)..':'..json(x) end
  return '{'..table.concat(out,',')..'}'
end
local function class(sec) return sec:match('^TQBR:') and 'TQBR' or 'SPBFUT' end
local function code(sec) return sec:gsub('^TQBR:', '') end
local function param(sec,name)
  local p=getParamEx(class(sec),code(sec),name)
  if not p or tostring(p.result)~='1' then return nil end
  return tonumber(p.param_value)
end
local function trade_date()
  local raw=tostring(getInfoParam('TRADEDATE') or '')
  local d,m,y=raw:match('(%d%d)%.(%d%d)%.(%d%d%d%d)')
  if y then return y..'-'..m..'-'..d end
  return nil
end
local function expiry(sec)
  local info=getSecurityInfo('SPBFUT',sec)
  local value=info and tostring(info.mat_date or '') or ''
  if #value==8 then return value:sub(1,4)..'-'..value:sub(5,6)..'-'..value:sub(7,8) end
  return nil
end
local function bars(ds)
  local out={__array=true}
  for i=math.max(1,ds:Size()-1499),ds:Size() do
    local t=ds:T(i)
    if t and ds:O(i) and ds:H(i) and ds:L(i) and ds:C(i) and ds:V(i) then
      out[#out+1]={t=string.format('%04d-%02d-%02dT%02d:%02d:%02d+03:00',t.year,t.month,t.day,t.hour,t.min,t.sec),o=ds:O(i),h=ds:H(i),l=ds:L(i),c=ds:C(i),v=ds:V(i)}
    end
  end
  return out
end
local function write_json(path, data)
  local f,err=io.open(path..'.tmp','wb')
  if not f then return nil,err end
  f:write(json(data)); f:close()
  os.remove(path)
  return os.rename(path..'.tmp',path)
end
local function history_key(ds)
  local n=ds:Size()
  local t=n>0 and ds:T(n) or nil
  if not t then return nil end
  return tostring(n)..':'..t.year..':'..t.month..':'..t.day..':'..t.hour..':'..t.min
end
function OnQuote(class,sec)
  if class=='SPBFUT' then updated[sec]=utc()
  elseif class=='TQBR' then updated['TQBR:'..sec]=utc() end
end
function OnStop() running=false; return 3000 end
function main()
  local output=config.output or (root..'\\runtime\\market.json')
  local history_dir=config.history_dir or (root..'\\runtime\\history')
  local last_universe=0
  local last_liquidity=0
  local selected={}
  while running do
    if os.time()-last_universe>=60 then
      -- The dashboard ranks all metadata; subscribe to history for top 20 only.
      local selection=io.open(config.subscriptions or (root..'\\runtime\\subscriptions.txt'),'r')
      if selection then
        selected={}
        for sec in selection:lines() do
          if sec:match('^[%w_%-]+$') or sec:match('^TQBR:[%w_%-]+$') then selected[#selected+1]=sec end
        end
        selection:close()
      end
      table.sort(selected)
      local active={}
      for _,sec in ipairs(selected) do active[sec]=true end
      for sec,frameset in pairs(streams) do
        if not active[sec] then
          for _,ds in pairs(frameset) do ds:Close() end
          Unsubscribe_Level_II_Quotes(class(sec),code(sec))
          streams[sec]=nil
        end
      end
      for _,sec in ipairs(selected) do
        if not streams[sec] then
          streams[sec]={}
          Subscribe_Level_II_Quotes(class(sec),code(sec))
        end
        for name,interval in pairs(frames) do
          if not streams[sec][name] and interval then
            local ds=CreateDataSource(class(sec),code(sec),interval)
            if ds then ds:SetEmptyCallback(); streams[sec][name]=ds end
          end
        end
      end
      last_universe=os.time()
    end
    -- Bound history work; quotes are published every cycle without a giant payload.
    local jobs={}
    for _,sec in ipairs(selected) do
      for name,ds in pairs(streams[sec]) do jobs[#jobs+1]={sec=sec,name=name,ds=ds} end
    end
    table.sort(jobs,function(a,b) return a.sec..a.name < b.sec..b.name end)
    local visited,written=0,0
    while #jobs>0 and visited<#jobs and written<24 and running do
      if history_cursor>#jobs then history_cursor=1 end
      local job=jobs[history_cursor]; history_cursor=history_cursor+1; visited=visited+1
      local id=job.sec:gsub(':','_')..'_'..job.name
      local key=history_key(job.ds)
      local cached=history_cache[id]
      if key and (not cached or cached.key~=key or os.time()-cached.written>=60) then
        if not id:match('^[%w_%-]+$') then error('Unsupported security filename') end
        local ok,why=write_json(history_dir..'\\'..id..'.json',bars(job.ds))
        if not ok then error('History write failed: '..tostring(why)) end
        history_cache[id]={key=key,written=os.time(),file=id..'.json'}
        written=written+1
      end
    end
    local instruments={__array=true}
    local securities={}
    for _,cls in ipairs({'SPBFUT','TQBR'}) do
      for sec in tostring(getClassSecurities(cls) or ''):gmatch('[^,]+') do
        securities[#securities+1]=cls=='TQBR' and 'TQBR:'..sec or sec
      end
    end
    for _,sec in ipairs(securities) do
      local stock=class(sec)=='TQBR'
      local lot=stock and param(sec,'LOTSIZE') or 1
      local step=param(sec,'SEC_PRICE_STEP')
      local ask=param(sec,'OFFER')
      local info=getSecurityInfo(class(sec),code(sec)) or {}
      local histories={}
      for name,_ in pairs(streams[sec] or {}) do
        local cached=history_cache[sec:gsub(':','_')..'_'..name]
        if cached then histories[name]=cached.file end
      end
      instruments[#instruments+1]={symbol=sec,class_code=class(sec),name=code(sec),lot_size=lot,bid=param(sec,'BID'),ask=param(sec,'OFFER'),
        quote_time=updated[sec],tick_size=step,tick_value=stock and (step and lot and step*lot) or param(sec,'STEPPRICE'),
        margin=stock and (ask and lot and ask*lot) or math.max(param(sec,'BUYDEPO') or 0,param(sec,'SELLDEPO') or 0),
        expiry=not stock and expiry(sec) or nil,trading=param(sec,'STATUS')==1,history_files=histories,
        turnover_rub=param(sec,config.turnover_param),turnover_currency=stock and (tostring(info.face_unit or '')=='SUR' and 'RUB' or info.face_unit) or config.turnover_currency,
        turnover_time=utc(),turnover_date=trade_date(),fee_per_side=stock and (ask and lot and ask*lot*0.0005) or config.paper_fee_per_side}
    end
    local data={schema=1,transport=2,source='QUIK_READONLY',connected=isConnected()==1,
      generated_at=utc(),instruments=instruments,
      account=account_reader.snapshot(root..'\\runtime\\selected-account.txt'),
      diagnostics={turnover_currency=config.turnover_currency,selected=#selected,account_connected=false}}
    -- Preserve the full universe, before TOP-20 filtering. Never archive accounts.
    if isConnected()==1 and os.time()-last_liquidity>=60 then
      local items={__array=true}
      for _,item in ipairs(instruments) do
        if item.class_code=='SPBFUT' then items[#items+1]={symbol=item.symbol,expiry=item.expiry,
          turnover_rub=item.turnover_rub,turnover_currency=item.turnover_currency,
          turnover_date=item.turnover_date,turnover_time=item.turnover_time,
          tick_size=item.tick_size,tick_value=item.tick_value,margin=item.margin,
          fee_per_side=item.fee_per_side} end
      end
      local journal,why=io.open(config.liquidity_journal or (root..'\\runtime\\liquidity.jsonl'),'ab')
      if journal then
        local ok,err=journal:write(json({schema=1,source='QUIK_READONLY',connected=true,
          universe_complete=true,generated_at=utc(),instruments=items})..'\n')
        journal:close()
        if not ok then message('Liquidity archive: '..tostring(err),2) end
      else message('Liquidity archive: '..tostring(why),2) end
      last_liquidity=os.time()
    end
    local ok,err=write_json(output,data)
    if not ok then message('Wyckoff collector: '..tostring(err),2); running=false end
    sleep(2000)
  end
  for sec,frameset in pairs(streams) do
    for _,ds in pairs(frameset) do ds:Close() end
    Unsubscribe_Level_II_Quotes(class(sec),code(sec))
  end
end
