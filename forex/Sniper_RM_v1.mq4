//+------------------------------------------------------------------+
//|                                              Sniper_RM_v1.mq4   |
//|          Reversal Moment + Session Zones + Key Levels           |
//+------------------------------------------------------------------+
#property copyright "2026"
#property version   "1.00"
#property strict
#property indicator_chart_window

//--- Inputs
input int    InpSwingBars   = 5;     // Баров для определения экстремума
input int    InpLevelBars   = 200;   // Баров для поиска ключевых уровней
input double InpLevelBuffer = 8.0;   // Буфер у уровня (пунктов)
input bool   InpShowSessions= true;  // Показывать метки сессий
input bool   InpShowZones   = true;  // Показывать фоновые зоны сессий
input bool   InpAlerts      = true;  // Алерты при появлении РМ
input color  InpBearRM      = clrRed;          // Цвет медвежьего РМ
input color  InpBullRM      = clrDodgerBlue;   // Цвет бычьего РМ
input color  InpBearArrow   = clrAqua;         // Цвет медвежьей стрелки
input color  InpBullArrow   = clrYellow;       // Цвет бычьей стрелки

//--- Globals
datetime g_lastAlert  = 0;
double   g_resistance = 0;
double   g_support    = DBL_MAX;

//+------------------------------------------------------------------+
int OnInit()
{
   IndicatorShortName("Sniper_RM v1.0");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "RM_");
   ObjectsDeleteAll(0, "Zone_");
}

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double   &open[],
                const double   &high[],
                const double   &low[],
                const double   &close[],
                const long     &tick_volume[],
                const long     &volume[],
                const int      &spread[])
{
   if(rates_total < InpLevelBars + InpSwingBars * 2 + 5) return 0;

   //--- Вычисляем ключевые уровни
   g_resistance = 0;
   g_support    = DBL_MAX;
   int lvStart  = rates_total - 1;
   int lvEnd    = MathMax(0, rates_total - InpLevelBars);
   for(int k = lvEnd; k <= lvStart; k++)
   {
      if(high[k] > g_resistance) g_resistance = high[k];
      if(low[k]  < g_support)    g_support    = low[k];
   }

   //--- Рисуем ключевые уровни
   DrawHLine("RM_Resistance", g_resistance, clrRed,  2, STYLE_SOLID);
   DrawHLine("RM_Support",    g_support,    clrLime, 2, STYLE_SOLID);

   //--- Стартовый бар
   int startBar = (prev_calculated == 0)
                  ? rates_total - InpSwingBars - 2
                  : rates_total - prev_calculated + 1;
   startBar = MathMin(startBar, rates_total - InpSwingBars - 2);

   datetime lastBullTime = 0;
   datetime lastBearTime = 0;

   for(int i = startBar; i >= InpSwingBars + 1; i--)
   {
      double lvBuf = InpLevelBuffer * _Point;

      //=== МЕДВЕЖИЙ экстремум (swing high) ===
      if(IsSwingHigh(high, i, InpSwingBars))
      {
         bool atLevel = (high[i] >= g_resistance - lvBuf);
         string rmName  = "RM_Bear_"  + TimeToStr(time[i], TIME_DATE|TIME_MINUTES);
         string arrName = "RM_BArr_"  + TimeToStr(time[i], TIME_DATE|TIME_MINUTES);

         // Красный прямоугольник РМ — только у уровня или выше
         if(atLevel) DrawRM(rmName, time[i], high[i], true);

         // Стрелка вниз: первая в серии жирнее
         bool isFirst = (time[i] - lastBearTime > (datetime)(PeriodSeconds() * 30));
         DrawArrow(arrName, time[i], high[i] + 8*_Point, 234, InpBearArrow, isFirst ? 2 : 1);
         lastBearTime = time[i];

         // Алерт
         if(atLevel && InpAlerts && i <= 2 && TimeCurrent() - g_lastAlert > 60)
         {
            Alert(Symbol()+" M"+IntegerToString(Period())+" РМ КРАСНЫЙ на уровне "+
                  DoubleToStr(g_resistance, Digits));
            g_lastAlert = TimeCurrent();
         }

         if(InpShowSessions) TryDrawSessionLabel(i, time, high, low);
      }

      //=== БЫЧИЙ экстремум (swing low) ===
      if(IsSwingLow(low, i, InpSwingBars))
      {
         bool atLevel = (low[i] <= g_support + lvBuf);
         string rmName  = "RM_Bull_"  + TimeToStr(time[i], TIME_DATE|TIME_MINUTES);
         string arrName = "RM_BuArr_" + TimeToStr(time[i], TIME_DATE|TIME_MINUTES);

         // Синий прямоугольник РМ — только у уровня или ниже
         if(atLevel) DrawRM(rmName, time[i], low[i], false);

         // Стрелка вверх: первая в серии жирнее
         bool isFirst = (time[i] - lastBullTime > (datetime)(PeriodSeconds() * 30));
         DrawArrow(arrName, time[i], low[i] - 8*_Point, 233, InpBullArrow, isFirst ? 2 : 1);
         lastBullTime = time[i];

         // Алерт
         if(atLevel && InpAlerts && i <= 2 && TimeCurrent() - g_lastAlert > 60)
         {
            Alert(Symbol()+" M"+IntegerToString(Period())+" РМ СИНИЙ на уровне "+
                  DoubleToStr(g_support, Digits));
            g_lastAlert = TimeCurrent();
         }

         if(InpShowSessions) TryDrawSessionLabel(i, time, high, low);
      }
   }

   if(InpShowZones) DrawSessionZones(time, rates_total);

   return rates_total;
}

//+------------------------------------------------------------------+
bool IsSwingHigh(const double &high[], int bar, int period)
{
   int sz = ArraySize(high);
   for(int j = 1; j <= period; j++)
   {
      if(bar + j >= sz)            return false;
      if(high[bar+j] >= high[bar]) return false;
      if(bar - j < 0)              return false;
      if(high[bar-j] >= high[bar]) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
bool IsSwingLow(const double &low[], int bar, int period)
{
   int sz = ArraySize(low);
   for(int j = 1; j <= period; j++)
   {
      if(bar + j >= sz)          return false;
      if(low[bar+j] <= low[bar]) return false;
      if(bar - j < 0)            return false;
      if(low[bar-j] <= low[bar]) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
void DrawRM(string name, datetime t, double price, bool isBear)
{
   if(ObjectFind(0, name) >= 0) return;
   int    ps  = PeriodSeconds();
   double h, l;
   color  col = isBear ? InpBearRM : InpBullRM;

   if(isBear) { h = price + 3*_Point; l = price - 8*_Point; }
   else       { h = price + 8*_Point; l = price - 3*_Point; }

   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t - ps, h, t + ps, l);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      col);
   ObjectSetInteger(0, name, OBJPROP_FILL,       true);
   ObjectSetInteger(0, name, OBJPROP_BACK,       false);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,      1);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
}

//+------------------------------------------------------------------+
void DrawArrow(string name, datetime t, double price, int code, color col, int width)
{
   if(ObjectFind(0, name) >= 0) return;
   ObjectCreate(0, name, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE,  code);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      col);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,      width);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
}

//+------------------------------------------------------------------+
void DrawHLine(string name, double price, color col, int width, int style)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   ObjectSetDouble(0,  name, OBJPROP_PRICE1,     price);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      col);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,      width);
   ObjectSetInteger(0, name, OBJPROP_STYLE,      style);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
}

//+------------------------------------------------------------------+
void TryDrawSessionLabel(int bar, const datetime &time[],
                         const double &high[], const double &low[])
{
   MqlDateTime dt;
   TimeToStruct(time[bar], dt);
   if(dt.min != 0) return;

   string label = "";
   color  col   = clrNONE;
   if(dt.hour == 0)  { label = "Asia";      col = clrRoyalBlue;  }
   if(dt.hour == 7)  { label = "Frankfurt"; col = clrDarkOrange; }
   if(dt.hour == 8)  { label = "London";    col = clrFireBrick;  }
   if(dt.hour == 13) { label = "New York";  col = clrDarkGreen;  }
   if(label == "") return;

   string name = "RM_Lbl_" + label + "_" + IntegerToString((int)time[bar]);
   if(ObjectFind(0, name) >= 0) return;

   double sHigh = high[bar], sLow = low[bar];
   for(int k = bar; k >= MathMax(0, bar-60); k--)
   {
      if(high[k] > sHigh) sHigh = high[k];
      if(low[k]  < sLow)  sLow  = low[k];
   }
   double pips = NormalizeDouble((sHigh - sLow) / _Point / 10.0, 2);

   double lPrice = (high[bar] + low[bar]) / 2.0;
   ObjectCreate(0, name, OBJ_TEXT, 0, time[bar], lPrice);
   ObjectSetString(0,  name, OBJPROP_TEXT,     label + " " + DoubleToStr(pips, 2));
   ObjectSetInteger(0, name, OBJPROP_COLOR,    col);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 7);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
}

//+------------------------------------------------------------------+
void DrawSessionZones(const datetime &time[], int total)
{
   int scanBars = MathMin(600, total - 2);

   for(int i = scanBars; i >= 1; i--)
   {
      MqlDateTime dt;
      TimeToStruct(time[i], dt);
      if(dt.min != 0) continue;

      string zoneName = "";
      color  zoneCol  = clrNONE;
      int    duration = 0;

      if(dt.hour == 0)  { zoneName = "Zone_Asia_" + IntegerToString((int)time[i]); zoneCol = C'220,220,255'; duration = 480; }
      if(dt.hour == 8)  { zoneName = "Zone_Lon_"  + IntegerToString((int)time[i]); zoneCol = C'255,220,220'; duration = 240; }
      if(dt.hour == 13) { zoneName = "Zone_NY_"   + IntegerToString((int)time[i]); zoneCol = C'220,255,220'; duration = 240; }

      if(zoneName == "" || ObjectFind(0, zoneName) >= 0) continue;

      int endBar = MathMax(0, i - duration);
      double zHigh = 0, zLow = DBL_MAX;
      for(int k = i; k >= endBar; k--)
      {
         if(high[k] > zHigh) zHigh = high[k];
         if(low[k]  < zLow)  zLow  = low[k];
      }

      ObjectCreate(0, zoneName, OBJ_RECTANGLE, 0, time[i], zHigh, time[endBar], zLow);
      ObjectSetInteger(0, zoneName, OBJPROP_COLOR,      zoneCol);
      ObjectSetInteger(0, zoneName, OBJPROP_FILL,       true);
      ObjectSetInteger(0, zoneName, OBJPROP_BACK,       true);
      ObjectSetInteger(0, zoneName, OBJPROP_WIDTH,      1);
      ObjectSetInteger(0, zoneName, OBJPROP_SELECTABLE, false);
   }
}
//+------------------------------------------------------------------+
