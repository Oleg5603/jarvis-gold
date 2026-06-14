//+------------------------------------------------------------------+
//|                                         Sniper_RM_EA_v1.mq4    |
//|     EA на основе индикатора Sniper_RM — Азиатская сессия       |
//+------------------------------------------------------------------+
#property copyright "2026"
#property version   "1.00"
#property strict

//=== ВХОДНЫЕ ПАРАМЕТРЫ ===

//--- Сигнал
input int    InpSwingBars    = 5;      // Баров для подтверждения экстремума
input int    InpLevelBars    = 200;    // Баров для поиска уровней
input double InpLevelBuffer  = 8.0;   // Буфер у уровня (пунктов)

//--- Тейк-профит
input double InpZoneBuffer   = 12.0;  // Отступ от уровня в % (10-15)

//--- Риск
input double InpRiskPercent  = 1.0;   // Риск на сделку % (1-5)
input double InpMinLot       = 0.01;  // Минимальный лот
input double InpMaxLot       = 10.0;  // Максимальный лот

//--- Стоп-лосс
input double InpSLBuffer     = 5.0;   // Буфер SL за экстремум (пунктов)

//--- Сессия (UTC)
input int    InpAsiaStart    = 0;     // Начало Азии (час UTC)
input int    InpAsiaEnd      = 8;     // Конец Азии (час UTC)
input int    InpGMTOffset    = 0;     // Смещение брокерского времени от UTC

//--- Управление позицией
input bool   InpTrailing     = true;  // Трейлинг-стоп
input double InpTrailStart   = 15.0;  // Трейлинг: начало (пунктов прибыли)
input double InpTrailStep    = 5.0;   // Трейлинг: шаг (пунктов)
input bool   InpBreakEven    = true;  // Перенос в безубыток
input double InpBEStart      = 10.0;  // Безубыток: начало (пунктов прибыли)

//--- Фильтры
input int    InpMaxSpread    = 30;    // Максимальный спред (пунктов)
input int    InpMagic        = 202601; // Magic number

//=== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ===
datetime g_lastBar   = 0;
double   g_resistance= 0;
double   g_support   = DBL_MAX;

//+------------------------------------------------------------------+
int OnInit()
{
   Print("Sniper_RM EA v1.0 запущен. Символ: ", Symbol(),
         " | Риск: ", InpRiskPercent, "%");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason) {}

//+------------------------------------------------------------------+
void OnTick()
{
   // Работаем только на открытии нового бара
   if(!IsNewBar()) return;

   // Обновляем ключевые уровни
   UpdateLevels();

   // Управляем открытыми позициями
   ManagePositions();

   // Фильтр спреда
   if((int)MarketInfo(Symbol(), MODE_SPREAD) > InpMaxSpread) return;

   // Фильтр сессии — только Азия
   if(!IsAsiaSession()) return;

   // Уже есть открытая позиция по этому инструменту?
   if(HasOpenPosition()) return;

   // Ищем сигнал на подтверждённых барах
   CheckSignals();
}

//+------------------------------------------------------------------+
// Определение нового бара
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime curBar = iTime(Symbol(), Period(), 0);
   if(curBar == g_lastBar) return false;
   g_lastBar = curBar;
   return true;
}

//+------------------------------------------------------------------+
// Азиатская сессия
//+------------------------------------------------------------------+
bool IsAsiaSession()
{
   datetime utcTime = TimeCurrent() - InpGMTOffset * 3600;
   MqlDateTime dt;
   TimeToStruct(utcTime, dt);
   int h = dt.hour;
   return (h >= InpAsiaStart && h < InpAsiaEnd);
}

//+------------------------------------------------------------------+
// Обновление ключевых уровней
//+------------------------------------------------------------------+
void UpdateLevels()
{
   g_resistance = 0;
   g_support    = DBL_MAX;
   int total    = iBars(Symbol(), Period());
   int lvEnd    = MathMax(0, total - InpLevelBars);

   for(int k = 1; k <= InpLevelBars && k < total; k++)
   {
      double h = iHigh(Symbol(), Period(), k);
      double l = iLow(Symbol(), Period(), k);
      if(h > g_resistance) g_resistance = h;
      if(l < g_support)    g_support    = l;
   }
}

//+------------------------------------------------------------------+
// Проверка сигналов
//+------------------------------------------------------------------+
void CheckSignals()
{
   int signalBar = InpSwingBars + 1; // Первый подтверждённый бар

   double lvBuf = InpLevelBuffer * _Point;

   //--- SELL: swing high у сопротивления
   if(IsSwingHigh(signalBar))
   {
      double swHigh = iHigh(Symbol(), Period(), signalBar);
      if(swHigh >= g_resistance - lvBuf)
      {
         double entry = iOpen(Symbol(), Period(), 0);
         double sl    = swHigh + InpSLBuffer * _Point;
         double tp    = CalcTP(false, entry, sl);

         if(tp > 0 && tp < entry)
            OpenTrade(OP_SELL, entry, sl, tp);
      }
   }

   //--- BUY: swing low у поддержки
   if(IsSwingLow(signalBar))
   {
      double swLow = iLow(Symbol(), Period(), signalBar);
      if(swLow <= g_support + lvBuf)
      {
         double entry = iOpen(Symbol(), Period(), 0);
         double sl    = swLow - InpSLBuffer * _Point;
         double tp    = CalcTP(true, entry, sl);

         if(tp > 0 && tp > entry)
            OpenTrade(OP_BUY, entry, sl, tp);
      }
   }
}

//+------------------------------------------------------------------+
// Расчёт тейк-профита (до следующего уровня минус зона %)
//+------------------------------------------------------------------+
double CalcTP(bool isBuy, double entry, double sl)
{
   double range  = g_resistance - g_support;
   if(range <= 0) return 0;

   double zoneOff = range * (InpZoneBuffer / 100.0);
   double tp;

   if(isBuy)
   {
      // Цель — сопротивление минус зона
      tp = g_resistance - zoneOff;
      if(tp <= entry) return 0; // TP должен быть выше входа
   }
   else
   {
      // Цель — поддержка плюс зона
      tp = g_support + zoneOff;
      if(tp >= entry) return 0; // TP должен быть ниже входа
   }

   // Минимальный R:R 1:1
   double rr = MathAbs(tp - entry) / MathAbs(entry - sl);
   if(rr < 1.0) return 0;

   return NormalizeDouble(tp, Digits);
}

//+------------------------------------------------------------------+
// Расчёт лота на основе риска
//+------------------------------------------------------------------+
double CalcLotSize(double entry, double sl)
{
   double riskAmount = AccountBalance() * InpRiskPercent / 100.0;
   double slDist     = MathAbs(entry - sl);
   if(slDist <= 0) return InpMinLot;

   double tickVal = MarketInfo(Symbol(), MODE_TICKVALUE);
   double tickSz  = MarketInfo(Symbol(), MODE_TICKSIZE);
   if(tickVal <= 0 || tickSz <= 0) return InpMinLot;

   double lot = riskAmount / (slDist / tickSz * tickVal);
   lot = MathFloor(lot / MarketInfo(Symbol(), MODE_LOTSTEP))
         * MarketInfo(Symbol(), MODE_LOTSTEP);
   lot = MathMax(InpMinLot, MathMin(InpMaxLot, lot));

   return NormalizeDouble(lot, 2);
}

//+------------------------------------------------------------------+
// Открытие сделки
//+------------------------------------------------------------------+
void OpenTrade(int type, double entry, double sl, double tp)
{
   double lot    = CalcLotSize(entry, sl);
   double price  = (type == OP_BUY)
                   ? MarketInfo(Symbol(), MODE_ASK)
                   : MarketInfo(Symbol(), MODE_BID);

   sl = NormalizeDouble(sl, Digits);
   tp = NormalizeDouble(tp, Digits);

   string comment = "Sniper_RM " + (type == OP_BUY ? "BUY" : "SELL");
   int ticket = OrderSend(Symbol(), type, lot, price, 3, sl, tp,
                          comment, InpMagic, 0, type == OP_BUY ? clrBlue : clrRed);

   if(ticket < 0)
      Print("Ошибка открытия сделки: ", GetLastError(),
            " | Тип: ", (type==OP_BUY?"BUY":"SELL"),
            " | Лот: ", lot,
            " | SL: ", sl, " | TP: ", tp);
   else
      Print("Открыта сделка #", ticket,
            " | ", (type==OP_BUY?"BUY":"SELL"),
            " | Лот: ", lot,
            " | SL: ", sl, " | TP: ", tp);
}

//+------------------------------------------------------------------+
// Управление открытыми позициями (трейлинг, безубыток)
//+------------------------------------------------------------------+
void ManagePositions()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol())   continue;
      if(OrderMagicNumber() != InpMagic) continue;

      double openPrice = OrderOpenPrice();
      double curSL     = OrderStopLoss();
      double newSL     = curSL;
      double bid       = MarketInfo(Symbol(), MODE_BID);
      double ask       = MarketInfo(Symbol(), MODE_ASK);

      if(OrderType() == OP_BUY)
      {
         double profit = bid - openPrice;

         // Безубыток
         if(InpBreakEven && curSL < openPrice &&
            profit >= InpBEStart * _Point)
            newSL = openPrice + _Point;

         // Трейлинг
         if(InpTrailing && profit >= InpTrailStart * _Point)
         {
            double trail = bid - InpTrailStep * _Point;
            if(trail > newSL) newSL = trail;
         }

         if(newSL > curSL && newSL < bid)
            ModifySL(newSL);
      }
      else if(OrderType() == OP_SELL)
      {
         double profit = openPrice - ask;

         // Безубыток
         if(InpBreakEven && curSL > openPrice &&
            profit >= InpBEStart * _Point)
            newSL = openPrice - _Point;

         // Трейлинг
         if(InpTrailing && profit >= InpTrailStart * _Point)
         {
            double trail = ask + InpTrailStep * _Point;
            if(trail < newSL || newSL == 0) newSL = trail;
         }

         if((newSL < curSL || curSL == 0) && newSL > ask)
            ModifySL(newSL);
      }
   }
}

//+------------------------------------------------------------------+
void ModifySL(double newSL)
{
   if(!OrderModify(OrderTicket(), OrderOpenPrice(),
                   NormalizeDouble(newSL, Digits),
                   OrderTakeProfit(), 0, clrOrange))
      Print("Ошибка модификации SL: ", GetLastError());
}

//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() == Symbol() && OrderMagicNumber() == InpMagic)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
bool IsSwingHigh(int bar)
{
   for(int j = 1; j <= InpSwingBars; j++)
   {
      if(iHigh(Symbol(),Period(),bar+j) >= iHigh(Symbol(),Period(),bar)) return false;
      if(iHigh(Symbol(),Period(),bar-j) >= iHigh(Symbol(),Period(),bar)) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
bool IsSwingLow(int bar)
{
   for(int j = 1; j <= InpSwingBars; j++)
   {
      if(iLow(Symbol(),Period(),bar+j) <= iLow(Symbol(),Period(),bar)) return false;
      if(iLow(Symbol(),Period(),bar-j) <= iLow(Symbol(),Period(),bar)) return false;
   }
   return true;
}
//+------------------------------------------------------------------+
