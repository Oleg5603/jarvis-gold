using System;
using System.Diagnostics;
using System.IO;
using System.Globalization;
using System.Threading;
using System.Threading.Tasks;
using System.Runtime.InteropServices;
public sealed class GuardianSpeedResult {
 public double LatencyMs=double.NaN, DownloadMbps=double.NaN, UploadMbps=double.NaN;
 public string DownloadError="", UploadError="";
}
public static class GuardianSpeedTest {
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern IntPtr FindWindow(string c,string title);
 [DllImport("user32.dll")] static extern bool ShowWindowAsync(IntPtr h,int cmd);
 [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
 public static void Activate() { var h=FindWindow(null,"Скорость интернета"); if(h!=IntPtr.Zero){ShowWindowAsync(h,9);SetForegroundWindow(h);} }
 static double[] Transfer(string extra,string url,CancellationToken token) {
  var info=new ProcessStartInfo("curl.exe", "--noproxy * --connect-timeout 5 --max-time 25 -sS -o NUL -w \"%{http_code};%{size_download};%{size_upload};%{speed_download};%{speed_upload};%{time_starttransfer}\" "+extra+" \""+url+"\"");
  info.UseShellExecute=false; info.CreateNoWindow=true;info.RedirectStandardOutput=true;info.RedirectStandardError=true;
  using(var p=Process.Start(info)) {
   var stdout=p.StandardOutput.ReadToEndAsync();var stderr=p.StandardError.ReadToEndAsync();
   while(!p.WaitForExit(100)){if(token.IsCancellationRequested){try{p.Kill();}catch{}token.ThrowIfCancellationRequested();}}
   string output=stdout.GetAwaiter().GetResult();stderr.GetAwaiter().GetResult();
   if(p.ExitCode!=0)throw new Exception("Ошибка сети / тайм-аут (curl "+p.ExitCode+")");
   string[] parts=output.Split(';');if(parts.Length!=6)throw new Exception("Некорректный ответ замера");
   var values=Array.ConvertAll(parts,s=>double.Parse(s,CultureInfo.InvariantCulture));
   if(values[0]!=200)throw new Exception("Сервер замера: HTTP "+values[0]);return values;
  }
 }
 public static Task<GuardianSpeedResult> Run(CancellationToken token) {return Task.Run(()=>{
  var r=new GuardianSpeedResult();
  try {var v=Transfer("","https://speed.cloudflare.com/__down?bytes=2000000&nonce="+Guid.NewGuid(),token);
   if(v[1]!=2000000)throw new Exception("Неполный ответ");r.DownloadMbps=v[3]*8/1000000;r.LatencyMs=v[5]*1000;
  }catch(OperationCanceledException){throw;}catch(Exception e){r.DownloadError=e.Message;}
  token.ThrowIfCancellationRequested();
  string path=Path.GetTempFileName();
  try {var data=new byte[1000000];new Random().NextBytes(data);File.WriteAllBytes(path,data);
   var v=Transfer("--data-binary @\""+path+"\"","https://speed.cloudflare.com/__up",token);
   if(v[2]!=data.Length)throw new Exception("Неполная отправка");r.UploadMbps=v[4]*8/1000000;
  }catch(OperationCanceledException){throw;}catch(Exception e){r.UploadError=e.Message;}finally{File.Delete(path);}
  return r;
 },token);}
}
