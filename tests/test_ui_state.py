"""Regression check for controls remaining disabled after async bulk Apply."""

import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_bulk_apply_reenables_undo_and_other_controls():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trc_plus/ui/app.js','utf8');
const controls=new Map();
const get=id=>{if(!controls.has(id))controls.set(id,{disabled:false,classList:{toggle(){}},close(){}});return controls.get(id);};
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
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_website_sync_stages_without_writing_and_preserves_match_warnings():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trc_plus/ui/app.js','utf8');
const controls=new Map();
const get=id=>{if(!controls.has(id))controls.set(id,{});return controls.get(id);};
const calls=[];
const initial={players:[{player_id:'game-1',name:'Custom Player'}],teams:[]};
const merged={players:[{player_id:'game-1',name:'Custom Player',attributes:{Speed:80}}],teams:[]};
let previews=0;
get('game-preview').onclick=async()=>{previews++;assert.strictEqual(context.gameBusy,false);};
const context=vm.createContext({$:get,gameBusy:false,livePending:0,liveTimers:new Map(),
 gameLoaded:true,gameStatus:{connected:true},roster:initial,gamePlan:null,workspaceNeedsSave:false,
 syncWarnings:[],dirtyRecords:new Set(),stopLiveLocally(){calls.push('stop-live');},
 updateLiveControls(){},updateGameStatus(){},setView(){},toast(){},
 api:async(path,body)=>{calls.push(path);
  if(path==='/api/trc/export')return {roster:{players:[{name:'Custom Player'},{name:'Missing Player'}]}};
  if(path==='/api/import'){assert.strictEqual(body.merge,true);return {roster:merged,warnings:['Missing Player: skipped.']};}
  if(path==='/api/game/live'){assert.strictEqual(body.enabled,false);return {};}
  throw Error('Unexpected request: '+path);
 }});
vm.runInContext(source.slice(source.indexOf('const showGamePreview='),source.indexOf("$('apply-game').onclick=")),context);
(async()=>{await get('trc-sync').onclick();
 assert.strictEqual(previews,1);assert.strictEqual(context.roster,merged);
 assert.strictEqual(context.syncWarnings[0],'Missing Player: skipped.');
 assert.strictEqual(context.gameBusy,false);assert.strictEqual(context.workspaceNeedsSave,true);
 assert.deepStrictEqual(calls,['/api/trc/export','/api/import','/api/game/live','stop-live']);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
@pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is needed for the frontend check')
def test_updates_require_saved_edits_and_install_only_after_user_click():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('src/trc_plus/ui/app.js','utf8');
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
