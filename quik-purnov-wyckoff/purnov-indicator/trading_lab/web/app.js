const api = (url, options) => fetch(url, options).then(async response => { const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Ошибка запроса'); return data; });
const money = number => new Intl.NumberFormat('ru-RU', {maximumFractionDigits: 2}).format(number);
let setups = [];

function formData(form) { return Object.fromEntries(new FormData(form)); }
function escapeHtml(value) { const node = document.createElement('span'); node.textContent = value; return node.innerHTML; }

function renderSetups(items) {
  document.querySelector('#setup-cards').innerHTML = items.map(item => `<article class="card"><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.context)}</p><ul>${item.checks.map(check => `<li>${escapeHtml(check)}</li>`).join('')}</ul><div class="source">${escapeHtml(item.source)}</div></article>`).join('');
  document.querySelector('#setup-select').innerHTML = `<option value="">Выберите сетап</option>${items.map(item => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)}</option>`).join('')}`;
}
function renderTrades(items) {
  const area = document.querySelector('#trades');
  area.innerHTML = items.length ? items.map(item => `<article class="trade"><div><strong>${escapeHtml(item.ticker)} · ${escapeHtml(item.setup)}</strong><br><small>Вход ${money(item.entry)} · стоп ${money(item.stop)} · цель ${money(item.target)} · ${item.risk_reward}R</small>${item.notes ? `<p>${escapeHtml(item.notes)}</p>` : ''}</div><span class="badge">${escapeHtml(item.result)}</span></article>`).join('') : '<div class="result">Пока нет записей. Запланируйте первую сделку до входа.</div>';
}
let trainerScenarios = [];
function marketScenario(fragment) { return {id:fragment.id, ticker:fragment.ticker, title:`${fragment.ticker} · ${fragment.interval} · ${fragment.from} — ${fragment.to}`, context:`Реальный исторический фрагмент ${fragment.ticker} (${fragment.interval}). Источник: ${fragment.source}. Сначала оцени уровень, объём, спред и результат — будущие даты скрыты.`, candles:fragment.candles.map(item => ({open:Number(item.open),high:Number(item.high),low:Number(item.low),close:Number(item.close),volume:Number(item.volume),begin:item.begin}))}; }
function trainerHint(scenario) { return `Контекст: ${scenario.ticker}, ${scenario.title.split(' · ').slice(1).join(' · ')}. Отметь уровни на уже видимой истории; затем сопоставь усилие (объём), спред и результат. Подсказка не раскрывает будущие реальные свечи.`; }
const trainerState = {scenarioIndex:0, candleIndex:59, action:null, entry:null, stopped:false, playing:false, timer:null};
const chart = document.querySelector('#trainer-chart');
const ctx = chart.getContext('2d');
const TRAINING_KEY = 'purnov-trading-lab-training-real-moex-v1';

function activeScenario() { return trainerScenarios[trainerState.scenarioIndex % trainerScenarios.length]; }
function candlesFor(scenario) { return scenario?.candles || []; }
function visibleCandles() { return candlesFor(activeScenario()).slice(0, trainerState.candleIndex + 1); }
function drawChart() {
  const candles = visibleCandles(); const all = candlesFor(activeScenario()); const pad = {l:46,r:16,t:24,b:32}; const width=chart.width-pad.l-pad.r, height=chart.height-pad.t-pad.b, priceHeight=height-64;
  const values = all.flatMap(c => [c.high,c.low]); const min=Math.min(...values)-.6, max=Math.max(...values)+.6, scaleY=value => pad.t+(max-value)/(max-min)*priceHeight;
  ctx.clearRect(0,0,chart.width,chart.height); ctx.fillStyle='#102430';ctx.fillRect(0,0,chart.width,chart.height);
  ctx.strokeStyle='rgba(220,235,233,.13)';ctx.lineWidth=1;ctx.font='12px system-ui';ctx.fillStyle='#9bb5b0';
  for(let i=0;i<5;i++){const y=pad.t+i*priceHeight/4;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(chart.width-pad.r,y);ctx.stroke();ctx.fillText((max-(max-min)*i/4).toFixed(1),4,y+4);}
  const step=width/Math.max(24,all.length-1); candles.forEach((c,index)=>{const x=pad.l+index*step;const up=c.close>=c.open;ctx.strokeStyle=up?'#53c2a2':'#e57670';ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(x,scaleY(c.high));ctx.lineTo(x,scaleY(c.low));ctx.stroke();const y=Math.min(scaleY(c.open),scaleY(c.close));const h=Math.max(2,Math.abs(scaleY(c.open)-scaleY(c.close)));ctx.fillRect(x-3,y,6,h);});
  const volumeTop=pad.t+priceHeight+12, volumeHeight=43, maxVolume=Math.max(...all.map(c=>c.volume)); ctx.fillStyle='#91aaa5';ctx.fillText('Объём MOEX',pad.l,volumeTop-2);candles.forEach((c,index)=>{const x=pad.l+index*step;const h=c.volume/maxVolume*volumeHeight;ctx.fillStyle=c.close>=c.open?'#3d957e':'#bd625f';ctx.fillRect(x-2,volumeTop+volumeHeight-h,4,h);});
  const last=candles.at(-1); ctx.fillStyle='#eef6f3';ctx.fillText(`Дата: ${last.begin.slice(0,10)} · закрытие: ${last.close.toFixed(2)} · свеча ${candles.length}/${all.length}`,pad.l,chart.height-10);
  if(trainerState.entry){const y=scaleY(trainerState.entry);ctx.strokeStyle='#e6a11a';ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(chart.width-pad.r,y);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#f3c259';ctx.fillText(`вход ${trainerState.action}: ${trainerState.entry.toFixed(2)}`,chart.width-170,y-7);}
  document.querySelector('#chart-info').textContent = activeScenario().context;
}
function currentBarHint() {
  const candles=visibleCandles(), bar=candles.at(-1), previous=candles.at(-2), sample=candles.slice(-13,-1); const range=bar.high-bar.low, avgRange=sample.reduce((sum,c)=>sum+c.high-c.low,0)/sample.length, avgVolume=sample.reduce((sum,c)=>sum+c.volume,0)/sample.length; const closePos=(bar.close-bar.low)/range, upper=bar.high-Math.max(bar.close,bar.open), lower=Math.min(bar.close,bar.open)-bar.low; const parts=[];
  parts.push(range>avgRange*1.3?'Спред широкий относительно последних свечей.':range<avgRange*.75?'Спред узкий: движение пока не убедительное.':'Спред обычный относительно последних свечей.');
  parts.push(bar.volume>avgVolume*1.25?'Объём MOEX повышен.':bar.volume<avgVolume*.8?'Объём MOEX снижен.':'Объём MOEX средний.');
  if(closePos>.72)parts.push('Закрытие близко к максимуму бара — покупатель удержал часть диапазона.'); else if(closePos<.28)parts.push('Закрытие близко к минимуму бара — продавец удержал часть диапазона.'); else parts.push('Закрытие в середине: преимущество пока неочевидно.');
  if(upper>range*.38)parts.push('Верхний хвост заметен: проверь реакцию на более высоких ценах.'); if(lower>range*.38)parts.push('Нижний хвост заметен: проверь реакцию на более низких ценах.'); if(previous)parts.push(bar.close>previous.close?'Есть положительный прогресс против предыдущей свечи.':'Есть отрицательный прогресс против предыдущей свечи.');
  return `Текущая свеча: ${parts.join(' ')} Это наблюдение, а не сигнал на вход.`;
}
function trainingLog() { try { return JSON.parse(localStorage.getItem(TRAINING_KEY) || '[]'); } catch { return []; } }
function saveTraining(item) { const log=trainingLog();log.push(item);localStorage.setItem(TRAINING_KEY,JSON.stringify(log.slice(-30))); }
function renderAnalysis() { const log=trainingLog(), area=document.querySelector('#training-analysis'); if(log.length<3){area.textContent=`Завершено ${log.length} из 3 реальных фрагментов. После третьего появится анализ дисциплины и результата.`;return;}
  const entered=log.filter(item=>item.action!=='skip'), wins=entered.filter(item=>item.r>0), avg=entered.length?entered.reduce((sum,item)=>sum+item.r,0)/entered.length:0;
  const weak=log.filter(item=>item.early).length; area.innerHTML=`<strong>Разбор последних ${Math.min(log.length,30)} реальных фрагментов MOEX</strong><br>Сделок: ${entered.length}, положительных: ${wins.length}, средний итог: ${avg.toFixed(2)}R, пропусков: ${log.length-entered.length}.${weak ? `<br><span>В ${weak} случаях решение принято вскоре после открытия фрагмента — проверь терпение у уровня.</span>` : '<br><span>Ранних решений нет: это хороший признак дисциплины.</span>'}`;
}
function stopPlayback(){trainerState.playing=false;if(trainerState.timer)clearInterval(trainerState.timer);trainerState.timer=null;document.querySelector('#play-chart').textContent='Пуск';document.querySelector('#chart-state').textContent='Пауза';}
function concludeScenario(){ if(trainerState.stopped)return; stopPlayback();const scenario=activeScenario(),all=candlesFor(scenario);let action=trainerState.action||'skip',r=0;if(action!=='skip'){const risk=Math.max(Math.abs(trainerState.entry-all[Math.max(0,trainerState.entryIndex-4)].close),Math.abs(all[trainerState.entryIndex].high-all[trainerState.entryIndex].low)*.8);const finalPrice=all.at(-1).close;r=(action==='long'?(finalPrice-trainerState.entry):(trainerState.entry-finalPrice))/risk;r=Number(r.toFixed(2));}const item={scenario:scenario.title,action,r,early:action!=='skip'&&trainerState.entryIndex<70,at:new Date().toISOString()};saveTraining(item);trainerState.stopped=true;document.querySelector('#decision-result').innerHTML=action==='skip'?'Итог: пропуск зафиксирован. Все свечи фрагмента были реальными историческими свечами MOEX.':`Итог: <strong>${r>0?'плюс':'минус'} ${r}R</strong> по реальному историческому фрагменту MOEX. Это разбор тренировки, не оценка текущего рынка.`;renderAnalysis();}
function advance(){if(trainerState.stopped)return;const last=candlesFor(activeScenario()).length-1;if(trainerState.candleIndex>=last){concludeScenario();return;}trainerState.candleIndex++;drawChart();if(trainerState.candleIndex>=last)concludeScenario();}
function resetScenario(){stopPlayback();trainerState.scenarioIndex++;trainerState.candleIndex=59;trainerState.action=null;trainerState.entry=null;trainerState.entryIndex=null;trainerState.stopped=false;document.querySelector('#case-title').textContent=activeScenario().title;document.querySelector('#decision-help').textContent='Оцените уровень, спред, объём, прогресс и точку отмены.';document.querySelector('#decision-result').textContent='Сделка ещё не зафиксирована.';drawChart();}
function decide(action){if(trainerState.stopped||trainerState.action)return;const last=visibleCandles().at(-1);trainerState.action=action;trainerState.entry=last.close;trainerState.entryIndex=trainerState.candleIndex;document.querySelector('#decision-result').textContent=action==='skip'?'Пропуск зафиксирован. Продолжи график до итога.':`${action==='long'?'Лонг':'Шорт'} зафиксирован по ${last.close.toFixed(2)}. Будущие свечи всё ещё скрыты.`;drawChart();}
function initTrainer(fragments){trainerScenarios=fragments.map(marketScenario);if(!trainerScenarios.length)throw new Error('Не удалось загрузить локальные фрагменты MOEX.');document.querySelector('#case-title').textContent=activeScenario().title;drawChart();renderAnalysis();document.querySelector('#step-chart').addEventListener('click',advance);document.querySelector('#next-case').addEventListener('click',resetScenario);document.querySelector('#hint-chart').addEventListener('click',()=>{document.querySelector('#decision-help').textContent=trainerHint(activeScenario());});document.querySelector('#bar-hint-chart').addEventListener('click',()=>{document.querySelector('#decision-help').textContent=currentBarHint();});document.querySelector('#play-chart').addEventListener('click',()=>{if(trainerState.playing){stopPlayback();return;}trainerState.playing=true;document.querySelector('#play-chart').textContent='Пауза';document.querySelector('#chart-state').textContent='Движение';trainerState.timer=setInterval(advance,700);});document.querySelectorAll('[data-action]').forEach(button=>button.addEventListener('click',()=>decide(button.dataset.action)));}
async function refreshTrades() { renderTrades(await api('/api/trades')); }

document.querySelector('#risk-form').addEventListener('submit', async event => {
  event.preventDefault(); const target = document.querySelector('#risk-result');
  try { const plan = await api('/api/risk', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(formData(event.target))}); target.innerHTML = `<strong>Допустимо: ${money(plan.quantity)} единиц</strong>Риск: ${money(plan.risk_money)} · позиция: ${money(plan.position_value)} (${plan.position_pct}% счёта) · риск на единицу: ${money(plan.per_unit)} · ограничено: ${escapeHtml(plan.limited_by)}<br><small>${escapeHtml(plan.warning)}</small>`; } catch (error) { target.textContent = error.message; }
});
document.querySelector('#trade-form').addEventListener('submit', async event => {
  event.preventDefault();
  try { await api('/api/trades',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(formData(event.target))}); event.target.reset(); await refreshTrades(); } catch (error) { alert(error.message); }
});
document.querySelector('#search-form').addEventListener('submit', async event => {
  event.preventDefault(); const target = document.querySelector('#search-results'); target.textContent = 'Ищу в расшифровках…';
  try { const matches = await api('/api/search?q=' + encodeURIComponent(formData(event.target).q)); target.innerHTML = matches.length ? matches.map(match => `<article><strong>${escapeHtml(match.lesson)}</strong> · ${escapeHtml(match.time)}<p class="quote">${escapeHtml(match.quote)}</p></article>`).join('') : 'Точных фрагментов не найдено. Попробуйте 1–2 ключевых слова.'; } catch (error) { target.textContent = error.message; }
});
Promise.all([api('/api/setups'),api('/api/market-fragments')]).then(([loadedSetups,fragments]) => {setups=loadedSetups;renderSetups(setups);initTrainer(fragments);return refreshTrades();}).catch(error => {document.body.insertAdjacentHTML('afterbegin', `<p>${escapeHtml(error.message)}</p>`);});
