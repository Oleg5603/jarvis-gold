//+------------------------------------------------------------------+
//|                                              GoldSessionEA v3.0  |
//|                                        XAUUSD M1 — Полная версия |
//|                                                                   |
//|  БЛОКИ:                                                           |
//|  1. Стратегия: EMA тренд M15/H1 + вход M1                       |
//|  2. RSI-фильтр (M1 + старший ТФ)                                 |
//|  3. MACD-подтверждение                                            |
//|  4. ATR-фильтр волатильности (флэт / хаос)                       |
//|  5. Новостной фильтр                                              |
//|  6. Сейф x2 (два уровня частичного закрытия)                     |
//|  7. Трейлинг + безубыток                                          |
//|  8. Защита капитала (дневной DD%, макс сделок, пятница)           |
//|  9. Надёжность (реквоты, маржа, CSV-лог)                          |
//| 10. Панель на графике                                             |
//| 11. Стрелки входов/выходов                                        |
//+------------------------------------------------------------------+

#property copyright "GoldSessionEA v3.0"
#property version   "3.0"
#property strict

// Compatibility fixes
#ifndef MODE_HIST
#define MODE_HIST 2
#endif

//=== СТРАТЕГИЯ ===
input string   S1               = "=== СТРАТЕГИЯ ===";
input bool     UseH1Filter      = false;   // true=H1, false=M15 (старший ТФ)
input int      EMA_Fast_Senior  = 21;      // Быстрая EMA старшего ТФ
input int      EMA_Slow_Senior  = 55;      // Медленная EMA старшего ТФ
input int      EMA_Fast_M1      = 8;       // Быстрая EMA M1
input int      EMA_Slow_M1      = 21;      // Медленная EMA M1
input int      ATR_Period       = 14;      // Период ATR

//=== РИСК ===
input string   S2               = "=== РИСК ===";
input double   RiskPercent      = 1.0;     // Риск на сделку (% от депозита)
input double   ATR_SL_Mult      = 1.5;     // Множитель ATR → стоп-лосс
input double   ATR_TP_Mult      = 2.5;     // Множитель ATR → тейк-профит
input double   MinLot           = 0.01;
input double   MaxLot           = 10.0;

//=== СЕЙФ 1 ===
input string   S3               = "=== СЕЙФ 1 ===";
input bool     UseSafe1         = true;
input int      Safe1Pips        = 150;     // Пунктов для первого сейфа
input double   Safe1Percent     = 40.0;    // Закрыть % позиции
input bool     MoveBreakEven    = true;    // Перенести SL в безубыток

//=== СЕЙФ 2 ===
input string   S4               = "=== СЕЙФ 2 ===";
input bool     UseSafe2         = true;
input int      Safe2Pips        = 300;     // Пунктов для второго сейфа
input double   Safe2Percent     = 30.0;    // Закрыть ещё % остатка

//=== ТРЕЙЛИНГ ===
input string   S5               = "=== ТРЕЙЛИНГ ===";
input bool     UseTrailing      = true;
input int      TrailingStart    = 200;
input int      TrailingStep     = 50;
input int      TrailingStop     = 100;

//=== СЕССИИ ===
input string   S6               = "=== СЕССИИ ===";
input bool     UseSessionFilter = true;
input int      LondonOpen       = 8;       // GMT час
input int      LondonClose      = 17;      // GMT час
input bool     BlockFriday      = true;    // Закрыть сделки в пятницу в 21:00 GMT

//=== RSI ФИЛЬТР ===
input string   S7               = "=== RSI ФИЛЬТР ===";
input bool     UseRSI           = true;
input int      RSI_Period       = 14;
input int      RSI_OB_M1        = 70;      // Перекупленность M1
input int      RSI_OS_M1        = 30;      // Перепроданность M1
input int      RSI_OB_Sr        = 65;      // Перекупленность старшего ТФ
input int      RSI_OS_Sr        = 35;      // Перепроданность старшего ТФ
input bool     UseRSI_Senior    = true;

//=== MACD ФИЛЬТР ===
input string   S8               = "=== MACD ФИЛЬТР ===";
input bool     UseMACD          = true;
input int      MACD_Fast        = 12;
input int      MACD_Slow        = 26;
input int      MACD_Signal      = 9;
// Для BUY: MACD гистограмма > 0 (или растёт)
// Для SELL: MACD гистограмма < 0 (или падает)

//=== ATR ФИЛЬТР ВОЛАТИЛЬНОСТИ ===
input string   S9               = "=== ATR ВОЛАТИЛЬНОСТЬ ===";
input bool     UseATR_Filter    = true;
input double   ATR_Min_Pips     = 5.0;     // Мин ATR в пипсах (флэт — не торгуем)
input double   ATR_Max_Pips     = 80.0;    // Макс ATR в пипсах (хаос — не торгуем)

//=== НОВОСТНОЙ ФИЛЬТР ===
input string   S10              = "=== НОВОСТНОЙ ФИЛЬТР ===";
input bool     UseNewsFilter    = true;
input int      NewsMinBefore    = 30;
input int      NewsMinAfter     = 30;
input string   NewsTimes        = "08:30,12:30,14:00,18:00,20:00"; // GMT

//=== ЗАЩИТА КАПИТАЛА ===
input string   S11              = "=== ЗАЩИТА КАПИТАЛА ===";
input bool     UseDailyDD       = true;
input double   MaxDailyDD_Pct   = 3.0;     // Макс дневная просадка (% от баланса)
input int      MaxDailyTrades   = 5;        // Макс сделок в день (0=выкл)

//=== ФИЛЬТРЫ / НАДЁЖНОСТЬ ===
input string   S12              = "=== ФИЛЬТРЫ / НАДЁЖНОСТЬ ===";
input int      MaxSpreadPoints  = 30;
input int      MaxRetries       = 3;        // Попыток при реквоте
input int      RetryDelay_ms    = 500;      // Пауза между попытками (мс)
input bool     SaveCSV          = true;     // Логировать сделки в CSV
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
datetime lastBarTime   = 0;
double   dayStartBalance = 0;
datetime dayStartTime    = 0;
int      dailyTradeCount = 0;
datetime lastTradeDay    = 0;

// Сейф-флаги
int      safe1Ticket[];
int      safe2Ticket[];
bool     safe1Done[];
bool     safe2Done[];

// Имя CSV-файла
string   csvFile;

//+------------------------------------------------------------------+
//| Инициализация                                                    |
//+------------------------------------------------------------------+
int OnInit()
{
   if(Digits == 3 || Digits == 5) pointMult = 10.0;
   else                            pointMult = 1.0;

   dayStartBalance = AccountBalance();
   dayStartTime    = TimeCurrent();

   ArrayResize(safe1Ticket, 0); ArrayResize(safe1Done, 0);
   ArrayResize(safe2Ticket, 0); ArrayResize(safe2Done, 0);

   csvFile = "GoldEA_" + Symbol() + "_" +
             TimeToStr(TimeCurrent(), TIME_DATE) + ".csv";

   if(SaveCSV) InitCSV();
   if(ShowPanel) DrawPanel();

   Print("GoldSessionEA v3.0 запущен | ТФ: ", UseH1Filter?"H1":"M15",
         " | Риск: ", RiskPercent, "%");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Основной тик                                                     |
//+------------------------------------------------------------------+
void OnTick()
{
   static bool firstTick = true;
   if(firstTick)
   {
      Print("GoldSessionEA v3.0 OnTick active | SessionFilter=", UseSessionFilter,
            " NewsFilter=", UseNewsFilter,
            " MaxDailyTrades=", MaxDailyTrades,
            " UseDailyDD=", UseDailyDD);
      firstTick = false;
   }

   // Обновление дневного счётчика
   UpdateDayCounter();

   // Закрытие в пятницу вечером
   if(BlockFriday && IsFridayClose()) CloseAllOrders("Пятница — закрытие");

   // Управление открытыми позициями
   ManageOpenTrades();

   // Обновление панели
   if(ShowPanel) DrawPanel();

   // Только на новой свече M1
   if(!IsNewBar(PERIOD_M1)) return;

   // --- Предварительные проверки ---
   if(MarketInfo(Symbol(), MODE_SPREAD) > MaxSpreadPoints)
   {
      Print("Блокировка: спред > MaxSpreadPoints");
      return;
   }
   if(UseSessionFilter && !IsSessionTime())
   {
      Print("Блокировка: вне торговой сессии GMT=", TimeToStr(TimeGMT(), TIME_SECONDS));
      return;
   }
   if(UseNewsFilter && IsNewsTime())
   {
      Print("Блокировка: новостной фильтр");
      return;
   }
   if(UseDailyDD && IsDailyDDBreached())
   {
      Print("Блокировка: дневная просадка достигнута");
      return;
   }
   if(MaxDailyTrades > 0 && dailyTradeCount >= MaxDailyTrades)
   {
      Print("Блокировка: достигнут лимит сделок за день");
      return;
   }
   if(!CheckMargin())
   {
      Print("Блокировка: недостаточно маржи");
      return;
   }
   if(CountOpenOrders() > 0)
   {
      Print("Блокировка: уже есть открытые ордера");
      return;
   }

   // --- Сигналы ---
   int trend = GetSeniorTrend();
   if(trend == 0) return;

   if(UseRSI && UseRSI_Senior && !IsRSI_SeniorOK(trend)) return;
   if(UseATR_Filter && !IsVolatilityOK())                 return;

   int signal = GetM1Signal();
   if(signal == 0 || signal != trend) return;

   if(UseRSI  && !IsRSI_M1_OK(signal))  return;
   if(UseMACD && !IsMACDOK(signal))      return;

   OpenOrder(signal);
}

//+------------------------------------------------------------------+
//| Тренд на старшем ТФ                                             |
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
//| Сигнал на M1                                                    |
//+------------------------------------------------------------------+
int GetM1Signal()
{
   double fc = iMA(Symbol(), PERIOD_M1, EMA_Fast_M1, 0, MODE_EMA, PRICE_CLOSE, 1);
   double sc = iMA(Symbol(), PERIOD_M1, EMA_Slow_M1, 0, MODE_EMA, PRICE_CLOSE, 1);
   double fp = iMA(Symbol(), PERIOD_M1, EMA_Fast_M1, 0, MODE_EMA, PRICE_CLOSE, 2);
   double sp = iMA(Symbol(), PERIOD_M1, EMA_Slow_M1, 0, MODE_EMA, PRICE_CLOSE, 2);
   if(fp < sp && fc > sc) return(1);
   if(fp > sp && fc < sc) return(-1);
   return(0);
}

//+------------------------------------------------------------------+
//| RSI-фильтр M1                                                   |
//+------------------------------------------------------------------+
bool IsRSI_M1_OK(int dir)
{
   double rsi = iRSI(Symbol(), PERIOD_M1, RSI_Period, PRICE_CLOSE, 1);
   if(dir ==  1 && rsi >= RSI_OB_M1) return(false);
   if(dir == -1 && rsi <= RSI_OS_M1) return(false);
   return(true);
}

//+------------------------------------------------------------------+
//| RSI-фильтр старшего ТФ                                          |
//+------------------------------------------------------------------+
bool IsRSI_SeniorOK(int dir)
{
   ENUM_TIMEFRAMES tf = UseH1Filter ? PERIOD_H1 : PERIOD_M15;
   double rsi = iRSI(Symbol(), tf, RSI_Period, PRICE_CLOSE, 1);
   if(dir ==  1 && rsi >= RSI_OB_Sr) return(false);
   if(dir == -1 && rsi <= RSI_OS_Sr) return(false);
   return(true);
}

//+------------------------------------------------------------------+
//| MACD-подтверждение                                              |
//| BUY:  гистограмма > 0 И растёт (моментум вверх)                |
//| SELL: гистограмма < 0 И падает                                  |
//+------------------------------------------------------------------+
bool IsMACDOK(int dir)
{
   ENUM_TIMEFRAMES tf = UseH1Filter ? PERIOD_H1 : PERIOD_M15;
   double hist1 = iMACD(Symbol(), tf, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_HIST, 1);
   double hist2 = iMACD(Symbol(), tf, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_HIST, 2);

   if(dir ==  1) return(hist1 > 0 && hist1 > hist2);  // Растущий бычий моментум
   if(dir == -1) return(hist1 < 0 && hist1 < hist2);  // Растущий медвежий моментум
   return(false);
}

//+------------------------------------------------------------------+
//| ATR-фильтр волатильности                                        |
//+------------------------------------------------------------------+
bool IsVolatilityOK()
{
   double atr      = iATR(Symbol(), PERIOD_M1, ATR_Period, 1);
   double atrPips  = atr / Point / pointMult;
   if(atrPips < ATR_Min_Pips) return(false);  // Флэт
   if(atrPips > ATR_Max_Pips) return(false);  // Хаос/гэп
   return(true);
}

//+------------------------------------------------------------------+
//| Новостной фильтр                                                |
//+------------------------------------------------------------------+
bool IsNewsTime()
{
   if(StringLen(NewsTimes) == 0) return(false);
   datetime gmtNow  = TimeGMT();
   int nowMin = TimeHour(gmtNow) * 60 + TimeMinute(gmtNow);
   string times[];
   int cnt = StringSplit(NewsTimes, ',', times);
   for(int i = 0; i < cnt; i++)
   {
      string t = times[i];
      StringTrimLeft(t); StringTrimRight(t);
      string p[]; if(StringSplit(t, ':', p) < 2) continue;
      int newsMin = (int)StringToInteger(p[0]) * 60 + (int)StringToInteger(p[1]);
      int diff    = nowMin - newsMin;
      if(diff >= -NewsMinBefore && diff <= NewsMinAfter)
      {
         Print("Новостной фильтр активен (новость в ", t, " GMT)");
         return(true);
      }
   }
   return(false);
}

//+------------------------------------------------------------------+
//| Защита капитала — дневная просадка                              |
//+------------------------------------------------------------------+
bool IsDailyDDBreached()
{
   double equity    = AccountEquity();
   double ddAmount  = dayStartBalance * MaxDailyDD_Pct / 100.0;
   if(equity < dayStartBalance - ddAmount)
   {
      Print("Дневной лимит просадки достигнут! Старт: ", dayStartBalance,
            " Текущий equity: ", equity);
      return(true);
   }
   return(false);
}

//+------------------------------------------------------------------+
//| Обновление дневного счётчика                                    |
//+------------------------------------------------------------------+
void UpdateDayCounter()
{
   datetime today = StringToTime(TimeToStr(TimeCurrent(), TIME_DATE));
   if(today != lastTradeDay)
   {
      lastTradeDay    = today;
      dailyTradeCount = 0;
      dayStartBalance = AccountBalance();
   }
}

//+------------------------------------------------------------------+
//| Закрытие позиций в пятницу 21:00 GMT                           |
//+------------------------------------------------------------------+
bool IsFridayClose()
{
   datetime gmt = TimeGMT();
   return(DayOfWeek() == 5 && TimeHour(gmt) >= 21);
}

void CloseAllOrders(string reason)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderMagicNumber() != MagicNumber)           continue;
      if(OrderSymbol() != Symbol())                   continue;
      double closePrice = (OrderType() == OP_BUY) ? Bid : Ask;
      if(OrderClose(OrderTicket(), OrderLots(), closePrice, 3, clrGray))
         Print("Закрыт ордер #", OrderTicket(), " | Причина: ", reason);
      else
         PrintFormat("Ошибка OrderClose #%d: %d", OrderTicket(), GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Проверка маржи                                                  |
//+------------------------------------------------------------------+
bool CheckMargin()
{
   double freeMargin = AccountFreeMargin();
   double minMargin  = AccountBalance() * 0.05; // Минимум 5% свободной маржи
   if(freeMargin < minMargin)
   {
      Print("Недостаточно маржи: ", freeMargin);
      return(false);
   }
   return(true);
}

//+------------------------------------------------------------------+
//| Расчёт лота                                                     |
//+------------------------------------------------------------------+
double CalculateLot(double slPoints)
{
   double balance   = AccountBalance();
   double riskAmt   = balance * RiskPercent / 100.0;
   double tickVal   = MarketInfo(Symbol(), MODE_TICKVALUE);
   double tickSize  = MarketInfo(Symbol(), MODE_TICKSIZE);
   if(tickVal == 0 || tickSize == 0 || slPoints == 0) return(MinLot);
   double lot = riskAmt / (slPoints * tickVal / tickSize);
   double step = MarketInfo(Symbol(), MODE_LOTSTEP);
   lot = MathFloor(lot / step) * step;
   return(NormalizeDouble(MathMax(MinLot, MathMin(MaxLot, lot)), 2));
}

//+------------------------------------------------------------------+
//| Открытие ордера с retry при реквоте                             |
//+------------------------------------------------------------------+
void OpenOrder(int dir)
{
   double atr = iATR(Symbol(), PERIOD_M1, ATR_Period, 1);
   if(atr == 0) return;

   double slPts = atr * ATR_SL_Mult / Point;
   double lot   = CalculateLot(slPts);
   double price, sl, tp;
   int    otype;

   if(dir == 1)
   {
      price = Ask;
      sl    = NormalizeDouble(price - atr * ATR_SL_Mult, Digits);
      tp    = NormalizeDouble(price + atr * ATR_TP_Mult, Digits);
      otype = OP_BUY;
   }
   else
   {
      price = Bid;
      sl    = NormalizeDouble(price + atr * ATR_SL_Mult, Digits);
      tp    = NormalizeDouble(price - atr * ATR_TP_Mult, Digits);
      otype = OP_SELL;
   }

   int ticket = -1;
   for(int attempt = 1; attempt <= MaxRetries; attempt++)
   {
      ticket = OrderSend(Symbol(), otype, lot, price, 3, sl, tp,
                         Comment_EA, MagicNumber, 0,
                         dir == 1 ? clrBlue : clrRed);
      if(ticket > 0) break;

      int err = GetLastError();
      Print("Попытка ", attempt, "/", MaxRetries, " — ошибка: ", err);

      // Реквота или устаревшая цена — обновляем цену и пробуем снова
      if(err == 136 || err == 135 || err == 138)
      {
         RefreshRates();
         price = (dir == 1) ? Ask : Bid;
         sl    = (dir == 1) ? NormalizeDouble(price - atr * ATR_SL_Mult, Digits)
                            : NormalizeDouble(price + atr * ATR_SL_Mult, Digits);
         tp    = (dir == 1) ? NormalizeDouble(price + atr * ATR_TP_Mult, Digits)
                            : NormalizeDouble(price - atr * ATR_TP_Mult, Digits);
         Sleep(RetryDelay_ms);
      }
      else break; // Другая ошибка — не повторяем
   }

   if(ticket > 0)
   {
      dailyTradeCount++;
      double rsi  = iRSI(Symbol(), PERIOD_M1, RSI_Period, PRICE_CLOSE, 1);
      double macd = iMACD(Symbol(), UseH1Filter?PERIOD_H1:PERIOD_M15,
                          MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_HIST, 1);
      Print("✓ Ордер #", ticket, " ", (dir==1?"BUY":"SELL"),
            " лот=", lot, " SL=", sl, " TP=", tp,
            " ATR=", DoubleToStr(atr/Point/pointMult,1), "p",
            " RSI=", DoubleToStr(rsi,1),
            " MACD=", DoubleToStr(macd,5));

      // Стрелка на графике
      string arrowName = "EA_Entry_" + IntegerToString(ticket);
      int arrowCode = (dir == 1) ? 233 : 234;
      color arrowClr = (dir == 1) ? clrDodgerBlue : clrTomato;
      ObjectCreate(0, arrowName, OBJ_ARROW, 0, TimeCurrent(), price);
      ObjectSetInteger(0, arrowName, OBJPROP_ARROWCODE, arrowCode);
      ObjectSetInteger(0, arrowName, OBJPROP_COLOR, arrowClr);
      ObjectSetInteger(0, arrowName, OBJPROP_WIDTH, 2);

      // Регистрация для сейфов
      int sz = ArraySize(safe1Ticket);
      ArrayResize(safe1Ticket, sz+1); ArrayResize(safe1Done, sz+1);
      ArrayResize(safe2Ticket, sz+1); ArrayResize(safe2Done, sz+1);
      safe1Ticket[sz] = ticket; safe1Done[sz] = false;
      safe2Ticket[sz] = ticket; safe2Done[sz] = false;

      if(SaveCSV) LogToCSV(ticket, dir, lot, price, sl, tp, rsi, macd, atr);
   }
   else Print("✗ Не удалось открыть ордер после ", MaxRetries, " попыток");
}

//+------------------------------------------------------------------+
//| Управление открытыми ордерами                                   |
//+------------------------------------------------------------------+
void ManageOpenTrades()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderMagicNumber() != MagicNumber)           continue;
      if(OrderSymbol() != Symbol())                   continue;

      int    ticket  = OrderTicket();
      int    otype   = OrderType();
      double oprice  = OrderOpenPrice();
      double csl     = OrderStopLoss();
      double lots    = OrderLots();

      double profit_pts = 0;
      if(otype == OP_BUY)  profit_pts = (Bid - oprice) / Point / pointMult;
      if(otype == OP_SELL) profit_pts = (oprice - Ask) / Point / pointMult;

      // === СЕЙФ 1 ===
      if(UseSafe1 && Safe1Percent > 0)
      {
         int idx = FindSafeIdx(safe1Ticket, ticket);
         if(idx >= 0 && !safe1Done[idx] && profit_pts >= Safe1Pips)
         {
            double vol = NormalizeDouble(lots * Safe1Percent / 100.0, 2);
            vol = MathMax(vol, MarketInfo(Symbol(), MODE_LOTSTEP));
            if(OrderClose(ticket, vol, (otype==OP_BUY)?Bid:Ask, 3, clrGold))
            {
               safe1Done[idx] = true;
               Print("Сейф1 #", ticket, ": закрыто ", Safe1Percent, "% при +", profit_pts, "p");
               DrawExitArrow(ticket, otype, "S1");

               // Безубыток
               if(MoveBreakEven && OrderSelect(ticket, SELECT_BY_TICKET))
               {
                  double spread = MarketInfo(Symbol(), MODE_SPREAD) * Point;
                  double nsl = (otype==OP_BUY) ? NormalizeDouble(oprice+spread, Digits)
                                               : NormalizeDouble(oprice-spread, Digits);
                  bool need = (otype==OP_BUY && nsl>csl) || (otype==OP_SELL && nsl<csl);
                  if(need)
                  {
                     if(OrderModify(ticket, oprice, nsl, OrderTakeProfit(), 0, clrYellow))
                        Print("SL → безубыток #", ticket);
                     else
                        PrintFormat("Ошибка OrderModify (break-even) #%d: %d", ticket, GetLastError());
                  }
               }
            }
         }
      }

      // === СЕЙФ 2 ===
      if(UseSafe2 && Safe2Percent > 0)
      {
         int idx1 = FindSafeIdx(safe1Ticket, ticket);
         int idx2 = FindSafeIdx(safe2Ticket, ticket);
         bool s1ok = (idx1 < 0 || safe1Done[idx1]); // Сейф2 только после Сейфа1
         if(s1ok && idx2 >= 0 && !safe2Done[idx2] && profit_pts >= Safe2Pips)
         {
            if(OrderSelect(ticket, SELECT_BY_TICKET))
            {
               double curLots = OrderLots();
               double vol = NormalizeDouble(curLots * Safe2Percent / 100.0, 2);
               vol = MathMax(vol, MarketInfo(Symbol(), MODE_LOTSTEP));
               if(OrderClose(ticket, vol, (otype==OP_BUY)?Bid:Ask, 3, clrLimeGreen))
               {
                  safe2Done[idx2] = true;
                  Print("Сейф2 #", ticket, ": закрыто ", Safe2Percent, "% при +", profit_pts, "p");
                  DrawExitArrow(ticket, otype, "S2");
               }
            }
         }
      }

      // === ТРЕЙЛИНГ ===
      if(UseTrailing && profit_pts >= TrailingStart)
      {
         double nsl = 0; bool modify = false;
         if(otype == OP_BUY)
         {
            nsl = NormalizeDouble(Bid - TrailingStop * Point * pointMult, Digits);
            if(nsl > csl + TrailingStep * Point * pointMult) modify = true;
         }
         else if(otype == OP_SELL)
         {
            nsl = NormalizeDouble(Ask + TrailingStop * Point * pointMult, Digits);
            if(nsl < csl - TrailingStep * Point * pointMult || csl == 0) modify = true;
         }
         if(modify && OrderSelect(ticket, SELECT_BY_TICKET))
         {
            if(!OrderModify(ticket, oprice, nsl, OrderTakeProfit(), 0, clrOrange))
               PrintFormat("Ошибка OrderModify (trailing) #%d: %d", ticket, GetLastError());
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Рисуем стрелку выхода                                           |
//+------------------------------------------------------------------+
void DrawExitArrow(int ticket, int otype, string label)
{
   string name = "EA_Exit_" + IntegerToString(ticket) + "_" + label;
   double exitPrice = (otype == OP_BUY) ? Bid : Ask;
   int arrowCode = (otype == OP_BUY) ? 242 : 241;
   ObjectCreate(0, name, OBJ_ARROW, 0, TimeCurrent(), exitPrice);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, arrowCode);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrGold);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
}

//+------------------------------------------------------------------+
//| Информационная панель на графике                                |
//+------------------------------------------------------------------+
void DrawPanel()
{
   ENUM_TIMEFRAMES tf = UseH1Filter ? PERIOD_H1 : PERIOD_M15;

   // Тренд
   double f = iMA(Symbol(), tf, EMA_Fast_Senior, 0, MODE_EMA, PRICE_CLOSE, 1);
   double s = iMA(Symbol(), tf, EMA_Slow_Senior, 0, MODE_EMA, PRICE_CLOSE, 1);
   string trendStr  = (f > s) ? "▲ БЫЧИЙ" : (f < s) ? "▼ МЕДВЕЖИЙ" : "→ НЕЙТРАЛЬНЫЙ";
   color  trendClr  = (f > s) ? clrLimeGreen : (f < s) ? clrTomato : clrYellow;

   // RSI
   double rsiM1 = iRSI(Symbol(), PERIOD_M1, RSI_Period, PRICE_CLOSE, 1);
   double rsiSr = iRSI(Symbol(), tf, RSI_Period, PRICE_CLOSE, 1);
   string rsiM1Str = DoubleToStr(rsiM1, 1);
   string rsiSrStr = DoubleToStr(rsiSr, 1);

   // MACD
   double macd = iMACD(Symbol(), tf, MACD_Fast, MACD_Slow, MACD_Signal,
                       PRICE_CLOSE, MODE_HIST, 1);
   string macdStr = (macd > 0) ? "▲ " + DoubleToStr(macd,4) : "▼ " + DoubleToStr(macd,4);
   color  macdClr = (macd > 0) ? clrLimeGreen : clrTomato;

   // ATR
   double atr     = iATR(Symbol(), PERIOD_M1, ATR_Period, 1);
   double atrPips = atr / Point / pointMult;
   string atrStr  = DoubleToStr(atrPips, 1) + "p";
   string volStr  = (atrPips < ATR_Min_Pips) ? "ФЛЭТ" :
                    (atrPips > ATR_Max_Pips) ? "ХАОС" : "НОРМА";

   // Новости
   string newsStr = (UseNewsFilter && IsNewsTime()) ? "⚠ БЛОК" : "✓ ОК";
   color  newsClr = (UseNewsFilter && IsNewsTime()) ? clrOrange : clrLimeGreen;

   // Дневная статистика
   double ddNow = (dayStartBalance > 0) ?
                  (dayStartBalance - AccountEquity()) / dayStartBalance * 100.0 : 0;
   string ddStr = DoubleToStr(ddNow, 2) + "% (лимит " + DoubleToStr(MaxDailyDD_Pct,1) + "%)";
   string tradesStr = IntegerToString(dailyTradeCount) + "/" +
                      (MaxDailyTrades>0 ? IntegerToString(MaxDailyTrades) : "∞");

   // Спред
   double spread = MarketInfo(Symbol(), MODE_SPREAD);
   string spreadStr = DoubleToStr(spread, 0) + (spread > MaxSpreadPoints ? " ⚠" : " ✓");

   string lines[];
   int linesCount = 10;
   ArrayResize(lines, linesCount);
   lines[0] = "══ GoldSessionEA v3.0 ══";
   lines[1] = StringConcatenate("Тренд (", UseH1Filter?"H1":"M15", "): ", trendStr);
   lines[2] = StringConcatenate("RSI M1: ", rsiM1Str, "  |  RSI ", UseH1Filter?"H1":"M15", ": ", rsiSrStr);
   lines[3] = StringConcatenate("MACD: ", macdStr);
   lines[4] = StringConcatenate("ATR: ", atrStr, "  [", volStr, "]");
   lines[5] = StringConcatenate("Новости: ", newsStr);
   lines[6] = StringConcatenate("Просадка дня: ", ddStr);
   lines[7] = StringConcatenate("Сделок сегодня: ", tradesStr);
   lines[8] = StringConcatenate("Спред: ", spreadStr, " пт");
   lines[9] = StringConcatenate("Баланс: ", DoubleToStr(AccountBalance(), 2));

   int lineH = 18;
   int padX  = 8;
   int padY  = 6;
   int w     = 260;
   int h     = ArraySize(lines) * lineH + padY * 2;

   // Фон
   string bgName = "EA_Panel_BG";
   if(ObjectFind(0, bgName) < 0)
      ObjectCreate(0, bgName, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, bgName, OBJPROP_XDISTANCE,  PanelX);
   ObjectSetInteger(0, bgName, OBJPROP_YDISTANCE,  PanelY);
   ObjectSetInteger(0, bgName, OBJPROP_XSIZE,      w);
   ObjectSetInteger(0, bgName, OBJPROP_YSIZE,      h);
   ObjectSetInteger(0, bgName, OBJPROP_BGCOLOR,    PanelBG);
   ObjectSetInteger(0, bgName, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, bgName, OBJPROP_COLOR,      clrDimGray);
   ObjectSetInteger(0, bgName, OBJPROP_CORNER,     CORNER_LEFT_UPPER);
   ObjectSetInteger(0, bgName, OBJPROP_BACK,       true);

   for(int i = 0; i < ArraySize(lines); i++)
   {
      string lname = "EA_Panel_L" + IntegerToString(i);
      if(ObjectFind(0, lname) < 0)
         ObjectCreate(0, lname, OBJ_LABEL, 0, 0, 0);

      color lclr = PanelText;
      if(i == 1) lclr = trendClr;
      if(i == 3) lclr = macdClr;
      if(i == 5) lclr = newsClr;

      ObjectSetInteger(0, lname, OBJPROP_XDISTANCE, PanelX + padX);
      ObjectSetInteger(0, lname, OBJPROP_YDISTANCE, PanelY + padY + i * lineH);
      ObjectSetInteger(0, lname, OBJPROP_COLOR,     lclr);
      ObjectSetInteger(0, lname, OBJPROP_FONTSIZE,  8);
      ObjectSetInteger(0, lname, OBJPROP_CORNER,    CORNER_LEFT_UPPER);
      ObjectSetString (0, lname, OBJPROP_TEXT,      lines[i]);
   }

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| CSV-логирование                                                  |
//+------------------------------------------------------------------+
void InitCSV()
{
   int fh = FileOpen(csvFile, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(fh != -1)
   {
      FileWrite(fh, "Ticket","Time","Direction","Lot","Price","SL","TP","RSI","MACD","ATR");
      FileClose(fh);
   }
}

void LogToCSV(int ticket, int dir, double lot, double price,
              double sl, double tp, double rsi, double macd, double atr)
{
   int fh = FileOpen(csvFile, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(fh != -1)
   {
      FileSeek(fh, 0, SEEK_END);
      FileWrite(fh,
         IntegerToString(ticket),
         TimeToStr(TimeCurrent(), TIME_DATE|TIME_MINUTES),
         (dir==1?"BUY":"SELL"),
         DoubleToStr(lot, 2),
         DoubleToStr(price, Digits),
         DoubleToStr(sl, Digits),
         DoubleToStr(tp, Digits),
         DoubleToStr(rsi, 1),
         DoubleToStr(macd, 5),
         DoubleToStr(atr/Point/pointMult, 1)
      );
      FileClose(fh);
   }
}

//+------------------------------------------------------------------+
//| Вспомогательные функции                                         |
//+------------------------------------------------------------------+
int FindSafeIdx(int &arr[], int ticket)
{
   for(int i = 0; i < ArraySize(arr); i++)
      if(arr[i] == ticket) return(i);
   return(-1);
}

int CountOpenOrders()
{
   int n = 0;
   for(int i = 0; i < OrdersTotal(); i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderMagicNumber()==MagicNumber && OrderSymbol()==Symbol()) n++;
   }
   return(n);
}

bool IsSessionTime()
{
   int h = TimeHour(TimeGMT());
   return(h >= LondonOpen && h < LondonClose);
}

bool IsNewBar(ENUM_TIMEFRAMES tf)
{
   datetime t = iTime(Symbol(), tf, 0);
   if(t != lastBarTime) { lastBarTime = t; return(true); }
   return(false);
}

void OnDeinit(const int reason)
{
   // Удаляем объекты панели
   for(int i = 0; i < 12; i++)
      ObjectDelete(0, "EA_Panel_L" + IntegerToString(i));
   ObjectDelete(0, "EA_Panel_BG");

   ArrayFree(safe1Ticket); ArrayFree(safe1Done);
   ArrayFree(safe2Ticket); ArrayFree(safe2Done);
   Print("GoldSessionEA v3.0 остановлен.");
}
//+------------------------------------------------------------------+
