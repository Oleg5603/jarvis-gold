//+------------------------------------------------------------------+
//|                                                  Sn-9_1_gold.mq4 |
//|  v2: HTF filter (M15+H1) · Level crossing stop · Quality 1-3    |
//|      EA buffers (iCustom) · More swing dots · Score arrows        |
//+------------------------------------------------------------------+
#property copyright ""
#property version   "2.00"
#property strict
#property indicator_chart_window
#property indicator_buffers 2

// EA-readable buffers (DRAW_NONE — only data)
double BuyBuf[];   // Buffer 0: buy signal quality  (0=none, 1/2/3)
double SellBuf[];  // Buffer 1: sell signal quality (0=none, 1/2/3)

//======================================================
//  INPUTS
//======================================================

#define SEP sinput string

//--- General
SEP s_gen    = "- - - - -";
input int    InpBrokerOffset  = 3;                 // Сдвиг времени брокера (UTC+N)
input int    InpHistoryBars   = 5000000;           // История в свечах (0=все)
input bool   InpVirtualTF     = false;             // Использовать виртуальный таймфрейм

//--- Multi-timeframe direction filter
SEP s_mtf    = "- - - - -";
input bool   InpUseMTF        = true;              // Использовать фильтр M15/H1
input int    InpTrendPeriod   = 20;                // Период EMA для определения тренда
input int    InpMinQuality    = 1;                 // Минимальное качество сигнала (1-3)

//--- Level behaviour
SEP s_lev    = "- - - - -";
input bool   InpLevelCrossStop = true;             // Обрывать уровень при пересечении ценой
input int    InpTouchTol       = 20;               // Допуск касания уровня (в пунктах)

//--- HH/LL
SEP s_hhll   = "- - - - -";
input color  InpColorHHLL     = clrDarkViolet;     // Цвет HH/LL (крупные свинги)
input int    InpWidthHHLL     = 3;
input color  InpColorMinor    = clrMediumOrchid;   // Цвет минорных экстремумов
input int    InpSwingLB       = 3;                 // Lookback свингов (3=больше точек)

//--- Reversal moments set 1
SEP s_rev1   = "- - - - -";
input color  InpRevSell1      = clrRed;
input color  InpRevBuy1       = clrMediumPurple;
input int    InpRevWidth1     = 1;
input bool   InpAlertRev1a    = true;
input bool   InpAlertRev1b    = true;

//--- Reversal moments set 2
SEP s_rev2   = "- - - - -";
input color  InpRevSell2      = clrBrown;
input color  InpRevBuy2       = clrMediumPurple;
input int    InpRevWidth2     = 1;

//--- Yellow lines (HIGH per session)
SEP s_yl     = "- - - - -";
input color           InpYC_Asia  = C'255,248,220'; // Цвет желтых линий 02:00-08:59 (UTC+3)
input ENUM_LINE_STYLE InpYS_Asia  = STYLE_DOT;
input int             InpYW_Asia  = 1;
input color           InpYC_Frank = clrPaleGreen;
input ENUM_LINE_STYLE InpYS_Frank = STYLE_DOT;
input int             InpYW_Frank = 1;
input color           InpYC_Lon   = clrRoyalBlue;
input ENUM_LINE_STYLE InpYS_Lon   = STYLE_DOT;
input int             InpYW_Lon   = 1;
input color           InpYC_NY    = clrTomato;
input ENUM_LINE_STYLE InpYS_NY    = STYLE_DOT;
input int             InpYW_NY    = 1;

//--- Teal lines (LOW per session)
SEP s_tl     = "- - - - -";
input color           InpTC_Asia  = C'255,248,220';
input ENUM_LINE_STYLE InpTS_Asia  = STYLE_DOT;
input int             InpTW_Asia  = 1;
input color           InpTC_Frank = clrPaleGreen;
input ENUM_LINE_STYLE InpTS_Frank = STYLE_DOT;
input int             InpTW_Frank = 1;
input color           InpTC_Lon   = clrRoyalBlue;
input ENUM_LINE_STYLE InpTS_Lon   = STYLE_DOT;
input int             InpTW_Lon   = 1;
input color           InpTC_NY    = clrTomato;
input ENUM_LINE_STYLE InpTS_NY    = STYLE_DOT;
input int             InpTW_NY    = 1;

//--- Correction zones
input int InpCorrWidth = 1;

//--- Pattern 4
SEP s_p4 = "- - - - -";
input bool            InpUseP4    = true;
input color           InpP4C_Asia = clrSilver;
input ENUM_LINE_STYLE InpP4S_Asia = STYLE_DOT;
input int             InpP4W_Asia = 1;
input color           InpP4C_Frank= clrSilver;
input ENUM_LINE_STYLE InpP4S_Frank= STYLE_DOT;
input int             InpP4W_Frank= 1;
input color           InpP4C_Lon  = clrSilver;
input ENUM_LINE_STYLE InpP4S_Lon  = STYLE_DOT;
input int             InpP4W_Lon  = 1;
input color           InpP4C_NY   = clrTomato;
input ENUM_LINE_STYLE InpP4S_NY   = STYLE_DOT;
input int             InpP4W_NY   = 1;

//--- Session labels
SEP s_lbl = "- - - - -";
input string InpLT_Asia  = "Asia";
input color  InpLC_Asia  = C'255,248,220';
input string InpLF_Asia  = "Times New Roman";
input int    InpLS_Asia  = 9;
input string InpLT_Frank = "Frankfurt";
input color  InpLC_Frank = clrPaleGreen;
input string InpLF_Frank = "Times New Roman";
input int    InpLS_Frank = 9;
input string InpLT_Lon   = "London";
input color  InpLC_Lon   = clrRoyalBlue;
input string InpLF_Lon   = "Times New Roman";
input int    InpLS_Lon   = 9;
input string InpLT_NY    = "New York";
input color  InpLC_NY    = clrTomato;
input string InpLF_NY    = "Times New Roman";
input int    InpLS_NY    = 9;

//--- Continued movement
SEP s_cont = "- - - - -";
input bool            InpShowCont  = true;
input color           InpContUp    = clrDarkGray;
input color           InpContDown  = clrDarkGray;
input ENUM_LINE_STYLE InpContStyle = STYLE_DASH;
input int             InpContWidth = 3;
input int             InpContFont  = 10;
input bool            InpAlertCont = false;

//--- Pattern 7
SEP s_p7 = "- - - - -";
input bool            InpUseP7   = true;
input color           InpP7Yellow= clrGreen;
input color           InpP7Teal  = clrGreen;
input int             InpP7Width = 3;
input ENUM_LINE_STYLE InpP7Style = STYLE_SOLID;

//--- Cont. movement sit. 2
SEP s_cont2 = "- - - - -";
input bool InpShowCont2=true; input bool InpAlertStop2=false;

//--- Cascade #4
SEP s_casc = "- - - - -";
input bool            InpShowCasc4 = true;
input color           InpCasc4Up   = clrSilver;
input color           InpCasc4Down = clrSilver;
input ENUM_LINE_STYLE InpCasc4Sty  = STYLE_DASH;
input bool            InpAlertCasc = false;

//--- Extension
SEP s_ext1 = "- - - - -";
input bool  InpShowExt1 =true; input int InpExt1Width=3;
input color InpExt1Up   =C'245,205,205'; input color InpExt1Down=clrSkyBlue; input bool InpAlertExt1=false;

//--- Cont. movement sit. 1
SEP s_cont1 = "- - - - -";
input bool  InpShowCont1 =true; input int InpCont1Width=5;
input color InpCont1Up  =clrRed; input color InpCont1Down=clrBlue; input bool InpAlertCont1=false;

//--- Custom session
SEP s_sess = "- - - - -";
input color  InpSessColor =clrNONE;
input string InpSessStart ="14:30";
input string InpSessEnd   ="23:55";
input color  InpSessYellow=clrRed;
input color  InpSessTeal  =clrBlue;

//--- History TF_a
input int InpHistBarsA = 50000;

//--- Arrows 1&2 (yellow UP — quality 1-2, expect перехай)
SEP s_a12 = "- - - - -";
input int   InpA1Size =2;  input color InpA1Color=clrYellow;
input int   InpA2Size =5;  input color InpA2Color=clrYellow;
input bool  InpAlert12=false;

//--- Arrows 3&4 (yellow DOWN — quality 1-2, expect прелой)
SEP s_a34 = "- - - - -";
input int   InpA3Size =2;  input color InpA3Color=clrYellow;
input int   InpA4Size =5;  input color InpA4Color=clrYellow;
input bool  InpAlert34=false;

//--- Arrows 5&6 (teal UP — quality 3)
SEP s_a56 = "- - - - -";
input int   InpA5Size =2;  input color InpA5Color=C'33,203,186';
input int   InpA6Size =5;  input color InpA6Color=C'32,198,181';
input bool  InpAlert56=false;

//--- Arrows 7&8 (teal DOWN — quality 3)
SEP s_a78 = "- - - - -";
input int   InpA7Size =2;  input color InpA7Color=clrTurquoise;
input int   InpA8Size =5;  input color InpA8Color=C'33,201,184';
input bool  InpAlert78=true;

//======================================================
//  STRUCTS & GLOBALS
//======================================================

#define PREFIX       "Sn91g_"
#define MAX_LEVELS    300
#define MAX_BREAKOUTS  60

struct SSession {
   int    sh,eh; bool cross;
   color  yc; ENUM_LINE_STYLE ys; int yw;
   color  tc; ENUM_LINE_STYLE ts; int tw;
   string lbl; color lc; string lf; int ls;
};
struct SLevel {
   double price; int sess; bool isHigh; datetime t;
   bool crossed; datetime crossTime; int touchCount;
};
struct SBreakout {
   int bar; double extreme; bool isUp; bool fired;
};

SSession  g_sess[4];
double    g_high[4], g_low[4];
datetime  g_sStart[4];
bool      g_active[4];
SLevel    g_lev[MAX_LEVELS];
int       g_levCount=0;
SBreakout g_brk[MAX_BREAKOUTS];
int       g_brkCount=0;
double    g_lastSwingH=0, g_lastSwingL=DBL_MAX;
int       g_lastSwingHBar=-1, g_lastSwingLBar=-1;

//======================================================
//  HELPER FUNCTIONS
//======================================================

bool InSession(int h,int sh,int eh,bool cross){
   if(!cross) return(h>=sh&&h<eh); return(h>=sh||h<eh);
}
int GetSession(datetime t){
   MqlDateTime dt; TimeToStruct(t,dt); int h=dt.hour;
   for(int i=0;i<4;i++) if(InSession(h,g_sess[i].sh,g_sess[i].eh,g_sess[i].cross)) return i;
   return -1;
}
void DelObjects(){
   int n=ObjectsTotal(0,0,-1);
   for(int i=n-1;i>=0;i--){ string nm=ObjectName(0,i,0,-1); if(StringFind(nm,PREFIX)==0) ObjectDelete(0,nm); }
}
void ObjTrend(string nm,datetime t1,double p1,datetime t2,double p2,
              color c,ENUM_LINE_STYLE s,int w,bool ray=false){
   if(ObjectFind(0,nm)<0){
      ObjectCreate(0,nm,OBJ_TREND,0,t1,p1,t2,p2);
      ObjectSetInteger(0,nm,OBJPROP_COLOR,c); ObjectSetInteger(0,nm,OBJPROP_STYLE,s);
      ObjectSetInteger(0,nm,OBJPROP_WIDTH,w); ObjectSetInteger(0,nm,OBJPROP_RAY_RIGHT,ray);
      ObjectSetInteger(0,nm,OBJPROP_SELECTABLE,false); ObjectSetInteger(0,nm,OBJPROP_HIDDEN,true);
   } else {
      ObjectSetInteger(0,nm,OBJPROP_TIME,0,t1); ObjectSetDouble(0,nm,OBJPROP_PRICE,0,p1);
      ObjectSetInteger(0,nm,OBJPROP_TIME,1,t2); ObjectSetDouble(0,nm,OBJPROP_PRICE,1,p2);
   }
}
void ObjText(string nm,datetime t,double p,string txt,color c,string fnt,int sz){
   if(ObjectFind(0,nm)>=0) return;
   ObjectCreate(0,nm,OBJ_TEXT,0,t,p);
   ObjectSetString(0,nm,OBJPROP_TEXT,txt); ObjectSetString(0,nm,OBJPROP_FONT,fnt);
   ObjectSetInteger(0,nm,OBJPROP_FONTSIZE,sz); ObjectSetInteger(0,nm,OBJPROP_COLOR,c);
   ObjectSetInteger(0,nm,OBJPROP_SELECTABLE,false); ObjectSetInteger(0,nm,OBJPROP_HIDDEN,true);
}
void ObjArrow(string nm,datetime t,double p,int code,color c,int sz){
   if(ObjectFind(0,nm)>=0) return;
   ObjectCreate(0,nm,OBJ_ARROW,0,t,p);
   ObjectSetInteger(0,nm,OBJPROP_ARROWCODE,code); ObjectSetInteger(0,nm,OBJPROP_COLOR,c);
   ObjectSetInteger(0,nm,OBJPROP_WIDTH,sz);
   ObjectSetInteger(0,nm,OBJPROP_SELECTABLE,false); ObjectSetInteger(0,nm,OBJPROP_HIDDEN,true);
}

// Stop a level line at crossing time
void StopLevelLine(int k,datetime tStop){
   string id=IntegerToString(g_lev[k].sess)+"_"+IntegerToString((int)g_lev[k].t);
   string nm=g_lev[k].isHigh ? PREFIX+"YH_"+id : PREFIX+"TL_"+id;
   if(ObjectFind(0,nm)<0) return;
   ObjectSetInteger(0,nm,OBJPROP_RAY_RIGHT,false);
   ObjectSetInteger(0,nm,OBJPROP_TIME,1,tStop);
   ObjectSetDouble(0, nm,OBJPROP_PRICE,1,g_lev[k].price);
}

// EMA trend: +1 bullish, -1 bearish, 0 flat
int GetTrend(int tf){
   double price=iClose(NULL,tf,1);
   double ema  =iMA(NULL,tf,InpTrendPeriod,0,MODE_EMA,PRICE_CLOSE,1);
   if(ema<=0) return 0;
   double band=ema*0.0002;
   if(price>ema+band) return  1;
   if(price<ema-band) return -1;
   return 0;
}

// Quality: 0=skip, 1=basic, 2=+M15, 3=+H1+fresh
int SignalQuality(bool isUp,int levIdx){
   int dir=isUp?1:-1;
   if(!InpUseMTF) return 1;
   if(GetTrend(PERIOD_M15)!=dir) return 0;
   int q=2;
   bool fresh=(levIdx>=0 && !g_lev[levIdx].crossed && g_lev[levIdx].touchCount<=1);
   if(GetTrend(PERIOD_H1)==dir && fresh) q=3;
   return q;
}

// Find nearest uncrossed level index (-1 if none)
int FindLevel(double price,bool wantHigh){
   double tol=InpTouchTol*Point; int best=-1; double bestD=tol;
   for(int k=0;k<g_levCount;k++){
      if(g_lev[k].crossed||g_lev[k].isHigh!=wantHigh) continue;
      double d=MathAbs(price-g_lev[k].price);
      if(d<bestD){ bestD=d; best=k; }
   }
   return best;
}

//======================================================
//  SESSION INIT
//======================================================

void InitSessions(){
   int o=InpBrokerOffset-3;
   g_sess[0].sh=(2+o+24)%24; g_sess[0].eh=(9+o+24)%24;  g_sess[0].cross=(g_sess[0].sh>g_sess[0].eh);
   g_sess[0].yc=InpYC_Asia; g_sess[0].ys=InpYS_Asia; g_sess[0].yw=InpYW_Asia;
   g_sess[0].tc=InpTC_Asia; g_sess[0].ts=InpTS_Asia; g_sess[0].tw=InpTW_Asia;
   g_sess[0].lbl=InpLT_Asia; g_sess[0].lc=InpLC_Asia; g_sess[0].lf=InpLF_Asia; g_sess[0].ls=InpLS_Asia;

   g_sess[1].sh=(9+o+24)%24;  g_sess[1].eh=(10+o+24)%24; g_sess[1].cross=false;
   g_sess[1].yc=InpYC_Frank; g_sess[1].ys=InpYS_Frank; g_sess[1].yw=InpYW_Frank;
   g_sess[1].tc=InpTC_Frank; g_sess[1].ts=InpTS_Frank; g_sess[1].tw=InpTW_Frank;
   g_sess[1].lbl=InpLT_Frank; g_sess[1].lc=InpLC_Frank; g_sess[1].lf=InpLF_Frank; g_sess[1].ls=InpLS_Frank;

   g_sess[2].sh=(10+o+24)%24; g_sess[2].eh=(15+o+24)%24; g_sess[2].cross=false;
   g_sess[2].yc=InpYC_Lon; g_sess[2].ys=InpYS_Lon; g_sess[2].yw=InpYW_Lon;
   g_sess[2].tc=InpTC_Lon; g_sess[2].ts=InpTS_Lon; g_sess[2].tw=InpTW_Lon;
   g_sess[2].lbl=InpLT_Lon; g_sess[2].lc=InpLC_Lon; g_sess[2].lf=InpLF_Lon; g_sess[2].ls=InpLS_Lon;

   g_sess[3].sh=(15+o+24)%24; g_sess[3].eh=(2+o+24)%24;  g_sess[3].cross=true;
   g_sess[3].yc=InpYC_NY; g_sess[3].ys=InpYS_NY; g_sess[3].yw=InpYW_NY;
   g_sess[3].tc=InpTC_NY; g_sess[3].ts=InpTS_NY; g_sess[3].tw=InpTW_NY;
   g_sess[3].lbl=InpLT_NY; g_sess[3].lc=InpLC_NY; g_sess[3].lf=InpLF_NY; g_sess[3].ls=InpLS_NY;
}

//======================================================
//  FINALISE SESSION
//======================================================

void FinaliseSession(int s,datetime tEnd){
   if(g_high[s]<=-DBL_MAX||g_low[s]>=DBL_MAX) return;
   string id=IntegerToString(s)+"_"+IntegerToString((int)g_sStart[s]);
   ENUM_LINE_STYLE ys=(g_sess[s].yw==1)?g_sess[s].ys:STYLE_SOLID;
   ENUM_LINE_STYLE ts=(g_sess[s].tw==1)?g_sess[s].ts:STYLE_SOLID;

   ObjTrend(PREFIX+"YH_"+id, g_sStart[s],g_high[s],tEnd,g_high[s], g_sess[s].yc,ys,g_sess[s].yw,true);
   ObjTrend(PREFIX+"TL_"+id, g_sStart[s],g_low[s], tEnd,g_low[s],  g_sess[s].tc,ts,g_sess[s].tw,true);
   ObjText(PREFIX+"LH_"+id,  g_sStart[s],g_high[s], g_sess[s].lbl,g_sess[s].lc,g_sess[s].lf,g_sess[s].ls);
   ObjText(PREFIX+"LL_"+id,  g_sStart[s],g_low[s],  g_sess[s].lbl,g_sess[s].lc,g_sess[s].lf,g_sess[s].ls);

   // Store levels (ring)
   for(int pass=0;pass<2;pass++){
      if(g_levCount>=MAX_LEVELS){ for(int k=0;k<MAX_LEVELS-1;k++) g_lev[k]=g_lev[k+1]; g_levCount=MAX_LEVELS-1; }
      g_lev[g_levCount].price     = (pass==0)?g_high[s]:g_low[s];
      g_lev[g_levCount].sess      = s;
      g_lev[g_levCount].isHigh    = (pass==0);
      g_lev[g_levCount].t         = g_sStart[s];
      g_lev[g_levCount].crossed   = false;
      g_lev[g_levCount].touchCount= 0;
      g_levCount++;
   }
}

//======================================================
//  LEVEL CROSSING + TOUCH
//======================================================

void CheckLevelCrossings(int i,const datetime &time[],
                          const double &high[],const double &low[],const double &close[]){
   double tol=InpTouchTol*Point;
   for(int k=0;k<g_levCount;k++){
      if(g_lev[k].crossed) continue;
      // Touch
      bool nearH= g_lev[k].isHigh  && high[i]>=g_lev[k].price-tol && high[i]<=g_lev[k].price+tol*2;
      bool nearL= !g_lev[k].isHigh && low[i] <=g_lev[k].price+tol && low[i] >=g_lev[k].price-tol*2;
      if(nearH||nearL) g_lev[k].touchCount++;
      // Cross (close through)
      bool cH= g_lev[k].isHigh  && close[i]>g_lev[k].price+tol;
      bool cL= !g_lev[k].isHigh && close[i]<g_lev[k].price-tol;
      if(cH||cL){
         g_lev[k].crossed=true; g_lev[k].crossTime=time[i];
         if(InpLevelCrossStop) StopLevelLine(k,time[i]);
      }
   }
}

//======================================================
//  SWING DETECTION  (major + minor dots)
//======================================================

void DetectSwings(int i,int total,const datetime &time[],
                  const double &high[],const double &low[]){
   int lb=InpSwingLB;
   if(i<lb||i+lb>=total) return;

   bool isH=true,isL=true;
   for(int k=1;k<=lb;k++){
      if(high[i]<=high[i-k]||high[i]<=high[i+k]) isH=false;
      if(low[i] >=low[i-k] ||low[i] >=low[i+k])  isL=false;
   }
   if(isH){ string nm=PREFIX+"SH_"+IntegerToString(i);
            if(ObjectFind(0,nm)<0) ObjArrow(nm,time[i],high[i],119,InpColorHHLL,2);
            if(high[i]>g_lastSwingH){ g_lastSwingH=high[i]; g_lastSwingHBar=i; } }
   if(isL){ string nm=PREFIX+"SL_"+IntegerToString(i);
            if(ObjectFind(0,nm)<0) ObjArrow(nm,time[i],low[i],119,InpColorHHLL,2);
            if(low[i]<g_lastSwingL){ g_lastSwingL=low[i]; g_lastSwingLBar=i; } }

   // Minor swings (half lookback — more dots on extremums)
   int lbm=MathMax(1,lb/2);
   if(lbm<lb){
      bool isHm=true,isLm=true;
      for(int k=1;k<=lbm;k++){
         if(high[i]<=high[i-k]||high[i]<=high[i+k]) isHm=false;
         if(low[i] >=low[i-k] ||low[i] >=low[i+k])  isLm=false;
      }
      if(isHm&&!isH){ string nm=PREFIX+"MH_"+IntegerToString(i); if(ObjectFind(0,nm)<0) ObjArrow(nm,time[i],high[i],119,InpColorMinor,1); }
      if(isLm&&!isL){ string nm=PREFIX+"ML_"+IntegerToString(i); if(ObjectFind(0,nm)<0) ObjArrow(nm,time[i],low[i], 119,InpColorMinor,1); }
   }
}

//======================================================
//  RM DETECTION
//======================================================

double AvgRange(int i,const double &high[],const double &low[],int n=14){
   double s=0; int cnt=0;
   for(int k=1;k<=n&&i-k>=0;k++){s+=high[i-k]-low[i-k];cnt++;}
   return cnt>0?s/cnt:0;
}

bool IsImpulse(int i,const double &high[],const double &low[]){
   if(i<10) return false;
   double rng=high[i]-low[i]; if(rng<=0) return false;
   for(int k=1;k<=10;k++) if(rng<=high[i-k]-low[i-k]) return false;
   return true;
}

void DrawArrows(int i,bool isUp,int quality,
                const datetime &time[],const double &high[],const double &low[]){
   double o1=8*Point, o2=16*Point;
   string b=PREFIX+"ARR_"+IntegerToString(i);
   if(isUp){
      if(quality==3){
         ObjArrow(b+"_5",time[i],low[i]-o1,233,InpA5Color,InpA5Size);
         ObjArrow(b+"_6",time[i],low[i]-o2,233,InpA6Color,InpA6Size);
         if(InpAlert56) Alert(PREFIX,": UP Q3 перехай ",Symbol()," ",TimeToString(time[i]));
      } else {
         ObjArrow(b+"_1",time[i],low[i]-o1,233,InpA1Color,InpA1Size);
         ObjArrow(b+"_2",time[i],low[i]-o2,233,InpA2Color,InpA2Size);
         if(InpAlert12) Alert(PREFIX,": UP Q",IntegerToString(quality)," перехай ",Symbol());
      }
      BuyBuf[i]=(double)quality;
   } else {
      if(quality==3){
         ObjArrow(b+"_7",time[i],high[i]+o1,234,InpA7Color,InpA7Size);
         ObjArrow(b+"_8",time[i],high[i]+o2,234,InpA8Color,InpA8Size);
         if(InpAlert78) Alert(PREFIX,": DN Q3 прелой ",Symbol()," ",TimeToString(time[i]));
      } else {
         ObjArrow(b+"_3",time[i],high[i]+o1,234,InpA3Color,InpA3Size);
         ObjArrow(b+"_4",time[i],high[i]+o2,234,InpA4Color,InpA4Size);
         if(InpAlert34) Alert(PREFIX,": DN Q",IntegerToString(quality)," прелой ",Symbol());
      }
      SellBuf[i]=(double)quality;
   }
}

void CheckBreakouts(int i,int total,
                    const datetime &time[],const double &open[],
                    const double &high[], const double &low[],const double &close[]){
   // Register impulse
   if(IsImpulse(i,high,low)){
      bool up=(close[i]>open[i]);
      SBreakout nb; nb.bar=i; nb.extreme=(up?high[i]:low[i]); nb.isUp=up; nb.fired=false;
      if(g_brkCount<MAX_BREAKOUTS){ g_brk[g_brkCount]=nb; g_brkCount++; }
      else{ for(int k=0;k<MAX_BREAKOUTS-1;k++) g_brk[k]=g_brk[k+1]; g_brk[MAX_BREAKOUTS-1]=nb; }
   }

   double swingRange=g_lastSwingH-g_lastSwingL;

   for(int b=0;b<g_brkCount;b++){
      if(g_brk[b].fired) continue;
      int dist=i-g_brk[b].bar;
      if(dist<1||dist>10) continue;

      // Cond 2: large contra candle
      double avgR=AvgRange(i,high,low);
      bool contra= g_brk[b].isUp
                   ?(close[i]<open[i]&&(high[i]-low[i])>avgR*1.5)
                   :(close[i]>open[i]&&(high[i]-low[i])>avgR*1.5);
      if(!contra) continue;

      // Cond 3: retrace > 21% of last swing
      if(swingRange<=0) continue;
      double retrace= g_brk[b].isUp?(g_brk[b].extreme-close[i]):(close[i]-g_brk[b].extreme);
      if(retrace/swingRange<0.21) continue;

      // RM confirmed — draw marker on impulse bar
      string mNm=PREFIX+"RM_"+IntegerToString(g_brk[b].bar);
      if(ObjectFind(0,mNm)<0){
         if(g_brk[b].isUp)
            ObjArrow(mNm,time[g_brk[b].bar],high[g_brk[b].bar]+5*Point,108,InpRevSell1,InpRevWidth1);
         else
            ObjArrow(mNm,time[g_brk[b].bar],low[g_brk[b].bar]-5*Point, 108,InpRevBuy1, InpRevWidth1);
         if(InpAlertRev1a&&i==total-1)
            Alert(PREFIX,": РМ ",Symbol()," ",TimeToString(time[g_brk[b].bar]));
      }

      // Direction after retrace: opposite to impulse
      bool expectUp=!g_brk[b].isUp;
      int levIdx=FindLevel(g_brk[b].extreme,g_brk[b].isUp);
      int quality=SignalQuality(expectUp,levIdx);
      if(quality<InpMinQuality){ g_brk[b].fired=true; continue; }

      // Draw arrows once per signal bar
      bool alreadyHasUp  =(ObjectFind(0,PREFIX+"ARR_"+IntegerToString(i)+"_1")>=0||
                           ObjectFind(0,PREFIX+"ARR_"+IntegerToString(i)+"_5")>=0);
      bool alreadyHasDn  =(ObjectFind(0,PREFIX+"ARR_"+IntegerToString(i)+"_3")>=0||
                           ObjectFind(0,PREFIX+"ARR_"+IntegerToString(i)+"_7")>=0);
      if((expectUp&&!alreadyHasUp)||(!expectUp&&!alreadyHasDn))
         DrawArrows(i,expectUp,quality,time,high,low);

      g_brk[b].fired=true;
   }
}

//======================================================
//  CONTINUED MOVEMENT (≥ 123%)
//======================================================

void CheckContinuedMovement(int i,int total,const datetime &time[],const double &close[]){
   if(!InpShowCont||g_lastSwingHBar<0||g_lastSwingLBar<0) return;
   double rng=g_lastSwingH-g_lastSwingL; if(rng<=0) return;
   ENUM_LINE_STYLE st=(InpContWidth==1)?InpContStyle:STYLE_SOLID;

   if(g_lastSwingLBar<g_lastSwingHBar){   // last major move was UP
      if(close[i]>=g_lastSwingL+rng*1.23){
         string nm=PREFIX+"CMU_"+IntegerToString(g_lastSwingLBar);
         if(ObjectFind(0,nm)<0){
            double pts=(close[i]-g_lastSwingL)/Point;
            ObjTrend(nm,time[g_lastSwingLBar],g_lastSwingL,time[i],close[i],InpContUp,st,InpContWidth);
            ObjText(PREFIX+"CMUL_"+IntegerToString(g_lastSwingLBar),time[i],close[i]+3*Point,
                    DoubleToString(pts,2),InpContUp,"Arial",InpContFont);
            if(InpAlertCont&&i==total-1) Alert(PREFIX,": Прод.вверх ",DoubleToString(pts,2),"пт ",Symbol());
         }
      }
   }
   if(g_lastSwingHBar<g_lastSwingLBar){   // last major move was DOWN
      if(close[i]<=g_lastSwingH-rng*1.23){
         string nm=PREFIX+"CMD_"+IntegerToString(g_lastSwingHBar);
         if(ObjectFind(0,nm)<0){
            double pts=(g_lastSwingH-close[i])/Point;
            ObjTrend(nm,time[g_lastSwingHBar],g_lastSwingH,time[i],close[i],InpContDown,st,InpContWidth);
            ObjText(PREFIX+"CMDL_"+IntegerToString(g_lastSwingHBar),time[i],close[i]-3*Point,
                    DoubleToString(pts,2),InpContDown,"Arial",InpContFont);
            if(InpAlertCont&&i==total-1) Alert(PREFIX,": Прод.вниз ",DoubleToString(pts,2),"пт ",Symbol());
         }
      }
   }
}

//======================================================
//  OnInit / OnDeinit / OnCalculate
//======================================================

int OnInit(){
   SetIndexBuffer(0,BuyBuf);  SetIndexStyle(0,DRAW_NONE); SetIndexLabel(0,"Buy Quality");
   SetIndexBuffer(1,SellBuf); SetIndexStyle(1,DRAW_NONE); SetIndexLabel(1,"Sell Quality");
   SetIndexEmptyValue(0,0.0); SetIndexEmptyValue(1,0.0);

   InitSessions();
   for(int i=0;i<4;i++){ g_high[i]=-DBL_MAX; g_low[i]=DBL_MAX; g_sStart[i]=0; g_active[i]=false; }
   g_levCount=0; g_brkCount=0;
   g_lastSwingH=0; g_lastSwingL=DBL_MAX; g_lastSwingHBar=-1; g_lastSwingLBar=-1;
   DelObjects();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){ DelObjects(); }

int OnCalculate(const int rates_total,const int prev_calculated,
                const datetime &time[],const double &open[],
                const double &high[],  const double &low[],
                const double &close[], const long &tick_volume[],
                const long &volume[],  const int &spread[]){

   if(rates_total<15) return 0;

   int startBar=(prev_calculated>1)?prev_calculated-1:0;
   if(InpHistoryBars>0) startBar=MathMax(startBar,rates_total-InpHistoryBars);

   for(int i=startBar;i<rates_total;i++){ BuyBuf[i]=0; SellBuf[i]=0; }

   for(int i=startBar;i<rates_total;i++){
      int s=GetSession(time[i]);

      for(int k=0;k<4;k++){
         if(s==k){
            if(!g_active[k]){ g_active[k]=true; g_sStart[k]=time[i]; g_high[k]=high[i]; g_low[k]=low[i]; }
            else{ if(high[i]>g_high[k])g_high[k]=high[i]; if(low[i]<g_low[k])g_low[k]=low[i]; }
         } else if(g_active[k]){
            FinaliseSession(k,time[i]);
            g_active[k]=false; g_high[k]=-DBL_MAX; g_low[k]=DBL_MAX;
         }
      }

      CheckLevelCrossings(i,time,high,low,close);

      if(i<rates_total-InpSwingLB)
         DetectSwings(i,rates_total,time,high,low);

      if(i>=10)
         CheckBreakouts(i,rates_total,time,open,high,low,close);

      CheckContinuedMovement(i,rates_total,time,close);
   }
   return rates_total;
}
