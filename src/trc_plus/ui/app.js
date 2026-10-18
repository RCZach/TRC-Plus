'use strict';
const $ = id => document.getElementById(id);
const clone = value => structuredClone(value);
let roster, baseline, profile, token, selected, view = 'players', category = 'attributes', imported, toastTimer, saving = false;
let workspaceNeedsSave=false, dirtyRecords=new Set();
let desktopUpdates=false, updateBusy=false;
let liveEnabled=false, livePending=0, liveQueue=Promise.resolve(), liveTimers=new Map(), gameValues=new Map(), undoCount=0, redoCount=0;
let syncWarnings=[];
let importDocument, gameStatus, gameLoaded = false, gamePlan, plannedRoster, gameBusy = false, connectionSettings, fieldValues={}, learningField, captureId, captureReport, capturePlayerId;
async function api(path, document){
 const options=document===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Editor-Token':token},body:JSON.stringify(document)};
 const response=await fetch(path,options),result=await response.json();
 if(response.status===404)throw Error('An older editor is still running. Close its terminal and relaunch TRC+, then use the newly opened page.');
 if(!response.ok)throw Error(result.error||'Request failed.');return result;
}
const categories = {identity:'Overview',attributes:'Attributes',tendencies:'Tendencies',badges:'Badges',vitals:'Vitals',signatures:'Signatures',gear:'Gear',accessories:'Accessories',appearance:'Appearance',hotzones:'Hotzones',advanced:'Advanced',metadata:'Metadata'};
const profileKeys = {attributes:'Attributes',tendencies:'Tendencies',badges:'Badges',vitals:'Vitals',signatures:'Signatures',gear:'Gear',accessories:'Accessories',appearance:'Appearance',hotzones:'Hotzones',advanced:'Advanced Fields'};
const idKey = kind => kind === 'players' ? 'player_id' : 'team_id';
const element = (tag, text, cls) => {const e = document.createElement(tag); if(text !== undefined)e.textContent=text; if(cls)e.className=cls; return e;};
function toast(message, error = false){$('toast').textContent=message;$('toast').className=error?'error':'';$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,error?9000:4500);}
function teamName(id){return roster.teams.find(t=>t.team_id===id)?.name || 'Free agent';}
function current(){return roster[view]?.find(r=>r[idKey(view)]===selected);}
function changes(){
 const rows=[];
 for(const key of new Set([...Object.keys(baseline),...Object.keys(roster)]))if(!['players','teams','version'].includes(key)&&JSON.stringify(baseline[key])!==JSON.stringify(roster[key]))rows.push({name:'Workspace',path:key,old:baseline[key],value:roster[key]});
 for(const kind of ['players','teams']){
  const before=new Map(baseline[kind].map(r=>[r[idKey(kind)],r]));
  for(const record of roster[kind]){
   const id=record[idKey(kind)], old=before.get(id);before.delete(id);
   if(old&&!dirtyRecords.has(`${kind}:${id}`))continue;
   if(!old){rows.push({name:record.name,path:'Record added',old:undefined,value:id});continue;}
   for(const key of new Set([...Object.keys(old),...Object.keys(record)])){
    if(key===idKey(kind))continue;
    const a=old[key],b=record[key];
    if(a && b && typeof a==='object' && typeof b==='object' && !Array.isArray(a) && !Array.isArray(b)){
     for(const field of new Set([...Object.keys(a),...Object.keys(b)]))if(JSON.stringify(a[field])!==JSON.stringify(b[field]))rows.push({name:record.name,path:`${categories[key]||key} / ${field}`,old:a[field],value:b[field]});
    }else if(JSON.stringify(a)!==JSON.stringify(b))rows.push({name:record.name,path:key,old:a,value:b});
   }
  }
  for(const record of before.values())rows.push({name:record.name,path:'Record removed',old:record[idKey(kind)],value:undefined});
 }
 return rows;
}
function refreshStatus(){
 const count=changes().length;
 $('change-count').textContent=count;$('pending').textContent=count?`${count} unsaved change${count===1?'':'s'}`:workspaceNeedsSave?'Game roster loaded · JSON copy not saved':'No unsaved changes';
 $('save').disabled=saving||(!count&&!workspaceNeedsSave);$('save-status').textContent=count?'Unsaved changes':workspaceNeedsSave?'JSON copy not saved':'Local edits only';
 $('footer-status').textContent=count?'Workspace has unsaved edits':'Ready to edit';
 $('edit-status').textContent=count?'Edited values are highlighted':'Select a value to edit';
 if(gamePlan&&plannedRoster!==JSON.stringify(roster))$('apply-game').disabled=true;
}
function setView(next){
 view=next;$('search').value='';$('field-search').value='';
 if(next!=='changes'){selected=roster[next][0]?.[idKey(next)];category=next==='teams'?'identity':'attributes';}
 render();
}
function render(){
 updateLiveControls();
 $('player-count').textContent=roster.players.length;$('team-count').textContent=roster.teams.length;
 $('roster-name').textContent=roster.name||'Imported roster';
 if(!gameLoaded)$('mode-note').textContent=roster.name==='Demo roster'?'Explore fictional demo data, or import your own roster. Changes save to a local JSON file.':'Your imported roster is ready to edit. Save workspace saves JSON; connect and merge into a game roster to preview game updates.';
 document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
 $('crumb').textContent=view==='changes'?'CHANGE REVIEW':view.toUpperCase();
 $('page-title').replaceChildren(document.createTextNode(view==='players'?'Player database':view==='teams'?'Team database':'Your changes'),element('span','.'));
 $('page-description').textContent=view==='players'?'Every player. Every detail. All in one place.':view==='teams'?'Build the teams behind your roster.':'A clear view of everything you have edited.';
 $('browser-view').hidden=view==='changes';$('review-view').hidden=view!=='changes';
 if(view==='changes'){renderChanges();refreshStatus();return;}
 const filter=$('team-filter').value;
 $('team-filter').replaceChildren(new Option('All teams',''),new Option('Free agents','__free'),...roster.teams.map(t=>new Option(t.name,t.team_id)));
 $('team-filter').value=filter;$('team-filter').hidden=view==='teams';
 $('all-records').textContent=view==='players'?'All players':'All teams';
 renderList();renderInspector();refreshStatus();
}
function renderList(){
 const query=$('search').value.toLowerCase(),filter=$('team-filter').value;
 const list=roster[view].filter(r=>(`${r.name} ${r[idKey(view)]}`).toLowerCase().includes(query)&&(view!=='players'||!filter||(filter==='__free'?!r.team_id:r.team_id===filter)));
 $('visible-count').textContent=list.length;$('list-summary').textContent=`${list.length} of ${roster[view].length} ${view}`;
 $('table-head').replaceChildren();const head=element('tr');
 for(const label of view==='players'?['PLAYER','TEAM','POS','AVG*']:['TEAM','CITY','PLAYERS'])head.append(element('th',label));
 $('table-head').append(head);$('record-list').replaceChildren();
 for(const record of list){
  const id=record[idKey(view)], row=element('tr',undefined,id===selected?'selected':'');row.tabIndex=0;row.setAttribute('aria-selected',String(id===selected));
  const cell=element('td'),person=element('div',undefined,'person'),avatar=element('div',record.name.split(/\s+/).map(w=>w[0]).slice(0,2).join(''),'avatar');
  const label=element('div');label.append(element('strong',record.name),element('small',id));person.append(avatar,label);cell.append(person);row.append(cell);
  if(view==='players'){
   row.append(element('td',roster.teams.find(t=>t.team_id===record.team_id)?.metadata?.abbreviation|| (record.team_id?'—':'FA')));
   const pos=element('td');pos.append(element('span',record.metadata?.position||'—','pill'));row.append(pos);
   const values=Object.values(record.attributes||{});const average=values.length?Math.round(values.reduce((a,b)=>a+b,0)/values.length):'—';row.append(element('td',String(average),'rating'));
  }else row.append(element('td',String(record.metadata?.city||'—')),element('td',String(roster.players.filter(p=>p.team_id===id).length)));
  const choose=()=>{selected=id;$('field-search').value='';renderList();renderInspector();};row.onclick=choose;row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}};$('record-list').append(row);
 }
 if(!list.length){const row=element('tr'),cell=element('td','No matching records. Try another search or import a roster.','empty');cell.colSpan=4;row.append(cell);$('record-list').append(row);}
 if(view==='players')$('list-summary').title='AVG is the mean of imported attributes, not the game overall rating.';
}
function renderInspector(){
 const record=current();$('record-header').replaceChildren();$('tabs').replaceChildren();$('fields').replaceChildren();$('revert-record').disabled=!record||liveEnabled||livePending>0;
 if(!record){$('fields').append(element('div','Import a roster to start editing.','empty'));return;}
 const title=element('div',undefined,'record-title'),avatar=element('div',record.name.split(/\s+/).map(w=>w[0]).slice(0,2).join(''),'avatar'),identity=element('div',undefined,'identity');
 identity.append(element('h2',record.name),element('p',view==='players'?`${record.metadata?.position||'No position'}  /  ${teamName(record.team_id)}  /  ${record.player_id}`:record.team_id));title.append(avatar,identity,element('span',gameValues.has(record.player_id)?'GAME RECORD':'LOCAL RECORD','tag'));$('record-header').append(title);
 const tabs=view==='teams'?['identity','metadata']:Object.keys(categories);
 for(const key of tabs){const tab=element('button',categories[key],category===key?'active':'');tab.onclick=()=>{category=key;$('field-search').value='';renderInspector();};$('tabs').append(tab);}
 renderFields();
}
function renderFields(){
 const record=current();if(!record)return;
 $('category-label').textContent=categories[category].toUpperCase();$('fields').replaceChildren();
 const query=$('field-search').value.toLowerCase(), old=baseline[view].find(r=>r[idKey(view)]===selected);
 let fields;
 if(category==='identity')fields=[{name:'name',label:'Name',text:true},...(view==='players'?[{name:'team_id',label:'Team',team:true}]:[])];
 else{
  const defined=view==='players'?(profile[profileKeys[category]]||[]):[];
  fields=defined.map(f=>({name:f.id||f.name,label:f.label||f.name,offset:f.offset,bits:f.bits||f.length,kind:f.kind||'bits',writable:f.writable===true}));
  const known=new Set(fields.map(f=>f.name));
  for(const name of Object.keys(record[category]||{}))if(!known.has(name))fields.push({name,label:name});
 }
 let shown=0;
 for(const field of fields){
  if(!`${field.label} ${field.name}`.toLowerCase().includes(query))continue;shown++;
  const source=category==='identity'?record:(record[category]||{}),original=category==='identity'?old:old?.[category];
  const fieldCategory=category;
  const value=source[field.name], row=element('div',undefined,'field'), label=element('label',field.label);
  const namedField=['signatures','gear','accessories','appearance'].includes(category)&&field.writable&&field.kind==='bits';
  const names=fieldValues[category]?.[field.name]||{};
  const input=field.team?element('select'):element('input');input.id=`field-${shown}`;label.htmlFor=input.id;
  if(field.team){input.append(new Option('Free agent',''),...roster.teams.map(t=>new Option(t.name,t.team_id)));input.value=value||'';}
  else if(namedField){input.type='text';input.className='text';input.value=Object.keys(names).find(name=>names[name]===value)||String(value??'');input.placeholder='Name or game ID';const list=element('datalist');list.id=`choices-${shown}`;for(const name of Object.keys(names)){const option=element('option');option.value=name;list.append(option);}input.setAttribute('list',list.id);row.append(list);}
  else if(['attributes','tendencies','badges'].includes(category)||(field.writable&&field.bits&&field.kind!=='utf16'&&typeof value!=='string')){
   input.type='number';input.min=gameLoaded&&category==='attributes'?25:0;input.max=category==='attributes'?99:category==='tendencies'?100:category==='badges'?5:field.kind==='float'?3.402823466e38:2**field.bits-1;input.step=field.kind==='float'?'any':1;input.value=value??'';input.placeholder='—';
   if(category==='attributes'){const meter=element('div',undefined,'meter'),bar=element('span');bar.style.width=`${value??0}%`;meter.append(bar);row.append(meter);}
  }else{input.type='text';input.className='text';input.value=value===undefined?'':typeof value==='object'?JSON.stringify(value):String(value);input.placeholder='Not set';if(field.kind==='utf16')input.maxLength=19;}
  row.prepend(label);row.append(input);const highlight=()=>row.classList.toggle('changed',JSON.stringify(source[field.name])!==JSON.stringify(original?.[field.name]));highlight();
  const liveField=view==='players'&&gameLoaded&&field.writable;
  if(gameLoaded&&namedField){const learn=element('button','Learn name','learn-value');learn.title='Save the name shown in 2K for this player’s current value';learn.onclick=()=>{if(gameBusy||livePending)return;learningField={player_id:record.player_id,category:fieldCategory,field:field.name};$('learn-title').textContent=`${record.name} · ${field.label}`;$('learn-name').value='';$('learn-dialog').showModal();};row.append(learn);}
  if(gameLoaded&&!liveField){input.title='Local JSON only: this field has no supported numeric game mapping.';label.append(element('small',' · LOCAL ONLY'));}
  const commitLive=()=>{if(liveField&&liveEnabled&&input.checkValidity()&&source[field.name]!==undefined)queueLiveEdit(record,fieldCategory,field.name,source[field.name]);};
  input.oninput=()=>{
   cancelLiveTimer(record.player_id,fieldCategory,field.name);
   let next=input.value;
   if(input.type==='number'){
    if(next===''){input.setCustomValidity('');delete source[field.name];}
    else{next=Number(next);if(!Number.isFinite(next)||(field.kind!=='float'&&!Number.isInteger(next))||next<Number(input.min)||next>Number(input.max)){input.setCustomValidity(`Enter a ${field.kind==='float'?'number':'whole number'} from ${input.min} to ${input.max}.`);input.reportValidity();return;}input.setCustomValidity('');source[field.name]=next;}
   }else if(field.team)source[field.name]=next||null;
   else if(category==='identity'){if(!next.trim()){input.setCustomValidity('Name is required.');input.reportValidity();return;}input.setCustomValidity('');source[field.name]=next;}
   else if(field.kind==='utf16')source[field.name]=next;
   else if(next==='')delete source[field.name];
   else{try{source[field.name]=JSON.parse(next);}catch{source[field.name]=next;}}
   if(namedField&&liveEnabled){const nextValue=source[field.name],mapped=typeof nextValue==='string'?Object.keys(names).some(name=>name.toLowerCase()===nextValue.trim().toLowerCase()):Number.isInteger(nextValue)&&nextValue>=0&&nextValue<2**field.bits;input.setCustomValidity(mapped||nextValue===undefined?'':'Choose a learned name or an integer game ID.');}
   if(category!=='identity')record[category]=source;
   dirtyRecords.add(`${view}:${record[idKey(view)]}`);highlight();const bar=row.querySelector('.meter span');if(bar)bar.style.width=`${source[field.name]??0}%`;refreshStatus();renderList();
   if(liveField&&liveEnabled&&source[field.name]!==undefined&&input.checkValidity()){const key=liveKey(record.player_id,fieldCategory,field.name);const timer=setTimeout(()=>{liveTimers.delete(key);commitLive();},450);liveTimers.set(key,timer);updateLiveControls();}
  };
  input.onchange=()=>{cancelLiveTimer(record.player_id,fieldCategory,field.name);commitLive();if(fieldCategory==='identity')renderInspector();};
  input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();input.blur();}};
  $('fields').append(row);
 }
 if(!shown)$('fields').append(element('div',query?'No matching fields.':category==='hotzones'?'Hotzone memory mappings are not verified yet. Use Capture unmapped field to record one change in 2K. Imported hotzones remain available in your JSON workspace.':'No fields in this category. Import values in JSON to populate it.','empty'));
}
const display=value=>value===undefined?'Not set':typeof value==='object'?JSON.stringify(value):String(value);
function renderChanges(){
 $('changes').replaceChildren();const list=changes();
 for(const change of list){const row=element('div',undefined,'change-row'),label=element('div',change.name);label.append(element('small',change.path));const values=element('div');values.append(element('del',display(change.old)),document.createTextNode(' → '),element('code',display(change.value)));row.append(label,values);$('changes').append(row);}
 if(!list.length)$('changes').append(element('div','Your workspace is up to date. Edits will appear here before you save.','empty'));
 $('discard').disabled=!list.length||liveEnabled||livePending>0;
}
$('search').oninput=renderList;$('team-filter').onchange=renderList;$('field-search').oninput=renderFields;
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>setView(b.dataset.view));
$('review').onclick=()=>setView('changes');$('connection-info').onclick=()=>$('info-dialog').showModal();
$('revert-record').onclick=()=>{if(liveEnabled||livePending)return;const old=baseline[view].find(r=>r[idKey(view)]===selected);const index=roster[view].findIndex(r=>r[idKey(view)]===selected);if(old)roster[view][index]=clone(old);else roster[view].splice(index,1);selected=roster[view][Math.max(0,index)]?.[idKey(view)];render();};
$('discard').onclick=()=>{if(liveEnabled||livePending)return;roster=clone(baseline);render();toast('Unsaved edits discarded.');};
$('import').onclick=()=>$('file').click();
$('file').onchange=async()=>{const file=$('file').files[0];if(!file)return;try{if(file.size>128_000_000)throw Error('Roster must be smaller than 128 MB.');importDocument=JSON.parse(await file.text());const result=await api('/api/import',{document:importDocument});imported=result.roster;$('merge-import').checked=gameLoaded;$('import-summary').textContent=`${file.name} · ${imported.players.length} players · ${imported.teams.length} teams`;$('import-warnings').replaceChildren();$('import-dialog').showModal();}catch(error){toast(`Import failed: ${error.message}`,true);}finally{$('file').value='';}};
$('cancel-import').onclick=()=>$('import-dialog').close();
$('confirm-import').onclick=async()=>{if(!imported)return;const button=$('confirm-import');button.disabled=true;try{stopLiveLocally();const merging=$('merge-import').checked;const snapshot=JSON.stringify(roster);const result=merging?await api('/api/import',{document:importDocument,merge:true,target:roster}):{roster:imported,warnings:[]};if(snapshot!==JSON.stringify(roster))throw Error('Workspace changed during import. Try again.');roster=result.roster;syncWarnings=[];for(const kind of ['players','teams'])for(const record of roster[kind])dirtyRecords.add(`${kind}:${record[idKey(kind)]}`);imported=null;gamePlan=null;$('import-dialog').close();setView('players');if(result.warnings.length){showGameWarnings(result.warnings);$('game-changes').replaceChildren();$('game-summary').textContent='Import completed. These players were skipped:';$('apply-game').disabled=true;$('game-dialog').showModal();}toast(merging?'TRC values merged. Review changes before saving or applying.':'Roster imported. Review and save your workspace.');}catch(error){toast(`Import failed: ${error.message}`,true);}finally{button.disabled=false;}};
$('export').onclick=()=>{const blob=new Blob([JSON.stringify(roster,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=element('a');link.href=url;link.download='TRC+-roster.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Roster exported, including unsaved edits.');};
$('save').onclick=async()=>{
 if(saving||(!changes().length&&!workspaceNeedsSave))return;
 if(!document.querySelector('input:invalid')){
  saving=true;refreshStatus();const snapshot=clone(roster);
  try{const response=await fetch('/api/roster',{method:'POST',headers:{'Content-Type':'application/json','X-Editor-Token':token},body:JSON.stringify(snapshot)});const result=await response.json();if(!response.ok)throw Error(result.error);baseline=clone(result.roster);workspaceNeedsSave=false;toast('Workspace saved to your local roster file.');}
  catch(error){toast(`Save failed: ${error.message}`,true);}finally{saving=false;render();}
 }else document.querySelector('input:invalid').reportValidity();
};
window.trcHasUnsavedChanges=()=>Boolean(roster&&(workspaceNeedsSave||changes().length||livePending||liveTimers.size||saving||gameBusy));
window.addEventListener('beforeunload',e=>{if(window.trcHasUnsavedChanges()){e.preventDefault();e.returnValue='';}});
function lockForUpdate(locked){
 updateBusy=locked;document.querySelectorAll('aside,.shell header,main').forEach(node=>node.inert=locked);
 $('close-update').disabled=locked;$('install-update').disabled=locked;$('check-updates').disabled=locked;
}
$('close-update').onclick=()=>{if(!updateBusy)$('update-dialog').close();};
$('update-dialog').addEventListener('cancel',event=>{if(updateBusy)event.preventDefault();});
$('check-updates').onclick=async()=>{
 if(updateBusy)return;
 $('install-update').hidden=true;$('update-notes').textContent='';$('update-title').textContent='App updates';
 $('update-status').textContent='Checking GitHub for a new release…';$('update-dialog').showModal();lockForUpdate(true);
 try{const result=await api('/api/updates/check',{});$('update-status').textContent=result.message;
  if(result.available){$('update-title').textContent=`TRC+ ${result.version} is available`;$('update-notes').textContent=result.notes;$('install-update').hidden=!desktopUpdates;
   if(!desktopUpdates)$('update-status').textContent+=' Open the packaged desktop app to install it.';}
 }catch(error){$('update-status').textContent=error.message;}finally{lockForUpdate(false);}
};
$('install-update').onclick=async()=>{
 if(updateBusy)return;
 if(window.trcHasUnsavedChanges()){toast('Save your workspace and finish pending edits before updating.',true);return;}
 lockForUpdate(true);$('update-status').textContent='Downloading and verifying the update. Keep the app open…';
 try{await api('/api/updates/download',{});$('update-status').textContent='Installing the update. TRC+ will restart shortly…';await api('/api/updates/install',{});}
 catch(error){$('update-status').textContent=error.message;lockForUpdate(false);}
};
window.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();$('save').click();}});
function showGameWarnings(warnings){
 $('game-warnings').replaceChildren(...warnings.map(message=>element('p',message)));
}
const liveKey=(id,cat,field)=>JSON.stringify([id,cat,field]);
function cancelLiveTimer(id,cat,field){const key=liveKey(id,cat,field);clearTimeout(liveTimers.get(key));liveTimers.delete(key);}
function stopLiveLocally(){liveEnabled=false;for(const timer of liveTimers.values())clearTimeout(timer);liveTimers.clear();updateLiveControls();}
function rememberGameValues(){gameValues=new Map(roster.players.map(player=>[player.player_id,Object.fromEntries(['attributes','tendencies','badges','vitals','signatures','gear','accessories','appearance','hotzones'].map(cat=>[cat,clone(player[cat]||{})]))]));undoCount=0;redoCount=0;}
function updateLiveControls(){
 $('trc-sync').disabled=gameBusy||livePending>0||liveTimers.size>0||!gameLoaded||!gameStatus?.connected;
 $('game-load').disabled=gameBusy||livePending>0||!gameStatus?.connected;
 $('game-preview').disabled=gameBusy||livePending>0||liveTimers.size>0||!gameLoaded||!gameStatus?.connected;
 $('mapping-capture').disabled=gameBusy||livePending>0||liveTimers.size>0||!gameLoaded||view!=='players'||!current();
 $('game-live').textContent=liveEnabled?'Stop live editing':'Start live editing';
 $('game-live').classList.toggle('primary',liveEnabled);
 $('game-live').disabled=gameBusy||livePending>0||!gameLoaded||!gameStatus?.connected;
 $('game-undo').disabled=gameBusy||livePending>0||liveTimers.size>0||!undoCount;
 $('game-redo').disabled=gameBusy||livePending>0||liveTimers.size>0||!redoCount;
 $('live-status').textContent=livePending||liveTimers.size?'Writing game value…':liveEnabled?'LIVE · edits apply automatically':'Live editing off';
 $('import').disabled=gameBusy||livePending>0;$('save-connection').disabled=gameBusy||livePending>0;
 $('revert-record').disabled=liveEnabled||livePending>0||!current();
 $('discard').disabled=liveEnabled||livePending>0;
}
function acceptGameChanges(result){
 undoCount=result.undo_count??undoCount;redoCount=result.redo_count??redoCount;
 for(const change of result.changes||[]){const values=gameValues.get(change.player_id);if(values){values[change.category]??={};values[change.category][change.field]=change.value;if(change.category==='vitals'&&['First Name','Last Name'].includes(change.field)){const player=roster.players.find(p=>p.player_id===change.player_id);if(player){player.name=[values.vitals['First Name'],values.vitals['Last Name']].filter(Boolean).join(' ');dirtyRecords.add(`players:${player.player_id}`);if(selected===player.player_id)$('record-header').querySelector('h2').textContent=player.name;}}}}
 updateLiveControls();
}
function queueLiveEdit(record,cat,field,value){
 if(!liveEnabled)return;
 livePending++;updateLiveControls();
 liveQueue=liveQueue.then(async()=>{
  if(!liveEnabled)return;const values=gameValues.get(record.player_id),expected=values?.[cat]?.[field];
  if(value===expected)return;
  try{const result=await api('/api/game/edit',{player_id:record.player_id,category:cat,field,value,expected});acceptGameChanges(result);$('live-status').textContent=`Applied ${field}: ${value}`;gamePlan=null;}
  catch(error){stopLiveLocally();if(record[cat]?.[field]===value){if(expected===undefined)delete record[cat][field];else record[cat][field]=expected;}toast(`Live edit failed: ${error.message} Live editing paused; your value was not confirmed.`,true);renderList();renderInspector();refreshStatus();}
 }).finally(()=>{livePending--;updateLiveControls();});
}
$('game-live').onclick=async()=>{
 if(gameBusy||livePending)return;gameBusy=true;updateLiveControls();
 try{const result=await api('/api/game/live',{enabled:!liveEnabled});liveEnabled=result.live_enabled;undoCount=result.undo_count;redoCount=result.redo_count;gamePlan=null;if(!liveEnabled)stopLiveLocally();updateGameStatus(result.status);toast(liveEnabled?'Live editing on. Values apply automatically; use Undo game edit to restore them.':'Live editing stopped. Game edits remain until undone.');}
 catch(error){toast(error.message,true);}finally{gameBusy=false;updateLiveControls();renderInspector();}
};
async function restoreGameEdit(redo){
 if(gameBusy||livePending||liveTimers.size)return;gameBusy=true;updateLiveControls();
 try{const result=await api(redo?'/api/game/redo':'/api/game/undo',{});acceptGameChanges(result);for(const change of result.changes){const player=roster.players.find(p=>p.player_id===change.player_id);if(player){player[change.category]??={};player[change.category][change.field]=change.value;dirtyRecords.add(`players:${player.player_id}`);}}gamePlan=null;renderList();renderInspector();refreshStatus();toast(redo?'Game edit redone.':'Game edit undone.');}
 catch(error){stopLiveLocally();toast(`Could not restore game edit: ${error.message}`,true);}finally{gameBusy=false;updateLiveControls();}
}
$('game-undo').onclick=()=>restoreGameEdit(false);$('game-redo').onclick=()=>restoreGameEdit(true);
$('cancel-learn').onclick=()=>$('learn-dialog').close();
$('mapping-capture').onclick=()=>{
 const player=current();if(!player||view!=='players'||gameBusy||livePending)return;
 capturePlayerId=player.player_id;captureId=null;captureReport=null;
 $('capture-player').textContent=`${player.name} · ${player.player_id}`;$('capture-label').value='';
 $('capture-result').replaceChildren();$('capture-after').disabled=true;$('capture-export').disabled=true;$('capture-dialog').showModal();
};
$('capture-before').onclick=async()=>{
 if(gameBusy)return;gameBusy=true;updateLiveControls();
 try{const result=await api('/api/game/capture',{player_id:capturePlayerId,label:$('capture-label').value});captureId=result.capture_id;$('capture-after').disabled=false;$('capture-result').textContent='Before snapshot saved. Now change only that field in 2K, commit it, then compare.';}
 catch(error){toast(error.message,true);}finally{gameBusy=false;updateLiveControls();}
};
$('capture-after').onclick=async()=>{
 if(gameBusy||!captureId)return;gameBusy=true;updateLiveControls();
 try{const result=await api('/api/game/compare',{capture_id:captureId});captureReport=result.report;$('capture-result').textContent=`${result.report.changed_bytes.length} changed bytes recorded. Saved to ${result.path}. This is evidence for verification, not an enabled mapping.`;$('capture-export').disabled=false;}
 catch(error){toast(error.message,true);}finally{gameBusy=false;updateLiveControls();}
};
$('capture-export').onclick=()=>{if(!captureReport)return;const url=URL.createObjectURL(new Blob([JSON.stringify(captureReport,null,2)],{type:'application/json'})),link=element('a');link.href=url;link.download='2k-field-capture.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('confirm-learn').onclick=async()=>{
 if(gameBusy||livePending||!learningField)return;gameBusy=true;$('confirm-learn').disabled=true;updateLiveControls();
 try{const result=await api('/api/game/learn-value',{...learningField,label:$('learn-name').value});fieldValues=result.field_values;acceptGameChanges(result);const change=result.changes[0],player=roster.players.find(p=>p.player_id===change.player_id);if(player){player[change.category][change.field]=change.value;dirtyRecords.add(`players:${player.player_id}`);}gamePlan=null;$('learn-dialog').close();renderInspector();refreshStatus();toast(`Learned ${result.mapping.label} = ${result.mapping.value} for this game build.`);}
 catch(error){toast(`Could not learn this value: ${error.message}`,true);}finally{gameBusy=false;$('confirm-learn').disabled=false;updateLiveControls();}
};
function fillConnectionSettings(){
 $('game-path').value=connectionSettings.game_path;
 $('verified-build').value=connectionSettings.verified_build;
 $('enable-writes').checked=connectionSettings.enable_writes;
}
$('save-connection').onclick=async()=>{
 if(gameBusy)return;gameBusy=true;$('save-connection').disabled=true;
 try{const result=await api('/api/game/settings',{game_path:$('game-path').value,verified_build:$('verified-build').value,enable_writes:$('enable-writes').checked});connectionSettings=result.game_settings;stopLiveLocally();gameLoaded=false;gamePlan=null;undoCount=0;redoCount=0;gameValues.clear();fillConnectionSettings();updateGameStatus({connected:false,error:'Settings saved. Check the game connection, then reload its roster.'});$('connection-settings-status').textContent='Saved. Reconnect and reload the game roster before previewing updates.';toast('Game connection settings saved.');}
 catch(error){toast(`Could not save connection settings: ${error.message}`,true);}finally{gameBusy=false;$('save-connection').disabled=false;}
};
function updateGameStatus(status){
 gameStatus=status;updateLiveControls();$('game-load').disabled=gameBusy||!status.connected;$('game-preview').disabled=gameBusy||livePending>0||!gameLoaded||!status.connected;
 $('connection-status').textContent=status.connected?'Connected directly to NBA 2K27':'Game not connected';
 $('game-state').textContent=status.connected?(status.writes_enabled?'GAME WRITES ENABLED':'GAME READ ONLY'):'LOCAL EDITOR';
 $('game-build-status').textContent=status.connected?`Build ${status.build} · ${status.writes_enabled?'Reviewed writes enabled':'Read only'}`:status.error||'Game not connected';
 $('mode-title').textContent=gameLoaded?'Game roster workspace':'Local editing mode';
 $('mode-note').textContent=gameLoaded?'Start live editing to apply individual field changes automatically. Undo restores game values. Save JSON workspace saves a local copy; save inside NBA 2K27 to keep game edits.':'Import your TRC export or load the roster from NBA 2K27.';
}
$('game-connect').onclick=async()=>{if(gameBusy)return;gameBusy=true;$('game-connect').disabled=true;try{updateGameStatus(await api('/api/game/status'));}catch(error){toast(error.message,true);}finally{gameBusy=false;$('game-connect').disabled=false;if(gameStatus)updateGameStatus(gameStatus);}};
$('game-load').onclick=async()=>{
 if(gameBusy||livePending)return;stopLiveLocally();if(changes().length&&!window.confirm('Loading the game roster replaces unsaved workspace edits. Continue?'))return;
 gameBusy=true;updateGameStatus(gameStatus);const snapshot=JSON.stringify(roster);toast('Reading the game roster…');
 try{const result=await api('/api/game/load',{});if(snapshot!==JSON.stringify(roster))throw Error('Workspace changed while reading the game. Load again when ready.');stopLiveLocally();roster=result.roster;syncWarnings=[];baseline=clone(roster);dirtyRecords.clear();workspaceNeedsSave=true;fieldValues=result.field_values||{};rememberGameValues();gameLoaded=true;gamePlan=null;updateGameStatus(result.status);setView('players');toast(`Loaded ${roster.players.length} players from NBA 2K27.`);}
 catch(error){toast(`Game load failed: ${error.message}`,true);}finally{gameBusy=false;if(gameStatus)updateGameStatus(gameStatus);}
};
$('game-preview').onclick=async()=>{
 if(gameBusy||livePending||liveTimers.size)return;if(document.querySelector('input:invalid')){document.querySelector('input:invalid').reportValidity();return;}
 gameBusy=true;updateGameStatus(gameStatus);const snapshot=JSON.stringify(roster);
 try{const result=await api('/api/game/preview',roster);if(snapshot!==JSON.stringify(roster))throw Error('Workspace changed during preview. Preview again.');gamePlan=result;plannedRoster=snapshot;$('game-summary').textContent=`${result.changes.length} supported field changes. ${result.writes_enabled?'Apply writes these values to the running game.':'Read only: close this preview and click Start live editing once to enable writes, then preview again.'}`;
 $('game-changes').replaceChildren(...result.changes.map(change=>{const row=element('div',undefined,'change-row'),label=element('div',change.name);label.append(element('small',`${categories[change.category]} / ${change.field}`));row.append(label,element('div',`${display(change.old)} → ${display(change.value)}`));return row;}));showGameWarnings([...syncWarnings,...result.warnings]);$('apply-game').disabled=!result.writes_enabled||!result.changes.length;$('game-dialog').showModal();}
 catch(error){toast(`Preview failed: ${error.message}`,true);}finally{gameBusy=false;if(gameStatus)updateGameStatus(gameStatus);}
};
$('cancel-game').onclick=()=>$('game-dialog').close();
const showGamePreview=$('game-preview').onclick;
$('trc-sync').onclick=async()=>{
 if(gameBusy||livePending||liveTimers.size||!gameLoaded||!gameStatus?.connected)return;
 gameBusy=true;updateLiveControls();const snapshot=JSON.stringify(roster);let ready=false;
 try{
  const source=await api('/api/trc/export',{});
  if(!source.roster.players.length){toast('TRC has no pending player upgrades.');return;}
  const result=await api('/api/import',{document:source.roster,merge:true,target:roster});
  if(snapshot!==JSON.stringify(roster))throw Error('Workspace changed during sync. Try again when ready.');
  // Stop automatic writes before staging a batch; Apply remains a separate action.
  await api('/api/game/live',{enabled:false});stopLiveLocally();
  if(snapshot!==JSON.stringify(roster))throw Error('Workspace changed during sync. Try again when ready.');
  roster=result.roster;syncWarnings=result.warnings;gamePlan=null;workspaceNeedsSave=true;
  for(const player of roster.players)dirtyRecords.add(`players:${player.player_id}`);
  setView('players');ready=true;
  const matched=source.roster.players.length-result.warnings.length;
  toast(`Fetched ${source.roster.players.length} TRC players; matched ${matched}. Review before applying.`);
  gameBusy=false;updateLiveControls();await showGamePreview();
 }catch(error){toast(`TRC sync failed: ${error.message}`,true);}
 finally{gameBusy=false;updateLiveControls();if(!ready&&gameStatus)updateGameStatus(gameStatus);}
};
$('apply-game').onclick=async()=>{
 if(gameBusy||!gamePlan)return;if(plannedRoster!==JSON.stringify(roster)){toast('Workspace changed. Preview game changes again.',true);$('apply-game').disabled=true;return;}
 gameBusy=true;$('apply-game').disabled=true;
 try{const result=await api('/api/game/apply',{plan_id:gamePlan.plan_id});gamePlan=null;acceptGameChanges(result);$('game-dialog').close();toast(`Applied ${result.applied} game field changes. Save the roster in-game to keep them.`);}
 catch(error){gamePlan=null;toast(`Game update failed: ${error.message}`,true);}finally{gameBusy=false;updateLiveControls();}
};
fetch('/api/session').then(async response=>{if(!response.ok)throw Error('Could not load the editor session.');return response.json();}).then(session=>{if(session.api_version!==6)throw Error('An older editor is still running. Close its terminal and relaunch TRC+, then use the newly opened page.');roster=session.roster;baseline=clone(roster);profile=session.profile;token=session.token;connectionSettings=session.game_settings;desktopUpdates=session.desktop_updates;$('app-version').textContent=`v${session.app_version}`;fillConnectionSettings();selected=roster.players[0]?.player_id;render();}).catch(error=>{document.querySelectorAll('button,input,select').forEach(control=>control.disabled=true);toast(error.message,true);});
