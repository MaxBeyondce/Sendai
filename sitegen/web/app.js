
(function(){
 var K='sendai2026:';
 var root=document.documentElement;
 var DAYMAP=__DAYMAP__;

 // 高對比切換
 var saved=localStorage.getItem(K+'theme');
 if(saved) root.setAttribute('data-theme',saved);
 document.getElementById('themeBtn').onclick=function(){
  var cur=root.getAttribute('data-theme');
  var dark=window.matchMedia('(prefers-color-scheme:dark)').matches;
  var next=cur? (cur==='contrast'?'light':'contrast') : (dark?'light':'contrast');
  root.setAttribute('data-theme',next);
  localStorage.setItem(K+'theme',next);
 };

 // 勾選記錄
 var ticks=[].slice.call(document.querySelectorAll('.tick'));
 ticks.forEach(function(t){
  if(localStorage.getItem(K+t.id)==='1') t.checked=true;
  t.addEventListener('change',function(){
   localStorage.setItem(K+t.id,t.checked?'1':'0'); prog();
  });
 });
 document.getElementById('clearBtn').onclick=function(){
  if(!confirm('清除全部勾選？')) return;
  ticks.forEach(function(t){t.checked=false;localStorage.removeItem(K+t.id);});
  prog();
 };
 function prog(){
  [].forEach.call(document.querySelectorAll('.day'),function(d){
   var all=d.querySelectorAll('.tick'), done=d.querySelectorAll('.tick:checked');
   var bar=d.querySelector('.prog .bar i'), txt=d.querySelector('.ptxt');
   if(!all.length||!bar) return;
   bar.style.width=(done.length/all.length*100)+'%';
   txt.textContent=done.length+'/'+all.length;
  });
 }
 prog();

 // 日期跳轉
 var bar=document.getElementById('daybar');
 function go(id){
  var el=document.getElementById(id);
  if(el) el.scrollIntoView({behavior:'smooth',block:'start'});
 }
 // 日期對照由 build 時從行程資料產生，不寫死在原始碼裡(原始碼會進公開 repo)
 function todayId(){
  var n=new Date();
  return DAYMAP[n.getFullYear()+'-'+(n.getMonth()+1)+'-'+n.getDate()]||null;
 }
 [].forEach.call(bar.querySelectorAll('.dbtn'),function(b){
  b.onclick=function(){
   var g=b.dataset.go;
   go(g==='today'? (todayId()||'D1') : g);
  };
 });

 // 捲動時標示目前這一天
 var days=[].slice.call(document.querySelectorAll('.day,#overview'));
 var btns={};
 [].forEach.call(bar.querySelectorAll('.dbtn'),function(b){ btns[b.dataset.go]=b; });
 var io=new IntersectionObserver(function(es){
  es.forEach(function(e){
   var b=btns[e.target.id];
   if(!b) return;
   if(e.isIntersecting){
    [].forEach.call(bar.querySelectorAll('.dbtn'),function(x){x.classList.remove('on');});
    b.classList.add('on');
    b.scrollIntoView({inline:'center',block:'nearest',behavior:'smooth'});
   }
  });
 },{rootMargin:'-70px 0px -65% 0px'});
 days.forEach(function(d){io.observe(d);});

 document.getElementById('topBtn').onclick=function(){scrollTo({top:0,behavior:'smooth'});};

 // 開啟時跳到今天(有 hash 就尊重 hash)
 if(!location.hash){
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
