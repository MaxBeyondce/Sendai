
(function(){
 var K='sendai2026:';
 var root=document.documentElement;
 var DAYMAP=__DAYMAP__;
 var $=function(s,r){return (r||document).querySelector(s);};
 var $$=function(s,r){return [].slice.call((r||document).querySelectorAll(s));};

 // storage 被封鎖時，連讀 localStorage 這個屬性本身都會丟 SecurityError。
 // 全部包起來 — 記不住勾選只是每次重來，沒包的話整支 JS 會死在第一次呼叫，
 // 分頁切不動、圖片不載入、篩選失效，而且畫面上完全沒有徵兆。
 var ls={
  get:function(k){try{return localStorage.getItem(k)}catch(e){return null}},
  set:function(k,v){try{localStorage.setItem(k,v)}catch(e){}},
  del:function(k){try{localStorage.removeItem(k)}catch(e){}},
  keys:function(){try{var a=[];for(var i=0;i<localStorage.length;i++)a.push(localStorage.key(i));return a}catch(e){return []}}
 };

 // ── 高對比切換 ─────────────────────────────────────────────
 var saved=ls.get(K+'theme');
 if(saved) root.setAttribute('data-theme',saved);
 $('#themeBtn').onclick=function(){
  var cur=root.getAttribute('data-theme');
  var dark=window.matchMedia('(prefers-color-scheme:dark)').matches;
  var next=cur? (cur==='contrast'?'light':'contrast') : (dark?'light':'contrast');
  root.setAttribute('data-theme',next);
  ls.set(K+'theme',next);
 };

 // ── 舊鍵遷移。舊的單檔版用沒有前綴的 item-N，會跟這個網站其他鍵混在一起。
 // 只在新前綴下沒有值時才去補，所以每次載入都跑也無所謂，不需要遷移標記。
 // **不刪舊鍵** — 舊版可能還開在另一台裝置上，刪掉救不回來。
 // 舊檔的鍵是 item-N；新版購物 checkbox 的 id 是 'k'+item-N，
 // 所以要寫成 sendai2026:kitem-N，少了那個 k 就沒有人讀得到。
 // 先把鍵名整份抓下來再寫 — 邊列舉邊寫會讓索引位移，漏掉一半。
 ls.keys().filter(function(k){return /^item-\d+$/.test(k);}).forEach(function(k){
  var nk=K+'k'+k;
  if(ls.get(nk)===null){var v=ls.get(k); if(v!==null) ls.set(nk,v);}
 });

 // ── 勾選記錄（行程與購物共用同一套儲存）─────────────────────
 function bindTicks(scope){
  $$('.tick',scope).forEach(function(t){
   if(ls.get(K+t.id)==='1') t.checked=true;
   syncItem(t);
   t.addEventListener('change',function(){
    ls.set(K+t.id,t.checked?'1':'0');
    syncItem(t); progress(); shopProgress(); applyFilter();
   });
  });
 }
 function syncItem(t){
  var it=t.closest('.it');
  if(it) it.classList.toggle('done',t.checked);
 }
 bindTicks(document);

 function progress(){
  $$('.day').forEach(function(d){
   var all=$$('.tick',d), done=all.filter(function(t){return t.checked;});
   var bar=$('.prog .bar i',d), txt=$('.ptxt',d);
   if(!all.length||!bar) return;
   bar.style.width=(done.length/all.length*100)+'%';
   txt.textContent=done.length+'/'+all.length;
  });
 }
 progress();

 // ── 圖片延後載入的資料 ─────────────────────────────────────
 // 92 張 480×480 全部解碼是 84MB 點陣圖，舊機器的分頁會被系統收掉。
 // base64 放在 JSON 區塊裡，捲到才填 src，捲離約兩個畫面就拿掉。
 // 這一段必須放在 showTab() 之前 — showTab 會呼叫 hydrate()，
 // 而 var 只提升宣告不提升賦值，放在後面的話 IMGS 會是 undefined。
 var IMGS={}, imgIO=null;
 try{ var rawimg=$('#shopimg'); if(rawimg) IMGS=JSON.parse(rawimg.textContent||'{}'); }catch(e){}

 // ── 分頁 ───────────────────────────────────────────────────
 var tabs=$$('.tab'), panes={}, labelSets={};
 $$('.pane').forEach(function(p){panes[p.dataset.pane]=p;});
 $$('.labelset').forEach(function(l){labelSets[l.dataset.for]=l;});
 var current=ls.get(K+'tab')||'trip';
 function showTab(name,push){
  current=name;
  ls.set(K+'tab',name);
  tabs.forEach(function(t){t.setAttribute('aria-selected',String(t.dataset.tab===name));});
  Object.keys(panes).forEach(function(k){panes[k].hidden=(k!==name);});
  Object.keys(labelSets).forEach(function(k){labelSets[k].hidden=(k!==name);});
  $('#topBtn').textContent = name==='shop' ? '⌕' : '↑';
  $('#topBtn').title = name==='shop' ? '回到搜尋與篩選' : '回頂部';
  if(name==='shop'){ hydrate(); }
  if(push) scrollTo({top:0,behavior:'auto'});
 }
 tabs.forEach(function(t){t.onclick=function(){showTab(t.dataset.tab,true);};});
 showTab(panes[current]?current:'trip',false);

 // ── 日期跳轉 ───────────────────────────────────────────────
 function go(id){var el=document.getElementById(id); if(el) el.scrollIntoView({behavior:'smooth',block:'start'});}
 // 日期對照由 build 時從行程資料產生，不寫死在原始碼裡(原始碼會進公開 repo)
 function todayId(){var n=new Date();return DAYMAP[n.getFullYear()+'-'+(n.getMonth()+1)+'-'+n.getDate()]||null;}
 $$('.labelset[data-for=trip] .dbtn').forEach(function(b){
  b.onclick=function(){var g=b.dataset.go; go(g==='today'?(todayId()||'D1'):g);};
 });

 var tripLabels=$('.labelset[data-for=trip]');
 var btns={};
 $$('.dbtn',tripLabels).forEach(function(b){btns[b.dataset.go]=b;});
 var io=new IntersectionObserver(function(es){
  es.forEach(function(e){
   var b=btns[e.target.id];
   if(!b||!e.isIntersecting) return;
   $$('.dbtn',tripLabels).forEach(function(x){x.classList.remove('on');});
   b.classList.add('on');
   b.scrollIntoView({inline:'center',block:'nearest',behavior:'smooth'});
  });
 },{rootMargin:'-70px 0px -65% 0px'});
 $$('.day,#overview').forEach(function(d){io.observe(d);});

 // ── 候選手風琴：一次只開一個 ────────────────────────────────
 $$('.picks').forEach(function(g){
  $$('.pick',g).forEach(function(d){
   d.addEventListener('toggle',function(){
    if(!d.open) return;
    $$('.pick',g).forEach(function(o){if(o!==d) o.open=false;});
   });
  });
 });

 // ── 購物：搜尋、店家篩選、只看未採購 ─────────────────────────
 var shopQ=$('#shopQ'), onlyLeft=$('#onlyLeft'), storeSel='all';
 var items=$$('.it');
 function itemText(el){
  return ((el.dataset.store||'')+' '+(el.dataset.n||'')+' '+(el.dataset.d||'')).toLowerCase();
 }
 function applyFilter(){
  if(!items.length) return;
  var q=(shopQ&&shopQ.value||'').trim().toLowerCase();
  var left=onlyLeft&&onlyLeft.checked;
  var shown=0;
  items.forEach(function(el){
   var t=$('.tick',el);
   var ok=(storeSel==='all'||el.dataset.store===storeSel)
        &&(!q||itemText(el).indexOf(q)>=0)
        &&(!left||!(t&&t.checked));
   el.hidden=!ok; if(ok) shown++;
  });
  $$('.shopstore').forEach(function(s){
   s.hidden=!$$('.it',s).some(function(el){return !el.hidden;});
  });
  var e=$('#shopEmpty'); if(e) e.hidden=shown>0;
  var filtered=(storeSel!=='all')||!!q||!!left;
  var tab=$('.tab[data-tab=shop]'); if(tab) tab.classList.toggle('filtered',filtered);
  if($('#shopShown')) $('#shopShown').textContent=shown;
  hydrate();
 }
 if(shopQ) shopQ.addEventListener('input',applyFilter);
 if(onlyLeft) onlyLeft.addEventListener('change',applyFilter);
 $$('.labelset[data-for=shop] .dbtn').forEach(function(b){
  b.onclick=function(){
   storeSel=b.dataset.store;
   $$('.labelset[data-for=shop] .dbtn').forEach(function(x){x.classList.remove('on');});
   b.classList.add('on');
   applyFilter();
   if(storeSel!=='all'){var s=document.getElementById('store-'+storeSel); if(s) s.scrollIntoView({behavior:'smooth',block:'start'});}
   else scrollTo({top:0,behavior:'smooth'});
  };
 });
 // 行程頁「今天會經過某店」的連結：切到購物分頁並套用該店篩選
 $$('[data-shopjump]').forEach(function(a){
  a.onclick=function(ev){
   ev.preventDefault();
   var id=a.dataset.shopjump;
   showTab('shop',false);
   var b=$('.labelset[data-for=shop] .dbtn[data-store="'+id+'"]');
   if(b) b.click();
  };
 });
 // 反向：購物頁的「D3 會經過」切回行程分頁並捲到那一天
 $$('[data-dayjump]').forEach(function(a){
  a.onclick=function(ev){ ev.preventDefault(); showTab('trip',false); go(a.dataset.dayjump); };
 });

 function shopProgress(){
  $$('.shopstore').forEach(function(s){
   var all=$$('.tick',s), done=all.filter(function(t){return t.checked;});
   var b=$('.labelset[data-for=shop] .dbtn[data-store="'+s.dataset.store+'"] em');
   if(b) b.textContent=done.length+'/'+all.length;
   var h=$('.stprog',s); if(h) h.textContent=done.length+'/'+all.length;
  });
  var all=$$('.it .tick'), done=all.filter(function(t){return t.checked;});
  if($('#shopDone')) $('#shopDone').textContent=done.length;
  var b=$('.labelset[data-for=shop] .dbtn[data-store=all] em');
  if(b) b.textContent=done.length+'/'+all.length;
 }
 shopProgress();

 // ── 圖片延後載入 ───────────────────────────────────────────
 function hydrate(){
  if(!IMGS||!Object.keys(IMGS).length) return;
  if(!imgIO){
   imgIO=new IntersectionObserver(function(es){
    es.forEach(function(e){
     var img=e.target, id=img.dataset.img;
     if(e.isIntersecting){ if(!img.getAttribute('src')&&IMGS[id]) img.src=IMGS[id]; }
     else if(img.getAttribute('src')) img.removeAttribute('src');
    });
   },{rootMargin:'400px 0px'});
  }
  $$('.it img[data-img]').forEach(function(img){
   if(!img.dataset.obs){ img.dataset.obs='1'; imgIO.observe(img); }
  });
 }

 // ── 工具列 ─────────────────────────────────────────────────
 // 清除只作用在當前分頁 — 從行程頁按一下就把購物清單掃掉是很糟的意外。
 $('#clearBtn').onclick=function(){
  var shop=current==='shop';
  var scope=shop?$('.pane[data-pane=shop]'):$('.pane[data-pane=trip]');
  var list=$$('.tick',scope);
  if(!list.length) return;
  if(!confirm('清除「'+(shop?'購物':'行程')+'」這一頁的勾選？共 '+list.length+' 項，另一頁不受影響。')) return;
  list.forEach(function(t){t.checked=false;ls.del(K+t.id);syncItem(t);});
  progress(); shopProgress(); applyFilter();
 };
 $('#topBtn').onclick=function(){
  scrollTo({top:0,behavior:'smooth'});
  if(current==='shop'&&shopQ) setTimeout(function(){shopQ.focus({preventScroll:true});},350);
 };

 applyFilter();

 // 開啟時跳到今天(有 hash 就尊重 hash)
 if(!location.hash&&current==='trip'){
  var t=todayId();
  if(t) setTimeout(function(){go(t);},120);
 }

 // https(GitHub Pages)或 localhost 才註冊離線快取。
 // 不能只判 https：localhost 也是安全來源、要能在本機驗證；
 // 也不能用 isSecureContext：Chrome 把 file:// 也算安全來源，單檔開啟時根本沒有 sw.js，註冊會 404。
 var h=location.hostname;
 if((location.protocol==='https:'||h==='localhost'||h==='127.0.0.1')&&'serviceWorker'in navigator){
  navigator.serviceWorker.register('sw.js').catch(function(){});
 }
})();
