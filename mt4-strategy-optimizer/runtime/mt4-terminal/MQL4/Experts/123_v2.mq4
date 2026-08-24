//+------------------------------------------------------------------+
//| 123_v2.mq4 - hardened MA cross + ATR Expert Advisor             |
//| Based on 123.20260814-113938.bak.mq4                            |
//+------------------------------------------------------------------+
#property strict
#property version "2.00"

input int FAST=8;
input int SLOW=30;
input int MID=20;
input ENUM_MA_METHOD MA_Method=MODE_SMA;

input bool USE_PRICE_FILTER=true;
input bool BUY_PRICE_BELOW_SLOW=true;

input int ATR_PERIOD=14;
input double ATR_MIN=0.5;
input double SL_MULT=1.0;

input bool USE_MA_GROWTH_FILTER=false;
input double MA_GROWTH_POINTS=0.5;
input int MA_GROWTH_BARS=3;
input bool USE_ATR_GROWTH_FILTER=false;
input double ATR_GROWTH_POINTS=0.5;
input int ATR_GROWTH_BARS=3;

input double BE_TRIG_MULT=1.5;
input double TP_K=3.0;
input double TP_BASE=4.5;

input bool USE_RISK_LOT=true;
input double RISK_PERCENT=1.0;
input double LOTS=0.1;

input int SLIPPAGE=5;
input int MAGIC=20260716;

// v2 safety controls
input double MAX_SPREAD_POINTS=0.0;       // 0 = disabled
input bool SKIP_IF_RISK_BELOW_MIN=true;   // do not exceed risk using broker min lot
input bool APPLY_GROWTH_TO_SELL=true;
input bool CLOSE_ON_OPPOSITE=true;

datetime lastBarTime=0;

double MAFast(int shift) { return(iMA(NULL,0,FAST,0,MA_Method,PRICE_CLOSE,shift)); }
double MAMid(int shift)  { return(iMA(NULL,0,MID,0,MA_Method,PRICE_CLOSE,shift)); }
double MASlow(int shift) { return(iMA(NULL,0,SLOW,0,MA_Method,PRICE_CLOSE,shift)); }
double ATRNow(int shift) { return(iATR(NULL,0,ATR_PERIOD,shift)); }

int OnInit()
{
   if(FAST<1 || MID<1 || SLOW<1 || ATR_PERIOD<1 || SL_MULT<=0.0 ||
      BE_TRIG_MULT<0.0 || TP_K<0.0 || TP_BASE<0.0 || LOTS<=0.0 ||
      RISK_PERCENT<=0.0 || MA_GROWTH_BARS<1 || ATR_GROWTH_BARS<1)
   {
      Print("123_v2: invalid input parameters");
      return(INIT_PARAMETERS_INCORRECT);
   }
   // Period ordering is intentionally not constrained. The optimizer may
   // evaluate any positive FAST, MID and SLOW combination.
   Print("123_v2 initialized: FAST=",FAST," MID=",MID," SLOW=",SLOW);
   return(INIT_SUCCEEDED);
}

bool EnoughBars()
{
   int need=MathMax(MathMax(FAST,MID),MathMax(SLOW,ATR_PERIOD));
   need=MathMax(need,MathMax(MA_GROWTH_BARS,ATR_GROWTH_BARS)+2);
   return(Bars>need+10);
}

double NormalizePrice(double value)
{
   return(NormalizeDouble(value,Digits));
}

int LotDigits(double step)
{
   if(step>=1.0) return(0);
   if(step>=0.1) return(1);
   if(step>=0.01) return(2);
   return(3);
}

bool SpreadAllowed()
{
   if(MAX_SPREAD_POINTS<=0.0) return(true);
   RefreshRates();
   return(((Ask-Bid)/Point)<=MAX_SPREAD_POINTS);
}

bool CheckMAGrowth(int direction)
{
   if(!USE_MA_GROWTH_FILTER) return(true);
   double first=MAFast(MA_GROWTH_BARS+1);
   double last=MAFast(1);
   if(first==0.0 || last==0.0) return(false);

   for(int i=1;i<=MA_GROWTH_BARS;i++)
   {
      double newer=MAFast(i);
      double older=MAFast(i+1);
      if(newer==0.0 || older==0.0) return(false);
      if(direction>0 && newer<=older) return(false);
      if(direction<0 && newer>=older) return(false);
   }
   return(direction*(last-first)/Point>=MA_GROWTH_POINTS);
}

bool CheckATRGrowth()
{
   if(!USE_ATR_GROWTH_FILTER) return(true);
   double first=ATRNow(ATR_GROWTH_BARS+1);
   double last=ATRNow(1);
   if(first<=0.0 || last<=0.0) return(false);
   for(int i=1;i<=ATR_GROWTH_BARS;i++)
   {
      double newer=ATRNow(i);
      double older=ATRNow(i+1);
      if(newer<=older) return(false);
   }
   return((last-first)/Point>=ATR_GROWTH_POINTS);
}

bool CheckPriceFilter(int type)
{
   if(!USE_PRICE_FILTER) return(true);
   double slow=MASlow(1);
   double closePrice=Close[1];
   if(slow==0.0) return(false);
   bool buyOk=BUY_PRICE_BELOW_SLOW ? closePrice<slow : closePrice>slow;
   return(type==OP_BUY ? buyOk : !buyOk);
}

bool FindOpenOrder(int &ticket,int &type)
{
   ticket=-1;
   type=-1;
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderSymbol()!=Symbol() || OrderMagicNumber()!=MAGIC) continue;
      if(OrderType()!=OP_BUY && OrderType()!=OP_SELL) continue;
      ticket=OrderTicket();
      type=OrderType();
      return(true);
   }
   return(false);
}

bool ClosePosition(int ticket)
{
   if(!OrderSelect(ticket,SELECT_BY_TICKET)) return(false);
   int type=OrderType();
   RefreshRates();
   double price=(type==OP_BUY ? Bid : Ask);
   ResetLastError();
   if(OrderClose(ticket,OrderLots(),price,SLIPPAGE,clrRed)) return(true);
   Print("123_v2: OrderClose failed ticket=",ticket," error=",GetLastError());
   return(false);
}

double CalcLotByRisk(double stopDistance)
{
   if(stopDistance<=0.0) return(0.0);
   double tickValue=MarketInfo(Symbol(),MODE_TICKVALUE);
   double tickSize=MarketInfo(Symbol(),MODE_TICKSIZE);
   double lotStep=MarketInfo(Symbol(),MODE_LOTSTEP);
   double minLot=MarketInfo(Symbol(),MODE_MINLOT);
   double maxLot=MarketInfo(Symbol(),MODE_MAXLOT);
   if(tickValue<=0.0 || tickSize<=0.0 || lotStep<=0.0 || minLot<=0.0) return(0.0);

   double riskMoney=AccountEquity()*RISK_PERCENT/100.0;
   double lossPerLot=stopDistance/tickSize*tickValue;
   if(lossPerLot<=0.0) return(0.0);
   double rawLot=riskMoney/lossPerLot;
   if(SKIP_IF_RISK_BELOW_MIN && rawLot<minLot) return(0.0);
   double lot=MathFloor(rawLot/lotStep+1e-8)*lotStep;
   lot=MathMax(minLot,MathMin(maxLot,lot));
   return(NormalizeDouble(lot,LotDigits(lotStep)));
}

bool PrepareStops(int type,double entry,double atr,double &sl,double &tp,double &distance)
{
   distance=SL_MULT*atr;
   double tpDistance=MathMax(TP_K*atr,TP_BASE);
   double brokerDistance=MarketInfo(Symbol(),MODE_STOPLEVEL)*Point;
   if(distance<brokerDistance) distance=brokerDistance;
   if(tpDistance<brokerDistance) tpDistance=brokerDistance;
   if(distance<=0.0 || tpDistance<=0.0) return(false);
   if(type==OP_BUY)
   {
      sl=NormalizePrice(entry-distance);
      tp=NormalizePrice(entry+tpDistance);
   }
   else
   {
      sl=NormalizePrice(entry+distance);
      tp=NormalizePrice(entry-tpDistance);
   }
   return(true);
}

bool OpenPosition(int type,double atr)
{
   if(!SpreadAllowed())
   {
      Print("123_v2: entry skipped because spread is too high");
      return(false);
   }
   RefreshRates();
   double entry=(type==OP_BUY ? Ask : Bid);
   double sl=0.0,tp=0.0,distance=0.0;
   if(!PrepareStops(type,entry,atr,sl,tp,distance)) return(false);
   double lot=USE_RISK_LOT ? CalcLotByRisk(distance) : LOTS;
   if(lot<=0.0)
   {
      Print("123_v2: entry skipped because safe lot cannot be calculated");
      return(false);
   }
   ResetLastError();
   int ticket=OrderSend(Symbol(),type,lot,entry,SLIPPAGE,sl,tp,"123_v2",MAGIC,0,
                        type==OP_BUY ? clrBlue : clrOrange);
   if(ticket<0)
   {
      Print("123_v2: OrderSend failed error=",GetLastError()," lot=",lot,
            " entry=",entry," sl=",sl," tp=",tp);
      return(false);
   }
   Print("123_v2: opened ticket=",ticket," type=",type," lot=",lot);
   return(true);
}

void ManageBreakeven(int ticket,int type,double atr)
{
   if(BE_TRIG_MULT<=0.0 || !OrderSelect(ticket,SELECT_BY_TICKET)) return;
   double entry=OrderOpenPrice();
   double currentSL=OrderStopLoss();
   bool alreadyDone=(type==OP_BUY ? currentSL>=entry : (currentSL>0.0 && currentSL<=entry));
   if(alreadyDone) return;
   RefreshRates();
   bool triggered=(type==OP_BUY ? Bid-entry : entry-Ask)>=BE_TRIG_MULT*atr;
   if(!triggered) return;

   double newSL=NormalizePrice(entry);
   double freeze=MarketInfo(Symbol(),MODE_FREEZELEVEL)*Point;
   if(type==OP_BUY && Bid-newSL<=freeze) return;
   if(type==OP_SELL && newSL-Ask<=freeze) return;
   ResetLastError();
   if(!OrderModify(ticket,entry,newSL,OrderTakeProfit(),0,clrGreen))
      Print("123_v2: breakeven failed ticket=",ticket," error=",GetLastError());
}

void ProcessSignal(int signalType,double atr)
{
   int ticket,type;
   bool hasOrder=FindOpenOrder(ticket,type);
   if(hasOrder && type!=signalType)
   {
      if(!CLOSE_ON_OPPOSITE) return;
      if(!ClosePosition(ticket)) return;
      hasOrder=FindOpenOrder(ticket,type);
   }
   if(hasOrder) return;

   int direction=(signalType==OP_BUY ? 1 : -1);
   bool growthOk=true;
   if(signalType==OP_BUY || APPLY_GROWTH_TO_SELL)
      growthOk=CheckMAGrowth(direction) && CheckATRGrowth();
   if(CheckPriceFilter(signalType) && growthOk) OpenPosition(signalType,atr);
}

void OnTick()
{
   if(!EnoughBars()) return;
   int ticket,type;
   if(FindOpenOrder(ticket,type)) ManageBreakeven(ticket,type,ATRNow(1));

   if(Time[0]==lastBarTime) return;
   lastBarTime=Time[0];

   double atr=ATRNow(1); // closed bar, consistent with the MA signal
   if(atr<=0.0 || atr<ATR_MIN) return;
   double fastPrev=MAFast(2),midPrev=MAMid(2);
   double fastNow=MAFast(1),midNow=MAMid(1);
   if(fastPrev==0.0 || midPrev==0.0 || fastNow==0.0 || midNow==0.0) return;

   bool crossUp=(fastPrev<=midPrev && fastNow>midNow);
   bool crossDown=(fastPrev>=midPrev && fastNow<midNow);
   if(crossUp) ProcessSignal(OP_BUY,atr);
   else if(crossDown) ProcessSignal(OP_SELL,atr);
}
//+------------------------------------------------------------------+
