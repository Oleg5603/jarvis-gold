(function(){
  // Watermark overlay
  var style = document.createElement('style');
  style.textContent = `
    #demo-wm {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 99999;
      overflow: hidden;
    }
    #demo-wm::before {
      content: '';
      position: absolute;
      inset: -100%;
      background-image: repeating-linear-gradient(
        -45deg,
        transparent,
        transparent 120px,
        rgba(11,31,58,0.06) 120px,
        rgba(11,31,58,0.06) 121px
      );
    }
    #demo-wm-text {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%,-50%) rotate(-30deg);
      font-family: 'Montserrat', sans-serif;
      font-size: clamp(48px, 10vw, 110px);
      font-weight: 800;
      color: rgba(11,31,58,0.07);
      white-space: nowrap;
      pointer-events: none;
      user-select: none;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    #demo-badge {
      position: fixed;
      top: 80px;
      right: 16px;
      z-index: 100000;
      background: #0B1F3A;
      color: #fff;
      font-family: sans-serif;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      padding: 6px 12px;
      border-radius: 4px;
      pointer-events: none;
      box-shadow: 0 2px 12px rgba(0,0,0,0.3);
    }
    #demo-badge span {
      color: #00A3E0;
    }
    #demo-notice {
      position: fixed;
      bottom: 16px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 100000;
      background: rgba(11,31,58,0.92);
      color: rgba(255,255,255,0.8);
      font-family: sans-serif;
      font-size: 12px;
      padding: 8px 20px;
      border-radius: 100px;
      white-space: nowrap;
      pointer-events: none;
      backdrop-filter: blur(8px);
    }
  `;
  document.head.appendChild(style);

  var wm = document.createElement('div');
  wm.id = 'demo-wm';
  wm.innerHTML = '<div id="demo-wm-text">ДЕМО</div>';
  document.body.appendChild(wm);

  var badge = document.createElement('div');
  badge.id = 'demo-badge';
  badge.innerHTML = '⚠ <span>ДЕМО</span> — не для использования';
  document.body.appendChild(badge);

  var notice = document.createElement('div');
  notice.id = 'demo-notice';
  notice.textContent = 'Демо-версия сайта ONHS Systems • Для получения рабочих файлов свяжитесь с разработчиком';
  document.body.appendChild(notice);

  // Block right-click
  document.addEventListener('contextmenu', function(e){ e.preventDefault(); });

  // Block Ctrl+U (view source), Ctrl+S (save), Ctrl+A (select all), Ctrl+C (copy), F12 (devtools)
  document.addEventListener('keydown', function(e){
    var ctrl = e.ctrlKey || e.metaKey;
    if (
      (ctrl && (e.key === 'u' || e.key === 'U')) ||
      (ctrl && (e.key === 's' || e.key === 'S')) ||
      (ctrl && (e.key === 'a' || e.key === 'A')) ||
      (ctrl && (e.key === 'c' || e.key === 'C')) ||
      e.key === 'F12'
    ) {
      e.preventDefault();
    }
  });

  // Block drag
  document.addEventListener('dragstart', function(e){ e.preventDefault(); });
})();
