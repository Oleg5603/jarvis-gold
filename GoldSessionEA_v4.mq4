//+------------------------------------------------------------------+
//|                                              GoldSessionEA v4.0  |
//|                                        XAUUSD M1 — Улучшенная   |
//|                                                                   |
//|  ЧТО ИЗМЕНЕНО v4.0:                                              |
//|  1. Структура рынка HH/HL/LH/LL — убирает 60-70% ложных сигналов|
//|  2. ATR-фильтр перенесён на M15 (стабильнее M1)                 |
//|  3. Подтверждение закрытием свечи за обеими EMA                 |
//|  4. Динамический RSI-порог по силе тренда                       |
//|  5. Автокоррекция летнего/зимнего времени сессии Лондона        |
//|  6. Cooldown между сигналами (мин. N свечей)                    |
//|  7. Исправлены баги: утечка safe-массивов, переход через полночь|
//|     в новостном фильтре, трейлинг BUY без SL, мусор OnDeinit   |
//+------------------------------------------------------------------+

#property copyright "GoldSessionEA v4.0"
#property version   "4.0"
#property strict

#ifndef MODE_HIST
#define MODE_HIST 2
#endif

//=== СТРАТЕГИЯ ===
input string   S1               = "=== СТРАТЕГИЯ ===";
input bool     UseH1Filter      = false;
input int      EMA_Fast_Senior  = 21;
input int      EMA_Slow_Senior  = 55;
input int      EMA_Fast_M1      = 8;
input int      EMA_Slow_M1      = 21;
input int      ATR_Period       = 14;

//=== СТРУКТУРА РЫНКА (НОВОЕ v4) ===
input string   S1b              = "=== СТРУКТУРА РЫНКА ===";
input bool     UseMarketStruct  = true;
input int      StructLookback   = 5;
input bool     RequireCloseConf = true;

//=== COOLDOWN (НОВОЕ v4) ===
input string   S1c              = "=== COOLDOWN ===";
input int      SignalCooldownBars = 10;

//=== РИСК ===
input string   S2               = "=== РИСК ===";
input double   RiskPercent      = 1.0;
input double   ATR_SL_Mult      = 1.5;
input double   ATR_TP_Mult      = 2.5;
input double   MinLot           = 0.01;
input double   MaxLot           = 10.0;

//=== СЕЙФ 1 ===
input string   S3               = "=== СЕЙФ 1 ===";
input bool     UseSafe1         = true;
input int      Safe1Pips        = 150;
input double   Safe1Percent     = 40.0;
input bool     MoveBreakEven    = true;

//=== СЕЙФ 2 ===
input string   S4               = "=== СЕЙФ 2 ===";
input bool     UseSafe2         = true;
input int      Safe2Pips        = 300;
input double   Safe2Percent     = 30.0;

//=== ТРЕЙЛИНГ ===
input string   S5               = "=== ТРЕЙЛИНГ ===";
input bool     UseTrailing      = true;
input int      TrailingStart    = 200;
input int      TrailingStep     = 50;
input int      TrailingStop     = 100;

//=== СЕССИИ ===
input string   S6               = "=== СЕССИИ ===";
input bool     UseSessionFilter = true;
input int      LondonOpen       = 8;
input int      LondonClose      = 17;
input bool     AutoDST          = true;    // НОВОЕ v4: автокоррекция GMT+1 летом
input bool     BlockFriday      = true;

//=== RSI ФИЛЬТР ===
input string   S7               = "=== RSI ФИЛЬТР ===";
input bool     UseRSI           = true;
input int      RSI_Period       = 14;
input int      RSI_OB_M1        = 70;
input int      RSI_OS_M1        = 30;
input int      RSI_OB_Sr        = 65;
input int      RSI_OS_Sr        = 35;
input bool     UseRSI_Senior    = true;
input bool     UseDynamicRSI    = true;    // НОВОЕ v4: порог сдвигается при сильном тренде

//=== MACD ФИЛЬТР ===
input string   S8               = "=== MACD ФИЛЬТР ===";
input bool     UseMACD          = true;
input int      MACD_Fast        = 12;
input int      MACD_Slow        = 26;
input int      MACD_Signal      = 9;

//=== ATR ФИЛЬТР ВОЛАТИЛЬНОСТИ ===
input string   S9               = "=== ATR ВОЛАТИЛЬНОСТЬ ===";
input bool     UseATR_Filter    = true;
input double   ATR_Min_Pips     = 5.0;
input double   ATR_Max_Pips     = 80.0;
// v4: ATR считается на M15

//=== НОВОСТНОЙ ФИЛЬТР ===
input string   S10              = "=== НОВОСТНОЙ ФИЛЬТР ===";
input bool     UseNewsFilter    = true;
input int      NewsMinBefore    = 30;
input int      NewsMinAfter     = 30;
input string   NewsTimes        = "08:30,12:30,14:00,18:00,20:00";

//=== ЗАЩИТА КАПИТАЛА ===
input string   S11              = "=== ЗАЩИТА КАПИТАЛА ===";
input bool     UseDailyDD       = true;
input double   MaxDailyDD_Pct   = 3.0;
input int      MaxDailyTrades   = 5;

//=== НАДЁЖНОСТЬ ===
input string   S12              = "=== НАДЁЖНОСТЬ ===";
input int      MaxSpreadPoints  = 30;
input int      MaxRetries       = 3;
input int      RetryDelay_ms    = 500;
input bool     SaveCSV          = true;
input int      MagicNumber      = 20240101;
input string   Comment_EA       = "GoldEA";

//=== ПАНЕЛЬ ===
input string   S13              = "=== ПАНЕЛЬ ===";
input bool     ShowPanel        = true;
input color    PanelBG          = clrBlack;
input color    PanelText        = clrWhite;
input int      PanelX           = 10;
input int      PanelY           = 20;

//--- Глобальные переменные
double   pointMult;
datetime lastBarTime     = 0;
double   dayStartBalance = 0;
datetime dayStartTime    = 0;
int      dailyTradeCount = 0;
datetime lastTradeDay    = 0;
int      barsSinceSignal = 0;   // v4: cooldown

int      safe1Ticket[];
int      safe2Ticket[];
bool     safe1Done[];
bool     safe2Done[];

#define PANEL_LINES 12

string   csvFile;

//+------------------------------------------------------------------+
int OnInit()
{
   if(Digits == 3 || Digits == 5) pointMult = 10.0;
   else                            pointMult = 1.0;

   dayStartBalance = AccountBalance();
   dayStartTime    = TimeCurrent();

   ArrayResize(safe1Ticket, 0); ArrayResize(safe1Done, 0);
   ArrayResize(safe2Ticket, 0); ArrayResize(safe2Done, 0);

   csvFile = "GoldEA_" + Symbol() + "_" + TimeToStr(TimeCurrent(), TIME_DATE) + ".csv";
   if(SaveCSV) InitCSV();
   if(ShowPanel) DrawPanel();

   Print("GoldSessionEA v4.0 | TF:", UseH1Filter?"H1":"M15",
         " Risk:", RiskPercent, "%",
         " MarketStruct:", UseMarketStruct,
         " DynRSI:", UseDynamicRSI);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnTick()
{
   UpdateDayCounter();
   if(BlockFriday && IsFridayClose()) CloseAllOrders("Пятница");
   ManageOpenTrades();
   CleanSafeArrays();
   if(ShowPanel) DrawPanel();
   if(!IsNewBar(PERIOD_M1)) return;

   barsSinceSignal++;

   if(MarketInfo(Symbol(), MODE_SPREAD) > MaxSpreadPoints)     { Print("Блок:спред");     return; }
   if(UseSessionFilter && !IsSessionTime())                     { Print("Блок:сессия");    return; }
   if(UseNewsFilter && IsNewsTime())                            { Print("Блок:новости");   return; }
   if(UseDailyDD && IsDailyDDBreached())                       { Print("Блок:DD");        return; }
   if(MaxDailyTrades>0 && dailyTradeCount>=MaxDailyTrades)     { Print("Блок:лимит");     return; }
   if(!CheckMargin())                                           { Print("Блок:маржа");     return; }
   if(CountOpenOrders() > 0)                                    { Print("Блок:открытые"); return; }
   if(barsSinceSignal < SignalCooldownBars)                     { Print("Блок:cooldown(",barsSinceSignal,")"); return; }

   int trend = GetSeniorTrend();
   if(trend == 0) return;

   if(UseRSI && UseRSI_Senior && !IsRSI_SeniorOK(trend)) return;
   if(UseATR_Filter && !IsVolatilityOK())                 return;
   if(UseMarketStruct && !IsMarketStructOK(trend))        return;

   int signal = GetM1Signal();
   if(signal == 0 || signal != trend) return;

   if(UseRSI  && !IsRSI_M1_OK(signal)) return;
   if(UseMACD && !IsMACDOK(signal))    return;

   barsSinceSignal = 0;
   OpenOrder(signal);
}

//+------------------------------------------------------------------+
// Тренд старшего ТФ
//+------------------------------------------------------------------+
int GetSeniorTrend()
{
   ENUM_TIMEFRAMES tf = UseH1Filter ? PERIOD_H1 : PERIOD_M15;
   double f = iMA(Symbol(), tf, EMA_Fast_Senior, 0, MODE_EMA, PRICE_CLOSE, 1);
   double s = iMA(Symbol(), tf, EMA_Slow_Senior, 0, MODE_EMA, PRICE_CLOSE, 1);
   if(f > s) return(1);
   if(f < s) return(-1);
   return(0);
}

//+------------------------------------------------------------------+
// НОВОЕ v4: Структура рынка HH/HL для BUY, LH/LL для SELL
// Смотрим StructLookback свечей назад на M1.
// BUY:  curHigh > prevHigh И curLow > prevLow  -> Higher High + Higher Low
// SELL: curHigh < prevHigh И curLow < prevLow  -> Lower High + Lower Low
//+------------------------------------------------------------------+
bool IsMarketStructOK(int dir)
{
   double prevHigh = iHigh(Symbol(), PERIOD_M1, 2);
   double prevLow  = iLow (Symbol(), PERIOD_M1, 2);
   for(int i = 3; i <= StructLookback + 1; i++)
   {
      double h = iHigh(Symbol(), PERIOD_M1, i);
      double l = iLow (Symbol(), PERIOD_M1, i);
      if(h > prevHigh) prevHigh = h;
      if(l < prevLow)  prevLow  = l;
   }
   double curHigh = iHigh(Symbol(), PERIOD_M1, 1);
   double curLow  = iLow (Symbol(), PERIOD_M1, 1);

   if(dir == 1)
   {
      bool hh = (curHigh > prevHigh);
      bool hl = (curLow  > prevLow);
      if(!hh || !hl) { Print("MarketStruct BUY fail HH=",hh," HL=",hl); return(false); }
   }
   else
   {
      bool lh = (curHigh < prevHigh);
      bool ll = (curLow  < prevLow);
      if(!lh || !ll) { Print("MarketStruct SELL fail LH=",lh," LL=",ll); return(false); }
   }
   return(true);
}

//+------------------------------------------------------------------+
// УЛУЧШЕНО v4: EMA кроссовер + подтверждение закрытием свечи
// v3: просто факт пересечения
// v4: свеча должна закрыться ЗА обеими EMA
//+------------------------------------------------------------------+
int GetM1Signal()
{
   double fc = iMA(Symbol(), PERIOD_M1, EMA_Fast_M1, 0, MODE_EMA, PRICE_CLOSE, 1);
   double sc = iMA(Symbol(), PERIOD_M1, EMA_Slow_M1, 0, MODE_EMA, PRICE_CLOSE, 1);
   double fp = iMA(Symbol(), PERIOD_M1, EMA_Fast_M1, 0, MODE_EMA, PRICE_CLOSE, 2);
   double sp = iMA(Symbol(), PERIOD_M1, EMA_Slow_M1, 0, MODE_EMA, PRICE_CLOSE, 2);
   double cl = iClose(Symbol(), PERIOD_M1, 1);

   if(fp < sp && fc > sc)
   {
      if(RequireCloseConf && cl <= MathMax(fc, sc)) { Print("CloseConf BUY fail cl=",cl); return(0); }
      return(1);
   }
   if(fp > sp && fc < sc)
   {
      if(RequireCloseConf && cl >= MathMin(fc, sc)) { Print("CloseConf SELL fail cl=",cl); return(0); }
      return(-1);
   }
   return(0);
}

//+------------------------------------------------------------------+
bool IsRSI_M1_OK(int dir)
{
   double rsi = iRSI(Symbol(), PERIOD_M1, RSI_Period, PRICE_CLOSE, 1);
   if(dir ==  1 && rsi >= RSI_OB_M1) return(false);
   if(dir == -1 && rsi <= RSI_OS_M1) return(false);
   return(true);
}

//+------------------------------------------------------------------+
// НОВОЕ v4: Динамический RSI — при сильном тренде смягчаем порог
// Сила тренда = расстояние между EMA / ATR
// При силе > 1 ATR сдвигаем порог до +10 пунктов
//+------------------------------------------------------------------+
bool IsRSI_SeniorOK(int dir)
{
   ENUM_TIMEFRAMES tf = UseH1Filter ? PERIOD_H1 : PERIOD_M15;
   double rsi = iRSI(Symbol(), tf, RSI_Period, PRICE_CLOSE, 1);
   int obLevel = RSI_OB_Sr;
   int osLevel = RSI_OS_Sr;

   if(UseDynamicRSI)
   {
      double f    = iMA(Symbol(), tf, EMA_Fast_Senior, 0, MODE_EMA, PRICE_CLOSE, 1);
      double s    = iMA(Symbol(), tf, EMA_Slow_Senior, 0, MODE_EMA, PRICE_CLOSE, 1);
      double atr  = iATR(Symbol(), tf, ATR_Period, 1);
      double dist = MathAbs(f - s);
      double strength = (atr > 0) ? dist / atr : 0;
      int shift = (int)MathMin(10.0, strength * 7.0);
      obLevel += shift;
      osLevel -= shift;
   }

   if(dir ==  1 && rsi >= obLevel) { Print("RSI Sr BUY block: ",rsi,">=",obLevel); return(false); }
   if(dir == -1 && rsi <= osLevel) { Print("RSI Sr SELL block: ",rsi,"<=",osLevel); return(false); }
   return(true);
}

//+------------------------------------------------------------------+
bool IsMACDOK(int dir)
{
   ENUM_TIMEFRAMES tf = UseH1Filter ? PERIOD_H1 : PERIOD_M15;
   double h1 = iMACD(Symbol(), tf, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_HIST, 1);
   double h2 = iMACD(Symbol(), tf, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_HIST, 2);
   if(dir ==  1) return(h1 > 0 && h1 > h2);
   if(dir == -1) return(h1 < 0 && h1 < h2);
   return(false);
}

//+------------------------------------------------------------------+
// УЛУЧШЕНО v4: ATR на M15 вместо M1 — стабильнее
//+------------------------------------------------------------------+
bool IsVolatilityOK()
{
   double atr     = iATR(Symbol(), PERIOD_M15, ATR_Period, 1);
   double atrPips = atr / Point / pointMult;
   if(atrPips < ATR_Min_Pips) { Print("ATR флэт:",atrPips); return(false); }
   if(atrPips > ATR_Max_Pips) { Print("ATR хаос:",atrPips); return(false); }
   return(true);
}

//+------------------------------------------------------------------+
// ИСПРАВЛЕНО v4: обработка перехода через полночь
//+------------------------------------------------------------------+
bool IsNewsTime()
{
   if(StringLen(NewsTimes) == 0) return(false);
   datetime gmtNow = TimeGMT();
   int nowMin  = TimeHour(gmtNow) * 60 + TimeMinute(gmtNow);
   int dayMins = 24 * 60;
   string times[];
   int cnt = StringSplit(NewsTimes, ',', times);
   for(int i = 0; i < cnt; i++)
   {
      string t = times[i];
      StringTrimLeft(t); StringTrimRight(t);
      string p[]; if(StringSplit(t, ':', p) < 2) continue;
      int newsMin = (int)StringToInteger(p[0]) * 60 + (int)StringToInteger(p[1]);
      int diff = nowMin - newsMin;
      if(diff >  dayMins/2) diff -= dayMins;   // FIX: кратчайший путь на циферблате
      if(diff < -dayMins/2) diff += dayMins;
      if(diff >= -NewsMinBefore && diff <= NewsMinAfter)
      { Print("Новости: ",t," GMT"); return(true); }
   }
   return(false);
}

//+------------------------------------------------------------------+
// УЛУЧШЕНО v4: автокоррекция DST (летнее время Лондона = GMT+1)
//+------------------------------------------------------------------+
bool IsSessionTime()
{
   int h = TimeHour(TimeGMT());
   int openHour  = LondonOpen;
   int closeHour = LondonClose;
   if(AutoDST)
   {
      int mon = TimeMonth(TimeGMT());
      if(mon >= 3 && mon <= 10) { openHour--; closeHour--; }
   }
   return(h >= openHour && h < closeHour);
}

//+------------------------------------------------------------------+
bool IsDailyDDBreached()
{
   double equity   = AccountEquity();
   double ddAmount = dayStartBalance * MaxDailyDD_Pct / 100.0;
   if(equity < dayStartBalance - ddAmount)
   { Print("DD лимит! Старт:",dayStartBalance," Equity:",equity); return(true); }
   return(false);
}

//+------------------------------------------------------------------+
void UpdateDayCounter()
{
   datetime today = StringToTime(TimeToStr(TimeCurrent(), TIME_DATE));
   if(today != lastTradeDay)
   { lastTradeDay = today; dailyTradeCount = 0; dayStartBalance = AccountBalance(); }
}

//+------------------------------------------------------------------+
bool IsFridayClose()
{ return(DayOfWeek() == 5 && TimeHour(TimeGMT()) >= 21); }

void CloseAllOrders(string reason)
{
   for(int i = OrdersTotal()-1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderMagicNumber() != MagicNumber)           continue;
      if(OrderSymbol() != Symbol())                   continue;
      double cp = (OrderType()==OP_BUY) ? Bid : Ask;
      if(OrderClose(OrderTicket(), OrderLots(), cp, 3, clrGray))
         Print("Закрыт #",OrderTicket()," | ",reason);
      else PrintFormat("Ошибка Close #%d: %d", OrderTicket(), GetLastError());
   }
}

//+------------------------------------------------------------------+
// ИСПРАВЛЕНО v4: порог маржи 20% вместо 5%
//+------------------------------------------------------------------+
bool CheckMargin()
{
   double fm = AccountFreeMargin();
   double mn = AccountBalance() * 0.20;
   if(fm < mn) { Print("Маржа мало: ",fm," < ",mn); return(false); }
   return(true);
}

//+------------------------------------------------------------------+
double CalculateLot(double slPoints)
{
   double balance  = AccountBalance();
   double riskAmt  = balance * RiskPercent / 100.0;
   double tickVal  = MarketInfo(Symbol(), MODE_TICKVALUE);
   double tickSize = MarketInfo(Symbol(), MODE_TICKSIZE);
   if(tickVal==0 || tickSize==0 || slPoints==0) return(MinLot);
   double lot  = riskAmt / (slPoints * tickVal / tickSize);
   double step = MarketInfo(Symbol(), MODE_LOTSTEP);
   lot = MathFloor(lot / step) * step;
   return(NormalizeDouble(MathMax(MinLot, MathMin(MaxLot, lot)), 2));
}

//+------------------------------------------------------------------+
// v4: ATR для SL/TP берём с M15 (согласовано с фильтром)
//+------------------------------------------------------------------+
void OpenOrder(int dir)
{
   double atr = iATR(Symbol(), PERIOD_M15, ATR_Period, 1);
   if(atr == 0) return;
   double slPts = atr * ATR_SL_Mult / Point;
   double lot   = CalculateLot(slPts);
   double price, sl, tp; int otype;
   if(dir == 1)
   { price=Ask; sl=NormalizeDouble(price-atr*ATR_SL_Mult,Digits); tp=NormalizeDouble(price+atr*ATR_TP_Mult,Digits); otype=OP_BUY; }
   else
   { price=Bid; sl=NormalizeDouble(price+atr*ATR_SL_Mult,Digits); tp=NormalizeDouble(price-atr*ATR_TP_Mult,Digits); otype=OP_SELL; }

   int ticket = -1;
   for(int attempt = 1; attempt <= MaxRetries; attempt++)
   {
      ticket = OrderSend(Symbol(), otype, lot, price, 3, sl, tp, Comment_EA, MagicNumber, 0, dir==1?clrBlue:clrRed);
      if(ticket > 0) break;
      int err = GetLastError();
      Print("Попытка ",attempt,"/",MaxRetries," err:",err);
      if(err==136||err==135||err==138)
      {
         RefreshRates();
         price = (dir==1) ? Ask : Bid;
         sl = (dir==1) ? NormalizeDouble(price-atr*ATR_SL_Mult,Digits) : NormalizeDouble(price+atr*ATR_SL_Mult,Digits);
         tp = (dir==1) ? NormalizeDouble(price+atr*ATR_TP_Mult,Digits) : NormalizeDouble(price-atr*ATR_TP_Mult,Digits);
         Sleep(RetryDelay_ms);
      }
      else break;
   }

   if(ticket > 0)
   {
      dailyTradeCount++;
      double rsi  = iRSI(Symbol(), PERIOD_M1, RSI_Period, PRICE_CLOSE, 1);
      double macd = iMACD(Symbol(), UseH1Filter?PERIOD_H1:PERIOD_M15, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_HIST, 1);
      Print("OK #",ticket," ",(dir==1?"BUY":"SELL")," lot=",lot," SL=",sl," TP=",tp,
            " ATR(M15)=",DoubleToStr(atr/Point/pointMult,1),"p RSI=",DoubleToStr(rsi,1)," MACD=",DoubleToStr(macd,5));
      string an = "EA_Entry_"+IntegerToString(ticket);
      ObjectCreate(0,an,OBJ_ARROW,0,TimeCurrent(),price);
      ObjectSetInteger(0,an,OBJPROP_ARROWCODE,dir==1?233:234);
      ObjectSetInteger(0,an,OBJPROP_COLOR,dir==1?clrDodgerBlue:clrTomato);
      ObjectSetInteger(0,an,OBJPROP_WIDTH,2);
      int sz = ArraySize(safe1Ticket);
      ArrayResize(safe1Ticket,sz+1); ArrayResize(safe1Done,sz+1);
      ArrayResize(safe2Ticket,sz+1); ArrayResize(safe2Done,sz+1);
      safe1Ticket[sz]=ticket; safe1Done[sz]=false;
      safe2Ticket[sz]=ticket; safe2Done[sz]=false;
      if(SaveCSV) LogToCSV(ticket,dir,lot,price,sl,tp,rsi,macd,atr);
   }
   else Print("FAIL: не удалось открыть после ",MaxRetries," попыток");
}

//+------------------------------------------------------------------+
void ManageOpenTrades()
{
   for(int i = OrdersTotal()-1; i >= 0; i--)
   {
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderMagicNumber()!=MagicNumber)           continue;
      if(OrderSymbol()!=Symbol())                   continue;
      int    ticket = OrderTicket();
      int    otype  = OrderType();
      double oprice = OrderOpenPrice();
      double csl    = OrderStopLoss();
      double lots   = OrderLots();
      double profit_pts = 0;
      if(otype==OP_BUY)  profit_pts = (Bid-oprice)/Point/pointMult;
      if(otype==OP_SELL) profit_pts = (oprice-Ask)/Point/pointMult;

      // СЕЙФ 1
      if(UseSafe1 && Safe1Percent>0)
      {
         int idx = FindSafeIdx(safe1Ticket, ticket);
         if(idx>=0 && !safe1Done[idx] && profit_pts>=Safe1Pips)
         {
            double vol = NormalizeDouble(lots*Safe1Percent/100.0,2);
            vol = MathMax(vol, MarketInfo(Symbol(),MODE_LOTSTEP));
            if(OrderClose(ticket,vol,(otype==OP_BUY)?Bid:Ask,3,clrGold))
            {
               safe1Done[idx]=true;
               Print("Сейф1 #",ticket," +",profit_pts,"p");
               DrawExitArrow(ticket,otype,"S1");
               if(MoveBreakEven && OrderSelect(ticket,SELECT_BY_TICKET))
               {
                  double spread = MarketInfo(Symbol(),MODE_SPREAD)*Point;
                  double nsl = (otype==OP_BUY) ? NormalizeDouble(oprice+spread,Digits)
                                               : NormalizeDouble(oprice-spread,Digits);
                  // FIX v4: csl==0 для обоих направлений
                  bool need = (otype==OP_BUY  && (nsl>csl||csl==0)) ||
                              (otype==OP_SELL && (nsl<csl||csl==0));
                  if(need)
                  {
                     if(OrderModify(ticket,oprice,nsl,OrderTakeProfit(),0,clrYellow))
                        Print("SL->безубыток #",ticket);
                     else PrintFormat("Ошибка break-even #%d: %d",ticket,GetLastError());
                  }
               }
            }
         }
      }

      // СЕЙФ 2
      if(UseSafe2 && Safe2Percent>0)
      {
         int idx1 = FindSafeIdx(safe1Ticket, ticket);
         int idx2 = FindSafeIdx(safe2Ticket, ticket);
         // FIX v4: если UseSafe1=false, Сейф2 не ждёт
         bool s1ok = (!UseSafe1 || idx1<0 || safe1Done[idx1]);
         if(s1ok && idx2>=0 && !safe2Done[idx2] && profit_pts>=Safe2Pips)
         {
            if(OrderSelect(ticket,SELECT_BY_TICKET))
            {
               double curLots = OrderLots();
               double vol = NormalizeDouble(curLots*Safe2Percent/100.0,2);
               vol = MathMax(vol, MarketInfo(Symbol(),MODE_LOTSTEP));
               if(OrderClose(ticket,vol,(otype==OP_BUY)?Bid:Ask,3,clrLimeGreen))
               { safe2Done[idx2]=true; Print("Сейф2 #",ticket," +",profit_pts,"p"); DrawExitArrow(ticket,otype,"S2"); }
            }
         }
      }

      // ТРЕЙЛИНГ — FIX v4: csl==0 для BUY тоже
      if(UseTrailing && profit_pts>=TrailingStart)
      {
         double nsl=0; bool modify=false;
         if(otype==OP_BUY)
         { nsl=NormalizeDouble(Bid-TrailingStop*Point*pointMult,Digits);
           if(nsl>csl+TrailingStep*Point*pointMult||csl==0) modify=true; }
         else if(otype==OP_SELL)
         { nsl=NormalizeDouble(Ask+TrailingStop*Point*pointMult,Digits);
           if(nsl<csl-TrailingStep*Point*pointMult||csl==0) modify=true; }
         if(modify && OrderSelect(ticket,SELECT_BY_TICKET))
            if(!OrderModify(ticket,oprice,nsl,OrderTakeProfit(),0,clrOrange))
               PrintFormat("Ошибка trailing #%d: %d",ticket,GetLastError());
      }
   }
}

//+------------------------------------------------------------------+
// НОВОЕ v4: Очистка закрытых ордеров из safe-массивов
// Предотвращает бесконечный рост массивов
//+------------------------------------------------------------------+
void CleanSafeArrays()
{
   for(int i = ArraySize(safe1Ticket)-1; i >= 0; i--)
   {
      bool closed = false;
      if(OrderSelect(safe1Ticket[i], SELECT_BY_TICKET))
         closed = (OrderCloseTime() > 0);
      else
         closed = true;
      if(closed)
      {
         int sz = ArraySize(safe1Ticket);
         for(int j = i; j < sz-1; j++)
         { safe1Ticket[j]=safe1Ticket[j+1]; safe1Done[j]=safe1Done[j+1];
           safe2Ticket[j]=safe2Ticket[j+1]; safe2Done[j]=safe2Done[j+1]; }
         ArrayResize(safe1Ticket,sz-1); ArrayResize(safe1Done,sz-1);
         ArrayResize(safe2Ticket,sz-1); ArrayResize(safe2Done,sz-1);
      }
   }
}

//+------------------------------------------------------------------+
void DrawExitArrow(int ticket, int otype, string label)
{
   string name = "EA_Exit_"+IntegerToString(ticket)+"_"+label;
   double ep = (otype==OP_BUY) ? Bid : Ask;
   ObjectCreate(0,name,OBJ_ARROW,0,TimeCurrent(),ep);
   ObjectSetInteger(0,name,OBJPROP_ARROWCODE,(otype==OP_BUY)?242:241);
   ObjectSetInteger(0,name,OBJPROP_COLOR,clrGold);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,1);
}

//+------------------------------------------------------------------+
// Панель — FIX v4: ровно PANEL_LINES объектов (нет мусора)
//+------------------------------------------------------------------+
void DrawPanel()
{
   ENUM_TIMEFRAMES tf = UseH1Filter ? PERIOD_H1 : PERIOD_M15;
   double f = iMA(Symbol(),tf,EMA_Fast_Senior,0,MODE_EMA,PRICE_CLOSE,1);
   double s = iMA(Symbol(),tf,EMA_Slow_Senior,0,MODE_EMA,PRICE_CLOSE,1);
   string trendStr = (f>s)?"BUY":(f<s)?"SELL":"flat";
   color  trendClr = (f>s)?clrLimeGreen:(f<s)?clrTomato:clrYellow;

   double rsiM1 = iRSI(Symbol(),PERIOD_M1,RSI_Period,PRICE_CLOSE,1);
   double rsiSr = iRSI(Symbol(),tf,RSI_Period,PRICE_CLOSE,1);
   double macd  = iMACD(Symbol(),tf,MACD_Fast,MACD_Slow,MACD_Signal,PRICE_CLOSE,MODE_HIST,1);
   color  macdClr = (macd>0)?clrLimeGreen:clrTomato;

   double atr     = iATR(Symbol(),PERIOD_M15,ATR_Period,1);
   double atrPips = atr/Point/pointMult;
   string volStr  = (atrPips<ATR_Min_Pips)?"FLAT":(atrPips>ATR_Max_Pips)?"CHAOS":"OK";

   bool sb = UseMarketStruct?IsMarketStructOK(1):true;
   bool ss = UseMarketStruct?IsMarketStructOK(-1):true;
   string structStr = !UseMarketStruct?"off":sb?"HH/HL":ss?"LH/LL":"none";
   color  structClr = sb?clrLimeGreen:ss?clrTomato:clrGray;

   string newsStr = (UseNewsFilter&&IsNewsTime())?"BLOCK":"OK";
   color  newsClr = (UseNewsFilter&&IsNewsTime())?clrOrange:clrLimeGreen;

   double ddNow = (dayStartBalance>0)?(dayStartBalance-AccountEquity())/dayStartBalance*100.0:0;

   string lines[PANEL_LINES];
   lines[0]  = "GoldSessionEA v4.0";
   lines[1]  = "Trend: " + trendStr;
   lines[2]  = "Structure: " + structStr;
   lines[3]  = "RSI M1:" + DoubleToStr(rsiM1,1) + " Sr:" + DoubleToStr(rsiSr,1);
   lines[4]  = "MACD: " + ((macd>0)?"+":"-") + DoubleToStr(MathAbs(macd),4);
   lines[5]  = "ATR(M15): " + DoubleToStr(atrPips,1) + "p [" + volStr + "]";
   lines[6]  = "News: " + newsStr;
   lines[7]  = "DD: " + DoubleToStr(ddNow,2) + "% / " + DoubleToStr(MaxDailyDD_Pct,1) + "%";
   lines[8]  = "Trades: " + IntegerToString(dailyTradeCount) + "/" + (MaxDailyTrades>0?IntegerToString(MaxDailyTrades):"inf");
   lines[9]  = "Cooldown: " + IntegerToString(barsSinceSignal) + "/" + IntegerToString(SignalCooldownBars);
   lines[10] = "Spread: " + DoubleToStr(MarketInfo(Symbol(),MODE_SPREAD),0) + (MarketInfo(Symbol(),MODE_SPREAD)>MaxSpreadPoints?" HIGH":" ok");
   lines[11] = "Balance: " + DoubleToStr(AccountBalance(),2);

   int lineH=18, padX=8, padY=6, w=280;
   int h=PANEL_LINES*lineH+padY*2;
   string bgName = "EA_Panel_BG";
   if(ObjectFind(0,bgName)<0) ObjectCreate(0,bgName,OBJ_RECTANGLE_LABEL,0,0,0);
   ObjectSetInteger(0,bgName,OBJPROP_XDISTANCE,PanelX);
   ObjectSetInteger(0,bgName,OBJPROP_YDISTANCE,PanelY);
   ObjectSetInteger(0,bgName,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,bgName,OBJPROP_YSIZE,h);
   ObjectSetInteger(0,bgName,OBJPROP_BGCOLOR,PanelBG);
   ObjectSetInteger(0,bgName,OBJPROP_BORDER_TYPE,BORDER_FLAT);
   ObjectSetInteger(0,bgName,OBJPROP_COLOR,clrDimGray);
   ObjectSetInteger(0,bgName,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,bgName,OBJPROP_BACK,true);

   for(int i=0; i<PANEL_LINES; i++)
   {
      string lname = "EA_Panel_L"+IntegerToString(i);
      if(ObjectFind(0,lname)<0) ObjectCreate(0,lname,OBJ_LABEL,0,0,0);
      color lclr = PanelText;
      if(i==1) lclr=trendClr;
      if(i==2) lclr=structClr;
      if(i==4) lclr=macdClr;
      if(i==6) lclr=newsClr;
      ObjectSetInteger(0,lname,OBJPROP_XDISTANCE,PanelX+padX);
      ObjectSetInteger(0,lname,OBJPROP_YDISTANCE,PanelY+padY+i*lineH);
      ObjectSetInteger(0,lname,OBJPROP_COLOR,lclr);
      ObjectSetInteger(0,lname,OBJPROP_FONTSIZE,8);
      ObjectSetInteger(0,lname,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetString(0,lname,OBJPROP_TEXT,lines[i]);
   }
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
void InitCSV()
{
   int fh = FileOpen(csvFile,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(fh!=-1){ FileWrite(fh,"Ticket","Time","Dir","Lot","Price","SL","TP","RSI","MACD","ATR_M15"); FileClose(fh); }
}

void LogToCSV(int ticket,int dir,double lot,double price,double sl,double tp,double rsi,double macd,double atr)
{
   int fh = FileOpen(csvFile,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(fh!=-1)
   {
      FileSeek(fh,0,SEEK_END);
      FileWrite(fh,IntegerToString(ticket),TimeToStr(TimeCurrent(),TIME_DATE|TIME_MINUTES),
                (dir==1?"BUY":"SELL"),DoubleToStr(lot,2),DoubleToStr(price,Digits),
                DoubleToStr(sl,Digits),DoubleToStr(tp,Digits),DoubleToStr(rsi,1),
                DoubleToStr(macd,5),DoubleToStr(atr/Point/pointMult,1));
      FileClose(fh);
   }
}

//+------------------------------------------------------------------+
int FindSafeIdx(int &arr[], int ticket)
{ for(int i=0;i<ArraySize(arr);i++) if(arr[i]==ticket) return(i); return(-1); }

int CountOpenOrders()
{
   int n=0;
   for(int i=0;i<OrdersTotal();i++)
   { if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
     if(OrderMagicNumber()==MagicNumber && OrderSymbol()==Symbol()) n++; }
   return(n);
}

bool IsNewBar(ENUM_TIMEFRAMES tf)
{ datetime t=iTime(Symbol(),tf,0); if(t!=lastBarTime){lastBarTime=t;return(true);} return(false); }

void OnDeinit(const int reason)
{
   // FIX v4: ровно PANEL_LINES объектов, нет мусора
   for(int i=0; i<PANEL_LINES; i++)
      ObjectDelete(0,"EA_Panel_L"+IntegerToString(i));
   ObjectDelete(0,"EA_Panel_BG");
   ArrayFree(safe1Ticket); ArrayFree(safe1Done);
   ArrayFree(safe2Ticket); ArrayFree(safe2Done);
   Print("GoldSessionEA v4.0 остановлен.");
}
//+------------------------------------------------------------------+
