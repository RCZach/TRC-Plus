import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_team_tabs_readouts_search_and_unknowns_do_not_edit_roster():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trace_app/ui/app.js','utf8'),controls=new Map();
const element=(tag,text)=>({tag,text,children:[],classList:{toggle(){}},append(...items){this.children.push(...items);},
 replaceChildren(...items){this.children=items;},setAttribute(key,value){this[key]=value;}});
const get=id=>{if(!controls.has(id))controls.set(id,element('div'));return controls.get(id);};
get('field-search').value='';
const team={team_id:'t',name:'Example Team',rotation:{player_ids:['p2','p1'],minutes:{p1:29,p2:0},total_minutes:29},
 coaching:{coach:'Morgan Coach',values:{'Help Defense':50,'Run Plays Frequency':70,'Zone Usage Frequency':0,Tempo:75}},
 staff:{entries:[{role:'COACH',name:'Morgan Coach'},{role:'HEAD_ASSISTANT',name:'Dana Assistant'}]}};
const roster={teams:[team],players:[{player_id:'p1',team_id:'t',name:'Alex One',metadata:{position:'PG'}},
 {player_id:'p2',team_id:'t',name:'Casey Two',metadata:{position:'SG'}},
 {player_id:'other',team_id:'other',name:'Other Team',metadata:{position:'C'}}]};
const before=JSON.stringify(roster);
const context=vm.createContext({$:get,element,current:()=>team,roster,view:'teams',category:'rotation',fieldGroup:'',liveEnabled:false,livePending:0});
vm.runInContext(source.slice(source.indexOf('const teamCategories='),source.indexOf('function renderFields(){')),context);
vm.runInContext(source.slice(source.indexOf('function renderFields(){'),source.indexOf('const display=')),context);
context.renderInspector();
assert.deepStrictEqual(get('tabs').children.map(t=>t.text),['Rotation','Coaching Emphasis','Staff']);
assert.strictEqual(get('revert-record').disabled,true);
assert.strictEqual(get('field-groups').hidden,true);
const table=get('fields').children.find(child=>child.tag==='table'),body=table.children[1];
assert.deepStrictEqual(body.children.map(row=>row.children.map(cell=>cell.text)),[['Casey Two','SG','0'],['Alex One','PG','29']]);
assert(get('fields').children.some(child=>child.text==='Team total: 29 min'));
get('field-search').value='Alex';context.renderFields();
assert.strictEqual(get('fields').children.find(c=>c.tag==='table').children[1].children.length,1);
get('tabs').children[1].onclick();
assert.strictEqual(context.category,'coaching');
let inputs=get('fields').children.flatMap(row=>row.children).filter(c=>c.tag==='input');
assert.deepStrictEqual(inputs.map(input=>input.value),['50','70','0','75']);
assert(inputs.every(input=>input.readOnly===true&&input.oninput===undefined));
get('tabs').children[2].onclick();
assert.strictEqual(context.category,'staff');
inputs=get('fields').children.flatMap(row=>row.children).filter(c=>c.tag==='input');
assert.deepStrictEqual(inputs.map(input=>input.value),['Morgan Coach','Dana Assistant']);
get('field-search').value='Dana';context.renderFields();
assert.strictEqual(get('fields').children.flatMap(row=>row.children).filter(c=>c.tag==='input').length,1);
assert.strictEqual(JSON.stringify(roster),before);
get('field-search').value='';delete team.coaching;context.category='coaching';context.renderFields();
inputs=get('fields').children.flatMap(row=>row.children).filter(c=>c.tag==='input');
assert(inputs.every(input=>input.value==='—'&&input.readOnly));
delete team.staff;context.category='staff';context.renderFields();
assert(get('fields').children.some(c=>c.text?.includes('No validated staff data')));
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_coaching_controls_stage_values_and_only_commit_with_live_enabled():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert'),source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const controls=new Map(),writes=[];
const element=(tag,text)=>({tag,text,children:[],classList:{toggle(){}},append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;},setAttribute(){},setCustomValidity(value){this.validityMessage=value;},checkValidity(){return !this.validityMessage;}});
const get=id=>{if(!controls.has(id))controls.set(id,element('div'));return controls.get(id);};get('field-search').value='';
const team={team_id:'t',name:'Example',coaching:{coach:'Morgan Coach',values:{'Help Defense':50,'Run Plays Frequency':70,'Zone Usage Frequency':8,Tempo:75},writable_fields:['Help Defense','Run Plays Frequency','Zone Usage Frequency','Tempo']}};
const baseline={players:[],teams:[JSON.parse(JSON.stringify(team))]},roster={players:[],teams:[team]};
const context=vm.createContext({$:get,element,current:()=>team,view:'teams',category:'coaching',liveEnabled:false,gameLoaded:true,gameStatus:{connected:true},teamGameValues:new Map([['t',{...team.coaching.values}]]),roster,baseline,dirtyRecords:new Set(),refreshStatus(){},cancelLiveTimer(){},queueTeamLiveEdit:(...args)=>writes.push(args)});
vm.runInContext(source.slice(source.indexOf('const teamCategories='),source.indexOf('function renderInspector(){')),context);
vm.runInContext(source.slice(source.indexOf('function renderTeamFields('),source.indexOf('function renderFields(){')),context);
context.renderTeamFields(team);
let inputs=get('fields').children.flatMap(row=>row.children).filter(c=>c.tag==='input');
assert(inputs.every(input=>input.type==='number'&&input.min===0&&input.max===100&&input.step===1));
const help=inputs[0];help.value='51';help.oninput();
assert.strictEqual(team.coaching.values['Help Defense'],51);assert.strictEqual(writes.length,0);assert(context.dirtyRecords.has('teams:t'));
context.liveEnabled=true;help.onchange();assert.deepStrictEqual(writes[0].slice(1),['Help Defense',51]);
help.value='101';help.oninput();assert.strictEqual(team.coaching.values['Help Defense'],51);assert(help.validityMessage);
help.onchange();assert.strictEqual(writes.length,1);
context.gameStatus.connected=false;get('fields').replaceChildren();context.renderTeamFields(team);
inputs=get('fields').children.flatMap(row=>row.children).filter(c=>c.tag==='input');assert(inputs.every(input=>input.readOnly&&input.oninput===undefined));
context.dirtyRecords.add('teams:t');context.categories={};context.idKey=kind=>kind==='players'?'player_id':'team_id';
vm.runInContext(source.slice(source.indexOf('function changes(){'),source.indexOf('function refreshStatus(){')),context);
const rows=context.changes();assert.strictEqual(rows.length,1);assert.strictEqual(rows[0].path,'Coaching Emphasis / Help Defense');assert.strictEqual(rows[0].old,50);assert.strictEqual(rows[0].value,51);
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_coaching_live_queue_expected_value_and_failure_pause():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert'),source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const calls=[],team={team_id:'t',coaching:{values:{'Help Defense':51}}};
const context=vm.createContext({liveEnabled:true,livePending:0,liveQueue:Promise.resolve(),teamGameValues:new Map([['t',{'Help Defense':50}]]),updateLiveControls(){},gamePlan:null,
 api:async(path,body)=>{calls.push(body);if(body.value===52)throw Error('stale coach');return {changes:[body]};},
 acceptGameChanges:result=>{for(const change of result.changes)context.teamGameValues.get(change.team_id)[change.field]=change.value;},
 stopLiveLocally:()=>{context.liveEnabled=false;},toast(){},renderInspector(){},refreshStatus(){}});
vm.runInContext(source.slice(source.indexOf('function queueTeamLiveEdit('),source.indexOf("$('game-live').onclick=")),context);
(async()=>{
 context.queueTeamLiveEdit(team,'Help Defense',51);await context.liveQueue;
 assert.strictEqual(calls[0].team_id,'t');assert.strictEqual(calls[0].category,'coaching');assert.strictEqual(calls[0].expected,50);assert.strictEqual(calls[0].value,51);
 assert.strictEqual(context.livePending,0);
 context.queueTeamLiveEdit(team,'Help Defense',51);await context.liveQueue;assert.strictEqual(calls.length,1);
 team.coaching.values['Help Defense']=52;context.queueTeamLiveEdit(team,'Help Defense',52);await context.liveQueue;
 assert.strictEqual(context.liveEnabled,false);assert.strictEqual(team.coaching.values['Help Defense'],51);assert.strictEqual(context.livePending,0);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
