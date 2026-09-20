// Employee operations page: renders /api/ops/me and posts actions.
// Field names follow OpsItem.to_dict() in xissite/models.py; the contract
// test in tests/test_panel_contract.py fails if this drifts from the API.
(function(){
  var API='/api/ops';
  var CSRF=document.querySelector('meta[name="csrf-token"]')?.content||'';
  var ME=document.body.getAttribute('data-username')||'';
  var els={tasks:document.getElementById('ops-tasks'),checklists:document.getElementById('ops-checklists'),
           notices:document.getElementById('ops-notices'),toast:document.getElementById('ops-toast')};

  function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;')}
  function checked(r){return r.json().catch(function(){return {}}).then(function(d){if(!r.ok)throw new Error(d.error||('HTTP '+r.status));return d})}
  function toast(msg,isError){els.toast.textContent=msg;els.toast.className='toast show'+(isError?' err':'');setTimeout(function(){els.toast.className='toast'},3000)}
  function when(iso){if(!iso)return '';var d=new Date(iso);return d.toLocaleString()}
  function due(iso){
    if(!iso)return '';
    var ms=new Date(iso).getTime()-Date.now(),h=Math.round(Math.abs(ms)/36e5);
    var span=h<1?'under an hour':h<48?h+'h':Math.round(h/24)+'d';
    return ms<0?'<span class="crit">overdue '+span+'</span>':'due in '+span;
  }
  function prio(p){var c=p==='critical'?'crit':p==='high'?'warn':'ok';return '<span class="'+c+'">'+esc(p)+'</span>'}
  function dot(item){return item.status==='done'?'dot-g':item.priority==='critical'?'dot-r':item.priority==='high'?'dot-y':'dot-g'}

  function renderTasks(items){
    if(!items.length){els.tasks.innerHTML='<div class="ops-empty">Nothing assigned to you yet.</div>';return}
    var html='';
    items.forEach(function(item){
      var done=item.status==='done';
      html+='<div class="ops-task'+(done?' done':'')+'"><div class="ops-task-status"><span class="dot '+dot(item)+'"></span></div><div class="ops-task-body">'+
        '<div class="ops-task-title">'+esc(item.title)+'</div>'+
        (item.body?'<div class="ops-task-desc">'+esc(item.body)+'</div>':'')+
        '<div class="ops-task-meta">'+(done?'<span class="badge-ok">Completed by '+esc(item.state.done_by||'')+' '+esc(when(item.state.done_at))+'</span>':'<span>Open</span>')+
        (item.due_at?'<span title="'+esc(when(item.due_at))+'">'+due(item.due_at)+'</span>':'')+'<span>Priority: '+prio(item.priority)+'</span></div>'+
        '<div class="ops-actions">'+(done?'<button class="btn btn-sm btn-outline" onclick="opsAct('+item.id+',\'reopen\')">Reopen</button>':
          '<button class="btn btn-sm btn-primary" onclick="opsAct('+item.id+',\'complete\')">Mark done</button>')+'</div></div></div>';
    });
    els.tasks.innerHTML=html;
  }

  function renderChecklists(items){
    if(!items.length){els.checklists.innerHTML='<div class="ops-empty">No checklists assigned.</div>';return}
    var html='';
    items.forEach(function(item){
      var steps=item.steps||[];
      var ticked=item.state.steps||{},total=steps.length,doneN=steps.filter(function(s){return ticked[s.key]}).length;
      var allDone=total>0&&doneN===total,done=item.status==='done';
      html+='<div class="ops-checklist"><div class="ops-checklist-title">'+esc(item.title)+(done?' <span class="badge-ok">Done</span>':'')+'</div>'+
        (item.body?'<div class="ops-task-desc">'+esc(item.body)+'</div>':'');
      steps.forEach(function(step){
        var on=!!ticked[step.key],by=on?' title="'+esc(ticked[step.key].by)+' '+esc(when(ticked[step.key].at))+'"':'';
        html+='<label class="ops-checklist-item'+(on?' checked':'')+'"'+by+'><input type="checkbox"'+(on?' checked':'')+(done?' disabled':'')+
          ' data-item-id="'+item.id+'" data-step-key="'+esc(step.key)+'">'+esc(step.label)+'</label>';
      });
      html+='<div class="ops-checklist-progress">'+doneN+' / '+total+' complete'+(item.due_at?' &middot; '+due(item.due_at):'')+'</div>'+
        '<div class="ops-actions">'+(done?'<button class="btn btn-sm btn-outline" onclick="opsAct('+item.id+',\'reopen\')">Reopen</button>':
          (allDone?'<button class="btn btn-sm btn-primary" onclick="opsAct('+item.id+',\'complete\')">Mark done</button>':''))+'</div></div>';
    });
    els.checklists.innerHTML=html;
  }

  function renderNotices(items){
    if(!items.length){els.notices.innerHTML='<div class="ops-empty">No notices.</div>';return}
    var html='';
    items.slice().sort(function(a,b){return (a.state.acks[ME]?1:0)-(b.state.acks[ME]?1:0)}).forEach(function(item){
      var acked=item.state.acks[ME],color=item.priority==='critical'?'var(--crit)':item.priority==='high'?'var(--warn)':'var(--g)';
      html+='<div class="ops-notif'+(acked?' acked':'')+'" style="border-left:3px solid '+color+'"><div class="ops-notif-icon"><span class="dot '+dot(item)+'"></span></div><div class="ops-notif-body">'+
        '<div class="ops-notif-text"><strong>'+esc(item.title)+'</strong>'+(item.body?' '+esc(item.body):'')+'</div>'+
        '<div class="ops-notif-time">'+esc(when(item.pushed_at))+(acked?' &middot; acknowledged '+esc(when(acked)):'')+'</div>'+
        (acked?'':'<div class="ops-actions"><button class="btn btn-sm btn-outline" onclick="opsAct('+item.id+',\'ack\')">Acknowledge</button></div>')+'</div></div>';
    });
    els.notices.innerHTML=html;
  }

  function render(items){
    renderTasks(items.filter(function(i){return i.kind==='task'}));
    renderChecklists(items.filter(function(i){return i.kind==='checklist'}));
    renderNotices(items.filter(function(i){return i.kind==='notice'}));
  }

  function load(){
    fetch(API+'/me',{credentials:'same-origin'}).then(checked).then(function(d){render(d.items||[])})
      .catch(function(e){['tasks','checklists','notices'].forEach(function(k){els[k].innerHTML='<div class="ops-empty">Could not load: '+esc(e.message)+'</div>'})});
  }

  window.opsAct=function(id,action,stepKey){
    fetch(API+'/items/'+id+'/events',{method:'POST',credentials:'same-origin',
      headers:{'Content-Type':'application/json','X-CSRFToken':CSRF},
      body:JSON.stringify({action:action,step_key:stepKey||null})})
      .then(checked).then(function(){toast('Saved');load()}).catch(function(e){toast('Error: '+e.message,true);load()});
  };

  els.checklists.addEventListener('change', function(e){
    var box = e.target;
    if (!box.matches('input[type="checkbox"][data-step-key]')) return;
    opsAct(parseInt(box.getAttribute('data-item-id'), 10), box.checked ? 'tick' : 'untick', box.getAttribute('data-step-key'));
  });

  load();
  setInterval(load,60000);
})();
