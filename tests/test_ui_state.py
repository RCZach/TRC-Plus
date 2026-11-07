"""Regression check for controls remaining disabled after async bulk Apply."""

import shutil
import subprocess
import json

import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_settings_navigation_and_display_preference_do_not_change_roster():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const html=fs.readFileSync('src/trace_app/ui/index.html','utf8');
assert.deepStrictEqual(Array.from(html.matchAll(/data-view="([^"]+)"/g),m=>m[1]),['players','teams','changes','settings']);
const toolbar=html.slice(html.indexOf('<div id="game-toolbar"'),html.indexOf('<section id="browser-view"'));
assert(!toolbar.includes('id="game-preview"'));
const footer=html.slice(html.indexOf('<footer'),html.indexOf('</footer>'));
assert(footer.indexOf('id="review"')<footer.indexOf('id="save"'));
assert(footer.indexOf('id="save"')<footer.indexOf('id="game-preview"'));
assert(footer.includes('Review game writes'));
const controls=new Map(),storage=new Map(),nav=['players','teams','changes','settings'].map(view=>({dataset:{view},classList:{toggle(){}}}));
const element=(tag,text)=>({tag,text,children:[],classList:{toggle(){}},setAttribute(){},replaceChildren(...items){this.children=items;}});
const get=id=>{if(!controls.has(id))controls.set(id,element('div'));return controls.get(id);};
const roster={players:[{player_id:'p',name:'Player',attributes:{Potential:85},vitals:{'Birth Year':1980}}],teams:[]};
const original=JSON.stringify(roster);
let fieldRenders=0;
const context=vm.createContext({$:get,element,roster,view:'players',selected:'p',category:'vitals',fieldGroup:'',pageIndex:0,
 showAdvancedFields:false,gameLoaded:true,showTrcMatches:false,trcMatchesKnown:false,trcMatchedIds:new Set(),idKey:kind=>kind==='players'?'player_id':'team_id',
 document:{querySelectorAll:()=>nav,createTextNode:text=>({text})},Option:function(text,value){this.text=text;this.value=value;},
 localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)},
 updateLiveControls(){},refreshStatus(){},renderChanges(){},renderInspector(){fieldRenders++;},renderList(){}});
vm.runInContext(source.slice(source.indexOf('function readAdvancedFieldsPreference(){'),source.indexOf('let showAdvancedFields=')),context);
assert.strictEqual(context.readAdvancedFieldsPreference(),false);
vm.runInContext(source.slice(source.indexOf('function setView(next){'),source.indexOf('function renderList(){')),context);
vm.runInContext(source.slice(source.indexOf('function renderSettings(){'),source.indexOf("document.querySelectorAll('[data-view]')",source.indexOf('function renderSettings(){'))),context);
context.setView('settings');
assert.strictEqual(get('settings-view').hidden,false);assert.strictEqual(get('browser-view').hidden,true);
assert.strictEqual(get('review-view').hidden,true);assert.strictEqual(get('workspace-footer').hidden,true);
assert.strictEqual(get('show-advanced-fields').checked,false);assert.strictEqual(context.selected,'p');
get('show-advanced-fields').checked=true;get('show-advanced-fields').onchange();
assert.strictEqual(context.showAdvancedFields,true);assert.strictEqual(context.readAdvancedFieldsPreference(),true);
assert.strictEqual(JSON.stringify(roster),original);
context.setView('players');assert.strictEqual(get('settings-view').hidden,true);assert.strictEqual(get('browser-view').hidden,false);
assert.strictEqual(get('workspace-footer').hidden,false);assert.strictEqual(fieldRenders,1);
context.setView('teams');assert.strictEqual(context.category,'rotation');
context.setView('changes');assert.strictEqual(get('review-view').hidden,false);
context.setView('settings');assert.strictEqual(get('show-advanced-fields').checked,true);
context.localStorage={getItem(){throw Error('Unavailable');},setItem(){throw Error('Unavailable');}};
assert.strictEqual(context.readAdvancedFieldsPreference(),false);
get('show-advanced-fields').checked=false;get('show-advanced-fields').onchange();
assert.strictEqual(context.showAdvancedFields,false);
assert.strictEqual(JSON.stringify(roster),original);
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_shoes_gear_order_keeps_original_storage_catalog_and_live_category():
    from trace_app.app import DEFAULT_PROFILE
    from trace_app.mappings import expand_profile

    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const profile=JSON.parse(fs.readFileSync(0,'utf8'));
const controls=new Map();
const element=(tag,text)=>({tag,text,children:[],classList:{toggle(){}},
 append(...items){this.children.push(...items);},prepend(...items){this.children.unshift(...items);},
 replaceChildren(...items){this.children=items;},setAttribute(){},checkValidity(){return true;},setCustomValidity(){}});
const get=id=>{if(!controls.has(id))controls.set(id,element('div'));return controls.get(id);};
get('field-search').value='';
const record={player_id:'p',gear:{'Shoe Home Style':5002,'Bench Outfit':7},
 accessories:{'Shorts Items':1,'Shorts Items Home Color':2,'Headband':0},appearance:{'Jersey Bagginess':4}};
const original=JSON.stringify(record),writes=[];
const context=vm.createContext({$:get,element,showAdvancedFields:true,current:()=>record,category:'gear',view:'players',selected:'p',
 baseline:{players:[JSON.parse(original)]},idKey:()=> 'player_id',profile,
 fieldValues:{gear:{'Shoe Home Style':{'Air Jordan III':5002}},accessories:{'Shorts Items':{'Observed shorts':1}}},
 gameLoaded:true,gameStatus:{build:'6AD2E48C:36532000',writable_fields:[['gear','Shoe Home Style'],['accessories','Shorts Items']]},
 liveEnabled:false,fieldGroup:'Shoes / Gear',fieldGroups:{gear:['Shoes / Gear','Other Gear'],accessories:['Upper Body','Lower Body']},
 profileKeys:{gear:'Gear',accessories:'Accessories',appearance:'Appearance'},
 Option:function(label,value){this.text=label;this.value=value;},
 cancelLiveTimer(){},dirtyRecords:new Set(),refreshStatus(){},renderList(){},queueLiveEdit:(...args)=>writes.push(args)});
vm.runInContext(source.slice(source.indexOf('const categories ='),source.indexOf('const profileKeys =')),context);
vm.runInContext(source.slice(source.indexOf('const profileKeys ='),source.indexOf('function arrangeVitals(')),context);
assert.deepStrictEqual(Array.from(vm.runInContext('Object.keys(categories).slice(0,3)',context)),['vitals','body','gear']);
assert.strictEqual(vm.runInContext('categories.gear',context),'Shoes / Gear');
assert.deepStrictEqual(Array.from(vm.runInContext('Object.values(categories).slice(0,7)',context)),['Vitals','Body','Shoes / Gear','Accessories','Attributes','Tendencies','Hot Zones']);
assert.deepStrictEqual(Array.from(vm.runInContext('Object.values(categories).slice(7,-1)',context)),['Signature','Contract','Badges','Advanced','Metadata','Appearance']);
assert.deepStrictEqual(Array.from(vm.runInContext('Object.keys(categories).slice(0,4)',context)),['vitals','body','gear','accessories']);
vm.runInContext(source.slice(source.indexOf('function arrangeVitals('),source.indexOf('const idKey =')),context);
vm.runInContext(source.slice(source.indexOf('function renderFields(){'),source.indexOf('const display=')),context);
context.renderFields();
const labels=()=>get('fields').children.map(row=>row.children[0]?.text);
assert.deepStrictEqual(labels(),['Shoe Home','Shoe Away','Sock Length Home','Sock Length Away','Undershirt',
 'Undershirt Home Color','Undershirt Away Color','Shorts','Shorts Preferred Type','Shorts Length',
 'Shorts Home Color','Shorts Away Color','Bagginess']);
const rows=get('fields').children;
assert.strictEqual(rows[0].children.find(child=>child.tag==='input').value,'Air Jordan III');
const shorts=rows[7].children.find(child=>child.tag==='input');
assert.strictEqual(shorts.value,'Observed shorts');
assert.strictEqual(shorts.title,undefined);
assert.strictEqual(JSON.stringify(record),original);
shorts.value='2';shorts.oninput();
assert.strictEqual(record.accessories['Shorts Items'],2);
assert.strictEqual(record.gear['Shorts Items'],undefined);
context.liveEnabled=true;shorts.onchange();
assert.deepStrictEqual(writes[0].slice(1),['accessories','Shorts Items',2]);
get('field-search').value='shorts';context.renderFields();
assert.strictEqual(labels().length,5);
get('field-search').value='';context.fieldGroup='Other Gear';context.renderFields();
assert(labels().includes('Bench Outfit'));assert(!labels().includes('Shoe Home'));
context.category='accessories';context.fieldGroup='';context.renderFields();
assert(labels().includes('Headband'));assert(!labels().includes('Shorts Items'));
assert(get('field-groups').children.some(button=>button.text==='Upper Body 52'));
assert(get('field-groups').children.some(button=>button.text==='Lower Body 27'));
const accessorySnapshot=JSON.stringify(record);
get('field-groups').children.find(button=>button.text==='Upper Body 52').onclick();
assert(labels().includes('Headband'));assert(labels().includes('Left Arm'));
assert(!labels().includes('Left Knee'));
get('field-search').value='knee';context.renderFields();
assert(get('fields').children[0].text.startsWith('No matching fields.'));
get('field-groups').children.find(button=>button.text.startsWith('Lower Body ')).onclick();
assert(labels().includes('Left Knee'));assert(!labels().includes('Left Arm'));
get('field-search').value='';context.renderFields();
assert(labels().includes('Left Leg'));assert(labels().includes('Right Ankle'));
assert.strictEqual(JSON.stringify(record),accessorySnapshot);
record.accessories['Custom Accessory']=3;context.fieldGroup='Other';context.renderFields();
assert.deepStrictEqual(labels(),['Custom Accessory']);
context.category='appearance';context.renderFields();
assert(!labels().includes('Jersey Bagginess'));
assert.strictEqual(record.appearance['Jersey Bagginess'],4);
const beforeGroups=JSON.stringify(record);
context.gameLoaded=false;context.liveEnabled=false;context.category='tendencies';context.fieldGroup='';
context.renderFields();
assert.strictEqual(labels().length,99);
assert.deepStrictEqual(get('field-groups').children.map(button=>button.text),['All 99','Jump Shooting 31','Layups and Dunks 11','Drive Setup 7','Driving 14','Passing 3','Post Game 17','Freelance 9','Defense 7']);
get('field-groups').children.find(button=>button.text==='Jump Shooting 31').onclick();
assert(labels().includes('Step Through Shot'));assert(!labels().includes('Shoot'));
get('field-search').value='post';context.renderFields();
assert(get('fields').children[0].text.startsWith('No matching fields.'));
get('field-groups').children.find(button=>button.text.startsWith('Post Game ')).onclick();
assert(labels().includes('Post Up'));assert(!labels().includes('Flashy Pass'));
context.category='badges';context.fieldGroup='';get('field-search').value='';context.renderFields();
assert.strictEqual(labels().length,69);
assert.deepStrictEqual(get('field-groups').children.map(button=>button.text),['All 69','Finishing 11','Shooting 9','Playmaking 10','Defense 12','Physicals 6','Rebounding 5','Personality 16']);
get('field-groups').children.find(button=>button.text==='Physicals 6').onclick();
assert(labels().includes('Pogo Stick'));assert(labels().includes('Slippery Off-Ball'));
assert(!labels().includes('Immovable Enforcer'));
get('field-groups').children.find(button=>button.text==='Shooting 9').onclick();
assert(labels().includes('Post Fade Phenom'));assert(!labels().includes('Post Powerhouse'));
get('field-groups').children.find(button=>button.text==='Personality 16').onclick();
assert.deepStrictEqual(labels(),['Reserved','Friendly','Team Player','Extremely Confident','Keep It Real','Pat My Back','Expressive','Unpredictable','Laid Back','Media Ringmaster','Warm Weather Fan','Finance Savvy','Alpha Dog','Enforcer','Work Ethic','Marketability']);
for(const [index,row] of get('fields').children.entries()){
 const control=row.children.find(child=>child.tag==='select');
 assert(!control.disabled);assert.strictEqual(typeof control.oninput,'function');
 assert.strictEqual(control.value,'');
 assert.deepStrictEqual(control.children.map(option=>option.text),index<14?['Not set','Unequipped','Equipped']:['Not set','Unequipped','Bronze','Silver','Gold','Hall of Fame']);
}
assert.strictEqual(JSON.stringify(record),beforeGroups);
record.badges={Reserved:1,'Work Ethic':4};context.renderFields();
const imported=get('fields').children[0].children.find(child=>child.tag==='select');
assert.strictEqual(imported.value,'1');
assert(imported.children.some(option=>option.text==='Equipped'&&option.value==='1'));
assert.strictEqual(record.badges.Reserved,1);assert.strictEqual(record.badges['Work Ethic'],4);
get('field-search').value='market';context.renderFields();assert.deepStrictEqual(labels(),['Marketability']);
get('field-search').value='';
context.profile.Badges=context.profile.Badges.filter(field=>field.ui_group!=='Personality');context.renderFields();
const unmapped=get('fields').children[0].children.find(child=>child.tag==='select');
assert.strictEqual(unmapped.disabled,true);assert.strictEqual(unmapped.oninput,undefined);
assert.strictEqual(unmapped.value,'workspace');
assert(unmapped.children.some(option=>option.text==='Workspace value 1 (unmapped)'));
context.category='body';context.fieldGroup='';context.gameLoaded=true;context.liveEnabled=false;
context.gameStatus={build:'6AD2E48C:36532000',body_writable:true,writable_fields:[['vitals','Height'],['vitals','Wingspan'],['vitals','Shoulder Width'],['vitals','Neck Length'],['vitals','Trunk Length']]};
record.vitals={Height:75,Weight:191,Wingspan:51,'Shoulder Width':54,'Neck Length':52,'Trunk Length':53};
context.renderFields();
const bodyRows=get('fields').children, height=bodyRows[0].children.find(child=>child.tag==='input');
assert.strictEqual(height.type,'number');assert.strictEqual(height.value,75);assert.strictEqual(height.step,1);
assert(!height.readOnly);assert(height.title.includes('inches'));
for(const row of bodyRows.slice(2)){
 const slider=row.children.find(child=>child.tag==='input');
 assert.strictEqual(slider.type,'range');assert(!slider.disabled);assert.strictEqual(typeof slider.oninput,'function');
}
height.value='76';height.oninput();assert.strictEqual(record.vitals.Height,76);
assert.strictEqual(record.body,undefined);
context.liveEnabled=true;height.onchange();assert.deepStrictEqual(writes.at(-1).slice(1),['vitals','Height',76]);
context.gameStatus.body_writable=false;context.renderFields();
const guardedHeight=get('fields').children[0].children.find(child=>child.tag==='input');
assert.strictEqual(guardedHeight.readOnly,true);assert.strictEqual(guardedHeight.type,'text');
assert.strictEqual(guardedHeight.oninput,undefined);
assert(get('fields').children[2].children.find(child=>child.tag==='input').disabled);
"""
    result = subprocess.run(['node', '-e', script], input=json.dumps(expand_profile(json.loads(DEFAULT_PROFILE.read_text()))),
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_field_categories_combine_with_search_without_changing_values():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const controls=new Map();
const element=(tag,text)=>({tag,text,children:[],classList:{toggle(){}},
 append(...items){this.children.push(...items);},prepend(...items){this.children.unshift(...items);},
 replaceChildren(...items){this.children=items;},setAttribute(){}});
const get=id=>{if(!controls.has(id))controls.set(id,element('div'));return controls.get(id);};
get('field-search').value='';
const record={player_id:'p',attributes:{Layup:80,Block:50,Custom:70,Potential:85},vitals:{'FIBA Team':69,Weight:190},advanced:{INJURY1TYPE:12},metadata:{college_from:'Arizona'}};
const original=JSON.stringify(record);
const context=vm.createContext({$:get,element,showAdvancedFields:true,current:()=>record,category:'attributes',view:'players',selected:'p',
 baseline:{players:[JSON.parse(original)]},idKey:()=> 'player_id',fieldValues:{},gameLoaded:false,
 liveEnabled:false,gameStatus:null,fieldGroup:'',fieldGroups:{attributes:['Offense','Defense']},
 Option:function(label,value){this.text=label;this.value=value;},
 profileKeys:{attributes:'Attributes',advanced:'Advanced Fields',vitals:'Vitals'},profile:{Vitals:[{name:'Weight',bits:32,kind:'float',writable:true},{name:'FIBA Team',bits:16,writable:true,options:{None:65535,USA:69}}],'Advanced Fields':[{id:'INJURY1TYPE',offset:300,bits:8}],Attributes:[
  {name:'Layup',bits:8,writable:true,ui_group:'Offense'},
  {name:'Block',bits:8,writable:true,ui_group:'Defense'}]}});
vm.runInContext(source.slice(source.indexOf('function arrangeVitals('),source.indexOf('const idKey =')),context);
vm.runInContext(source.slice(source.indexOf('function renderFields(){'),source.indexOf('const display=')),context);
const labels=()=>get('fields').children.map(row=>row.children[0]?.text);
context.renderFields();
assert.deepStrictEqual(labels(),['Layup','Block','Custom','Potential']);
assert(get('field-groups').children.some(button=>button.text==='Other 2'));
get('field-groups').children.find(button=>button.text==='Defense 1').onclick();
assert.deepStrictEqual(labels(),['Block']);
get('field-search').value='Layup';context.renderFields();
assert(get('fields').children[0].text.startsWith('No matching fields.'));
get('field-groups').children.find(button=>button.text==='All 1').onclick();
assert.deepStrictEqual(labels(),['Layup']);
assert.strictEqual(JSON.stringify(record),original);
get('field-search').value='';context.category='vitals';
context.profile.Attributes.push({name:'Potential',bits:8,writable:true});
context.renderFields();
let mirror=get('fields').children.find(row=>row.children[0].text==='Potential').children[1];
assert.strictEqual(mirror.value,'85');assert.strictEqual(mirror.readOnly,true);assert.strictEqual(mirror.oninput,undefined);
record.attributes.Potential=89;context.renderFields();
mirror=get('fields').children.find(row=>row.children[0].text==='Potential').children[1];assert.strictEqual(mirror.value,'89');
record.attributes.Potential=85;
context.showAdvancedFields=false;context.renderFields();
assert.deepStrictEqual(labels(),['First Name','Last Name','Position','College / From','Birthplace','Jersey Number','Dominant Hand','Dominant Dunk Hand','Injury 1 Type','Injury 1 Duration Days','Play Initiator','Play Type 1','Play Type 2','Play Type 3','Play Type 4']);
assert.strictEqual(JSON.stringify(record),original);
get('field-search').value='Potential';context.renderFields();assert(get('fields').children[0].text.startsWith('No matching fields.'));
get('field-search').value='';context.showAdvancedFields=true;context.renderFields();
assert.strictEqual(get('field-groups').hidden,true);
const rows=get('fields').children;
assert.deepStrictEqual(labels().slice(0,8),['First Name','Last Name','Position','Secondary Position','FIBA Team','College / From','High School','Birthplace']);
const fiba=rows.find(row=>row.children[0].text==='FIBA Team');
assert.strictEqual(fiba.children[1].value,'69');
assert(fiba.children[1].children.some(option=>option.text==='USA'));
const injury=rows.find(row=>row.children[0].text==='Injury 1 Type');
assert.strictEqual(injury.children[1].value,'12');
assert.strictEqual(injury.children[1].readOnly,true);
assert.strictEqual(injury.children[1].oninput,undefined);
const college=rows.find(row=>row.children[0].text==='College / From');
assert.strictEqual(college.children[1].value,'Arizona');
assert.strictEqual(college.children[1].readOnly,true);
assert.strictEqual(JSON.stringify(record),original);
assert(!labels().includes('Weight'));
context.category='body';context.gameLoaded=true;
context.gameStatus={build:'test',writable_fields:[['vitals','Weight']]};
context.renderFields();
assert.deepStrictEqual(labels(),['Height','Weight','Wingspan','Shoulder Width','Neck Length','Trunk Length']);
const bodyRows=get('fields').children;
assert.strictEqual(bodyRows[0].children[1].placeholder,'Not mapped');
assert.strictEqual(bodyRows[0].children[1].readOnly,true);
for(const row of bodyRows.slice(2)){
 const slider=row.children[1];
 assert.strictEqual(slider.type,'range');assert.strictEqual(slider.min,0);assert.strictEqual(slider.max,100);
 assert.strictEqual(slider.disabled,true);assert.strictEqual(slider.oninput,undefined);
 assert.strictEqual(row.children[2].text,'—');
}
assert.strictEqual(JSON.stringify(record),original);
const weight=bodyRows[1].children[1];
assert.strictEqual(weight.type,'number');assert.strictEqual(weight.value,190);
assert.strictEqual(weight.title,undefined); // Existing Vitals capability applies in Body.
Object.assign(context,{cancelLiveTimer(){},dirtyRecords:new Set(),refreshStatus(){},renderList(){}});
weight.setCustomValidity=()=>{};weight.value='191';weight.oninput();
assert.strictEqual(record.vitals.Weight,191);assert.strictEqual(record.body,undefined);
const writes=[];
Object.assign(context,{liveEnabled:true,queueLiveEdit:(...args)=>writes.push(args)});
weight.checkValidity=()=>true;weight.onchange();
assert.strictEqual(writes.length,1);
assert.deepStrictEqual(writes[0].slice(1),['vitals','Weight',191]);
context.profile.Body=['Height','Wingspan','Shoulder Width','Neck Length','Trunk Length'].map(name=>({name,readOnly:true,writable:false,kind:name==='Height'?'float':'bits'}));
Object.assign(record.vitals,{Height:75,Wingspan:51,'Shoulder Width':54,'Neck Length':52,'Trunk Length':53});
context.renderFields();
const mappedRows=get('fields').children;
assert.strictEqual(mappedRows[0].children[1].value,'6′3″ (75 in)');
assert.deepStrictEqual(mappedRows.slice(2).map(row=>row.children[2].text),['51','54','52','53']);
for(const row of mappedRows.slice(2)){
 assert.strictEqual(row.children[1].disabled,true);
 assert.strictEqual(row.children[1].oninput,undefined);
 assert(!row.children[0].children.some(child=>child.text===' · NOT MAPPED'));
}
context.category='vitals';context.renderFields();
assert(!labels().some(label=>['Height','Weight','Wingspan','Shoulder Width','Neck Length','Trunk Length'].includes(label)));
context.profile.Vitals.push({name:'College / From',bits:64,offset:176,kind:'college_reference',writable:true});
context.fieldValues.vitals={'College / From':{Arizona:'Arizona',Argentina:'Argentina'}};
context.gameStatus={build:'6AD2E48C:36532000',college_writable:true,writable_fields:[['vitals','College / From']]};
record.vitals['College / From']='Arizona';context.liveEnabled=false;context.renderFields();
const collegeChoice=get('fields').children.find(row=>row.children[0].text==='College / From').children[1];
assert.strictEqual(collegeChoice.value,'Arizona');assert(!collegeChoice.disabled);
collegeChoice.setCustomValidity=()=>{};collegeChoice.checkValidity=()=>true;
collegeChoice.value='Argentina';collegeChoice.oninput();assert.strictEqual(record.vitals['College / From'],'Argentina');
context.liveEnabled=true;collegeChoice.onchange();assert.deepStrictEqual(writes.at(-1).slice(1),['vitals','College / From','Argentina']);
context.gameStatus.college_writable=false;context.renderFields();
assert.strictEqual(get('fields').children.find(row=>row.children[0].text==='College / From').children[1].disabled,true);

"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_player_list_uses_overall_and_distinguishes_unknown_teams():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const context=vm.createContext({roster:{teams:[{team_id:'atl',name:'Atlanta Hawks'}]}});
vm.runInContext(source.slice(source.indexOf('function teamName('),source.indexOf('function current(')),context);
assert.strictEqual(context.playerOverall({metadata:{overall:88},attributes:{Speed:20}}),'88');
assert.strictEqual(context.playerOverall({attributes:{Speed:99}}),'—');
assert.strictEqual(context.playerOverall({metadata:{overall:null}}),'—');
assert.strictEqual(context.playerTeamName({team_id:'atl'}),'Atlanta Hawks');
assert.strictEqual(context.playerTeamName({metadata:{team_status:'unknown'}}),'Unknown team');
assert.strictEqual(context.isFreeAgent({metadata:{team_status:'unknown'}}),false);
assert.strictEqual(context.isFreeAgent({}),true);
const positionPlayer={metadata:{}};
context.updatePlayerPosition(positionPlayer,{Position:0,'Secondary Position':5});
assert.strictEqual(positionPlayer.metadata.position,'PG');
context.updatePlayerPosition(positionPlayer,{Position:1,'Secondary Position':2});
assert.strictEqual(positionPlayer.metadata.position,'SG / SF');
assert(source.includes("['PLAYER','TEAM','POS','OVR']"));
assert(!source.includes('AVG*'));
const controls=new Map();
const element=(tag,text)=>({tag,text,children:[],append(...items){this.children.push(...items);},
 replaceChildren(...items){this.children=items;},setAttribute(){}});
const get=id=>{if(!controls.has(id))controls.set(id,element('div'));return controls.get(id);};
get('search').value='';get('team-filter').value='';
Object.assign(context,{$:get,element,idKey:()=> 'player_id',view:'players',pageIndex:0,PAGE_SIZE:100,selected:'game-0',showTrcMatches:false,trcMatchedIds:new Set(),renderInspector(){}});
context.roster.teams[0].metadata={abbreviation:'ATL'};
context.roster.players=[
 {player_id:'game-0',name:'Mike Bibby',team_id:'atl',metadata:{position:'PG',overall:76,overall_source:'game'},attributes:{Speed:99}},
 {player_id:'game-1',name:'Joe Johnson',team_id:'atl',metadata:{position:'SG / SF',overall:88,overall_source:'game'},attributes:{Speed:25}},
 {player_id:'unknown',name:'Unknown Team',metadata:{team_status:'unknown'},attributes:{Speed:99}},
 {player_id:'free',name:'Free Agent',metadata:{},attributes:{Speed:99}}
];
vm.runInContext(source.slice(source.indexOf('function renderList(){'),source.indexOf('function renderInspector(){')),context);
context.renderList();
const rows=get('record-list').children;
assert.strictEqual(rows[0].children[1].text,'ATL');
assert.strictEqual(rows[0].children[1].title,'Atlanta Hawks');
assert.strictEqual(rows[0].children[3].text,'76');
assert.strictEqual(rows[1].children[2].children[0].text,'SG / SF');
assert.strictEqual(rows[1].children[3].text,'88');
assert.strictEqual(rows[2].children[1].text,'—');
assert.strictEqual(rows[2].children[3].text,'—');
assert.strictEqual(rows[3].children[1].text,'FA');
context.showTrcMatches=true;context.trcMatchedIds=new Set(['game-1']);context.renderList();
assert.strictEqual(get('record-list').children.length,1);
assert.strictEqual(get('record-list').children[0].children[0].children[0].children[1].children[0].text,'Joe Johnson');
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_bulk_apply_reenables_undo_and_other_controls():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const controls=new Map();
const get=id=>{if(!controls.has(id))controls.set(id,{disabled:false,classList:{toggle(){}},setAttribute(name,value){this[name]=value;},close(){}});return controls.get(id);};
const roster={players:[],teams:[]};
const context=vm.createContext({$:get,gameBusy:false,livePending:0,liveTimers:new Map(),
 liveEnabled:false,gameLoaded:true,gameStatus:{connected:true},view:'players',undoCount:0,redoCount:0,
 gameValues:new Map(),current:()=>null,roster,plannedRoster:JSON.stringify(roster),
 gamePlan:{plan_id:'test'},toast:()=>{},api:async()=>({applied:1,changes:[],undo_count:1,redo_count:0})});
vm.runInContext(source.slice(source.indexOf('function updateLiveControls(){'),source.indexOf('function queueLiveEdit(')),context);
vm.runInContext(source.slice(source.indexOf("$('apply-game').onclick=async()=>{"),source.indexOf("fetch('/api/session')")),context);
(async()=>{await get('apply-game').onclick();
 assert.strictEqual(context.gameBusy,false);
 assert.strictEqual(get('game-undo').disabled,false);
 assert.strictEqual(get('game-preview').disabled,false);
 assert.strictEqual(get('game-load').disabled,false);
 assert.strictEqual(get('game-live').textContent,'Start live editing');
 context.liveEnabled=true;context.updateLiveControls();
 assert(get('game-live').textContent.includes('Live editing ON'));
 assert.strictEqual(get('game-live')['aria-pressed'],'true');
 context.livePending=1;context.updateLiveControls();
 assert(get('game-live').textContent.includes('Writing'));
 assert.strictEqual(get('game-live').disabled,true);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_trc_player_toggle_only_filters_loaded_roster():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const controls=new Map();const get=id=>{if(!controls.has(id))controls.set(id,{});return controls.get(id);};
const roster={players:[{player_id:'p1',name:'Kelly Jordan'},{player_id:'p2',name:'NBA Player'}],teams:[]};
const original=JSON.stringify(roster),calls=[],notices=[];
const context=vm.createContext({$:get,roster,gameLoaded:true,gameBusy:false,pageIndex:0,
 trcMatchedIds:new Set(),trcMatchesKnown:false,showTrcMatches:false,
 normalizedPlayerName:name=>name.normalize('NFKC').toLowerCase().trim().replace(/\s+/g,' '),
 updateLiveControls(){},render(){},toast:message=>notices.push(message),
 api:async(path,body)=>{calls.push(path);assert.deepStrictEqual(Array.from(body.names),['Kelly Jordan','NBA Player']);
  return {roster:{players:[{name:'Kelly Jordan'}]}};}});
vm.runInContext(source.slice(source.indexOf("$('all-records').onclick="),source.indexOf('function renderSettings(){')),context);
(async()=>{
 await get('trc-records').onclick();
 assert.deepStrictEqual(calls,['/api/trc/export']);
 assert.strictEqual(context.showTrcMatches,true);assert.strictEqual(context.trcMatchesKnown,true);
 assert.deepStrictEqual(Array.from(context.trcMatchedIds),['p1']);
 assert.strictEqual(JSON.stringify(roster),original);
 await get('trc-records').onclick();assert.strictEqual(context.showTrcMatches,false);
 await get('trc-records').onclick();assert.strictEqual(context.showTrcMatches,true);
 assert.strictEqual(calls.length,1);
 get('all-records').onclick();assert.strictEqual(context.showTrcMatches,false);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_reviewed_game_preview_allows_apply_without_live_editing():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const controls=new Map();
const get=id=>{if(!controls.has(id))controls.set(id,{showModal(){this.open=true;}});return controls.get(id);};
const roster={players:[],teams:[]};
const context=vm.createContext({$:get,gameBusy:false,livePending:0,liveTimers:new Map(),
 roster,syncPreviewRoster:null,syncWarnings:[],gameStatus:{connected:true},
 document:{querySelector(){return null;}},setTrcSyncStatus(){},updateGameStatus(){},
 showGameChanges(){},showGameWarnings(){},toast(message){throw Error(message);},
 api:async path=>{assert.strictEqual(path,'/api/game/preview');return {
  plan_id:'reviewed',changes:[{field:'Speed'}],warnings:[],writes_enabled:false,can_apply:true};}
});
vm.runInContext(source.slice(source.indexOf("$('game-preview').onclick=async()=>{"),
 source.indexOf("$('cancel-game').onclick=")),context);
(async()=>{await get('game-preview').onclick();
 assert.strictEqual(get('apply-game').disabled,false);
 assert.strictEqual(get('game-dialog').open,true);
 assert.match(get('game-summary').textContent,/Apply writes these reviewed values/);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_website_sync_stages_without_writing_and_preserves_match_warnings():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const controls=new Map();
const get=id=>{if(!controls.has(id))controls.set(id,{});return controls.get(id);};
const calls=[];
const initial={players:[{player_id:'game-1',name:'Zachary James Jr.'}],teams:[]};
const merged={players:[{player_id:'game-1',name:'Zachary James Jr.',attributes:{Speed:80}}],teams:[]};
const scoped={players:[{player_id:'game-1',name:'Zachary James Jr.',attributes:{Speed:80}}],teams:[]};
let previews=0;
get('game-preview').onclick=async()=>{previews++;assert.strictEqual(context.gameBusy,false);};
const context=vm.createContext({$:get,gameBusy:false,livePending:0,liveTimers:new Map(),
 gameLoaded:true,gameStatus:{connected:true},roster:initial,gamePlan:null,workspaceNeedsSave:false,
 syncWarnings:[],syncPreviewRoster:null,trcMatchedIds:new Set(),trcMatchesKnown:false,showTrcMatches:false,
 dirtyRecords:new Set(),stopLiveLocally(){calls.push('stop-live');},
 updateLiveControls(){},updateGameStatus(){},setView(){},toast(){},
 setTrcSyncStatus(message){get('trc-sync-status').textContent=message;},
 api:async(path,body)=>{calls.push(path);
  if(path==='/api/trc/export'){assert.deepStrictEqual(Array.from(body.names),['Zachary James Jr.']);return {roster:{players:[{name:'Zachary James Jr'},{name:'Missing Player'}]}};}
  if(path==='/api/import'){assert.strictEqual(body.merge,true);return {roster:merged,sync_roster:scoped,warnings:['Missing Player: skipped.']};}
  if(path==='/api/game/live'){assert.strictEqual(body.enabled,false);return {};}
  throw Error('Unexpected request: '+path);
 }});
vm.runInContext(source.match(/^const normalizedPlayerName=.*$/m)[0],context);
vm.runInContext(source.slice(source.indexOf('const showGamePreview='),source.indexOf("$('apply-game').onclick=")),context);
(async()=>{await get('trc-sync').onclick();
 assert.strictEqual(previews,1);assert.strictEqual(context.roster,merged);
 assert.strictEqual(context.syncWarnings[0],'Missing Player: skipped.');
 assert.strictEqual(context.syncPreviewRoster,scoped);
 assert.strictEqual(context.gameBusy,false);assert.strictEqual(context.workspaceNeedsSave,true);
 assert.strictEqual(context.showTrcMatches,true);
 assert.strictEqual(context.trcMatchesKnown,true);
 assert.deepStrictEqual(Array.from(context.trcMatchedIds),['game-1']);
 assert.deepStrictEqual(Array.from(context.dirtyRecords),['players:game-1']);
 assert.deepStrictEqual(calls,['/api/trc/export','/api/import','/api/game/live','stop-live']);
 assert.strictEqual(get('trc-sync-status').textContent,'');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_large_game_preview_renders_in_bounded_batches():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const controls=new Map();
const get=id=>{if(!controls.has(id))controls.set(id,{children:[],replaceChildren(...items){this.children=items;},append(...items){this.children.push(...items);}});return controls.get(id);};
const element=(tag,value,cls)=>({tag,textContent:value,className:cls,children:[],append(...items){this.children.push(...items);}});
const changes=Array.from({length:11820},(_,i)=>({name:`Player ${i%92}`,category:'attributes',field:`Field ${i}`,old:25,value:80}));
const warnings=Array.from({length:3894},(_,i)=>`Skipped ${i}`);
const context=vm.createContext({$:get,element,gamePlan:{changes},gameWarningMessages:[],gameWarningsShown:0,gameChangesShown:0,
 GAME_CHANGE_BATCH:100,GAME_WARNING_BATCH:50,teamCategories:{},categories:{attributes:'Attributes'},display:value=>String(value)});
vm.runInContext(source.slice(source.indexOf('function showGameWarnings('),source.indexOf('const liveKey=')),context);
vm.runInContext('showGameChanges(gamePlan.changes);showGameWarnings('+JSON.stringify(warnings)+')',context);
assert.strictEqual(get('game-changes').children.length,100);
assert.strictEqual(get('game-warnings').children.length,50);
assert.strictEqual(get('more-game-changes').hidden,false);
assert.strictEqual(get('more-game-warnings').hidden,false);
assert(get('game-change-breakdown').textContent.includes('92 players'));
get('more-game-changes').onclick();get('more-game-warnings').onclick();
assert.strictEqual(get('game-changes').children.length,200);
assert.strictEqual(get('game-warnings').children.length,100);
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_updates_require_saved_edits_and_install_only_after_user_click():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trace_app/ui/app.js','utf8');
const controls=new Map(),calls=[],panes=[{},{}];
const get=id=>{if(!controls.has(id))controls.set(id,{addEventListener(){},showModal(){},close(){}});return controls.get(id);};
let dirty=true;
const context=vm.createContext({$:get,desktopUpdates:true,updateBusy:false,
 document:{querySelectorAll:()=>panes},window:{trcHasUnsavedChanges:()=>dirty},toast(){},
 api:async path=>{calls.push(path);return {available:true,version:'0.4.0',message:'Available',notes:'New release'};}});
vm.runInContext(source.slice(source.indexOf('function lockForUpdate('),source.indexOf("window.addEventListener('keydown'")),context);
(async()=>{
 await get('check-updates').onclick();
 assert.deepStrictEqual(calls,['/api/updates/check']);
 assert.strictEqual(get('install-update').hidden,false);
 assert.strictEqual(get('update-notes').textContent,'New release');
 await get('install-update').onclick();
 assert.deepStrictEqual(calls,['/api/updates/check']);
 dirty=false;await get('install-update').onclick();
 assert.deepStrictEqual(calls,['/api/updates/check','/api/updates/download','/api/updates/install']);
 assert(panes.every(pane=>pane.inert));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
