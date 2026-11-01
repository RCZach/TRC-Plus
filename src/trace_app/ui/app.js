'use strict';
const $ = id => document.getElementById(id);
const clone = value => structuredClone(value);
let roster, baseline, profile, token, selected, view = 'players', category = 'vitals', imported, toastTimer, saving = false;
let pageIndex=0;
let fieldGroup='';
function readAdvancedFieldsPreference(){
 try{return localStorage.getItem('trace.showAdvancedFields')==='true';}catch{return false;}
}
let showAdvancedFields=readAdvancedFieldsPreference();
const PAGE_SIZE=25;
let workspaceNeedsSave=false, dirtyRecords=new Set();
let desktopUpdates=false, updateBusy=false;
let liveEnabled=false, livePending=0, liveQueue=Promise.resolve(), liveTimers=new Map(), gameValues=new Map(), teamGameValues=new Map(), undoCount=0, redoCount=0;
let syncWarnings=[];
let importDocument, gameStatus, gameLoaded = false, gamePlan, plannedRoster, gameBusy = false, connectionSettings, fieldValues={}, learningField;
async function api(path, document){
 const options=document===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Editor-Token':token},body:JSON.stringify(document)};
 const response=await fetch(path,options),result=await response.json();
 if(response.status===404)throw Error('An older editor is still running. Close its terminal and relaunch TRACE, then use the newly opened page.');
 if(!response.ok)throw Error(result.error||'Request failed.');return result;
}
const categories = {vitals:'Vitals',body:'Body',gear:'Shoes / Gear',accessories:'Accessories',attributes:'Attributes',tendencies:'Tendencies',hotzones:'Hot Zones',signatures:'Signature',contract:'Contract',badges:'Badges',advanced:'Advanced',metadata:'Metadata',appearance:'Appearance',identity:'Details'};
const profileKeys = {attributes:'Attributes',tendencies:'Tendencies',badges:'Badges',vitals:'Vitals',signatures:'Signatures',gear:'Gear',accessories:'Accessories',appearance:'Appearance',hotzones:'Hotzones',advanced:'Advanced Fields'};
const fieldGroups = {
 attributes:['Inside Scoring','Outside Scoring','Playmaking','Athleticism','Defense','Durability','Miscellaneous'],
 tendencies:['Jump Shooting','Layups and Dunks','Drive Setup','Driving','Passing','Post Game','Freelance','Defense'],
 badges:['Finishing','Shooting','Playmaking','Defense','Physicals','Rebounding','Personality'],
 gear:['Shoes / Gear','Other Gear'],
 accessories:['Upper Body','Lower Body']
};
function arrangeVitals(fields){
 const order=[
  ['vitals','First Name'],['vitals','Last Name'],['vitals','Position'],['vitals','Secondary Position'],
  ['vitals','FIBA Team'],['metadata','college_from','College / From'],['vitals','High School'],
  ['vitals','Birthplace'],['vitals','Birth Month'],['vitals','Birth Day'],['vitals','Birth Year'],
  ['vitals','Years Pro'],['vitals','Number','Jersey Number'],['vitals','Dominant Hand'],
  ['vitals','Dominant Dunk Hand'],['vitals','Peak Age','Peak Start Age'],['vitals','Peak End Age'],
  ['attributes','Potential'],['vitals','Min Potential'],['vitals','Max Potential'],
  ['vitals','Bust Percent'],['vitals','AVG Percent'],['vitals','Boom Percent'],
  ['vitals','Play for Winner'],['vitals','Financial Security'],
  ['vitals','Loyalty'],['advanced','INJURY1TYPE','Injury 1 Type'],
  ['vitals','Injury 1 Duration Days'],['advanced','INJURY2TYPE','Injury 2 Type'],
  ['vitals','Injury 2 Duration Days'],['vitals','Forced Non-Starter'],
  ['vitals','Play Initiator'],['vitals','Play Type 1'],['vitals','Play Type 2'],['vitals','Play Type 3'],['vitals','Play Type 4']
 ];
 const used=new Set(),ordered=order.map(([source,name,label])=>{
  if(source==='vitals'){
   const field=fields.find(field=>field.name===name);if(field){used.add(name);const player=current(),slot=name==='Injury 2 Duration Days'?2:1;const inactive=field.kind==='injury_days'&&(!(player.advanced?.[`INJURY${slot}TYPE`]>=1&&player.advanced?.[`INJURY${slot}TYPE`]<=156)||![1,4].includes(player.advanced?.[`INJURY${slot}STATUS`])||!player.vitals?.[name]);return {...field,label:label||field.label,readOnly:inactive,readOnlyReason:inactive?'Create or clear injuries inside NBA 2K27. Duration editing requires a supported active injury state.':undefined};}
  }else if(source==='metadata'&&name==='college_from'){
   const mapped=fields.find(field=>field.name==='College / From');
   if(mapped&&current()?.vitals?.[mapped.name]===undefined&&current()?.metadata?.college_from){used.add(mapped.name);return {name,label,sourceCategory:'metadata',readOnly:true,readOnlyReason:'Load the game roster to resolve the college catalog.'};}
   if(mapped){used.add(mapped.name);const choices=fieldValues.vitals?.['College / From']||{},value=current()?.vitals?.[mapped.name];return {...mapped,label,options:choices,readOnly:!gameStatus?.college_writable||!choices[value],readOnlyReason:'College editing requires a validated loaded catalog and an unambiguous current label.'};}
   return {name,label,sourceCategory:'metadata',readOnly:true,readOnlyReason:'Verified College / From readout. Changing the referenced college requires a validated catalog lookup; editing is not supported yet.'};
  }else if(source!=='unmapped'){
   const definitions=profile[profileKeys[source]]||[],matches=definitions.filter(field=>(field.id||field.name)===name);
   if(matches.length===1){const field=matches[0];return {name,label:label||field.label||field.name,sourceCategory:source,readOnly:true,offset:field.offset,bits:field.bits||field.length,kind:field.kind||'bits'};}
  }
  return {name,label:label||name,readOnly:true,unmapped:true};
 });
 const all=[...ordered,...fields.filter(field=>!used.has(field.name)&&!['Potential','Height','Weight','Wingspan','Shoulder Width','Neck Length','Trunk Length'].includes(field.name))];
 if(showAdvancedFields)return all;
 const everyday=new Set(['First Name','Last Name','Position','college_from','College / From','Birthplace','Number','Dominant Hand','Dominant Dunk Hand','INJURY1TYPE','Injury 1 Duration Days','Play Initiator','Play Type 1','Play Type 2','Play Type 3','Play Type 4']);
 return all.filter(field=>everyday.has(field.name));
}
function bodyFields(){
 // Body is a display group; retain the existing Vitals storage and write path.
 return ['Height','Weight','Wingspan','Shoulder Width','Neck Length','Trunk Length'].map((name,index)=>{
  const definition=(name==='Weight'?profile.Vitals||[]:profile.Body||[]).find(field=>field.name===name);
  return {...definition,name,label:name,sourceCategory:'vitals',
   kind:definition?.kind||'float',writable:definition?.writable===true,
   verifiedBuild:definition?.verified_build,readOnly:!definition||definition.readOnly===true||(definition.linkedBody&&gameLoaded&&(!gameStatus?.body_writable||current()?.metadata?.body_editable===false||!Number.isFinite(current()?.vitals?.[name]))),unmapped:!definition,
   readOnlyReason:definition?.linkedBody?'Body editing requires a verified model and a freshly loaded roster.':definition?.readOnlyReason,
   slider:index>=2,minimum:index>=2?0:definition?.minimum,maximum:index>=2?100:definition?.maximum};
 });
}
function gearFields(fields){
 const order=[
  ['gear','Shoe Home Style','Shoe Home'],['gear','Shoe Away Style','Shoe Away'],
  ['gear','Socks Item Home','Sock Length Home'],['gear','Socks Item Away','Sock Length Away'],
  ['gear','Shirts Items','Undershirt'],['gear','Shirts Items Home Color','Undershirt Home Color'],
  ['gear','Shirts Items Away Color','Undershirt Away Color'],['accessories','Shorts Items','Shorts'],
  ['gear','Preferred Shorts Type','Shorts Preferred Type'],['gear','Shorts Length','Shorts Length'],
  ['accessories','Shorts Items Home Color','Shorts Home Color'],['accessories','Shorts Items Away Color','Shorts Away Color'],
  ['appearance','Jersey Bagginess','Bagginess']
 ];
 const main=order.map(([sourceCategory,name,label])=>{
  const definition=sourceCategory==='gear'?fields.find(field=>field.name===name):
   (profile[profileKeys[sourceCategory]]||[]).find(field=>(field.id||field.name)===name);
  return {...definition,name,label,sourceCategory,group:'Shoes / Gear',
   bits:definition?.bits||definition?.length,kind:definition?.kind||'bits',
   writable:definition?.writable===true,verifiedBuild:definition?.verified_build||definition?.verifiedBuild,
   readOnly:!definition||definition.readOnly===true,unmapped:!definition};
 });
 return [...main,...fields.filter(field=>!main.some(item=>item.sourceCategory==='gear'&&item.name===field.name)).map(field=>({...field,group:'Other Gear'}))];
}
function personalityFields(fields){
 const names=['Reserved','Friendly','Team Player','Extremely Confident','Keep It Real','Pat My Back','Expressive','Unpredictable','Laid Back','Media Ringmaster','Warm Weather Fan','Finance Savvy','Alpha Dog','Enforcer','Work Ethic','Marketability'];
 // Use verified profile mappings when present; retain placeholders for older
 // or custom profiles that do not yet define these fields.
 const personality=names.map((name,index)=>fields.find(field=>field.name===name&&field.options&&field.bits&&field.offset!==undefined)||({name,label:name,group:'Personality',
  readOnly:true,unmapped:true,displayChoices:index<14?['Unequipped','Equipped']:['Unequipped','Bronze','Silver','Gold','Hall of Fame'],
  readOnlyReason:'Choices confirmed from the game UI. Memory mapping and numeric values are not verified yet.'}));
 return [...fields.filter(field=>!names.includes(field.name)),...personality];
}
const idKey = kind => kind === 'players' ? 'player_id' : 'team_id';
const element = (tag, text, cls) => {const e = document.createElement(tag); if(text !== undefined)e.textContent=text; if(cls)e.className=cls; return e;};
function toast(message, error = false){$('toast').textContent=message;$('toast').className=error?'error':'';$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,error?9000:4500);}
function teamName(id){return roster.teams.find(t=>t.team_id===id)?.name || 'Free agent';}
function playerTeamName(record){return roster.teams.find(t=>t.team_id===record.team_id)?.name || (record.metadata?.team_status==='unknown'||record.team_id?'Unknown team':'Free agent');}
function isFreeAgent(record){return !record.team_id&&record.metadata?.team_status!=='unknown';}
function playerOverall(record){const value=record.metadata?.overall;return Number.isInteger(value)&&value>=25&&value<=99?String(value):'\u2014';}
function updatePlayerPosition(player,vitals){
 const labels={0:'PG',1:'SG',2:'SF',3:'PF',4:'C'},primary=labels[vitals.Position],secondary=labels[vitals['Secondary Position']];
 player.metadata??={};player.metadata.primary_position=primary||null;player.metadata.secondary_position=secondary||null;
 if(primary)player.metadata.position=[primary,...(secondary&&secondary!==primary?[secondary]:[])].join(' / ');
 else delete player.metadata.position;
}
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
    if(kind==='teams'&&key==='coaching'&&a&&b&&typeof a==='object'&&typeof b==='object'){for(const field of new Set([...Object.keys(a.values||{}),...Object.keys(b.values||{})]))if(JSON.stringify(a.values?.[field])!==JSON.stringify(b.values?.[field]))rows.push({name:record.name,path:`Coaching Emphasis / ${field}`,old:a.values?.[field],value:b.values?.[field]});for(const field of new Set([...Object.keys(a),...Object.keys(b)]))if(field!=='values'&&JSON.stringify(a[field])!==JSON.stringify(b[field]))rows.push({name:record.name,path:`Coaching Emphasis / ${field}`,old:a[field],value:b[field]});continue;}
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
 $('save').disabled=saving||(!count&&!workspaceNeedsSave);$('save-status').textContent=count?'Unsaved changes':workspaceNeedsSave?'Game roster not saved to JSON':'No unsaved changes';
 $('footer-status').textContent=count?'Workspace has unsaved edits':'Ready to edit';
 $('edit-status').textContent=view==='teams'?category==='coaching'&&hasEditableCoaching(current())?'Coach defaults are editable':'Team readouts · read only':count?'Edited values are highlighted':'Select a value to edit';
 if(gamePlan&&plannedRoster!==JSON.stringify(roster))$('apply-game').disabled=true;
}
function setView(next){
 view=next;pageIndex=0;fieldGroup='';$('search').value='';$('field-search').value='';
 if(next==='players'||next==='teams'){selected=roster[next][0]?.[idKey(next)];category=next==='teams'?'rotation':'vitals';}
 render();
}
function render(){
 updateLiveControls();
 $('player-count').textContent=roster.players.length;$('team-count').textContent=roster.teams.length;
 $('roster-name').textContent=roster.name||'Imported roster';
 if(!gameLoaded)$('mode-note').textContent=roster.name==='Demo roster'?'Explore the demo roster or import your own roster to begin.':'Roster ready. Save your changes or connect to a game roster to preview updates.';
 document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
 $('page-title').replaceChildren(document.createTextNode(view==='players'?'Player database':view==='teams'?'Team database':view==='settings'?'Settings':'Your changes'),element('span','.'));
 $('browser-view').hidden=view!=='players'&&view!=='teams';$('review-view').hidden=view!=='changes';$('settings-view').hidden=view!=='settings';
 $('editor-notice').hidden=view==='settings';$('game-toolbar').hidden=view==='settings';$('workspace-footer').hidden=view==='settings';$('roster-label').hidden=view==='settings';
 if(view==='settings'){renderSettings();refreshStatus();return;}
 if(view==='changes'){renderChanges();refreshStatus();return;}
 const filter=$('team-filter').value;
 $('team-filter').replaceChildren(new Option('All teams',''),new Option('Free agents','__free'),new Option('Unknown team','__unknown'),...roster.teams.map(t=>new Option(t.name,t.team_id)));
 $('team-filter').value=filter;$('team-filter').hidden=view==='teams';
 $('all-records').textContent=view==='players'?'All players':'All teams';
 renderList();renderInspector();refreshStatus();
}
function renderList(){
 if(view!=='players'&&view!=='teams')return;
 const query=$('search').value.toLowerCase(),filter=$('team-filter').value;
 const list=roster[view].filter(r=>(`${r.name} ${r[idKey(view)]}`).toLowerCase().includes(query)&&(view!=='players'||!filter||(filter==='__free'?isFreeAgent(r):filter==='__unknown'?r.metadata?.team_status==='unknown':r.team_id===filter)));
 const pages=Math.max(1,Math.ceil(list.length/PAGE_SIZE));pageIndex=Math.max(0,Math.min(pageIndex,pages-1));
 const page=list.slice(pageIndex*PAGE_SIZE,(pageIndex+1)*PAGE_SIZE),previousSelection=selected;
 if(page.length&&!page.some(record=>record[idKey(view)]===selected))selected=page[0][idKey(view)];
 $('visible-count').textContent=list.length;
 const start=list.length?pageIndex*PAGE_SIZE+1:0,end=Math.min((pageIndex+1)*PAGE_SIZE,list.length);
 $('list-summary').textContent=`${start}–${end} of ${list.length} ${view}`;$('page-label').textContent=`Page ${pageIndex+1} of ${pages}`;
 $('page-prev').disabled=pageIndex===0;$('page-next').disabled=pageIndex>=pages-1;
 $('table-head').replaceChildren();const head=element('tr');
 for(const label of view==='players'?['PLAYER','TEAM','POS','OVR']:['TEAM','CITY','PLAYERS'])head.append(element('th',label));
 $('table-head').append(head);$('record-list').replaceChildren();
 for(const record of page){
  const id=record[idKey(view)], row=element('tr',undefined,id===selected?'selected':'');row.tabIndex=0;row.setAttribute('aria-selected',String(id===selected));
  const cell=element('td'),person=element('div',undefined,'person'),avatar=element('div',record.name.split(/\s+/).map(w=>w[0]).slice(0,2).join(''),'avatar');
  const label=element('div');label.append(element('strong',record.name));person.append(avatar,label);cell.append(person);row.append(cell);
  if(view==='players'){
   const team=roster.teams.find(t=>t.team_id===record.team_id),teamCell=element('td',team?.metadata?.abbreviation||team?.name||(isFreeAgent(record)?'FA':'\u2014'));teamCell.title=playerTeamName(record);row.append(teamCell);
   const pos=element('td');pos.append(element('span',record.metadata?.position||'—','pill'));row.append(pos);
   const ratingCell=element('td',playerOverall(record),'rating');ratingCell.title=record.metadata?.overall_source==='game'?'Overall rating from NBA 2K27. Reload after in-game changes.':'Overall rating unavailable';row.append(ratingCell);
  }else row.append(element('td',String(record.metadata?.city||'—')),element('td',String(roster.players.filter(p=>p.team_id===id).length)));
  const choose=()=>{selected=id;$('field-search').value='';renderList();renderInspector();};row.onclick=choose;row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}};$('record-list').append(row);
 }
 if(!list.length){const row=element('tr'),cell=element('td','No matching records. Try another search or import a roster.','empty');cell.colSpan=4;row.append(cell);$('record-list').append(row);}
 if(previousSelection!==selected)renderInspector();
 if(view==='players')$('list-summary').title='OVR is the overall rating read from NBA 2K27; \u2014 means unavailable.';
}
const teamCategories={rotation:'Rotation',coaching:'Coaching Emphasis',staff:'Staff'};
function hasEditableCoaching(team){return Array.isArray(team?.coaching?.writable_fields)&&team.coaching.writable_fields.length>0&&gameLoaded&&gameStatus?.connected&&teamGameValues.has(team.team_id);}
function renderInspector(){
 if(view!=='players'&&view!=='teams')return;
 const record=current();$('record-header').replaceChildren();$('tabs').replaceChildren();$('fields').replaceChildren();$('revert-record').disabled=!record||liveEnabled||livePending>0||(view==='teams'&&!hasEditableCoaching(record));$('revert-record').textContent=view==='teams'?'Revert team changes':'Revert player changes';
 if(!record){$('field-groups').hidden=true;$('fields').append(element('div','Import a roster to start editing.','empty'));return;}
 const title=element('div',undefined,'record-title'),avatar=element('div',record.name.split(/\s+/).map(w=>w[0]).slice(0,2).join(''),'avatar'),identity=element('div',undefined,'identity');
 identity.append(element('h2',record.name),element('p',view==='players'?`${record.metadata?.position||'No position'}  /  ${playerTeamName(record)}  /  ${record.player_id}`:record.team_id));title.append(avatar,identity);$('record-header').append(title);
 const tabs=view==='teams'?Object.keys(teamCategories):Object.keys(categories).filter(key=>key!=='identity');
 for(const key of tabs){const tab=element('button',view==='teams'?teamCategories[key]:categories[key],category===key?'active':'');tab.onclick=()=>{category=key;fieldGroup=key==='gear'?'Shoes / Gear':'';$('field-search').value='';renderInspector();};$('tabs').append(tab);}
 renderFields();
}
function renderTeamFields(record){
 $('field-groups').replaceChildren();$('field-groups').hidden=true;
 const query=$('field-search').value.trim().toLowerCase(),pane=$('fields');
 const caption=element('div',undefined,'team-detail-heading');
 caption.append(element('strong',teamCategories[category]||'Team'),element('span',category==='coaching'&&hasEditableCoaching(record)?liveEnabled?'Live':'Editable':'Read only','pill'));pane.append(caption);
 const matches=text=>String(text).toLowerCase().includes(query);
 const readout=(label,value)=>{const row=element('div',undefined,'field team-readout'),input=element('input');input.type='text';input.readOnly=true;input.value=value??'—';input.setAttribute('aria-label',label);row.append(element('label',label),input);pane.append(row);};
 if(category==='rotation'){
  const players=roster.players.filter(p=>p.team_id===record.team_id),byId=new Map(players.map(p=>[p.player_id,p]));
  const ids=Array.isArray(record.rotation?.player_ids)?record.rotation.player_ids:[];
  const ordered=[...new Set([...ids,...players.map(p=>p.player_id)])].map(id=>byId.get(id)).filter(Boolean);
  const table=element('table',undefined,'team-rotation'),head=element('thead'),heading=element('tr'),body=element('tbody');
  for(const label of ['Player','Position','Minutes'])heading.append(element('th',label));head.append(heading);table.append(head,body);
  for(const player of ordered){
   const value=record.rotation?.minutes?.[player.player_id],minutes=Number.isInteger(value)?value:'—';
   if(!matches(`${player.name} ${player.metadata?.position||''} Minutes ${minutes}`))continue;
   const row=element('tr');row.append(element('td',player.name),element('td',player.metadata?.position||'—'),element('td',String(minutes)));body.append(row);
  }
  if(!body.children.length)pane.append(element('div',query?'No matching players.':'No players linked to this team.','empty'));
  else pane.append(table);
  const total=record.rotation?.total_minutes;
  pane.append(element('p',`Team total: ${Number.isInteger(total)?total:'—'} min`,'team-total'));
 }else if(category==='coaching'){
  if(typeof record.coaching?.coach==='string')pane.append(element('p',`Coach defaults · ${record.coaching.coach}`,'team-source'));
  let shown=0;
  const names=Array.isArray(record.coaching?.field_order)?record.coaching.field_order:['Help Defense','Run Plays Frequency','Zone Usage Frequency','Tempo'];
  for(const name of names){
   const value=record.coaching?.values?.[name];if(!matches(name))continue;
   const valid=Number.isInteger(value)&&value>=0&&value<=100;
   if(hasEditableCoaching(record)&&record.coaching.writable_fields.includes(name)&&valid){
    const row=element('div',undefined,'field team-readout'),input=element('input');input.type='number';input.min=0;input.max=100;input.step=1;input.value=value;input.setAttribute('aria-label',name);
    const original=baseline.teams.find(t=>t.team_id===record.team_id)?.coaching?.values?.[name];
    const highlight=()=>row.classList.toggle('changed',record.coaching.values[name]!==original);highlight();
    const commit=()=>{if(liveEnabled&&input.checkValidity())queueTeamLiveEdit(record,name,record.coaching.values[name]);};
    input.oninput=()=>{cancelLiveTimer(`team:${record.team_id}`,'coaching',name);const next=Number(input.value),valid=input.value!==''&&Number.isInteger(next)&&next>=0&&next<=100;input.setCustomValidity(valid?'':'Enter a whole number from 0 to 100.');if(!valid)return;record.coaching.values[name]=next;dirtyRecords.add(`teams:${record.team_id}`);highlight();refreshStatus();gamePlan=null;if(liveEnabled){const key=liveKey(`team:${record.team_id}`,'coaching',name);liveTimers.set(key,setTimeout(()=>{liveTimers.delete(key);commit();},450));updateLiveControls();}};
    input.onchange=()=>{cancelLiveTimer(`team:${record.team_id}`,'coaching',name);commit();};input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();input.blur();}};
    row.append(element('label',name),input);pane.append(row);
   }else readout(name,valid?String(value):undefined);
   shown++;
  }
  if(!shown)pane.append(element('div','No matching fields.','empty'));
 }else if(category==='staff'){
  const entries=Array.isArray(record.staff?.entries)?record.staff.entries.filter(entry=>entry&&typeof entry.name==='string'):[];
  let shown=0;
  const roles={COACH:'Coach',SCOUT:'Scout',TRAINER:'Trainer',GM:'General Manager',CFO:'CFO',OWNER:'Owner',HEAD_ASSISTANT:'Head Assistant',ASSISTANT_GM:'Assistant General Manager',SHOTDOCTOR:'Shot Doctor',GUARDGURU:'Guard Guru',WINGWHISPERER:'Wing Whisperer',BIGMANCOACH:'Big Man Coach'};
  for(const entry of entries){
   const label=roles[entry.role]||String(entry.role||'Staff').replaceAll('_',' ');
   if(!matches(`${label} ${entry.name}`))continue;readout(label,entry.name);shown++;
  }
  if(!shown)pane.append(element('div',query?'No matching staff.':'No validated staff data is available for this team.','empty'));
 }
}
function renderFields(){
 const record=current();if(!record)return;
 $('fields').replaceChildren();
 if(view==='teams'){renderTeamFields(record);return;}
 const query=$('field-search').value.toLowerCase(), old=baseline[view].find(r=>r[idKey(view)]===selected);
 let fields;
 if(category==='identity')fields=[{name:'name',label:'Name',text:true},...(view==='players'?[{name:'team_id',label:'Team',team:true}]:[])];
 else{
  const defined=view==='players'?(profile[profileKeys[category]]||[]):[];
  fields=defined.map(f=>({name:f.id||f.name,label:f.label||f.name,offset:f.offset,bits:f.bits||f.length,kind:f.kind||'bits',writable:f.writable===true,options:f.options,verifiedBuild:f.verified_build,group:f.ui_group||(category==='accessories'?f.group?.replace(/ Accessories$/,''):undefined),minimum:f.minimum,maximum:f.maximum}));
  const known=new Set(fields.map(f=>f.name));
  for(const name of Object.keys(record[category]||{}))if(!known.has(name))fields.push({name,label:name});
 }
 if(category==='vitals')fields=arrangeVitals(fields);
 if(category==='body')fields=bodyFields();
 if(category==='gear')fields=gearFields(fields);
 if(category==='badges')fields=personalityFields(fields);
 if(category==='accessories')fields=fields.filter(field=>!['Shorts Items','Shorts Items Home Color','Shorts Items Away Color'].includes(field.name));
 if(category==='appearance')fields=fields.filter(field=>field.name!=='Jersey Bagginess');
 const groups=view==='players'?fieldGroups[category]:null,groupBar=$('field-groups');
 groupBar.replaceChildren();groupBar.hidden=!groups;
 const matchesSearch=field=>`${field.label} ${field.name}`.toLowerCase().includes(query);
 const groupOf=field=>groups?.includes(field.group)?field.group:'Other';
 if(groups){
  const choices=['',...groups];if(fields.some(field=>groupOf(field)==='Other'))choices.push('Other');
  if(!choices.includes(fieldGroup))fieldGroup='';
  for(const group of choices){
   const count=fields.filter(field=>matchesSearch(field)&&(!group||groupOf(field)===group)).length;
   const button=element('button',`${group||'All'} ${count}`,fieldGroup===group?'active':'');
   button.type='button';button.setAttribute('aria-pressed',String(fieldGroup===group));
   button.onclick=()=>{fieldGroup=group;renderFields();};groupBar.append(button);
  }
 }
 let shown=0;
 for(const field of fields){
  if(!matchesSearch(field)||(groups&&fieldGroup&&groupOf(field)!==fieldGroup))continue;shown++;
  const fieldCategory=field.sourceCategory||category;
  const source=category==='identity'?record:(record[fieldCategory]||{}),original=category==='identity'?old:old?.[fieldCategory];
  const value=source[field.name], row=element('div',undefined,'field'), label=element('label',field.label);
  const namedField=['signatures','gear','accessories','appearance'].includes(fieldCategory)&&field.writable&&field.kind==='bits';
  const names=fieldValues[fieldCategory]?.[field.name]||{};
  const input=field.team||field.options||field.displayChoices?element('select'):element('input');input.id=`field-${shown}`;label.htmlFor=input.id;
  if(category==='badges'&&field.group==='Personality')input.className='personality-choice';
  if(field.displayChoices){input.className='personality-choice';input.append(new Option('Not mapped',''),...field.displayChoices.map(label=>new Option(label,label)));if(value!==undefined)input.append(new Option(`Workspace value ${value} (unmapped)`,'workspace'));input.value=value===undefined?'':'workspace';}
  else if(field.options){input.append(new Option('Not set',''),...Object.entries(field.options).map(([label,id])=>new Option(label,String(id))));if(value!==undefined&&!Object.values(field.options).includes(value))input.append(new Option(field.kind==='college_reference'?`Current: ${value}`:`Game ID ${value} (name unknown)`,String(value)));input.value=value===undefined?'':String(value);}
  else if(field.team){input.append(new Option('Free agent',''),...roster.teams.map(t=>new Option(t.name,t.team_id)));input.value=value||'';}
  else if(namedField){input.type='text';input.className='text';input.value=Object.keys(names).find(name=>names[name]===value)||String(value??'');input.placeholder='Name or game ID';const list=element('datalist');list.id=`choices-${shown}`;for(const name of Object.keys(names)){const option=element('option');option.value=name;list.append(option);}input.setAttribute('list',list.id);row.append(list);}
  else if(field.slider){input.type='range';input.min=0;input.max=100;input.step=1;input.value=value??0;}
  else if(['attributes','tendencies','badges'].includes(category)||(field.writable&&field.bits&&field.kind!=='utf16'&&typeof value!=='string')){
   input.type='number';input.min=field.minimum??(gameLoaded&&category==='attributes'?25:0);input.max=field.maximum??(category==='attributes'?99:category==='tendencies'?100:category==='badges'?5:field.kind==='float'?3.402823466e38:2**field.bits-1);input.step=field.kind==='float'?'any':1;input.value=value??'';input.placeholder='—';
  }else{input.type='text';input.className='text';input.value=value===undefined?'':typeof value==='object'?JSON.stringify(value):String(value);input.placeholder='Not set';if(field.kind==='utf16')input.maxLength=19;}
  if(category==='body'&&field.name==='Height'&&!field.readOnly){input.step=value===undefined||Number.isInteger(value)?1:'any';input.title='Enter height in whole inches; 75 inches is 6 feet 3 inches. Existing game measurements may contain fractions.';input.placeholder='Inches';}
  row.prepend(label);row.append(input);
  const sliderValue=field.slider?element('output',value===undefined?'—':String(value),'slider-value'):null;
  if(sliderValue){sliderValue.htmlFor=input.id;row.append(sliderValue);}
  const highlight=()=>row.classList.toggle('changed',JSON.stringify(source[field.name])!==JSON.stringify(original?.[field.name]));highlight();
  if(field.readOnly){
   input.readOnly=true;if(field.options||field.slider||field.displayChoices)input.disabled=true;
   if(field.unmapped){if(!field.slider&&!field.displayChoices)input.value='';input.placeholder='Not mapped';}
   else{const names=fieldValues[fieldCategory]?.[field.name]||{},name=Object.keys(names).find(name=>names[name]===value);if(name&&!field.slider)input.value=name;}
   if(category==='body'&&field.name==='Height'&&typeof value==='number'){input.type='text';input.className='text';input.value=`${Math.floor(value/12)}′${Math.round((value%12)*100)/100}″ (${value} in)`;}
   input.title=field.readOnlyReason||(field.unmapped?'No memory definition identified.':field.sourceCategory==='attributes'?'Shown from Attributes; edit this value in Attributes.':'Raw read-only value. Display names and units have not been validated; raw injury durations are not yet confirmed as days.');
   label.append(element('small',field.unmapped?' · NOT MAPPED':' · READ ONLY'));$('fields').append(row);continue;
  }
  const allowedFields=gameStatus?.writable_fields;
  const liveField=view==='players'&&gameLoaded&&field.writable&&(!field.verifiedBuild||field.verifiedBuild.toLowerCase()===gameStatus?.build?.toLowerCase())&&(!Array.isArray(allowedFields)||allowedFields.some(([cat,name])=>cat===fieldCategory&&name===field.name));
  if(gameLoaded&&namedField){const learn=element('button','Learn name','learn-value');learn.title='Save the name shown in 2K for this player’s current value';learn.onclick=()=>{if(gameBusy||livePending)return;learningField={player_id:record.player_id,category:fieldCategory,field:field.name};$('learn-title').textContent=`${record.name} · ${field.label}`;$('learn-name').value='';$('learn-dialog').showModal();};row.append(learn);}
  if(gameLoaded&&!liveField){input.title='Local JSON only: this field has no verified write mapping for this connection.';label.append(element('small',' · LOCAL ONLY'));}
  const commitLive=()=>{if(liveField&&liveEnabled&&input.checkValidity()&&source[field.name]!==undefined)queueLiveEdit(record,fieldCategory,field.name,source[field.name]);};
  input.oninput=()=>{
   cancelLiveTimer(record.player_id,fieldCategory,field.name);
   let next=input.value;
   if(field.options){if(next==='')delete source[field.name];else source[field.name]=field.kind==='college_reference'?next:Number(next);}
   else if(input.type==='number'||input.type==='range'){
    if(next===''){input.setCustomValidity('');delete source[field.name];}
    else{next=Number(next);const whole=field.kind!=='float'||category==='body'&&field.name==='Height';if(!Number.isFinite(next)||(whole&&!Number.isInteger(next))||next<Number(input.min)||next>Number(input.max)){input.setCustomValidity(`Enter a ${whole?'whole number':'number'} from ${input.min} to ${input.max}.`);input.reportValidity();return;}input.setCustomValidity('');source[field.name]=next;}
   }else if(field.team)source[field.name]=next||null;
   else if(category==='identity'){if(!next.trim()){input.setCustomValidity('Name is required.');input.reportValidity();return;}input.setCustomValidity('');source[field.name]=next;}
   else if(field.kind==='utf16')source[field.name]=next;
   else if(next==='')delete source[field.name];
   else{try{source[field.name]=JSON.parse(next);}catch{source[field.name]=next;}}
   if(namedField&&liveEnabled){const nextValue=source[field.name],mapped=typeof nextValue==='string'?Object.keys(names).some(name=>name.toLowerCase()===nextValue.trim().toLowerCase()):Number.isInteger(nextValue)&&nextValue>=0&&nextValue<2**field.bits;input.setCustomValidity(mapped||nextValue===undefined?'':'Choose a learned name or an integer game ID.');}
   if(sliderValue)sliderValue.textContent=String(source[field.name]??'—');
   if(category!=='identity')record[fieldCategory]=source;
   dirtyRecords.add(`${view}:${record[idKey(view)]}`);highlight();refreshStatus();renderList();
   if(liveField&&liveEnabled&&source[field.name]!==undefined&&input.checkValidity()){const key=liveKey(record.player_id,fieldCategory,field.name);const timer=setTimeout(()=>{liveTimers.delete(key);commitLive();},450);liveTimers.set(key,timer);updateLiveControls();}
  };
  input.onchange=()=>{cancelLiveTimer(record.player_id,fieldCategory,field.name);commitLive();if(fieldCategory==='identity')renderInspector();};
  input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();input.blur();}};
  $('fields').append(row);
 }
 if(!shown)$('fields').append(element('div',category==='badges'&&fieldGroup==='Personality'&&!query?'No Personality badge definitions are mapped yet.':query||groups&&fieldGroup?'No matching fields. Try another category or search.':category==='contract'?'Contract fields will be added here.':category==='hotzones'?'Hotzone memory mappings are not verified yet. Imported hotzones remain available in your JSON workspace.':'No fields in this category. Import values in JSON to populate it.','empty'));
}
const display=value=>value===undefined?'Not set':typeof value==='object'?JSON.stringify(value):String(value);
function renderChanges(){
 $('changes').replaceChildren();const list=changes();
 for(const change of list){const row=element('div',undefined,'change-row'),label=element('div',change.name);label.append(element('small',change.path));const values=element('div');values.append(element('del',display(change.old)),document.createTextNode(' → '),element('code',display(change.value)));row.append(label,values);$('changes').append(row);}
 if(!list.length)$('changes').append(element('div','Your workspace is up to date. Edits will appear here before you save.','empty'));
 $('discard').disabled=!list.length||liveEnabled||livePending>0;
}
$('search').oninput=()=>{pageIndex=0;renderList();};$('team-filter').onchange=()=>{pageIndex=0;renderList();};$('page-prev').onclick=()=>{if(pageIndex>0){pageIndex--;renderList();}};$('page-next').onclick=()=>{pageIndex++;renderList();};$('field-search').oninput=renderFields;
function renderSettings(){
 $('show-advanced-fields').checked=showAdvancedFields;
}
$('show-advanced-fields').onchange=()=>{
 showAdvancedFields=$('show-advanced-fields').checked;
 try{localStorage.setItem('trace.showAdvancedFields',String(showAdvancedFields));}catch{}
};
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>setView(b.dataset.view));
$('review').onclick=()=>setView('changes');$('connection-info').onclick=()=>$('info-dialog').showModal();
$('revert-record').onclick=()=>{if(liveEnabled||livePending)return;const old=baseline[view].find(r=>r[idKey(view)]===selected);const index=roster[view].findIndex(r=>r[idKey(view)]===selected);if(old)roster[view][index]=clone(old);else roster[view].splice(index,1);selected=roster[view][Math.max(0,index)]?.[idKey(view)];render();};
$('discard').onclick=()=>{if(liveEnabled||livePending)return;roster=clone(baseline);render();toast('Unsaved edits discarded.');};
$('import').onclick=()=>$('file').click();
$('file').onchange=async()=>{const file=$('file').files[0];if(!file)return;try{if(file.size>128_000_000)throw Error('Roster must be smaller than 128 MB.');importDocument=JSON.parse(await file.text());const result=await api('/api/import',{document:importDocument});imported=result.roster;$('merge-import').checked=gameLoaded;$('import-summary').textContent=`${file.name} · ${imported.players.length} players · ${imported.teams.length} teams`;$('import-warnings').replaceChildren();$('import-dialog').showModal();}catch(error){toast(`Import failed: ${error.message}`,true);}finally{$('file').value='';}};
$('cancel-import').onclick=()=>$('import-dialog').close();
$('confirm-import').onclick=async()=>{if(!imported)return;const button=$('confirm-import');button.disabled=true;try{stopLiveLocally();const merging=$('merge-import').checked;const snapshot=JSON.stringify(roster);const result=merging?await api('/api/import',{document:importDocument,merge:true,target:roster}):{roster:imported,warnings:[]};if(snapshot!==JSON.stringify(roster))throw Error('Workspace changed during import. Try again.');roster=result.roster;syncWarnings=[];for(const kind of ['players','teams'])for(const record of roster[kind])dirtyRecords.add(`${kind}:${record[idKey(kind)]}`);imported=null;gamePlan=null;$('import-dialog').close();setView('players');if(result.warnings.length){showGameWarnings(result.warnings);$('game-changes').replaceChildren();$('game-summary').textContent='Import completed. These players were skipped:';$('apply-game').disabled=true;$('game-dialog').showModal();}toast(merging?'TRC values merged. Review changes before saving or applying.':'Roster imported. Review and save your workspace.');}catch(error){toast(`Import failed: ${error.message}`,true);}finally{button.disabled=false;}};
$('export').onclick=()=>{const blob=new Blob([JSON.stringify(roster,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=element('a');link.href=url;link.download='TRACE-roster.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Roster exported, including unsaved edits.');};
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
  if(result.available){$('update-title').textContent=`TRACE ${result.version} is available`;$('update-notes').textContent=result.notes;$('install-update').hidden=!desktopUpdates;
   if(!desktopUpdates)$('update-status').textContent+=' Open the packaged desktop app to install it.';}
 }catch(error){$('update-status').textContent=error.message;}finally{lockForUpdate(false);}
};
$('install-update').onclick=async()=>{
 if(updateBusy)return;
 if(window.trcHasUnsavedChanges()){toast('Save your workspace and finish pending edits before updating.',true);return;}
 lockForUpdate(true);$('update-status').textContent='Downloading and verifying the update. Keep the app open…';
 try{await api('/api/updates/download',{});$('update-status').textContent='Installing the update. TRACE will restart shortly…';await api('/api/updates/install',{});}
 catch(error){$('update-status').textContent=error.message;lockForUpdate(false);}
};
window.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();$('save').click();}});
function showGameWarnings(warnings){
 $('game-warnings').replaceChildren(...warnings.map(message=>element('p',message)));
}
const liveKey=(id,cat,field)=>JSON.stringify([id,cat,field]);
function cancelLiveTimer(id,cat,field){const key=liveKey(id,cat,field);clearTimeout(liveTimers.get(key));liveTimers.delete(key);}
function stopLiveLocally(){liveEnabled=false;for(const timer of liveTimers.values())clearTimeout(timer);liveTimers.clear();updateLiveControls();}
function rememberGameValues(){gameValues=new Map(roster.players.map(player=>[player.player_id,Object.fromEntries(['attributes','tendencies','badges','vitals','signatures','gear','accessories','appearance','hotzones'].map(cat=>[cat,clone(player[cat]||{})]))]));teamGameValues=new Map(roster.teams.map(team=>[team.team_id,clone(team.coaching?.values||{})]));undoCount=0;redoCount=0;}
function updateLiveControls(){
 $('trc-sync').disabled=gameBusy||livePending>0||liveTimers.size>0||!gameLoaded||!gameStatus?.connected;
 $('game-load').disabled=gameBusy||livePending>0||!gameStatus?.connected;
 $('game-preview').disabled=gameBusy||livePending>0||liveTimers.size>0||!gameLoaded||!gameStatus?.connected;
 $('game-live').textContent=liveEnabled?(livePending||liveTimers.size?'● Live editing ON · Writing…':'● Live editing ON · Stop'):'Start live editing';
 $('game-live').classList.toggle('primary',liveEnabled);
 $('game-live').classList.toggle('live-active',liveEnabled);
 $('game-live').setAttribute('aria-pressed',String(liveEnabled));
 $('game-live').title=liveEnabled?'Edits apply directly to the game. Click to stop live editing.':'Enable live editing for supported game fields.';
 $('game-live').disabled=gameBusy||livePending>0||!gameLoaded||!gameStatus?.connected;
 $('game-undo').disabled=gameBusy||livePending>0||liveTimers.size>0||!undoCount;
 $('game-redo').disabled=gameBusy||livePending>0||liveTimers.size>0||!redoCount;
 $('import').disabled=gameBusy||livePending>0;$('save-connection').disabled=gameBusy||livePending>0;
 $('revert-record').disabled=liveEnabled||livePending>0||!current()||(view==='teams'&&!hasEditableCoaching(current()));
 $('discard').disabled=liveEnabled||livePending>0;
}
function acceptGameChanges(result){
 for(const change of result.changes||[])if(change.team_id){const values=teamGameValues.get(change.team_id);if(values)values[change.field]=change.value;}
 undoCount=result.undo_count??undoCount;redoCount=result.redo_count??redoCount;let positionChanged=false;
 for(const change of result.changes||[]){if(change.category==='attributes'||change.category==='vitals'&&['Position','Secondary Position','Height','Wingspan','Shoulder Width','Neck Length','Trunk Length'].includes(change.field)){const player=roster.players.find(p=>p.player_id===change.player_id);if(player?.metadata?.overall_source==='game')player.metadata.overall=null;}const values=gameValues.get(change.player_id);if(values){values[change.category]??={};values[change.category][change.field]=change.value;if(change.category==='vitals'&&['Position','Secondary Position'].includes(change.field)&&gameStatus?.build?.toLowerCase()==='6ad2e48c:36532000'){const player=roster.players.find(p=>p.player_id===change.player_id);if(player){updatePlayerPosition(player,values.vitals);positionChanged=true;}}if(change.category==='vitals'&&['First Name','Last Name'].includes(change.field)){const player=roster.players.find(p=>p.player_id===change.player_id);if(player){player.name=[values.vitals['First Name'],values.vitals['Last Name']].filter(Boolean).join(' ');dirtyRecords.add(`players:${player.player_id}`);if(selected===player.player_id)$('record-header').querySelector('h2').textContent=player.name;}}}}
 if(positionChanged&&view==='players'){renderList();const player=current(),description=$('record-header').querySelector('p');if(player&&description)description.textContent=`${player.metadata?.position||'No position'}  /  ${playerTeamName(player)}  /  ${player.player_id}`;}
 for(const change of result.changes||[])if(change.category==='vitals'&&change.field==='College / From'){const player=roster.players.find(p=>p.player_id===change.player_id);if(player){player.metadata??={};player.metadata.college_from=change.value;}}
 updateLiveControls();
}
function queueLiveEdit(record,cat,field,value){
 if(!liveEnabled)return;
 livePending++;updateLiveControls();
 liveQueue=liveQueue.then(async()=>{
  if(!liveEnabled)return;const values=gameValues.get(record.player_id),expected=values?.[cat]?.[field];
  if(value===expected)return;
  try{const result=await api('/api/game/edit',{player_id:record.player_id,category:cat,field,value,expected});acceptGameChanges(result);gamePlan=null;}
  catch(error){stopLiveLocally();if(record[cat]?.[field]===value){if(expected===undefined)delete record[cat][field];else record[cat][field]=expected;}toast(`Live edit failed: ${error.message} Live editing paused; your value was not confirmed.`,true);renderList();renderInspector();refreshStatus();}
 }).finally(()=>{livePending--;updateLiveControls();});
}
function queueTeamLiveEdit(record,field,value){
 if(!liveEnabled)return;livePending++;updateLiveControls();
 liveQueue=liveQueue.then(async()=>{
  if(!liveEnabled)return;const expected=teamGameValues.get(record.team_id)?.[field];if(value===expected)return;
  try{const result=await api('/api/game/edit',{team_id:record.team_id,category:'coaching',field,value,expected});acceptGameChanges(result);gamePlan=null;}
  catch(error){stopLiveLocally();if(record.coaching.values[field]===value)record.coaching.values[field]=expected;toast(`Coaching edit failed: ${error.message} Live editing paused.`,true);renderInspector();refreshStatus();}
 }).finally(()=>{livePending--;updateLiveControls();});
}
$('game-live').onclick=async()=>{
 if(gameBusy||livePending)return;gameBusy=true;updateLiveControls();
 try{const result=await api('/api/game/live',{enabled:!liveEnabled});liveEnabled=result.live_enabled;undoCount=result.undo_count;redoCount=result.redo_count;gamePlan=null;if(!liveEnabled)stopLiveLocally();updateGameStatus(result.status);toast(liveEnabled?'Live editing on. Values apply automatically; use Undo game edit to restore them.':'Live editing stopped. Game edits remain until undone.');}
 catch(error){toast(error.message,true);}finally{gameBusy=false;updateLiveControls();renderInspector();}
};
async function restoreGameEdit(redo){
 if(gameBusy||livePending||liveTimers.size)return;gameBusy=true;updateLiveControls();
 try{const result=await api(redo?'/api/game/redo':'/api/game/undo',{});acceptGameChanges(result);for(const change of result.changes){if(change.team_id){const team=roster.teams.find(t=>t.team_id===change.team_id);if(team){team.coaching.values[change.field]=change.value;dirtyRecords.add(`teams:${team.team_id}`);}continue;}const player=roster.players.find(p=>p.player_id===change.player_id);if(player){player[change.category]??={};player[change.category][change.field]=change.value;dirtyRecords.add(`players:${player.player_id}`);}}gamePlan=null;renderList();renderInspector();refreshStatus();toast(redo?'Game edit redone.':'Game edit undone.');}
 catch(error){stopLiveLocally();toast(`Could not restore game edit: ${error.message}`,true);}finally{gameBusy=false;updateLiveControls();}
}
$('game-undo').onclick=()=>restoreGameEdit(false);$('game-redo').onclick=()=>restoreGameEdit(true);
$('cancel-learn').onclick=()=>$('learn-dialog').close();
$('confirm-learn').onclick=async()=>{
 if(gameBusy||livePending||!learningField)return;gameBusy=true;$('confirm-learn').disabled=true;updateLiveControls();
 try{const result=await api('/api/game/learn-value',{...learningField,label:$('learn-name').value});fieldValues=result.field_values;acceptGameChanges(result);const change=result.changes[0],player=roster.players.find(p=>p.player_id===change.player_id);if(player){player[change.category][change.field]=change.value;dirtyRecords.add(`players:${player.player_id}`);}gamePlan=null;$('learn-dialog').close();renderInspector();refreshStatus();toast(`Learned ${result.mapping.label} = ${result.mapping.value} for this game build.`);}
 catch(error){toast(`Could not learn this value: ${error.message}`,true);}finally{gameBusy=false;$('confirm-learn').disabled=false;updateLiveControls();}
};
function fillConnectionSettings(){
 $('game-path').value=connectionSettings.game_path;
}
$('build-diagnostic').onclick=async()=>{
 if(gameBusy)return;gameBusy=true;$('build-diagnostic').disabled=true;
 try{
  const report=await api('/api/game/diagnostics',{});
  const prompt=`Help diagnose TRACE's NBA 2K27 roster-load failure using this read-only live report. Identify exactly which lookup step failed and what evidence supports the next fix. Do not guess or recommend unverified addresses. If the report is inconclusive, tell me the next safe observation to collect.\n\n${JSON.stringify(report,null,2)}`;
  $('diagnostic-prompt').value=prompt;$('info-dialog').close();$('diagnostic-dialog').showModal();
 }catch(error){toast(`Could not collect game diagnostics: ${error.message}`,true);}
 finally{gameBusy=false;$('build-diagnostic').disabled=false;}
};
$('copy-diagnostic').onclick=async()=>{
 try{await navigator.clipboard.writeText($('diagnostic-prompt').value);toast('Diagnosis prompt copied. Paste it here to continue.');}
 catch{$('diagnostic-prompt').focus();$('diagnostic-prompt').select();toast('Select and copy the diagnosis prompt, then paste it here.');}
};
$('save-connection').onclick=async()=>{
 if(gameBusy)return;gameBusy=true;$('save-connection').disabled=true;
 try{const result=await api('/api/game/settings',{game_path:$('game-path').value});connectionSettings=result.game_settings;stopLiveLocally();gameLoaded=false;gamePlan=null;undoCount=0;redoCount=0;gameValues.clear();fillConnectionSettings();updateGameStatus({connected:false,error:'Settings saved. Check the game connection, then reload its roster.'});toast('Game connection settings saved.');}
 catch(error){toast(`Could not save connection settings: ${error.message}`,true);}finally{gameBusy=false;$('save-connection').disabled=false;}
};
function updateGameStatus(status){
 gameStatus=status;updateLiveControls();$('game-load').disabled=gameBusy||!status.connected;$('game-preview').disabled=gameBusy||livePending>0||!gameLoaded||!status.connected;
 $('connection-status').textContent=status.connected?'Connected to NBA 2K27':'Game not connected';
 $('mode-title').textContent=gameLoaded?'Game roster loaded':'Roster editing';
 $('mode-note').textContent=gameLoaded?'Start live editing to apply individual changes; save inside NBA 2K27 to keep them.':'Import your TRC export or load your NBA 2K27 roster.';
}
$('game-connect').onclick=async()=>{if(gameBusy)return;gameBusy=true;$('game-connect').disabled=true;try{updateGameStatus(await api('/api/game/status'));}catch(error){toast(error.message,true);}finally{gameBusy=false;$('game-connect').disabled=false;if(gameStatus)updateGameStatus(gameStatus);}};
$('game-load').onclick=async()=>{
 if(gameBusy||livePending)return;stopLiveLocally();if(changes().length&&!window.confirm('Loading the game roster replaces unsaved workspace edits. Continue?'))return;
 gameBusy=true;updateGameStatus(gameStatus);const snapshot=JSON.stringify(roster);toast('Reading the game roster…');
 try{const result=await api('/api/game/load',{});if(snapshot!==JSON.stringify(roster))throw Error('Workspace changed while reading the game. Load again when ready.');stopLiveLocally();roster=result.roster;syncWarnings=[];baseline=clone(roster);dirtyRecords.clear();workspaceNeedsSave=true;fieldValues=result.field_values||{};rememberGameValues();gameLoaded=true;gamePlan=null;updateGameStatus(result.status);setView('players');toast(Array.isArray(result.status.writable_fields)?`Loaded ${roster.players.length} players. ${result.status.writable_fields.length} mapped fields available for live editing.`:result.status.array_source==='validated community path'?`Loaded ${roster.players.length} players using a recovered roster location. Live editing needs a verified build profile.`:`Loaded ${roster.players.length} players from NBA 2K27.`);}
 catch(error){toast(`Game load failed: ${error.message}`,true);}finally{gameBusy=false;if(gameStatus)updateGameStatus(gameStatus);}
};
$('game-preview').onclick=async()=>{
 if(gameBusy||livePending||liveTimers.size)return;if(document.querySelector('input:invalid')){document.querySelector('input:invalid').reportValidity();return;}
 gameBusy=true;updateGameStatus(gameStatus);const snapshot=JSON.stringify(roster);
 try{const result=await api('/api/game/preview',roster);if(snapshot!==JSON.stringify(roster))throw Error('Workspace changed during preview. Preview again.');gamePlan=result;plannedRoster=snapshot;$('game-summary').textContent=`${result.changes.length} supported field changes. ${result.writes_enabled?'Apply writes these values to the running game.':'Read only: close this preview and click Start live editing once to enable writes, then preview again.'}`;
 $('game-changes').replaceChildren(...result.changes.map(change=>{const row=element('div',undefined,'change-row'),label=element('div',change.name);label.append(element('small',`${teamCategories[change.category]||categories[change.category]} / ${change.field}`));row.append(label,element('div',`${display(change.old)} → ${display(change.value)}`));return row;}));showGameWarnings([...syncWarnings,...result.warnings]);$('apply-game').disabled=!result.writes_enabled||!result.changes.length;$('game-dialog').showModal();}
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
fetch('/api/session').then(async response=>{if(!response.ok)throw Error('Could not load the editor session.');return response.json();}).then(session=>{if(session.api_version!==6)throw Error('An older editor is still running. Close its terminal and relaunch TRACE, then use the newly opened page.');roster=session.roster;baseline=clone(roster);profile=session.profile;token=session.token;connectionSettings=session.game_settings;desktopUpdates=session.desktop_updates;$('app-version').textContent=`v${session.app_version}`;fillConnectionSettings();selected=roster.players[0]?.player_id;render();}).catch(error=>{document.querySelectorAll('button,input,select').forEach(control=>control.disabled=true);toast(error.message,true);});
