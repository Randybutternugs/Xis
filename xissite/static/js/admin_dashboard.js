(function(){
'use strict';
var API='/api/admin';
var CSRF=document.querySelector('meta[name="csrf-token"]')?.content||'';
var REFRESH=20;
var cd=REFRESH,cdTimer,refreshTimer;
var visDays=7;
// Caches to prevent flicker
var cache={users:null,logins:null,stats:null,visitors:null,security:null,customers:null,purchases:null,feedback:null};

// ---- Utility ---------------------------------------------------------------
function esc(s){var d=document.createElement('div');d.textContent=s||'';return d.innerHTML}
function relTime(iso){
  if(!iso)return'--';
  var diff=Math.max(0,Math.floor((Date.now()-new Date(iso).getTime())/1000));
  if(diff<60)return diff+'s ago';if(diff<3600)return Math.floor(diff/60)+'m ago';
  if(diff<86400)return Math.floor(diff/3600)+'h ago';return Math.floor(diff/86400)+'d ago';
}
function fullDate(iso){if(!iso)return'--';return new Date(iso).toLocaleString()}
function showToast(msg){var t=document.getElementById('toast-el');t.textContent=msg;t.classList.add('show');setTimeout(function(){t.classList.remove('show')},3000)}
function openModal(id){document.getElementById(id).classList.add('show')}
function closeModal(id){document.getElementById(id).classList.remove('show')}
function parseUA(ua){
  if(!ua)return{browser:'Unknown',os:'Unknown',device:'Unknown'};
  var b='Unknown',o='Unknown';
  if(/Edg\//.test(ua))b='Edge';else if(/OPR\//.test(ua))b='Opera';else if(/Chrome\//.test(ua))b='Chrome';else if(/Safari\//.test(ua)&&!/Chrome/.test(ua))b='Safari';else if(/Firefox\//.test(ua))b='Firefox';
  if(/Windows NT 10/.test(ua))o='Windows';else if(/Mac OS X/.test(ua))o='macOS';else if(/Linux/.test(ua))o='Linux';else if(/Android/.test(ua))o='Android';else if(/iPhone|iPad/.test(ua))o='iOS';
  var dev=/Mobile|Android|iPhone/.test(ua)?'Mobile':'Desktop';
  return{browser:b,os:o,device:dev};
}
function setApiStatus(ok){
  var dot=document.getElementById('api-dot'),lbl=document.getElementById('api-label');
  dot.className='dot '+(ok?'dot-g refresh-pulse':'dot-r');lbl.textContent=ok?'Connected':'API Unreachable';
}

// ---- CSRF-aware fetch helpers ----------------------------------------------
function apiPost(path,body){
  return fetch(API+path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':CSRF},credentials:'same-origin',body:JSON.stringify(body)});
}
function apiPut(path,body){
  return fetch(API+path,{method:'PUT',headers:{'Content-Type':'application/json','X-CSRFToken':CSRF},credentials:'same-origin',body:JSON.stringify(body)});
}
function apiDelete(path){
  return fetch(API+path,{method:'DELETE',headers:{'X-CSRFToken':CSRF},credentials:'same-origin'});
}

// ---- Section nav scroll ----------------------------------------------------
function initNav(){
  document.querySelectorAll('.sec-nav a').forEach(function(a){
    a.addEventListener('click',function(e){
      e.preventDefault();
      var tgt=document.querySelector(this.getAttribute('href'));
      if(tgt)tgt.scrollIntoView({behavior:'smooth',block:'start'});
      document.querySelectorAll('.sec-nav a').forEach(function(l){l.classList.remove('active')});
      this.classList.add('active');
    });
  });
  var secEls=document.querySelectorAll('.sec-card');
  var navLinks=document.querySelectorAll('.sec-nav a');
  window.addEventListener('scroll',function(){
    var scrollY=window.scrollY+100;
    secEls.forEach(function(sec){
      if(sec.offsetTop<=scrollY&&sec.offsetTop+sec.offsetHeight>scrollY){
        var id=sec.id;
        navLinks.forEach(function(l){l.classList.toggle('active',l.getAttribute('href')==='#'+id)});
      }
    });
  },{passive:true});
}

// ---- Stats -----------------------------------------------------------------
function fetchStats(){
  fetch(API+'/stats').then(function(r){if(!r.ok)throw new Error();return r.json()}).then(function(d){
    if(d.error){setApiStatus(false);return}
    cache.stats=d;setApiStatus(true);
    var su=document.getElementById('s-users'),sc=document.getElementById('s-customers'),sp=document.getElementById('s-purchases'),sf=document.getElementById('s-feedback');
    var uCount=d.user_counts?d.user_counts.active:0;
    su.textContent=uCount;su.className='val'+(uCount>0?' ok':'');
    sc.textContent=d.customer_count||0;
    var pc=d.purchase_count||0,paid=d.paid_count||0;
    sp.innerHTML=esc(String(pc))+'<span class="val-sub">'+paid+' paid</span>';
    var fb=d.feedback_unresolved||0;
    sf.textContent=fb;sf.className='val'+(fb>0?' warn':'');
    // Security stats
    var l24=d.login_24h||{};
    document.getElementById('sec-total').textContent=l24.total||0;
    document.getElementById('sec-ok').textContent=l24.successful||0;
    var fail=l24.failed||0;
    var secF=document.getElementById('sec-fail');secF.textContent=fail;secF.className='val'+(fail>0?' crit':'');
  }).catch(function(){setApiStatus(false)});
}

// ---- Users -----------------------------------------------------------------
function fetchUsers(){
  fetch(API+'/users').then(function(r){if(!r.ok)throw new Error();return r.json()}).then(function(d){
    if(!Array.isArray(d))return;
    cache.users=d;renderUsers(d);
  }).catch(function(){});
}
function renderUsers(users){
  var tb=document.getElementById('users-body'),tbl=document.getElementById('users-table'),emp=document.getElementById('users-empty'),cnt=document.getElementById('user-count');
  if(!users||users.length===0){tbl.style.display='none';emp.style.display='block';emp.textContent='No users';cnt.textContent='';return}
  emp.style.display='none';tbl.style.display='table';cnt.textContent='('+users.length+')';
  var html='';
  users.forEach(function(u){
    var isHash=u.email&&u.email.length>50;
    var label=isHash?'Primary Admin':esc(u.email);
    var typeBadge=u.user_type==='admin'?'badge-ok':'badge-off';
    var statusBadge=u.status==='active'?'badge-ok':u.status==='suspended'?'badge-warn':'badge-crit';
    var isPrimary=isHash;
    html+='<tr>'+
      '<td>'+u.id+'</td>'+
      '<td><span class="badge '+typeBadge+'">'+esc(u.user_type)+'</span></td>'+
      '<td><span class="badge '+statusBadge+'">'+esc(u.status||'active')+'</span></td>'+
      '<td title="'+esc(fullDate(u.last_login))+'">'+relTime(u.last_login)+'</td>'+
      '<td>'+(u.failed_attempts||0)+'</td>'+
      '<td style="font-size:.85em;color:var(--mut)">'+esc(u.notes||'--')+'</td>'+
      '<td style="white-space:nowrap">'+
        (u.status==='suspended'?'<button class="btn btn-primary btn-sm" onclick="activateUser('+u.id+')">Activate</button> ':'<button class="btn btn-sm btn-outline" style="color:var(--warn);border-color:var(--warn)" onclick="suspendUser('+u.id+')">Suspend</button> ')+
        '<button class="btn btn-sm btn-outline" onclick="openEditUser('+u.id+')">Edit</button> '+
        (isPrimary?'':'<button class="btn btn-sm btn-danger" onclick="deleteUser('+u.id+')">Delete</button>')+
      '</td></tr>';
  });
  tb.innerHTML=html;
}
window.openCreateUser=function(){
  document.getElementById('cu-email').value='';document.getElementById('cu-pass').value='';
  document.getElementById('cu-type').value='admin';document.getElementById('cu-display-name').value='';document.getElementById('cu-notes').value='';
  openModal('modal-create-user');
};
window.submitCreateUser=function(){
  var email=document.getElementById('cu-email').value.trim(),pass=document.getElementById('cu-pass').value,
      type=document.getElementById('cu-type').value,displayName=document.getElementById('cu-display-name').value.trim(),notes=document.getElementById('cu-notes').value;
  if(!email||!pass){showToast('Email and password required');return}
  apiPost('/users',{email:email,password:pass,user_type:type,display_name:displayName||null,notes:notes||null})
    .then(function(r){return r.json()}).then(function(d){
      if(d.error){showToast('Error: '+(d.error||'Unknown'));return}
      showToast('User created');closeModal('modal-create-user');fetchUsers();
    }).catch(function(){showToast('Failed to create user')});
};
window.openEditUser=function(id){
  var u=(cache.users||[]).find(function(x){return x.id===id});
  if(!u)return;
  document.getElementById('eu-id').value=id;
  document.getElementById('eu-type').value=u.user_type;
  document.getElementById('eu-status').value=u.status||'active';
  document.getElementById('eu-display-name').value=u.display_name||'';
  document.getElementById('eu-notes').value=u.notes||'';
  document.getElementById('eu-pass').value='';
  openModal('modal-edit-user');
};
window.submitEditUser=function(){
  var id=document.getElementById('eu-id').value;
  var body={user_type:document.getElementById('eu-type').value,status:document.getElementById('eu-status').value,display_name:document.getElementById('eu-display-name').value.trim()||null,notes:document.getElementById('eu-notes').value||null};
  var pass=document.getElementById('eu-pass').value;
  if(pass)body.password=pass;
  apiPut('/users/'+id,body)
    .then(function(r){return r.json()}).then(function(d){
      if(d.error){showToast('Error: '+d.error);return}
      showToast('User updated');closeModal('modal-edit-user');fetchUsers();
    }).catch(function(){showToast('Failed to update')});
};
window.suspendUser=function(id){if(confirm('Suspend this user?'))apiPost('/users/'+id+'/suspend',{}).then(function(){showToast('User suspended');fetchUsers()})};
window.activateUser=function(id){apiPost('/users/'+id+'/activate',{}).then(function(){showToast('User activated');fetchUsers()})};
window.deleteUser=function(id){if(confirm('Delete this user? This is a soft delete.'))apiDelete('/users/'+id).then(function(){showToast('User deleted');fetchUsers()})};

// ---- Logins ----------------------------------------------------------------
var expandedLoginId=null;
function fetchLogins(){
  var params=[];
  var res=document.getElementById('login-filter-result').value;if(res)params.push('success='+res);
  var ip=document.getElementById('login-filter-ip').value.trim();if(ip)params.push('ip='+encodeURIComponent(ip));
  params.push('limit=50');
  fetch(API+'/login-attempts?'+params.join('&')).then(function(r){if(!r.ok)throw new Error();return r.json()}).then(function(d){
    if(!Array.isArray(d))return;
    cache.logins=d;renderLogins(d);
  }).catch(function(){});
}
function renderLogins(attempts){
  var tb=document.getElementById('logins-body'),tbl=document.getElementById('logins-table'),emp=document.getElementById('logins-empty'),cnt=document.getElementById('login-count');
  if(!attempts||attempts.length===0){tbl.style.display='none';emp.style.display='block';cnt.textContent='';return}
  emp.style.display='none';tbl.style.display='table';cnt.textContent='('+attempts.length+')';
  var html='';
  attempts.forEach(function(a){
    var ok=a.success;
    var dotC=ok?'dot-g':'dot-r';
    var rowClass=ok?'':'fail-row';
    html+='<tr class="expandable '+rowClass+'" onclick="toggleLoginDetail('+a.id+')">'+
      '<td title="'+esc(fullDate(a.timestamp))+'" style="font-family:Consolas,monospace;font-size:.85em;color:var(--mut);white-space:nowrap">'+relTime(a.timestamp)+'</td>'+
      '<td style="font-family:Consolas,monospace;font-size:.85em">'+esc(a.ip_address||'--')+'</td>'+
      '<td style="font-size:.85em">'+esc(a.username_attempted||'--')+'</td>'+
      '<td><span class="dot '+dotC+'"></span> '+(ok?'OK':'Fail')+'</td>'+
      '<td style="font-size:.8em;color:var(--mut)">'+esc(a.failure_reason||'')+'</td>'+
      '<td style="font-size:.7em;color:var(--mut)">&#9660;</td></tr>';
    // Detail row
    var ua=parseUA(a.user_agent);
    html+='<tr id="ld-'+a.id+'" style="display:none"><td colspan="6" style="padding:0"><div class="login-detail show" style="display:block">'+
      '<div class="ld-row"><span class="ld-label">Timestamp</span><span class="ld-val">'+esc(fullDate(a.timestamp))+'</span></div>'+
      '<div class="ld-row"><span class="ld-label">IP Address</span><span class="ld-val">'+esc(a.ip_address||'--')+'</span></div>'+
      '<div class="ld-row"><span class="ld-label">Username</span><span class="ld-val">'+esc(a.username_attempted||'--')+'</span></div>'+
      '<div class="ld-row"><span class="ld-label">Result</span><span class="ld-val">'+(a.success?'<span class="ok">Success</span>':'<span class="crit">Failed</span> - '+esc(a.failure_reason||'unknown'))+'</span></div>'+
      '<div class="ld-row"><span class="ld-label">Matched Type</span><span class="ld-val">'+esc(a.user_type_matched||'none')+'</span></div>'+
      '<div class="ld-row"><span class="ld-label">Browser</span><span class="ld-val">'+esc(ua.browser)+' on '+esc(ua.os)+' ('+esc(ua.device)+')</span></div>'+
      '<div class="ld-row"><span class="ld-label">User Agent</span><span class="ld-val" style="font-size:.8em;color:var(--mut)">'+esc(a.user_agent||'--')+'</span></div>'+
      (a.ip_address?'<div style="margin-top:8px"><button class="btn btn-sm btn-danger ban-ip-btn" data-ip="'+esc(a.ip_address)+'">Ban This IP</button></div>':'')+
    '</div></td></tr>';
  });
  tb.innerHTML=html;
  // Re-expand if one was open
  if(expandedLoginId){var el=document.getElementById('ld-'+expandedLoginId);if(el)el.style.display='table-row'}
}
window.toggleLoginDetail=function(id){
  if(expandedLoginId===id){document.getElementById('ld-'+id).style.display='none';expandedLoginId=null;return}
  if(expandedLoginId){var prev=document.getElementById('ld-'+expandedLoginId);if(prev)prev.style.display='none'}
  document.getElementById('ld-'+id).style.display='table-row';expandedLoginId=id;
};

// Delegated handler for ban-ip buttons (avoids inline onclick XSS)
document.addEventListener('click',function(e){
  var btn=e.target.closest('.ban-ip-btn');
  if(!btn)return;
  e.stopPropagation();
  banIPQuick(btn.getAttribute('data-ip'));
});

// ---- Login Heatmap ---------------------------------------------------------
function fetchLoginHeatmap(){
  fetch(API+'/security/login-heatmap?days=7').then(function(r){if(!r.ok)throw new Error();return r.json()}).then(function(d){
    if(!d.hours)return;renderLoginHeatmap(d);
  }).catch(function(){});
}
function renderLoginHeatmap(d){
  var el=document.getElementById('sec-heatmap');
  var hours=d.hours||[],mx=d.max||1;
  var html='';
  for(var i=0;i<24;i++){
    var h=hours[i]||{total:0,failed:0};
    var tPct=Math.round((h.total/mx)*100);
    html+='<div class="heatmap-cell" title="'+i+':00 - '+h.total+' total, '+h.failed+' failed">'+
      '<div class="heatmap-bar">'+
        '<div class="heatmap-fill" style="height:'+tPct+'%"></div>'+
        (h.failed>0?'<div class="heatmap-fail" style="height:'+Math.round((h.failed/mx)*100)+'%"></div>':'')+
      '</div>'+
      '<span class="heatmap-hour">'+i+'</span></div>';
  }
  el.innerHTML=html;
}

// ---- Customers -------------------------------------------------------------
function fetchCustomers(){
  var search=document.getElementById('cust-search').value.trim();
  fetch(API+'/customers?limit=50'+(search?'&search='+encodeURIComponent(search):'')).then(function(r){if(!r.ok)throw new Error();return r.json()}).then(function(d){
    if(d.error)return;
    var custs=d.customers||d||[];cache.customers=custs;renderCustomers(custs,d.total);
  }).catch(function(){});
}
function renderCustomers(custs,total){
  var tb=document.getElementById('cust-body'),tbl=document.getElementById('cust-table'),emp=document.getElementById('cust-empty'),cnt=document.getElementById('cust-count');
  if(!custs||custs.length===0){tbl.style.display='none';emp.style.display='block';cnt.textContent='';return}
  emp.style.display='none';tbl.style.display='table';cnt.textContent='('+(total||custs.length)+')';
  var html='';
  custs.forEach(function(c){
    html+='<tr>'+
      '<td>'+c.id+'</td><td>'+esc(c.email)+'</td><td>'+esc(c.name||'--')+'</td>'+
      '<td title="'+esc(fullDate(c.creation_date))+'">'+relTime(c.creation_date)+'</td>'+
      '<td>'+(c.purchase_count||0)+'</td>'+
      '<td><button class="btn btn-sm btn-outline" onclick="viewCustomer('+c.id+')">View</button> <button class="btn btn-sm btn-danger" onclick="deleteCustomer('+c.id+')">Delete</button></td></tr>';
  });
  tb.innerHTML=html;
}
window.viewCustomer=function(id){
  var el=document.getElementById('cust-detail-content');el.innerHTML='Loading...';openModal('modal-cust-detail');
  fetch(API+'/customers/'+id).then(function(r){return r.json()}).then(function(d){
    if(d.error){el.innerHTML='<span class="crit">Error: '+esc(d.error)+'</span>';return}
    var html='<div style="margin-bottom:12px"><strong>'+esc(d.email)+'</strong><br><span style="color:var(--mut);font-size:.85em">'+esc(d.name||'--')+' - Joined '+relTime(d.creation_date)+'</span></div>';
    var p=d.purchases||[];
    if(p.length>0){
      html+='<table class="table"><thead><tr><th>Order #</th><th>Product</th><th>Location</th><th>Status</th><th>Date</th></tr></thead><tbody>';
      p.forEach(function(o){
        var sb=o.pay_status==='paid'?'badge-ok':o.pay_status==='pending'?'badge-warn':'badge-crit';
        html+='<tr><td>'+o.id+'</td><td>'+esc(o.product_name)+'</td><td>'+esc((o.city||'')+', '+(o.state||''))+'</td><td><span class="badge '+sb+'">'+esc(o.pay_status)+'</span></td><td>'+relTime(o.purchase_date)+'</td></tr>';
      });
      html+='</tbody></table>';
    }else{html+='<div class="alert-none">No purchases</div>';}
    el.innerHTML=html;
    document.getElementById('cd-cust-id').value=d.id;
  }).catch(function(){el.innerHTML='Failed to load'});
};
window.deleteCustomer=function(id){if(confirm('Delete this customer and all their purchases?'))apiDelete('/customers/'+id).then(function(){showToast('Customer deleted');fetchCustomers()})};

// ---- Orders (Purchases) ----------------------------------------------------
function fetchPurchases(){
  var st=document.getElementById('purch-status').value;
  fetch(API+'/purchases?limit=50'+(st?'&status='+st:'')).then(function(r){if(!r.ok)throw new Error();return r.json()}).then(function(d){
    if(!Array.isArray(d))return;
    cache.purchases=d;renderPurchases(d);
  }).catch(function(){});
}
function renderPurchases(items){
  var tb=document.getElementById('purch-body'),tbl=document.getElementById('purch-table'),emp=document.getElementById('purch-empty'),cnt=document.getElementById('purch-count');
  if(!items||items.length===0){tbl.style.display='none';emp.style.display='block';cnt.textContent='';return}
  emp.style.display='none';tbl.style.display='table';cnt.textContent='('+items.length+')';
  var html='';
  items.forEach(function(p){
    var sb=p.pay_status==='paid'?'badge-ok':p.pay_status==='pending'?'badge-warn':'badge-crit';
    html+='<tr><td>'+p.id+'</td><td>'+esc(p.product_name)+'</td><td>'+esc(p.customer_email||'--')+'</td>'+
      '<td>'+esc((p.city||'')+', '+(p.state||''))+'</td>'+
      '<td><span class="badge '+sb+'">'+esc(p.pay_status||'--')+'</span></td>'+
      '<td title="'+esc(fullDate(p.purchase_date))+'">'+relTime(p.purchase_date)+'</td></tr>';
  });
  tb.innerHTML=html;
}

// ---- Feedback --------------------------------------------------------------
function fbAgeColor(dateStr){
  if(!dateStr)return'var(--mut)';
  var hours=(Date.now()-new Date(dateStr).getTime())/3600000;
  if(hours<72)return'var(--g)';if(hours<168)return'var(--blue,#3b82f6)';if(hours<336)return'var(--warn)';return'var(--crit)';
}
function fetchFeedback(){
  var ty=document.getElementById('fb-filter-type').value,res=document.getElementById('fb-filter-resolved').value;
  var params=[];if(ty)params.push('type='+ty);if(res)params.push('resolved='+res);
  fetch(API+'/feedback?'+params.join('&')).then(function(r){if(!r.ok)throw new Error();return r.json()}).then(function(d){
    if(!Array.isArray(d))return;
    cache.feedback=d;renderFeedback(d);
  }).catch(function(){});
}
function renderFeedback(items){
  var list=document.getElementById('fb-list'),emp=document.getElementById('fb-empty'),cnt=document.getElementById('fb-count');
  if(!items||items.length===0){list.innerHTML='';emp.style.display='block';cnt.textContent='';return}
  emp.style.display='none';cnt.textContent='('+items.length+')';
  var html='';
  items.forEach(function(f){
    var ref='TULL-'+String(f.id).padStart(4,'0');
    var typeColors={General:'var(--blue)',Technical:'#a855f7',Order:'var(--warn)',Feature:'#14b8a6'};
    var tc=typeColors[f.feedbacktype]||'var(--mut)';
    var statusBadge=f.resolved?'badge-ok':'badge-warn';
    var statusText=f.resolved?'Resolved':'Open';
    html+='<div style="background:#0a0a0a;border:1px solid #1a1a1a;padding:10px 14px;margin-bottom:4px">'+
      '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;cursor:pointer" onclick="toggleFb('+f.id+')">'+
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'+
          '<span class="fb-age-dot" style="background:'+fbAgeColor(f.date)+'"></span>'+
          '<span style="font-family:Consolas,monospace;font-size:.8em;color:var(--g)">'+ref+'</span>'+
          '<span style="font-size:.8em">'+esc(f.feedbackmail)+'</span>'+
          '<span style="padding:2px 8px;font-size:.6em;font-weight:700;text-transform:uppercase;letter-spacing:1px;background:rgba(255,255,255,.05);color:'+tc+'">'+esc(f.feedbacktype||'--')+'</span>'+
          '<span class="badge '+statusBadge+'" style="font-size:.6em">'+statusText+'</span>'+
        '</div>'+
        '<div style="display:flex;align-items:center;gap:8px">'+
          '<span style="font-size:.75em;color:var(--mut)">'+relTime(f.date)+'</span>'+
          '<span style="font-size:.7em;color:var(--mut)">&#9660;</span>'+
        '</div>'+
      '</div>'+
      '<div class="fb-detail" id="fb-'+f.id+'">'+
        (f.feedbackorderid?'<div style="font-size:.8em;color:var(--mut);margin-bottom:4px">Order: '+esc(f.feedbackorderid)+'</div>':'')+
        (f.serial_number?'<div style="font-size:.8em;color:var(--mut);margin-bottom:4px">Serial: '+esc(f.serial_number)+'</div>':'')+
        '<div class="fb-msg">'+esc(f.feedbackfullfield||'No message')+'</div>'+
        '<label style="display:block;font-size:.7em;color:var(--mut);text-transform:uppercase;letter-spacing:1px;margin:8px 0 4px">Admin Notes</label>'+
        '<textarea id="fb-notes-'+f.id+'" style="width:100%;min-height:50px;background:#0a0a0a;border:1px solid var(--brd);color:var(--txt);padding:6px 8px;font-size:.85em;font-family:inherit;resize:vertical">'+esc(f.admin_notes||'')+'</textarea>'+
        '<div style="display:flex;gap:8px;margin-top:8px">'+
          '<button class="btn btn-sm '+(f.resolved?'btn-outline':'btn-primary')+'" onclick="resolveFeedback('+f.id+','+(!f.resolved)+')">'+(f.resolved?'Mark Open':'Mark Resolved')+'</button>'+
          '<button class="btn btn-sm btn-outline" onclick="updateFeedbackNotes('+f.id+')">Save Notes</button>'+
          '<button class="btn btn-sm btn-danger" onclick="deleteFb('+f.id+')">Delete</button>'+
        '</div>'+
      '</div>'+
    '</div>';
  });
  list.innerHTML=html;
}
window.toggleFb=function(id){var el=document.getElementById('fb-'+id);if(el)el.classList.toggle('show')};
window.resolveFeedback=function(id,val){
  apiPut('/feedback/'+id,{resolved:val})
    .then(function(r){return r.json()}).then(function(){showToast(val?'Marked resolved':'Marked open');fetchFeedback()}).catch(function(){showToast('Failed')});
};
window.updateFeedbackNotes=function(id){
  var notes=document.getElementById('fb-notes-'+id).value;
  apiPut('/feedback/'+id,{admin_notes:notes})
    .then(function(){showToast('Notes saved')}).catch(function(){showToast('Failed')});
};
window.deleteFb=function(id){if(confirm('Delete this feedback?'))apiDelete('/feedback/'+id).then(function(){showToast('Deleted');fetchFeedback()})};

// ---- Visitors --------------------------------------------------------------
function fetchVisitors(){
  fetch(API+'/visitors?days='+visDays).then(function(r){return r.json()}).then(function(d){
    if(d.error)return;cache.visitors=d;renderVisitors(d);
  }).catch(function(){});
  fetchVisitorHeatmap();
}
function renderVisitors(d){
  var chart=document.getElementById('vis-chart'),emp=document.getElementById('vis-empty');
  document.getElementById('vis-unique').textContent=d.total_unique||0;
  document.getElementById('vis-views').textContent=d.total_views||0;
  document.getElementById('vis-avg').textContent=d.avg_daily||0;
  var topP=(d.top_pages||[])[0];
  document.getElementById('vis-top').textContent=topP?topP.path:'--';
  var days=d.daily||[];
  if(!days.length){chart.innerHTML='';emp.style.display='block';return}
  emp.style.display='none';
  var maxV=1;days.forEach(function(x){if(x.views>maxV)maxV=x.views});
  var html='';
  days.forEach(function(x){
    var pct=Math.round((x.views/maxV)*100);
    var label=x.day||'--';if(label.length>5)label=label.substring(5);
    html+='<div class="bar-row"><span class="bar-label">'+esc(label)+'</span><div class="bar-track"><div class="bar-fill" style="width:'+pct+'%"></div></div><span class="bar-count">'+x.views+'</span></div>';
  });
  chart.innerHTML=html;
  // Top pages
  var pages=d.top_pages||[];
  var ptb=document.getElementById('vis-pages-body'),ptbl=document.getElementById('vis-pages-table');
  if(pages.length>0){
    ptbl.style.display='table';
    var ph='';pages.forEach(function(p){ph+='<tr><td style="font-family:Consolas,monospace">'+esc(p.path)+'</td><td>'+p.hits+'</td><td>'+p.unique_ips+'</td></tr>'});
    ptb.innerHTML=ph;
  }else{ptbl.style.display='none'}
}
function fetchVisitorHeatmap(){
  fetch(API+'/visitors/heatmap?days='+visDays).then(function(r){if(!r.ok)throw new Error();return r.json()}).then(function(d){
    if(!d.hours)return;renderVisitorHeatmap(d);
  }).catch(function(){});
}
function renderVisitorHeatmap(d){
  var el=document.getElementById('vis-heatmap'),emp=document.getElementById('vis-heatmap-empty');
  var hours=d.hours||[],mx=d.max||1;
  if(!hours.length){el.innerHTML='';emp.style.display='block';return}
  emp.style.display='none';
  var html='';
  for(var i=0;i<24;i++){
    var cnt=hours[i]||0;
    var pct=Math.round((cnt/mx)*100);
    html+='<div class="heatmap-cell" title="'+i+':00 - '+cnt+' visits">'+
      '<div class="heatmap-bar"><div class="heatmap-fill" style="height:'+pct+'%"></div></div>'+
      '<span class="heatmap-hour">'+i+'</span></div>';
  }
  el.innerHTML=html;
}
window.setVisPeriod=function(days,btn){
  visDays=days;
  document.querySelectorAll('.vis-period').forEach(function(b){b.classList.remove('active')});
  btn.classList.add('active');fetchVisitors();
};

// ---- Security --------------------------------------------------------------
var geoCache={};
function fetchSecurity(){
  fetch(API+'/security/alerts').then(function(r){return r.json()}).then(function(d){
    if(d.error)return;cache.security=d;renderSecurity(d);
  }).catch(function(){});
  fetchBannedIPs();
  fetchAuditLog();
}
function renderSecurity(d){
  var banner=document.getElementById('threat-banner'),alerts=document.getElementById('sec-alerts'),emp=document.getElementById('sec-empty');
  var bf=d.brute_force||[],sus=d.suspicious_ips||[],fu=d.failed_usernames||[];
  if(bf.length>0){banner.className='threat-crit';banner.textContent='Active threats detected - '+bf.length+' brute force source(s)'}
  else if(sus.length>0){banner.className='threat-warn';banner.textContent='Suspicious activity - '+sus.length+' IP(s) with repeated failures'}
  else{banner.className='threat-ok';banner.textContent='No threats detected'}
  var html='';
  if(bf.length>0){
    html+='<div style="margin-bottom:12px"><div style="font-size:.65em;color:var(--crit);text-transform:uppercase;letter-spacing:2px;margin-bottom:6px;font-weight:700">Brute Force</div>';
    bf.forEach(function(b){html+='<div class="alert-item"><div><span class="alert-ip" data-ip="'+esc(b.ip)+'">'+esc(b.ip)+'</span><span class="geo-tag" data-geo-ip="'+esc(b.ip)+'"></span><span class="alert-count"> - '+b.attempts+' attempts - '+relTime(b.latest)+'</span></div><div style="display:flex;gap:6px;align-items:center"><button class="btn btn-sm btn-danger ban-ip-btn" data-ip="'+esc(b.ip)+'">Ban</button><span class="badge badge-crit">Critical</span></div></div>'});
    html+='</div>';
  }
  if(sus.length>0){
    html+='<div style="margin-bottom:12px"><div style="font-size:.65em;color:var(--warn);text-transform:uppercase;letter-spacing:2px;margin-bottom:6px;font-weight:700">Suspicious IPs</div>';
    sus.forEach(function(s){
      var sev=s.attempts>=5?'badge-crit':'badge-warn';
      html+='<div class="alert-item"><div><span class="alert-ip" data-ip="'+esc(s.ip)+'">'+esc(s.ip)+'</span><span class="geo-tag" data-geo-ip="'+esc(s.ip)+'"></span><span class="alert-count"> - '+s.attempts+' failures</span></div><div style="display:flex;gap:6px;align-items:center"><button class="btn btn-sm btn-danger ban-ip-btn" data-ip="'+esc(s.ip)+'">Ban</button><span class="badge '+sev+'">'+esc(s.severity||'warning')+'</span></div></div>';
    });
    html+='</div>';
  }
  if(fu.length>0){
    html+='<div><div style="font-size:.65em;color:var(--mut);text-transform:uppercase;letter-spacing:2px;margin-bottom:6px;font-weight:700">Failed Usernames</div>';
    html+='<div style="display:flex;flex-wrap:wrap;gap:6px">';
    fu.forEach(function(u){
      var botNames=['admin','root','test','administrator','user','guest','login','info','support'];
      var isBot=botNames.indexOf((u.username||'').toLowerCase())>=0;
      html+='<span style="padding:3px 10px;font-size:.8em;font-family:Consolas,monospace;background:'+(isBot?'rgba(255,50,50,.1);color:var(--crit)':'#0a0a0a;color:var(--txt)')+';border:1px solid #1a1a1a">'+esc(u.username)+' <span style="color:var(--mut)">('+u.attempts+')</span></span>';
    });
    html+='</div></div>';
  }
  if(!bf.length&&!sus.length&&!fu.length){emp.style.display='block';alerts.innerHTML=''}
  else{emp.style.display='none';alerts.innerHTML=html;setTimeout(resolveGeoTags,100)}
}

// ---- Geo Resolution --------------------------------------------------------
function resolveGeoTags(){
  var els=document.querySelectorAll('[data-geo-ip]');
  var ipsNeeded=[];
  els.forEach(function(el){
    var ip=el.getAttribute('data-geo-ip');
    if(geoCache[ip]){el.textContent='('+geoCache[ip]+')';return}
    if(ipsNeeded.indexOf(ip)===-1)ipsNeeded.push(ip);
  });
  if(ipsNeeded.length===0)return;
  apiPost('/security/resolve-geo',{ips:ipsNeeded.slice(0,20)})
    .then(function(r){return r.json()}).then(function(d){
      if(d.error)return;
      Object.keys(d).forEach(function(ip){
        var info=d[ip];
        var label=[info.city,info.country].filter(Boolean).join(', ');
        geoCache[ip]=label;
      });
      els.forEach(function(el){
        var ip=el.getAttribute('data-geo-ip');
        if(geoCache[ip])el.textContent='('+geoCache[ip]+')';
      });
    }).catch(function(){});
}

// ---- Banned IPs ------------------------------------------------------------
function fetchBannedIPs(){
  fetch(API+'/banned-ips?active=true').then(function(r){if(!r.ok)throw new Error();return r.json()}).then(function(d){
    if(!Array.isArray(d))return;renderBannedIPs(d);
  }).catch(function(){});
}
function renderBannedIPs(bans){
  var tb=document.getElementById('ban-body'),tbl=document.getElementById('ban-table'),emp=document.getElementById('ban-empty'),cnt=document.getElementById('ban-count');
  if(!bans||bans.length===0){tbl.style.display='none';emp.style.display='block';cnt.textContent='';return}
  emp.style.display='none';tbl.style.display='table';cnt.textContent='('+bans.length+')';
  var html='';
  bans.forEach(function(b){
    html+='<tr><td style="font-family:Consolas,monospace;font-size:.85em">'+esc(b.ip_address)+'</td>'+
      '<td style="font-size:.85em">'+esc(b.reason||'--')+'</td>'+
      '<td><span class="badge '+(b.banned_by==='auto'?'badge-warn':'badge-ok')+'">'+esc(b.banned_by||'--')+'</span></td>'+
      '<td style="font-size:.85em;color:var(--mut)">'+(b.expires_at?fullDate(b.expires_at):'Permanent')+'</td>'+
      '<td><button class="btn btn-sm btn-outline" onclick="unbanIP('+b.id+')">Unban</button></td></tr>';
  });
  tb.innerHTML=html;
}
window.openBanModal=function(ip){
  document.getElementById('ban-ip-input').value=ip||'';
  document.getElementById('ban-reason').value='';
  document.getElementById('ban-hours').value='24';
  openModal('modal-ban-ip');
};
window.submitBanIP=function(){
  var ip=document.getElementById('ban-ip-input').value.trim();
  if(!ip){showToast('IP address required');return}
  var reason=document.getElementById('ban-reason').value;
  var hours=document.getElementById('ban-hours').value;
  var body={ip_address:ip};
  if(reason)body.reason=reason;
  if(hours)body.expires_hours=parseInt(hours);
  apiPost('/banned-ips',body)
    .then(function(r){return r.json()}).then(function(d){
      if(d.error){showToast('Error: '+d.error);return}
      showToast('IP banned');closeModal('modal-ban-ip');fetchBannedIPs();
    }).catch(function(){showToast('Failed to ban IP')});
};
window.unbanIP=function(id){if(confirm('Unban this IP?'))apiDelete('/banned-ips/'+id).then(function(){showToast('IP unbanned');fetchBannedIPs()})};
window.banIPQuick=function(ip){openBanModal(ip)};

// ---- Audit Log -------------------------------------------------------------
function fetchAuditLog(){
  fetch(API+'/security/audit-log?limit=30').then(function(r){if(!r.ok)throw new Error();return r.json()}).then(function(d){
    if(!Array.isArray(d))return;renderAuditLog(d);
  }).catch(function(){});
}
function renderAuditLog(items){
  var tb=document.getElementById('audit-body'),tbl=document.getElementById('audit-table'),emp=document.getElementById('audit-empty');
  if(!items||items.length===0){tbl.style.display='none';emp.style.display='block';return}
  emp.style.display='none';tbl.style.display='table';
  var html='';
  items.forEach(function(a){
    var det=a.details||'';if(det.length>80)det=det.substring(0,80)+'...';
    html+='<tr>'+
      '<td style="white-space:nowrap;font-size:.8em;color:var(--mut)" title="'+esc(fullDate(a.timestamp))+'">'+relTime(a.timestamp)+'</td>'+
      '<td style="font-size:.85em;font-family:Consolas,monospace">'+esc(a.action)+'</td>'+
      '<td style="font-size:.85em">'+esc((a.target_type||'')+(a.target_id?' #'+a.target_id:''))+'</td>'+
      '<td style="font-size:.8em;color:var(--mut);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+esc(a.details||'')+'">'+esc(det)+'</td>'+
      '<td style="font-family:Consolas,monospace;font-size:.8em">'+esc(a.admin_ip||'--')+'</td></tr>';
  });
  tb.innerHTML=html;
}

// ---- Countdown & Refresh ---------------------------------------------------
function updateCountdown(){
  cd--;if(cd<=0)cd=REFRESH;
  document.getElementById('countdown').textContent=cd+'s';
}

function refresh(){
  cd=REFRESH;
  fetchStats();
  fetchUsers();
  fetchLogins();
  fetchLoginHeatmap();
  fetchCustomers();
  fetchPurchases();
  fetchFeedback();
  fetchVisitors();
  fetchSecurity();
}

// ---- Initialization --------------------------------------------------------
document.addEventListener('DOMContentLoaded',function(){
  initNav();
  refresh();
  refreshTimer=setInterval(refresh,REFRESH*1000);
  cdTimer=setInterval(updateCountdown,1000);
  // Close modals on overlay click
  document.querySelectorAll('.modal-overlay').forEach(function(m){
    m.addEventListener('click',function(e){if(e.target===m)m.classList.remove('show')});
  });
});
})();
