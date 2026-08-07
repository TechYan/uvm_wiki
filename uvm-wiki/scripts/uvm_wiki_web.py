#!/usr/bin/env python3
"""Standalone HTML application and localhost source server for UVM Wiki."""

from __future__ import annotations

import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from uvm_wiki_core import SOURCE_EXTS, iter_sources, read_text


HTML_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UVM Wiki</title>
<style>
*{box-sizing:border-box}html,body{height:100%}body{margin:0;overflow:hidden;background:#f8fafc;color:#182235;font:13px/1.45 "Segoe UI",Arial,sans-serif;letter-spacing:0}
button,input,select{font:inherit;color:inherit}button{cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid #2563eb;outline-offset:1px}header{height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;background:#fff;border-bottom:1px solid #d9e0ea}
h1{font-size:18px;margin:0;white-space:nowrap}.badges{display:flex;gap:7px;flex-wrap:wrap}.badge{padding:3px 7px;border:1px solid #d9e0ea;border-radius:5px;background:#f8fafc;color:#64748b;font-size:12px}
nav{height:43px;display:flex;align-items:end;gap:2px;padding:0 14px;background:#fff;border-bottom:1px solid #d9e0ea;overflow-x:auto}.tab{width:auto;flex:0 0 auto;white-space:nowrap;border:0;border-bottom:2px solid transparent;background:transparent;padding:11px 14px 9px;color:#64748b}.tab.active{color:#1d4ed8;border-bottom-color:#2563eb;font-weight:650}
.layout{display:grid;grid-template-columns:270px minmax(0,1fr) 350px;height:calc(100vh - 97px)}aside{min-width:0;background:#fff;overflow:auto}.left{border-right:1px solid #d9e0ea}.right{border-left:1px solid #d9e0ea}.section{padding:12px;border-bottom:1px solid #edf1f6}.section-title{font-size:12px;color:#64748b;margin:0 0 7px}.field{width:100%;padding:8px 9px;border:1px solid #cfd8e6;border-radius:5px;background:#fff}.hint,.muted{color:#64748b;font-size:12px}.stats{display:grid;grid-template-columns:1fr 1fr;gap:7px}.stat{padding:7px;border:1px solid #e2e8f0;border-radius:5px}.stat strong{display:block;font-size:16px}.roles{display:flex;gap:5px;flex-wrap:wrap}.role-chip{width:auto;padding:4px 7px;border:1px solid #d9e0ea;border-radius:5px;background:#fff}.role-chip.active{border-color:#2563eb;background:#eff6ff;color:#1d4ed8}
main{min-width:0;min-height:0;overflow:auto}.view{display:none;min-height:100%}.view.active{display:block}.toolbar{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:8px;padding:9px 12px;background:rgba(255,255,255,.96);border-bottom:1px solid #d9e0ea}.toolbar button,.toolbar select{width:auto;padding:6px 9px;border:1px solid #cfd8e6;border-radius:5px;background:#fff}.toolbar button.active{border-color:#2563eb;background:#eff6ff;color:#1d4ed8}
.architecture{padding:16px;max-width:1200px}.arch-summary{margin-bottom:12px;color:#64748b}.tree-root{display:grid;gap:7px}.tree-branch{position:relative;margin-left:22px;padding-left:18px;border-left:1px solid #cbd5e1}.tree-branch>.tree-node:before{content:"";position:absolute;width:18px;border-top:1px solid #cbd5e1;left:-18px;top:18px}.tree-node{position:relative;margin:5px 0}.arch-row{display:grid;grid-template-columns:22px 10px minmax(120px,1fr) auto;align-items:center;gap:7px;min-height:36px;padding:5px 8px;border:1px solid #d9e0ea;border-radius:6px;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,.04)}.arch-row:hover{border-color:#93c5fd;background:#f8fbff}.arch-row.selected{border-color:#2563eb;background:#eff6ff}.toggle{width:22px;height:22px;border:0;background:transparent;color:#475569;padding:0}.node-dot{width:9px;height:9px;border-radius:50%}.node-name{font:600 12px/1.25 Consolas,"Courier New",monospace;word-break:break-word}.node-meta{color:#64748b;font-size:11px}.count{color:#64748b;border:1px solid #e2e8f0;border-radius:4px;padding:1px 5px}.empty{padding:30px;color:#64748b}
#wikiView{position:relative;overflow:hidden}#graph{display:block;width:100%;height:calc(100vh - 184px);background:#fff}.graph-hud{position:absolute;left:12px;bottom:12px;display:flex;gap:6px}.graph-hud span{background:rgba(255,255,255,.9);border:1px solid #d9e0ea;border-radius:5px;padding:4px 7px;color:#64748b}
.tlm-wrap{padding:16px}.connect-group{border:1px solid #d9e0ea;border-radius:6px;background:#fff;margin-bottom:12px}.connect-head{padding:8px 10px;border-bottom:1px solid #edf1f6;font-weight:650}.connect-row{display:grid;grid-template-columns:minmax(0,1fr) 34px minmax(0,1fr);align-items:center;gap:8px;padding:9px 10px;border-bottom:1px solid #edf1f6;cursor:pointer}.connect-row:last-child{border-bottom:0}.connect-row:hover,.connect-row.active{background:#eff6ff}.endpoint{font:12px Consolas,"Courier New",monospace;word-break:break-word}.arrow{text-align:center;color:#0f766e;font-weight:700}.port-table{width:100%;border-collapse:collapse;background:#fff}.port-table th,.port-table td{text-align:left;padding:7px 8px;border-bottom:1px solid #edf1f6}.port-table th{position:sticky;top:44px;background:#f8fafc;color:#64748b;font-weight:600}
.code-layout{display:grid;grid-template-columns:300px minmax(0,1fr);height:calc(100vh - 140px)}.code-nav{overflow:auto;border-right:1px solid #d9e0ea;background:#fff}.code-results{display:grid}.code-result{border:0;border-bottom:1px solid #edf1f6;background:#fff;text-align:left;padding:7px 9px}.code-result:hover,.code-result.active{background:#eff6ff}.code-result strong{display:block;font:12px Consolas,"Courier New",monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.code-result span{color:#64748b;font-size:11px}.code-stage{min-width:0;display:grid;grid-template-rows:auto 1fr;background:#0f172a;color:#dbeafe}.code-head{padding:8px 12px;border-bottom:1px solid #334155;color:#93c5fd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.code-box{overflow:auto;padding:8px 0;font:12px/1.5 Consolas,"Courier New",monospace}.code-line{display:grid;grid-template-columns:56px minmax(max-content,1fr);gap:10px;min-height:18px;padding:0 12px;white-space:pre}.code-line.hit{background:rgba(37,99,235,.3)}.ln{color:#64748b;text-align:right;user-select:none}.kw{color:#93c5fd;font-weight:650}.macro{color:#fde047}.str{color:#86efac}.com{color:#94a3b8;font-style:italic}.num{color:#fca5a5}
.detail-name{font:700 15px Consolas,"Courier New",monospace;word-break:break-word}.kv{display:grid;grid-template-columns:75px 1fr;gap:5px 7px;margin-top:9px}.kv div:nth-child(odd){color:#64748b}.relation{padding:7px;border-left:3px solid transparent;border-bottom:1px solid #edf1f6;cursor:pointer;font:11px/1.4 Consolas,"Courier New",monospace;word-break:break-word}.relation:hover,.relation.active{background:#eff6ff;border-left-color:#2563eb}.node-list{display:grid;max-height:260px;overflow:auto;border:1px solid #e2e8f0;border-radius:5px}.node-list button{border:0;border-bottom:1px solid #edf1f6;background:#fff;text-align:left;padding:6px 7px;font:11px Consolas,"Courier New",monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.node-list button:last-child{border-bottom:0}.node-list button:hover,.node-list button.active{background:#eff6ff;color:#1d4ed8}.snippet{max-height:360px;overflow:auto;background:#0f172a;color:#dbeafe;padding:7px 0;margin-top:8px;border-radius:5px;font:11px/1.45 Consolas,"Courier New",monospace}
@media(max-width:1050px){.layout{grid-template-columns:230px minmax(0,1fr)}.right{display:none}}@media(max-width:720px){header{height:48px;padding:0 10px}h1{font-size:16px}.badges{display:none}nav{height:42px;align-items:stretch;padding:0 3px}.tab{padding:10px 9px 8px;font-size:12px}.layout{height:calc(100vh - 90px);grid-template-columns:1fr}.left{display:none}.toolbar{overflow-x:auto}.toolbar>*{flex:0 0 auto}#graph{height:calc(100vh - 134px)}.architecture,.tlm-wrap{padding:10px}.arch-row{grid-template-columns:22px 10px minmax(90px,1fr) auto}#codeView>.toolbar{display:grid;grid-template-columns:minmax(0,1fr) auto;overflow:visible}#codeView>.toolbar .field{max-width:none!important;min-width:0}#codeMode{display:none}.code-layout{height:calc(100vh - 134px);grid-template-columns:1fr;grid-template-rows:minmax(120px,180px) minmax(0,1fr);overflow:hidden}.code-nav{max-height:none;border-right:0;border-bottom:1px solid #d9e0ea}.code-stage{min-height:0}}
</style>
</head>
<body>
<header><h1>UVM Wiki</h1><div class="badges" id="badges"></div></header>
<nav><button class="tab active" data-view="architecture">Architecture</button><button class="tab" data-view="wiki">Wiki Graph</button><button class="tab" data-view="tlm">TLM Connections</button><button class="tab" data-view="code">Code Explorer</button></nav>
<div class="layout">
<aside class="left">
  <div class="section"><p class="section-title">Search current view</p><input id="globalSearch" class="field" placeholder="class / instance / port"></div>
  <div class="section"><p class="section-title">Project</p><div class="stats" id="stats"></div><p class="hint" id="parserInfo"></p></div>
  <div class="section"><p class="section-title">Class roles</p><div class="roles" id="roles"></div></div>
  <div class="section"><p class="section-title">Source</p><div class="hint" id="sourceRoot"></div></div>
</aside>
<main>
  <section class="view active" id="architectureView"><div class="toolbar"><button class="active" data-arch="topology">Component Topology</button><button data-arch="inheritance">Class Inheritance</button><button id="collapseArch">Collapse</button></div><div class="architecture" id="architecture"></div></section>
  <section class="view" id="wikiView"><div class="toolbar"><button class="active" data-graph-mode="extends">Inheritance</button><button data-graph-mode="topology">Topology</button><button data-graph-mode="all">All relations</button><button id="resetGraph">Reset view</button></div><canvas id="graph"></canvas><div class="graph-hud" id="graphHud"></div></section>
  <section class="view" id="tlmView"><div class="toolbar"><select id="tlmKind"><option value="">All connections</option><option value="tlm_connect">TLM</option><option value="seq_item_connect">Seq item</option></select></div><div class="tlm-wrap" id="tlm"></div></section>
  <section class="view" id="codeView"><div class="toolbar"><input id="codeSearch" class="field" style="max-width:520px" placeholder="Search symbols or full source"><button id="runCodeSearch">Search</button><span class="hint" id="codeMode"></span></div><div class="code-layout"><div class="code-nav"><div class="code-results" id="codeResults"></div></div><div class="code-stage"><div class="code-head" id="codeHead">Select a symbol or source result</div><div class="code-box" id="codeBox"></div></div></div></section>
</main>
<aside class="right"><div class="section"><p class="section-title">Selection</p><div id="detail" class="muted">Select a node, connection, or relation.</div></div><div class="section" id="nodePanel" style="display:none"><p class="section-title">Visible nodes</p><div class="node-list" id="nodeList"></div></div><div class="section"><p class="section-title">Related</p><div id="relations"></div></div><div class="section"><p class="section-title">Source preview</p><div id="preview" class="muted">No source selected.</div></div></aside>
</div>
<script>
const DATA=__DATA__;
const $=id=>document.getElementById(id),esc=value=>String(value??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const state={view:"architecture",archMode:"topology",graphMode:"extends",query:"",role:"",expanded:new Set(),selected:null,activeRelation:null,server:location.protocol==="http:"||location.protocol==="https:",tlmKind:"",graph:{nodes:[],edges:[],scale:window.innerWidth<720?.55:1,panX:0,panY:0,drag:null,panDrag:null,hover:null,running:false}};
const symbolByName=new Map();(DATA.symbols||[]).forEach(item=>{if(!symbolByName.has(item.name))symbolByName.set(item.name,item)});
const relationsByName=new Map();function addRel(name,rel){if(!name)return;const list=relationsByName.get(name)||[];list.push(rel);relationsByName.set(name,list)}
(DATA.relations||[]).forEach(rel=>{addRel(String(rel.source||"").split(".")[0],rel);addRel(String(rel.target||"").split(".")[0],rel)});
function color(role){return DATA.role_colors?.[role]||"#64748b"}function text(value){return JSON.stringify(value).toLowerCase()}
function init(){renderHeader();bind();renderRoles();renderArchitecture();renderWiki();renderTlm();renderCodeIndex();}
function renderHeader(){const s=DATA.stats||{};$("badges").innerHTML=[["files",s.files],["classes",s.classes],["relations",s.relations],["parser",DATA.metadata?.parser_effective]].map(([k,v])=>`<span class="badge">${esc(k)} ${esc(v)}</span>`).join("");$("stats").innerHTML=[["Files",s.files],["Classes",s.classes],["Ports",s.ports],["Connects",s.connections]].map(([k,v])=>`<div class="stat"><strong>${esc(v||0)}</strong>${k}</div>`).join("");$("parserInfo").textContent=`requested ${DATA.metadata?.parser_requested}; cache reused ${DATA.metadata?.cache?.reused_files||0}, reparsed ${DATA.metadata?.cache?.reparsed_files||0}`;$("sourceRoot").textContent=DATA.metadata?.source_root||"";$("codeMode").textContent=state.server?"full source mode":"embedded snippet mode"}
function bind(){document.querySelectorAll(".tab").forEach(button=>button.onclick=()=>switchView(button.dataset.view));document.querySelectorAll("[data-arch]").forEach(button=>button.onclick=()=>{state.archMode=button.dataset.arch;document.querySelectorAll("[data-arch]").forEach(x=>x.classList.toggle("active",x===button));state.expanded.clear();renderArchitecture()});document.querySelectorAll("[data-graph-mode]").forEach(button=>button.onclick=()=>{state.graphMode=button.dataset.graphMode;document.querySelectorAll("[data-graph-mode]").forEach(x=>x.classList.toggle("active",x===button));resetGraphView();renderWiki()});$("resetGraph").onclick=()=>{resetGraphView();renderWiki()};$("collapseArch").onclick=()=>{state.expanded.clear();renderArchitecture()};$("globalSearch").oninput=event=>{state.query=event.target.value.trim().toLowerCase();renderCurrent()};$("tlmKind").onchange=event=>{state.tlmKind=event.target.value;renderTlm()};$("runCodeSearch").onclick=runCodeSearch;$("codeSearch").onkeydown=event=>{if(event.key==="Enter")runCodeSearch()};window.addEventListener("resize",()=>{if(state.view==="wiki")resizeGraph()})}
function switchView(view){state.view=view;document.querySelectorAll(".tab").forEach(x=>x.classList.toggle("active",x.dataset.view===view));document.querySelectorAll(".view").forEach(x=>x.classList.toggle("active",x.id===`${view}View`));$("nodePanel").style.display=view==="wiki"?"block":"none";renderCurrent();if(view==="wiki")setTimeout(resizeGraph,0)}
function renderCurrent(){if(state.view==="architecture")renderArchitecture();else if(state.view==="wiki")renderWiki();else if(state.view==="tlm")renderTlm();else renderCodeIndex()}
function renderRoles(){const roles=[...new Set((DATA.symbols||[]).filter(x=>x.kind==="class").map(x=>x.role).filter(Boolean))].sort();$("roles").innerHTML=`<button class="role-chip active" data-role="">All</button>`+roles.map(role=>`<button class="role-chip" data-role="${esc(role)}">${esc(role)}</button>`).join("");$("roles").onclick=event=>{const button=event.target.closest("[data-role]");if(!button)return;state.role=button.dataset.role;document.querySelectorAll("[data-role]").forEach(x=>x.classList.toggle("active",x===button));renderCurrent()}}
function hierarchy(){return DATA.hierarchies?.[state.archMode]||{roots:[],children:{}}}function nodeMatches(name){const symbol=symbolByName.get(name)||{};return(!state.query||text({name,symbol,relations:relationsByName.get(name)||[]}).includes(state.query))&&(!state.role||symbol.role===state.role)}
function descendantHit(name,tree,seen=new Set()){if(seen.has(name))return false;seen.add(name);if(nodeMatches(name))return true;return(tree.children[name]||[]).some(child=>descendantHit(child.id,tree,seen))}
function archNode(name,tree,depth=0,path=new Set(),edge=null){const symbol=symbolByName.get(name)||{name,role:"external"},children=tree.children[name]||[],hasChildren=children.length>0,open=state.expanded.has(name),selected=state.selected?.name===name,instance=state.archMode==="topology"?edge?.instance:null,label=instance||name;if(state.query&&!descendantHit(name,tree))return"";const nextPath=new Set(path);nextPath.add(name);const childHtml=open?children.filter(child=>!nextPath.has(child.id)).map(child=>archNode(child.id,tree,depth+1,nextPath,child)).join(""):"";const typeMeta=instance?`${name} | `:"";return `<div class="tree-node"><div class="arch-row${selected?" selected":""}" data-node="${esc(name)}"><button class="toggle" data-toggle="${esc(name)}">${hasChildren?(open?"-":"+"):""}</button><span class="node-dot" style="background:${color(symbol.role)}"></span><div><div class="node-name">${esc(label)}</div><div class="node-meta">${esc(typeMeta)}${esc(symbol.role||symbol.kind||"external")}${symbol.base?` extends ${esc(symbol.base)}`:""}</div></div>${hasChildren?`<span class="count">${children.length}</span>`:""}</div>${childHtml?`<div class="tree-branch">${childHtml}</div>`:""}</div>`}
function renderArchitecture(){const tree=hierarchy(),roots=(tree.roots||[]).filter(root=>!state.query||descendantHit(root,tree));$("architecture").innerHTML=`<div class="arch-summary">${state.archMode==="topology"?"Inferred from create and member relationships.":"Derived from class extends relationships."} Click + to expand one level.</div><div class="tree-root">${roots.map(root=>archNode(root,tree)).join("")||'<div class="empty">No matching hierarchy roots.</div>'}</div>`;$("architecture").onclick=event=>{const toggle=event.target.closest("[data-toggle]");if(toggle){event.stopPropagation();const name=toggle.dataset.toggle;state.expanded.has(name)?state.expanded.delete(name):state.expanded.add(name);renderArchitecture();return}const row=event.target.closest("[data-node]");if(row)selectName(row.dataset.node)}}
function selectName(name){const symbol=symbolByName.get(name)||{name,role:"external"};state.selected=symbol;renderDetail(symbol);if(state.view==="architecture")renderArchitecture();if(state.view==="wiki"){renderNodeList(state.graph.nodes);drawGraph()}}
function clearSelection(){state.selected=null;state.activeRelation=null;$("detail").innerHTML='<div class="muted">Select a node, connection, or relation.</div>';$("relations").innerHTML="";$("preview").innerHTML='<div class="muted">No source selected.</div>';renderNodeList(state.graph.nodes);drawGraph()}
function relationKey(rel){return[rel.kind,rel.source,rel.target,rel.file,rel.line].join("|")}function renderDetail(item){const rels=(relationsByName.get(item.name)||[]).slice(0,120);$("detail").innerHTML=`<div class="detail-name">${esc(item.name)}</div><div class="kv"><div>role</div><div>${esc(item.role||item.kind||"")}</div><div>base</div><div>${esc(item.base||"")}</div><div>file</div><div>${esc(item.file||"")}${item.line?`:${item.line}`:""}</div><div>related</div><div>${rels.length}</div></div>`;renderRelations(rels);showLocation(item.file,item.line,item.name)}
function renderRelations(rels){$("relations").innerHTML=rels.map(rel=>`<div class="relation${state.activeRelation===relationKey(rel)?" active":""}" data-rel="${esc(relationKey(rel))}"><b>${esc(rel.kind)}</b> ${esc(rel.source)} -> ${esc(rel.target)}<div class="muted">${esc(rel.file||"")}${rel.line?`:${rel.line}`:""}</div></div>`).join("")||'<div class="muted">No related relationships.</div>';$("relations").onclick=event=>{const row=event.target.closest("[data-rel]");if(!row)return;const rel=rels.find(x=>relationKey(x)===row.dataset.rel);if(rel){state.activeRelation=relationKey(rel);showLocation(rel.file,rel.line,`${rel.kind}: ${rel.source} -> ${rel.target}`);renderRelations(rels)}}}
function syntax(textValue){const token=/(`\w+)|\b(\d+'[sS]?[bBoOdDhH][0-9a-fA-F_xzXZ?]+|\d+\.\d+|\d+)\b|\b(class|endclass|extends|virtual|function|endfunction|task|endtask|module|endmodule|interface|endinterface|package|endpackage|import|typedef|enum|struct|rand|constraint|new|super|this|begin|end|if|else|case|endcase|foreach|for|while|return|void|bit|logic|wire|reg|int|integer|string|time|localparam|parameter|static|automatic|protected|local|extern)\b/g;let output="",last=0;String(textValue).replace(token,(match,macro,num,kw,offset)=>{output+=esc(String(textValue).slice(last,offset));output+=`<span class="${macro?"macro":num?"num":"kw"}">${esc(match)}</span>`;last=offset+match.length;return match});return output+esc(String(textValue).slice(last))}
function highlightLine(value){const line=String(value),comment=line.indexOf("//");if(comment>=0)return syntax(line.slice(0,comment))+`<span class="com">${esc(line.slice(comment))}</span>`;return syntax(line).replace(/(&quot;.*?&quot;)/g,'<span class="str">$1</span>')}
function codeRows(lines,hit){return(lines||[]).map(row=>`<div class="code-line${Number(row.line)===Number(hit)?" hit":""}"><span class="ln">${row.line}</span><span>${highlightLine(row.text)}</span></div>`).join("")}
const sourceCache=new Map();async function sourceBody(file){if(sourceCache.has(file))return sourceCache.get(file);const response=await fetch(`/api/source?path=${encodeURIComponent(file)}`);if(!response.ok)throw new Error(await response.text());const body=await response.json();sourceCache.set(file,body);return body}
async function showLocation(file,line=1,title=""){if(!file)return;const key=`${file}:${line}`,snippet=DATA.snippets?.[key];if(snippet)$("preview").innerHTML=`<div class="snippet">${codeRows(snippet.lines,line)}</div>`;else $("preview").innerHTML=`<div class="muted">Loading ${esc(file)}:${esc(line)}</div>`;if(state.server){try{const body=await sourceBody(file),start=Math.max(0,Number(line)-16),previewLines=body.lines.slice(start,start+31);if(!snippet)$("preview").innerHTML=`<div class="snippet">${codeRows(previewLines,line)}</div>`;$("codeHead").textContent=title?`${title} - ${file}:${line}`:`${file}:${line}`;$("codeBox").innerHTML=codeRows(body.lines,line);setTimeout(()=>$("codeBox").querySelector(".hit")?.scrollIntoView({block:"center"}),0);return}catch(error){$("preview").innerHTML=`<div class="muted">${esc(error.message)}</div>`}}if(state.view==="code")await loadSource(file,line,title||key)}
async function loadSource(file,line=1,title=""){$("codeHead").textContent=title?`${title} - ${file}:${line}`:`${file}:${line}`;if(state.server){try{const body=await sourceBody(file);$("codeBox").innerHTML=codeRows(body.lines,line);setTimeout(()=>$("codeBox").querySelector(".hit")?.scrollIntoView({block:"center"}),0);return}catch(error){$("codeBox").innerHTML=`<div class="empty">${esc(error.message)}</div>`;return}}const snippet=DATA.snippets?.[`${file}:${line}`];$("codeBox").innerHTML=snippet?codeRows(snippet.lines,line):'<div class="empty">Full source requires serve mode.</div>'}
function graphData(){const relationKinds=state.graphMode==="extends"?["extends"]:state.graphMode==="topology"?["creates","has_member"]:["extends","creates","has_member"],degree=new Map(),symbolNames=new Set((DATA.symbols||[]).filter(x=>x.kind==="class").map(x=>x.name)),edgeKeys=new Set(),edges=[];(DATA.relations||[]).filter(rel=>relationKinds.includes(rel.kind)).forEach(rel=>{const source=String(rel.source||"").split(".")[0],target=String(rel.target||""),group=rel.kind==="extends"?"extends":"topology",key=`${group}|${source}|${target}`;if(symbolNames.has(source)&&symbolNames.has(target)&&!edgeKeys.has(key)){edgeKeys.add(key);edges.push({...rel,source,target});degree.set(source,(degree.get(source)||0)+1);degree.set(target,(degree.get(target)||0)+1)}});let nodes=[...symbolNames].map(name=>({...symbolByName.get(name),degree:degree.get(name)||0})).filter(node=>node.degree>0&&nodeMatches(node.name)).sort((a,b)=>b.degree-a.degree||a.name.localeCompare(b.name)).slice(0,state.query?300:150);const ids=new Set(nodes.map(x=>x.name));return{nodes,edges:edges.filter(edge=>ids.has(edge.source)&&ids.has(edge.target))}}
function renderWiki(){const graph=graphData(),old=new Map(state.graph.nodes.map(x=>[x.name,x]));state.graph.nodes=graph.nodes.map((node,index)=>{const prior=old.get(node.name),angle=index*2.399963,radius=50+12*Math.sqrt(index);return prior?{...node,x:prior.x,y:prior.y,vx:prior.vx,vy:prior.vy}:{...node,x:Math.cos(angle)*radius,y:Math.sin(angle)*radius,vx:0,vy:0}});state.graph.edges=graph.edges;state.graph.running=true;renderNodeList(state.graph.nodes);resizeGraph();requestAnimationFrame(graphTick)}
function renderNodeList(nodes){if(state.view!=="wiki")return;$("nodeList").innerHTML=(nodes||[]).map(node=>`<button class="${state.selected?.name===node.name?"active":""}" data-graph-node="${esc(node.name)}" title="${esc(node.name)}">${esc(node.name)}</button>`).join("")||'<div class="empty">No nodes.</div>';$("nodeList").querySelectorAll("[data-graph-node]").forEach(button=>button.onclick=()=>{const node=state.graph.nodes.find(item=>item.name===button.dataset.graphNode);if(!node)return;state.graph.panX=-node.x*state.graph.scale;state.graph.panY=-node.y*state.graph.scale;selectName(node.name)})}
function resetGraphView(){state.graph.scale=window.innerWidth<720?.55:1;state.graph.panX=0;state.graph.panY=0;state.graph.hover=null}
function resizeGraph(){const canvas=$("graph"),rect=canvas.getBoundingClientRect(),ratio=devicePixelRatio||1;canvas.width=Math.max(1,rect.width*ratio);canvas.height=Math.max(1,rect.height*ratio);canvas.getContext("2d").setTransform(ratio,0,0,ratio,0,0);bindGraph();drawGraph()}
let graphBound=false;function bindGraph(){if(graphBound)return;graphBound=true;const canvas=$("graph");canvas.onmousemove=event=>{if(state.graph.drag){const p=screenWorld(event.offsetX,event.offsetY);state.graph.drag.x=p.x;state.graph.drag.y=p.y;drawGraph();return}if(state.graph.panDrag){const drag=state.graph.panDrag,dx=event.offsetX-drag.x,dy=event.offsetY-drag.y;if(Math.abs(dx)+Math.abs(dy)>3)drag.moved=true;state.graph.panX=drag.panX+dx;state.graph.panY=drag.panY+dy;drawGraph();return}const hit=pickGraph(event.offsetX,event.offsetY);state.graph.hover=hit?.name||null;canvas.style.cursor=hit?"pointer":"grab";drawGraph()};canvas.onmousedown=event=>{const hit=pickGraph(event.offsetX,event.offsetY);if(hit){state.graph.drag=hit;selectName(hit.name)}else state.graph.panDrag={x:event.offsetX,y:event.offsetY,panX:state.graph.panX,panY:state.graph.panY,moved:false}};canvas.onmouseup=()=>{if(state.graph.panDrag&&!state.graph.panDrag.moved)clearSelection();state.graph.drag=null;state.graph.panDrag=null};canvas.onmouseleave=()=>{state.graph.hover=null;canvas.style.cursor="default";drawGraph()};window.addEventListener("mouseup",()=>{state.graph.drag=null;state.graph.panDrag=null});canvas.onwheel=event=>{event.preventDefault();state.graph.scale=Math.max(.25,Math.min(3,state.graph.scale*(event.deltaY<0?1.1:.9)));drawGraph()}}
function screenWorld(x,y){const rect=$("graph").getBoundingClientRect();return{x:(x-rect.width/2-state.graph.panX)/state.graph.scale,y:(y-rect.height/2-state.graph.panY)/state.graph.scale}}function graphScreen(x,y){const rect=$("graph").getBoundingClientRect();return{x:rect.width/2+state.graph.panX+x*state.graph.scale,y:rect.height/2+state.graph.panY+y*state.graph.scale}}
function pickGraph(x,y){const point=screenWorld(x,y);let best=null,distance=Infinity;state.graph.nodes.forEach(node=>{const d=Math.hypot(node.x-point.x,node.y-point.y);if(d<distance&&d<14){best=node;distance=d}});return best}
function graphTick(){if(state.view!=="wiki"||!state.graph.running)return;const nodes=state.graph.nodes,byName=new Map(nodes.map(x=>[x.name,x]));state.graph.edges.forEach(edge=>{const a=byName.get(edge.source),b=byName.get(edge.target);if(!a||!b)return;const dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),force=(d-125)*.0025;a.vx+=dx/d*force;a.vy+=dy/d*force;b.vx-=dx/d*force;b.vy-=dy/d*force});for(let i=0;i<nodes.length;i++){for(let j=i+1;j<nodes.length;j++){const a=nodes[i],b=nodes[j],dx=b.x-a.x,dy=b.y-a.y,d2=Math.max(50,dx*dx+dy*dy),f=-36/d2;a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f}const n=nodes[i];n.vx+=-n.x*.0005;n.vy+=-n.y*.0005;n.vx*=.91;n.vy*=.91;n.x+=n.vx;n.y+=n.vy}drawGraph();if(nodes.some(n=>Math.abs(n.vx)+Math.abs(n.vy)>.01))requestAnimationFrame(graphTick);else state.graph.running=false}
function drawGraph(){const canvas=$("graph"),ctx=canvas.getContext("2d"),rect=canvas.getBoundingClientRect(),nodes=state.graph.nodes,ids=new Set(nodes.map(x=>x.name)),selectedName=state.selected?.name,active=(selectedName&&ids.has(selectedName)?selectedName:null)||state.graph.hover,neighbors=new Set();state.graph.edges.forEach(edge=>{if(edge.source===active)neighbors.add(edge.target);if(edge.target===active)neighbors.add(edge.source)});ctx.clearRect(0,0,rect.width,rect.height);ctx.fillStyle="#fff";ctx.fillRect(0,0,rect.width,rect.height);const byName=new Map(nodes.map(x=>[x.name,x]));state.graph.edges.forEach(edge=>{if(!ids.has(edge.source)||!ids.has(edge.target))return;const a=graphScreen(byName.get(edge.source).x,byName.get(edge.source).y),b=graphScreen(byName.get(edge.target).x,byName.get(edge.target).y),focus=!active||edge.source===active||edge.target===active;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.strokeStyle=focus?"rgba(71,85,105,.5)":"rgba(148,163,184,.15)";ctx.lineWidth=focus&&active?2:1;ctx.stroke()});nodes.forEach(node=>{const p=graphScreen(node.x,node.y),selected=selectedName===node.name,hover=state.graph.hover===node.name,near=neighbors.has(node.name),dim=active&&!selected&&!hover&&!near,base=Math.max(5,Math.min(13,5+Math.sqrt(node.degree||1))),r=base*state.graph.scale*(hover?1.2:1);ctx.beginPath();ctx.arc(p.x,p.y,r,0,Math.PI*2);ctx.fillStyle=dim?"#cbd5e1":color(node.role);ctx.fill();ctx.lineWidth=selected?3:hover?2:1;ctx.strokeStyle=selected?"#111827":"#fff";ctx.stroke();if(selected||hover||near||state.query){ctx.font="11px Segoe UI";ctx.fillStyle="#182235";ctx.fillText(node.name,p.x+r+4,p.y+4)}});$("graphHud").innerHTML=`<span>${nodes.length} nodes</span><span>${state.graph.edges.length} edges</span><span>${esc(state.graphMode)}</span>`}
function renderTlm(){const query=state.query,connections=(DATA.tlm?.connections||[]).filter(item=>(!state.tlmKind||item.kind===state.tlmKind)&&(!query||text(item).includes(query))),groups=new Map();connections.forEach(item=>{const key=item.context||"global",list=groups.get(key)||[];list.push(item);groups.set(key,list)});let html=[...groups].map(([context,items])=>`<div class="connect-group"><div class="connect-head">${esc(context)} <span class="muted">${items.length} connection(s)</span></div>${items.map(item=>`<div class="connect-row" data-connect="${esc(relationKey({...item,source:item.lhs,target:item.rhs}))}"><div class="endpoint">${esc(item.lhs)}</div><div class="arrow">-></div><div class="endpoint">${esc(item.rhs)}<div class="muted">${esc(item.kind)}</div></div></div>`).join("")}</div>`).join("");const ports=(DATA.tlm?.ports||[]).filter(item=>!query||text(item).includes(query));html+=`<h3>Declared ports</h3><table class="port-table"><thead><tr><th>Owner</th><th>Port</th><th>Type</th><th>Transaction</th></tr></thead><tbody>${ports.map(port=>`<tr data-port="${esc(port.owner)}"><td>${esc(port.owner)}</td><td>${esc(port.name)}</td><td>${esc(port.port_type)}</td><td>${esc((port.transaction_types||[]).join(", "))}</td></tr>`).join("")}</tbody></table>`;$("tlm").innerHTML=html||'<div class="empty">No matching connections.</div>';$("tlm").onclick=event=>{const row=event.target.closest("[data-connect]");if(row){const item=connections.find(x=>relationKey({...x,source:x.lhs,target:x.rhs})===row.dataset.connect);if(item){showLocation(item.file,item.line,`${item.kind}: ${item.lhs} -> ${item.rhs}`);renderRelations([{...item,source:item.lhs,target:item.rhs}])}}const port=event.target.closest("[data-port]");if(port)selectName(port.dataset.port)}}
function localCodeItems(query=""){const symbols=(DATA.symbols||[]).filter(item=>(!state.role||item.role===state.role)&&(!query||text(item).includes(query))),files=state.role?[]:(DATA.files||[]).filter(item=>!query||item.path.toLowerCase().includes(query));return[...symbols.slice(0,220).map(item=>({type:item.kind,title:item.name,file:item.file,line:item.line})),...files.slice(0,120).map(item=>({type:"file",title:item.path,file:item.path,line:1}))]}
function renderCodeIndex(items=localCodeItems(state.query)){$("codeResults").innerHTML=items.map((item,index)=>`<button class="code-result" data-code-index="${index}"><strong>${esc(item.title)}</strong><span>${esc(item.type)} | ${esc(item.file||"")}${item.line?`:${item.line}`:""}</span></button>`).join("")||'<div class="empty">No matches.</div>';$("codeResults").querySelectorAll("[data-code-index]").forEach(button=>button.onclick=()=>{document.querySelectorAll(".code-result").forEach(x=>x.classList.toggle("active",x===button));const item=items[Number(button.dataset.codeIndex)];loadSource(item.file,item.line||1,item.title)})}
async function runCodeSearch(){const query=$("codeSearch").value.trim();if(!query){renderCodeIndex();return}if(state.server){$("codeResults").innerHTML='<div class="empty">Searching...</div>';try{const response=await fetch(`/api/search?q=${encodeURIComponent(query)}`),items=await response.json();renderCodeIndex(items)}catch(error){$("codeResults").innerHTML=`<div class="empty">${esc(error.message)}</div>`}}else renderCodeIndex(localCodeItems(query.toLowerCase()))}
init();
</script>
</body>
</html>'''


def render_html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</script>", "<\\/script>")
    return HTML_TEMPLATE.replace("__DATA__", payload)


def write_html(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(data), encoding="utf-8", newline="\n")


def _safe_source_path(root: Path, requested: str) -> Path:
    relative = Path(unquote(requested.replace("\\", "/")))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("invalid source path")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("source path is outside the configured root") from exc
    if path.suffix.lower() not in SOURCE_EXTS or not path.is_file():
        raise FileNotFoundError(requested)
    return path


def source_payload(root: Path, requested: str) -> dict[str, Any]:
    path = _safe_source_path(root, requested)
    lines = read_text(path).splitlines()
    return {"path": path.relative_to(root).as_posix(), "line_count": len(lines), "lines": [{"line": number, "text": value} for number, value in enumerate(lines, 1)]}


def search_source(root: Path, query: str, limit: int = 200) -> list[dict[str, Any]]:
    query_lower = query.lower()
    if not query_lower:
        return []
    results: list[dict[str, Any]] = []
    pattern = re.compile(re.escape(query), re.I)
    for path in iter_sources(root):
        relative = path.relative_to(root).as_posix()
        if query_lower in relative.lower():
            results.append({"type": "file", "title": relative, "file": relative, "line": 1})
        try:
            lines = read_text(path).splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, 1):
            if pattern.search(line):
                results.append({"type": "source", "title": line.strip()[:160] or query, "file": relative, "line": line_number})
                if len(results) >= limit:
                    return results
    return results


class WikiRequestHandler(BaseHTTPRequestHandler):
    html_text = ""
    source_root = Path(".")

    def _send(self, body: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: Any, status: int = HTTPStatus.OK) -> None:
        self._send(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path in {"/", "/index.html"}:
                self._send(self.html_text.encode("utf-8"), "text/html; charset=utf-8")
            elif parsed.path == "/api/status":
                self._json({"ok": True, "source_root": str(self.source_root)})
            elif parsed.path == "/api/source":
                self._json(source_payload(self.source_root, query.get("path", [""])[0]))
            elif parsed.path == "/api/search":
                self._json(search_source(self.source_root, query.get("q", [""])[0]))
            else:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except FileNotFoundError as exc:
            self._json({"error": f"source file not found: {exc}"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[uvm-wiki] {self.address_string()} {fmt % args}")


def serve_html(data: dict[str, Any], source_root: Path, host: str, port: int) -> None:
    handler = type("ConfiguredWikiHandler", (WikiRequestHandler,), {"html_text": render_html(data), "source_root": source_root.resolve()})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"UVM Wiki serving http://{host}:{port}")
    print(f"Source root: {source_root.resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping UVM Wiki server")
    finally:
        server.server_close()
