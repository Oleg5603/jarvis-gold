//+------------------------------------------------------------------+
//| MA2MA_MID.mq4                                                     |
//| Вход — пересечение SMA(FAST)/SMA(SLOW). Направление дополнительно |
//| фильтруется SMA(MID): BUY только если Close > MID, SELL — только  |
//| если Close < MID. ATR-фильтр: новые входы запрещены при ATR<ATR_MIN.|
//| SL ATR-based, перевод в БУ, TP = max(TP_BASE, TP_K*ATR).           |
//| Портирован из two_ma_mid_filter_be_atr.py — лучшая связка          |
//| форвард-теста (XAUUSD M1, 2023-2025):                              |
//| FAST=8 SLOW=30 MID=20 ATR_PER=14 ATR_MIN=0.5 SL_MULT=1.0            |
//| BE_TRIG=1.5 TP_K=3.0 TP_BASE=4.5 (уточнено tp_variants_test.py:     |
//| форвард PnL 41193.3 vs 39579.5 при TP_K=1.5, DD ниже)               |
//+------------------------------------------------------------------+
#property strict

input int    FAST          = 8;      // период быстрой SMA (сигнал входа)
input int    SLOW          = 30;     // период медленной SMA (сигнал входа)
input int    MID           = 20;     // период средней SMA (фильтр направления, FAST<MID<SLOW)
input int    ATR_PERIOD    = 14;     // период ATR
input double ATR_MIN       = 0.5;    // новые входы запрещены при ATR < ATR_MIN
input double SL_MULT       = 1.0;    // SL = entry -/+ SL_MULT * ATR
input double BE_TRIG_MULT  = 1.5;    // перевод в БУ при профите >= BE_TRIG_MULT * ATR
input double TP_K          = 3.0;    // TP-расстояние = TP_K * ATR
input double TP_BASE       = 4.5;    // минимальное TP-расстояние в валюте котировки ($)
input bool   USE_RISK_LOT  = true;   // true — лот по риску от депозита, false — фикс. LOTS
input double RISK_PERCENT  = 1.0;    // % от депозита на сделку (риск = SL_MULT*ATR)
input double LOTS          = 0.1;    // фикс. лот (если USE_RISK_LOT=false)
input int    SLIPPAGE      = 5;      // проскальзывание, пунктов
input int    MAGIC         = 20260716;

datetime lastBarTime = 0;
bool     beDone       = false;

int OnInit()
  {
   if(FAST >= SLOW)
     {
      Print("MA2MA_MID: FAST должен быть меньше SLOW");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(!(FAST < MID && MID < SLOW))
     {
      Print("MA2MA_MID: требуется FAST < MID < SLOW");
      return(INIT_PARAMETERS_INCORRECT);
     }
   return(INIT_SUCCEEDED);
  }

double MAFast(int shift) { return iMA(NULL, 0, FAST, 0, MODE_SMA, PRICE_CLOSE, shift); }
double MASlow(int shift) { return iMA(NULL, 0, SLOW, 0, MODE_SMA, PRICE_CLOSE, shift); }
double MAMid(int shift)  { return iMA(NULL, 0, MID,  0, MODE_SMA, PRICE_CLOSE, shift); }
double ATRNow(int shift) { return iATR(NULL, 0, ATR_PERIOD, shift); }

bool FindOpenOrder(int &ticket, int &type)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != MAGIC)
         continue;
      if(OrderType() != OP_BUY && OrderType() != OP_SELL)
         continue;
      ticket = OrderTicket();
      type   = OrderType();
      return(true);
     }
   return(false);
  }

void ClosePosition(int ticket, int type)
  {
   double px = (type == OP_BUY) ? Bid : Ask;
   if(!OrderSelect(ticket, SELECT_BY_TICKET))
      return;
   if(!OrderClose(ticket, OrderLots(), px, SLIPPAGE, clrRed))
      Print("MA2MA_MID: OrderClose failed, error=", GetLastError());
  }

//+------------------------------------------------------------------+
//| Лот по риску: RISK_PERCENT% от депозита на дистанцию SL (dist,   |
//| в валюте котировки). Нормализуется на шаг/мин/макс лота брокера. |
//+------------------------------------------------------------------+
double CalcLotByRisk(double distPrice)
  {
   if(distPrice <= 0)
      return(LOTS);
   double tickValue = MarketInfo(Symbol(), MODE_TICKVALUE);
   double tickSize   = MarketInfo(Symbol(), MODE_TICKSIZE);
   if(tickValue <= 0 || tickSize <= 0)
      return(LOTS);
   double riskMoney   = AccountBalance() * RISK_PERCENT / 100.0;
   double moneyPerLot = distPrice / tickSize * tickValue;   // риск на 1.0 лот
   if(moneyPerLot <= 0)
      return(LOTS);
   double lot = riskMoney / moneyPerLot;

   double lotStep = MarketInfo(Symbol(), MODE_LOTSTEP);
   double lotMin  = MarketInfo(Symbol(), MODE_MINLOT);
   double lotMax  = MarketInfo(Symbol(), MODE_MAXLOT);
   if(lotStep <= 0)
      lotStep = 0.01;
   lot = MathFloor(lot / lotStep) * lotStep;
   lot = MathMax(lotMin, MathMin(lotMax, lot));
   return(lot);
  }

void OpenPosition(int type, double atr)
  {
   double px, sl, tp, dist, tpDist, lot;
   if(type == OP_BUY)
     {
      px     = Ask;
      dist   = SL_MULT * atr;
      sl     = px - dist;
      tpDist = MathMax(TP_K * atr, TP_BASE);
      tp     = px + tpDist;
     }
   else
     {
      px     = Bid;
      dist   = SL_MULT * atr;
      sl     = px + dist;
      tpDist = MathMax(TP_K * atr, TP_BASE);
      tp     = px - tpDist;
     }
   lot = USE_RISK_LOT ? CalcLotByRisk(dist) : LOTS;
   int ticket = OrderSend(Symbol(), type, lot, px, SLIPPAGE, sl, tp, "MA2MA_MID", MAGIC, 0,
                           (type == OP_BUY) ? clrBlue : clrOrange);
   if(ticket < 0)
      Print("MA2MA_MID: OrderSend failed, error=", GetLastError());
   else
      beDone = false;
  }

void ManageBreakeven(int ticket, int type, double atr)
  {
   if(beDone)
      return;
   if(!OrderSelect(ticket, SELECT_BY_TICKET))
      return;
   double entry = OrderOpenPrice();
   if(type == OP_BUY)
     {
      if(Bid - entry >= BE_TRIG_MULT * atr)
        {
         if(!OrderModify(ticket, entry, entry, OrderTakeProfit(), 0, clrGreen))
            Print("MA2MA_MID: OrderModify(BE) failed, error=", GetLastError());
         beDone = true;
        }
     }
   else
     {
      if(entry - Ask >= BE_TRIG_MULT * atr)
        {
         if(!OrderModify(ticket, entry, entry, OrderTakeProfit(), 0, clrGreen))
            Print("MA2MA_MID: OrderModify(BE) failed, error=", GetLastError());
         beDone = true;
        }
     }
  }

void OnTick()
  {
   int ticket, type;
   bool hasOrder = FindOpenOrder(ticket, type);

   double atr = ATRNow(0);
   if(atr <= 0)
      return;

   if(hasOrder)
      ManageBreakeven(ticket, type, atr);

   if(Time[0] == lastBarTime)
      return;
   lastBarTime = Time[0];

   double fastPrev = MAFast(2), slowPrev = MASlow(2);
   double fastCur  = MAFast(1), slowCur  = MASlow(1);
   double midCur   = MAMid(1);
   double closeCur = Close[1];
   if(fastPrev == 0 || slowPrev == 0 || fastCur == 0 || slowCur == 0 || midCur == 0)
      return;

   bool crossUp = (fastPrev <= slowPrev && fastCur > slowCur);
   bool crossDn = (fastPrev >= slowPrev && fastCur < slowCur);

   if(!crossUp && !crossDn)
      return;

   bool allowAtr  = (atr >= ATR_MIN);
   bool dirOkBuy  = (closeCur > midCur);
   bool dirOkSell = (closeCur < midCur);

   hasOrder = FindOpenOrder(ticket, type);

   if(crossUp)
     {
      if(hasOrder && type == OP_SELL)
        {
         ClosePosition(ticket, type);
         hasOrder = false;
        }
      if(!hasOrder && allowAtr && dirOkBuy)
         OpenPosition(OP_BUY, atr);
     }
   else if(crossDn)
     {
      if(hasOrder && type == OP_BUY)
        {
         ClosePosition(ticket, type);
         hasOrder = false;
        }
      if(!hasOrder && allowAtr && dirOkSell)
         OpenPosition(OP_SELL, atr);
     }
  }
//+------------------------------------------------------------------+
