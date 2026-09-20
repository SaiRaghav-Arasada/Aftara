(() => {
const settings=document.querySelector('input[name=all_settings]')?.form;
let dirty=false;
settings?.addEventListener('input',()=>dirty=true);
settings?.addEventListener('change',()=>dirty=true);
settings?.addEventListener('submit',()=>dirty=false);
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
const message=document.getElementById('finder-message');
if(!message)return;
let wasBusy=false;
async function refresh(){
 try{
  const r=await fetch('/browser-status');
  if(r.status===401){location.href='/login';return;}
  if(!r.ok)throw Error();
  const s=await r.json();message.textContent=s.message;
  document.getElementById('run-badge').textContent=s.busy?'Working':'Ready';
  document.querySelectorAll('[data-busy-button]').forEach(b=>b.disabled=s.busy);
  if(wasBusy&&!s.busy&&s.imported>0){document.title='Ready to review · Aftara';}
  if(location.pathname==='/linkedin' && Boolean(document.querySelector('.linkedin-frame'))!==Boolean(s.browser_open))location.reload();
  wasBusy=s.busy;
 }catch(_){message.textContent='Connection interrupted. Reload this page to reconnect.';}
}
refresh();setInterval(refresh,4000);
})();
