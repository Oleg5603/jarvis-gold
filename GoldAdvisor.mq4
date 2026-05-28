//+------------------------------------------------------------------+
//| GoldAdvisor.mq4                                                  |
//| Ложный пробой уровней + ATR волатильность + мультитаймфрейм     |
//| H1 тренд | H1+M15 уровни | M1 вход | Риск 1% | 50/25/25        |
//+------------------------------------------------------------------+
#property copyright "GoldAdvisor"
#property version   "1.0"
#property strict

//--- Входные параметры
input double RiskPercent    = 1.0;    // Риск на сделку (%)
input int    FastMA         = 50;     // Быстрая MA (H1)
input int    SlowMA         = 200;    // Медленная MA (H1)
input int    ATR_Period     = 14;     // Период ATR
input double ATR_Mult       = 1.5;    // Множитель ATR для фильтра волатильности
input double SL_ATR_Mult    = 2.0;    // SL = ATR * множитель
input double TP1_ATR_Mult   = 2.0;    // TP1 (закрываем 50%)
input double TP2_ATR_Mult   = 4.0;    // TP2 (закрываем 25%)
input double TP3_ATR_Mult   = 6.0;    // TP3 (финальные 25%)
input int    LevelLookback  = 20;     // Глубина поиска уровней (баров)
input double FakeLevelPts   = 5.0;    // Макс. пробой уровня (пунктов)
input bool   UseBreakEven   = true;   // Безубыток ВКЛ/ВЫКЛ
input bool   Scheme_50_50   = false;  // true=50/50, false=50/25/25
input int    Magic          = 202401; // Magic number
input string Comment_       = "GoldAdvisor";

double LotStep, MinLot, MaxLot, TickValue, TickSize;

int OnInit()
{
    LotStep   = MarketInfo(Symbol(), MODE_LOTSTEP);
    MinLot    = MarketInfo(Symbol(), MODE_MINLOT);
    MaxLot    = MarketInfo(Symbol(), MODE_MAXLOT);
    TickValue = MarketInfo(Symbol(), MODE_TICKVALUE);
    TickSize  = MarketInfo(Symbol(), MODE_TICKSIZE);
    Print("GoldAdvisor запущен. Риск: ", RiskPercent, "% | Безубыток: ", UseBreakEven ? "ВКЛ" : "ВЫКЛ");
    return INIT_SUCCEEDED;
}

void OnTick()
{
    ManagePositions();
    if (HasOpenPosition()) return;

    // Фильтр волатильности: ATR(M1) должен быть выше среднего
    double atr_m1     = iATR(Symbol(), PERIOD_M1, ATR_Period, 1);
    double atr_m1_avg = iATR(Symbol(), PERIOD_M1, ATR_Period * 3, 1);
    if (atr_m1 < atr_m1_avg * ATR_Mult) return;

    // Тренд на H1
    int trend = GetTrend();

    // Уровни H1 и M15
    double res_h1, sup_h1, res_m15, sup_m15;
    GetLevels(PERIOD_H1,  res_h1,  sup_h1);
    GetLevels(PERIOD_M15, res_m15, sup_m15);

    double nearest_res = MathMin(res_h1, res_m15);
    double nearest_sup = MathMax(sup_h1, sup_m15);
    double fake_pts    = FakeLevelPts * Point;

    // Ложный пробой сопротивления → SELL
    if (Bid > nearest_res && Ask < nearest_res + fake_pts)
    {
        OpenTrade(OP_SELL, atr_m1);
        return;
    }

    // Ложный пробой поддержки → BUY
    if (Ask < nearest_sup && Bid > nearest_sup - fake_pts)
    {
        OpenTrade(OP_BUY, atr_m1);
        return;
    }
}

//--- Тренд по EMA50/EMA200 на H1
int GetTrend()
{
    double mf = iMA(Symbol(), PERIOD_H1, FastMA, 0, MODE_EMA, PRICE_CLOSE, 1);
    double ms = iMA(Symbol(), PERIOD_H1, SlowMA, 0, MODE_EMA, PRICE_CLOSE, 1);
    if (mf > ms * 1.0001) return  1;
    if (mf < ms * 0.9999) return -1;
    return 0;
}

//--- Уровни: High/Low за LevelLookback баров
void GetLevels(int tf, double &res, double &sup)
{
    res = iHigh(Symbol(), tf, iHighest(Symbol(), tf, MODE_HIGH, LevelLookback, 1));
    sup = iLow (Symbol(), tf, iLowest (Symbol(), tf, MODE_LOW,  LevelLookback, 1));
}

//--- Расчёт лота по риску 1%
double CalcLot(double sl_points)
{
    if (sl_points <= 0 || TickValue <= 0 || TickSize <= 0) return MinLot;
    double risk_money = AccountBalance() * RiskPercent / 100.0;
    double sl_money   = (sl_points / TickSize) * TickValue;
    if (sl_money <= 0) return MinLot;
    double lot = MathFloor((risk_money / sl_money) / LotStep) * LotStep;
    return MathMax(MinLot, MathMin(MaxLot, lot));
}

//--- Открытие сделки
void OpenTrade(int type, double atr)
{
    double sl_pts = atr * SL_ATR_Mult;
    double lot    = CalcLot(sl_pts);
    double price  = (type == OP_BUY) ? Ask : Bid;
    double sl     = (type == OP_BUY) ? price - sl_pts              : price + sl_pts;
    double tp     = (type == OP_BUY) ? price + atr * TP3_ATR_Mult  : price - atr * TP3_ATR_Mult;

    int ticket = OrderSend(Symbol(), type, lot, price, 3, sl, tp, Comment_, Magic, 0, clrNONE);
    if (ticket < 0)
        Print("OpenTrade ошибка: ", GetLastError());
    else
        Print("Открыта сделка: ", (type == OP_BUY ? "BUY" : "SELL"), " лот=", lot, " SL=", sl, " TP=", tp);
}

//--- Есть ли открытая позиция
bool HasOpenPosition()
{
    for (int i = 0; i < OrdersTotal(); i++)
        if (OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
            if (OrderSymbol() == Symbol() && OrderMagicNumber() == Magic)
                return true;
    return false;
}

double NormalizeLot(double lot)
{
    return MathMax(MinLot, MathFloor(lot / LotStep) * LotStep);
}

//--- Управление позицией: PartialClose + BreakEven
void ManagePositions()
{
    double atr = iATR(Symbol(), PERIOD_M1, ATR_Period, 1);

    for (int i = OrdersTotal() - 1; i >= 0; i--)
    {
        if (!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
        if (OrderSymbol() != Symbol() || OrderMagicNumber() != Magic) continue;

        int    type       = OrderType();
        int    ticket     = OrderTicket();
        double open_price = OrderOpenPrice();
        double lots       = OrderLots();
        double sl         = OrderStopLoss();
        double tp         = OrderTakeProfit();
        double tp1, tp2;

        if (type == OP_BUY)
        {
            tp1 = open_price + atr * TP1_ATR_Mult;
            tp2 = open_price + atr * TP2_ATR_Mult;

            // TP1 достигнут: закрываем 50%
            if (Bid >= tp1 && sl < open_price)
            {
                double close_lot = NormalizeLot(lots * 0.5);
                if (close_lot >= MinLot)
                    OrderClose(ticket, close_lot, Bid, 3, clrGreen);

                // Безубыток
                if (UseBreakEven)
                {
                    double new_sl = open_price + atr * 0.3;
                    if (new_sl > sl)
                        OrderModify(ticket, open_price, new_sl, tp, 0, clrYellow);
                }
            }

            // TP2 достигнут: закрываем ещё 25% (схема 50/25/25)
            if (!Scheme_50_50 && Bid >= tp2 && sl < tp1)
            {
                double close_lot = NormalizeLot(OrderLots() * 0.5);
                if (close_lot >= MinLot)
                    OrderClose(ticket, close_lot, Bid, 3, clrGreen);

                // SL на уровень TP1
                if (tp1 > sl)
                    OrderModify(ticket, open_price, tp1, tp, 0, clrYellow);
            }
        }
        else if (type == OP_SELL)
        {
            tp1 = open_price - atr * TP1_ATR_Mult;
            tp2 = open_price - atr * TP2_ATR_Mult;

            // TP1 достигнут: закрываем 50%
            if (Ask <= tp1 && (sl > open_price || sl == 0))
            {
                double close_lot = NormalizeLot(lots * 0.5);
                if (close_lot >= MinLot)
                    OrderClose(ticket, close_lot, Ask, 3, clrGreen);

                // Безубыток
                if (UseBreakEven)
                {
                    double new_sl = open_price - atr * 0.3;
                    if (new_sl < sl || sl == 0)
                        OrderModify(ticket, open_price, new_sl, tp, 0, clrYellow);
                }
            }

            // TP2 достигнут: закрываем ещё 25% (схема 50/25/25)
            if (!Scheme_50_50 && Ask <= tp2 && (sl > tp1 || sl == 0))
            {
                double close_lot = NormalizeLot(OrderLots() * 0.5);
                if (close_lot >= MinLot)
                    OrderClose(ticket, close_lot, Ask, 3, clrGreen);

                // SL на уровень TP1
                if (tp1 < sl || sl == 0)
                    OrderModify(ticket, open_price, tp1, tp, 0, clrYellow);
            }
        }
    }
}
