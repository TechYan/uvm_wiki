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


D3_PATH = Path(__file__).resolve().parents[1] / "assets" / "vendor" / "d3.v7.min.js"


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
.layout{display:grid;grid-template-columns:270px minmax(0,1fr) 350px;height:calc(100vh - 97px)}.layout.tlm-mode{grid-template-columns:minmax(0,1fr) 350px}.layout.tlm-mode>.left{display:none}aside{min-width:0;background:#fff;overflow:auto}.left{border-right:1px solid #d9e0ea}.right{border-left:1px solid #d9e0ea}.section{padding:12px;border-bottom:1px solid #edf1f6}.section-title{font-size:12px;color:#64748b;margin:0 0 7px}.field{width:100%;padding:8px 9px;border:1px solid #cfd8e6;border-radius:5px;background:#fff}.hint,.muted{color:#64748b;font-size:12px}.stats{display:grid;grid-template-columns:1fr 1fr;gap:7px}.stat{padding:7px;border:1px solid #e2e8f0;border-radius:5px}.stat strong{display:block;font-size:16px}.roles{display:flex;gap:5px;flex-wrap:wrap}.role-chip{width:auto;padding:4px 7px;border:1px solid #d9e0ea;border-radius:5px;background:#fff}.role-chip.active{border-color:#2563eb;background:#eff6ff;color:#1d4ed8}
main{min-width:0;min-height:0;overflow:auto}.view{display:none;min-height:100%}.view.active{display:block}.toolbar{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:8px;padding:9px 12px;background:rgba(255,255,255,.96);border-bottom:1px solid #d9e0ea}.toolbar button,.toolbar select{width:auto;padding:6px 9px;border:1px solid #cfd8e6;border-radius:5px;background:#fff}.toolbar button.active{border-color:#2563eb;background:#eff6ff;color:#1d4ed8}
#architectureView{height:100%;overflow:hidden}
.arch-toolbar{min-width:0}.arch-root{max-width:min(420px,35vw);min-width:190px}.arch-path{min-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#475569;font:12px Consolas,"Courier New",monospace}.arch-options{display:flex;align-items:center;gap:9px;white-space:nowrap}.arch-toggle{display:flex;align-items:center;gap:4px;color:#475569;font-size:12px}.arch-toggle input{margin:0;accent-color:#2563eb}.arch-status{margin-left:auto;white-space:nowrap;padding:3px 7px;border:1px solid #a7f3d0;border-radius:5px;background:#ecfdf5;color:#047857;font-size:11px}
.architecture{position:relative;isolation:isolate;height:calc(100vh - 141px);min-height:360px;overflow:hidden;background:#f3f6fa}
.arch-svg{position:absolute;inset:0;display:block;width:100%;height:100%;touch-action:none}
.arch-context-svg{z-index:0;opacity:0;filter:blur(0);transform:scale(1);transform-origin:center;pointer-events:none;transition:opacity 460ms cubic-bezier(.22,1,.36,1),filter 520ms cubic-bezier(.22,1,.36,1),transform 520ms cubic-bezier(.22,1,.36,1)}
.arch-focus-svg{z-index:2;background:transparent}.architecture.is-focused .arch-context-svg{opacity:.28;filter:blur(6px);transform:scale(.985)}.architecture.is-focused .arch-focus-svg{cursor:zoom-out}.architecture.focus-forward .arch-focus-svg{animation:arch-focus-in 520ms cubic-bezier(.22,1,.36,1)}.architecture.focus-back .arch-focus-svg{animation:arch-focus-back 420ms cubic-bezier(.22,1,.36,1)}
.arch-legend{position:absolute;z-index:4;left:12px;bottom:12px;display:flex;align-items:center;gap:12px;padding:6px 9px;border:1px solid rgba(148,163,184,.55);border-radius:6px;background:rgba(255,255,255,.9);box-shadow:0 6px 20px rgba(15,23,42,.08);color:#475569;font-size:11px;pointer-events:none;backdrop-filter:blur(8px)}.arch-legend span{display:flex;align-items:center;gap:5px}.arch-legend i{display:inline-block;width:10px;height:10px;background:#fff;border:2px solid #0f766e}.arch-legend .port{border-radius:50%}.arch-legend .export{transform:rotate(45deg);width:9px;height:9px}.arch-legend .implementation{border-radius:1px}.arch-legend .seq-line{width:18px;height:0;border:0;border-top:2px solid #b45309;background:transparent}.arch-legend .analysis-line{width:18px;height:0;border:0;border-top:2px solid #0f766e;background:transparent}
.arch-boundary{fill:#fff;stroke:#94a3b8;stroke-width:1.2;stroke-dasharray:7 5}.arch-boundary-title{fill:#475569;font:650 12px "Segoe UI",Arial,sans-serif}
.arch-wire-halo{fill:none;stroke:rgba(255,255,255,.94);stroke-width:6;opacity:.9;pointer-events:none;vector-effect:non-scaling-stroke}.arch-wire{fill:none;stroke:#0f766e;stroke-width:2.2;opacity:.94;pointer-events:none;vector-effect:non-scaling-stroke}.arch-wire.analysis,.arch-wire.tlm_connect{stroke:#0f766e}.arch-wire.seq_item_connect{stroke:#b45309}.arch-wire.virtual_interface{stroke:#64748b;stroke-dasharray:6 4}.arch-wire.boundary{stroke-width:2.5}.arch-wire.dim{opacity:.1}.arch-wire.selected{stroke:#1d4ed8;stroke-width:3.2;opacity:1}.arch-wire-hit{fill:none;stroke:transparent;stroke-width:14;cursor:pointer;pointer-events:stroke}.arch-wire-detail{opacity:0;pointer-events:none;transition:opacity 150ms ease}.arch-wire-detail.visible{opacity:1}.arch-port-label{fill:#334155;paint-order:stroke;stroke:#f8fafc;stroke-width:4px;stroke-linejoin:round;font:10px Consolas,"Courier New",monospace}.arch-port-mark{fill:#fff;stroke:#0f766e;stroke-width:2;vector-effect:non-scaling-stroke}.arch-port-mark.seq_item_connect{stroke:#b45309}.arch-port-mark.virtual_interface{stroke:#64748b}.arch-port-mark.direction-implementation{fill:#ecfeff}.arch-port-mark.direction-export{fill:#f0fdfa}
.arch-entity{cursor:pointer;outline:none;transition:opacity 180ms ease}.arch-entity.dim{opacity:.25}.arch-entity.context-peer{cursor:default}.arch-entity-surface{transition:transform 220ms cubic-bezier(.22,1,.36,1),filter 220ms cubic-bezier(.22,1,.36,1);transform-box:fill-box;transform-origin:center}.arch-entity:hover>.arch-entity-surface,.arch-entity:focus-visible>.arch-entity-surface{transform:scale(1.018);filter:drop-shadow(0 7px 10px rgba(15,23,42,.16))}.arch-focus-root>.arch-entity-surface{filter:drop-shadow(0 18px 30px rgba(15,23,42,.13))}
.arch-container-box{fill:#f8fafc;stroke:#64748b;stroke-width:1.4}.arch-container.test>.arch-entity-surface>.arch-container-box{fill:#e7f0fb;stroke:#3b6f9f}.arch-container.env>.arch-entity-surface>.arch-container-box{fill:#e8f7ee;stroke:#4d8b64}.arch-container.agent>.arch-entity-surface>.arch-container-box{fill:#e5f6f8;stroke:#3b8190}.arch-container.driver>.arch-entity-surface>.arch-container-box{fill:#fff1f2;stroke:#b85d6b}.arch-container.monitor>.arch-entity-surface>.arch-container-box{fill:#fff7ed;stroke:#b97836}.arch-container.sequencer>.arch-entity-surface>.arch-container-box{fill:#eef2ff;stroke:#6676b4}.arch-container.scoreboard>.arch-entity-surface>.arch-container-box{fill:#fef2f2;stroke:#b85d6b}.arch-container.coverage>.arch-entity-surface>.arch-container-box{fill:#f5f3ff;stroke:#7c6bb0}.arch-container.config>.arch-entity-surface>.arch-container-box{fill:#ecfdf5;stroke:#3f8a57}.arch-container.component>.arch-entity-surface>.arch-container-box{fill:#f8fafc;stroke:#64748b}.arch-container.selected>.arch-entity-surface>.arch-container-box,.arch-leaf.selected>.arch-entity-surface>.arch-leaf-box,.arch-external.selected>.arch-entity-surface>.arch-leaf-box{stroke:#1d4ed8;stroke-width:2.6}
.arch-container-rule{stroke:rgba(71,85,105,.3);stroke-width:1}.arch-leaf-box{fill:#fff;stroke:#94a3b8;stroke-width:1.25}.arch-leaf.config>.arch-entity-surface>.arch-leaf-box{fill:#dcfce7;stroke:#3f8a57}.arch-leaf.scoreboard>.arch-entity-surface>.arch-leaf-box{fill:#ffe4e6;stroke:#be6470}.arch-leaf.coverage>.arch-entity-surface>.arch-leaf-box{fill:#ede9fe;stroke:#7c6bb0}.arch-context-peer>.arch-entity-surface>.arch-leaf-box{fill:#f8fafc;stroke:#64748b;stroke-dasharray:5 3}.arch-external:not(.context-peer)>.arch-entity-surface>.arch-leaf-box{fill:#fef9c3;stroke:#9a8b36}
.arch-role-strip{shape-rendering:crispEdges}.arch-label{fill:#172033;font:650 13px Consolas,"Courier New",monospace}.arch-container-label{fill:#172033;font:700 14px Consolas,"Courier New",monospace}.arch-type{fill:#475569;font:11px Consolas,"Courier New",monospace}.arch-meta{fill:#64748b;font:10px "Segoe UI",Arial,sans-serif}.arch-count{fill:#fff;stroke:#94a3b8}.arch-count-text{fill:#334155;font:650 10px "Segoe UI",Arial,sans-serif;text-anchor:middle}.arch-collapsed{fill:#eff6ff;stroke:#93c5fd}.arch-collapsed-text{fill:#1d4ed8;font:650 10px "Segoe UI",Arial,sans-serif;text-anchor:middle}.arch-empty{position:absolute;z-index:5;inset:0;display:grid;place-items:center;color:#64748b;pointer-events:none}.arch-empty[hidden]{display:none}.empty{padding:30px;color:#64748b}
@keyframes arch-focus-in{from{opacity:0;transform:scale(.96);filter:blur(5px)}to{opacity:1;transform:scale(1);filter:blur(0)}}@keyframes arch-focus-back{from{opacity:.55;transform:scale(1.025);filter:blur(3px)}to{opacity:1;transform:scale(1);filter:blur(0)}}
@media(prefers-reduced-motion:reduce){.arch-context-svg,.arch-entity,.arch-entity-surface,.arch-wire-detail{transition:none!important}.architecture.focus-forward .arch-focus-svg,.architecture.focus-back .arch-focus-svg{animation:none!important}}
#wikiView{position:relative;overflow:hidden}#graph{display:block;width:100%;height:calc(100vh - 184px);background:#fff}.graph-hud{position:absolute;left:12px;bottom:12px;display:flex;gap:6px}.graph-hud span{background:rgba(255,255,255,.9);border:1px solid #d9e0ea;border-radius:5px;padding:4px 7px;color:#64748b}
#tlmView{height:100%;overflow:hidden}.tlm-toolbar{min-width:0}.tlm-search{width:210px;min-width:150px}.tlm-context{min-width:210px;max-width:min(430px,38vw)}.tlm-status{margin-left:auto;white-space:nowrap;color:#64748b;font-size:12px}.tlm-stage{position:relative;isolation:isolate;height:calc(100vh - 141px);min-height:360px;overflow:hidden;background:#f3f6fa}.tlm-svg{position:absolute;inset:0;display:block;width:100%;height:100%;touch-action:none}.tlm-frame{fill:#f8fafc;stroke:#94a3b8;stroke-width:1.2;stroke-dasharray:7 5}.tlm-frame-title{fill:#172033;font:700 14px Consolas,"Courier New",monospace}.tlm-frame-meta{fill:#64748b;font:11px "Segoe UI",Arial,sans-serif}.tlm-column-title{fill:#475569;font:650 11px "Segoe UI",Arial,sans-serif;text-transform:uppercase}.tlm-owner{cursor:default;outline:none}.tlm-owner-box{fill:#fff;stroke:#a8b4c5;stroke-width:1.25;filter:drop-shadow(0 6px 12px rgba(15,23,42,.07))}.tlm-owner-strip{shape-rendering:crispEdges}.tlm-owner-rule{stroke:#dbe3ed;stroke-width:1}.tlm-owner-name{fill:#172033;font:700 13px Consolas,"Courier New",monospace}.tlm-owner-type{fill:#475569;font:11px Consolas,"Courier New",monospace}.tlm-owner-path{fill:#64748b;font:10px Consolas,"Courier New",monospace}.tlm-port-row{cursor:pointer}.tlm-port-row-bg{fill:#fff;transition:fill 160ms ease}.tlm-port-row:hover .tlm-port-row-bg,.tlm-port-row.hot .tlm-port-row-bg{fill:#ecfeff}.tlm-port-row.selected .tlm-port-row-bg{fill:#dbeafe}.tlm-port-rule{stroke:#edf1f6;stroke-width:1}.tlm-port-name{fill:#263449;font:11px Consolas,"Courier New",monospace}.tlm-port-direction{fill:#64748b;font:9px "Segoe UI",Arial,sans-serif;text-anchor:end}.tlm-port-mark{fill:#fff;stroke:#0f766e;stroke-width:2;vector-effect:non-scaling-stroke}.tlm-port-mark.seq_item_connect{stroke:#b45309}.tlm-port-mark.direction-implementation{fill:#ecfeff}.tlm-port-mark.direction-export{fill:#f0fdfa}.tlm-wire-halo{fill:none;stroke:rgba(255,255,255,.96);stroke-width:7;opacity:.96;pointer-events:none;vector-effect:non-scaling-stroke}.tlm-wire{fill:none;stroke:#0f766e;stroke-width:2.6;opacity:.9;pointer-events:none;vector-effect:non-scaling-stroke}.tlm-wire.seq_item_connect{stroke:#b45309}.tlm-wire-halo.dim,.tlm-wire.dim{opacity:.08}.tlm-wire.hot,.tlm-wire.selected{stroke:#1d4ed8;stroke-width:3.5;opacity:1}.tlm-wire-hit{fill:none;stroke:transparent;stroke-width:17;cursor:pointer;pointer-events:stroke}.tlm-legend{position:absolute;z-index:3;left:12px;bottom:12px;display:flex;align-items:center;gap:12px;padding:6px 9px;border:1px solid rgba(148,163,184,.55);border-radius:6px;background:rgba(255,255,255,.92);box-shadow:0 6px 20px rgba(15,23,42,.08);color:#475569;font-size:11px;pointer-events:none;backdrop-filter:blur(8px)}.tlm-legend span{display:flex;align-items:center;gap:5px}.tlm-legend i{display:inline-block;width:10px;height:10px;background:#fff;border:2px solid #0f766e}.tlm-legend .port{border-radius:50%}.tlm-legend .export{width:9px;height:9px;transform:rotate(45deg)}.tlm-legend .implementation{border-radius:1px}.tlm-legend .analysis-line{width:18px;height:0;border:0;border-top:2px solid #0f766e}.tlm-legend .seq-line{width:18px;height:0;border:0;border-top:2px solid #b45309}.tlm-empty{position:absolute;inset:0;display:grid;place-items:center;color:#64748b;pointer-events:none}.tlm-empty[hidden]{display:none}
.code-layout{display:grid;grid-template-columns:300px minmax(0,1fr);height:calc(100vh - 140px)}.code-nav{overflow:auto;border-right:1px solid #d9e0ea;background:#fff}.code-results{display:grid}.code-result{border:0;border-bottom:1px solid #edf1f6;background:#fff;text-align:left;padding:7px 9px}.code-result:hover,.code-result.active{background:#eff6ff}.code-result strong{display:block;font:12px Consolas,"Courier New",monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.code-result span{color:#64748b;font-size:11px}.code-stage{min-width:0;display:grid;grid-template-rows:auto 1fr;background:#0f172a;color:#dbeafe}.code-head{padding:8px 12px;border-bottom:1px solid #334155;color:#93c5fd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.code-box{overflow:auto;padding:8px 0;font:12px/1.5 Consolas,"Courier New",monospace}.code-line{display:grid;grid-template-columns:56px minmax(max-content,1fr);gap:10px;min-height:18px;padding:0 12px;white-space:pre}.code-line.hit{background:rgba(37,99,235,.3)}.ln{color:#64748b;text-align:right;user-select:none}.kw{color:#93c5fd;font-weight:650}.macro{color:#fde047}.str{color:#86efac}.com{color:#94a3b8;font-style:italic}.num{color:#fca5a5}
.detail-name{font:700 15px Consolas,"Courier New",monospace;word-break:break-word}.kv{display:grid;grid-template-columns:75px 1fr;gap:5px 7px;margin-top:9px}.kv div:nth-child(odd){color:#64748b}.relation{padding:7px;border-left:3px solid transparent;border-bottom:1px solid #edf1f6;cursor:pointer;font:11px/1.4 Consolas,"Courier New",monospace;word-break:break-word}.relation:hover,.relation.active{background:#eff6ff;border-left-color:#2563eb}.node-list{display:grid;max-height:260px;overflow:auto;border:1px solid #e2e8f0;border-radius:5px}.node-list button{border:0;border-bottom:1px solid #edf1f6;background:#fff;text-align:left;padding:6px 7px;font:11px Consolas,"Courier New",monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.node-list button:last-child{border-bottom:0}.node-list button:hover,.node-list button.active{background:#eff6ff;color:#1d4ed8}.snippet{max-height:360px;overflow:auto;background:#0f172a;color:#dbeafe;padding:7px 0;margin-top:8px;border-radius:5px;font:11px/1.45 Consolas,"Courier New",monospace}
@media(max-width:1050px){.layout{grid-template-columns:230px minmax(0,1fr)}.layout.tlm-mode{grid-template-columns:minmax(0,1fr)}.right{display:none}}@media(max-width:720px){header{height:48px;padding:0 10px}h1{font-size:16px}.badges{display:none}nav{height:42px;align-items:stretch;padding:0 3px}.tab{padding:10px 9px 8px;font-size:12px}.layout{height:calc(100vh - 90px);grid-template-columns:1fr}.left{display:none}.toolbar{overflow-x:auto;scrollbar-width:none}.toolbar::-webkit-scrollbar{display:none}.toolbar>*{flex:0 0 auto}.arch-root,.tlm-context{min-width:170px;max-width:250px}.tlm-search{width:170px}.arch-path,.arch-status,.tlm-status{display:none}.architecture,.tlm-stage{height:calc(100vh - 156px);min-height:280px}#graph{height:calc(100vh - 134px)}#codeView>.toolbar{display:grid;grid-template-columns:minmax(0,1fr) auto;overflow:visible}#codeView>.toolbar .field{max-width:none!important;min-width:0}#codeMode{display:none}.code-layout{height:calc(100vh - 134px);grid-template-columns:1fr;grid-template-rows:minmax(120px,180px) minmax(0,1fr);overflow:hidden}.code-nav{max-height:none;border-right:0;border-bottom:1px solid #d9e0ea}.code-stage{min-height:0}}
</style>
</head>
<body>
<header><h1>UVM Wiki</h1><div class="badges" id="badges"></div></header>
<nav><button class="tab active" data-view="architecture">Architecture</button><button class="tab" data-view="wiki">Wiki Graph</button><button class="tab" data-view="tlm">TLM Connections</button><button class="tab" data-view="code">Code Explorer</button></nav>
<div class="layout" id="appLayout">
<aside class="left">
  <div class="section"><p class="section-title">Search current view</p><input id="globalSearch" class="field" placeholder="class / instance / port"></div>
  <div class="section"><p class="section-title">Project</p><div class="stats" id="stats"></div><p class="hint" id="parserInfo"></p></div>
  <div class="section"><p class="section-title">Class roles</p><div class="roles" id="roles"></div></div>
  <div class="section"><p class="section-title">Source</p><div class="hint" id="sourceRoot"></div></div>
</aside>
<main>
  <section class="view active" id="architectureView"><div class="toolbar arch-toolbar"><select id="archRoot" class="arch-root" aria-label="Architecture root"></select><button id="archBack" disabled>Back</button><button id="fitArch">Fit</button><div class="arch-options"><label class="arch-toggle"><input id="archTlm" type="checkbox" checked> TLM</label><label class="arch-toggle"><input id="archInterfaces" type="checkbox" checked> Interfaces</label></div><span class="arch-path" id="archPath"></span><span class="arch-status" id="archStatus">Static inferred</span></div><div class="architecture" id="architecture"><svg id="archContextGraph" class="arch-svg arch-context-svg" aria-hidden="true"><g id="archContextLayer"><g id="archContextBackNodes"></g><g id="archContextWires"></g><g id="archContextNodes"></g><g id="archContextMarks"></g></g></svg><svg id="archGraph" class="arch-svg arch-focus-svg" role="img" aria-label="UVM component architecture"><defs><marker id="archArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 Z" fill="#0f766e"></path></marker><marker id="archSeqArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 Z" fill="#b45309"></path></marker><marker id="archVifArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 Z" fill="#64748b"></path></marker></defs><g id="archLayer"><g id="archBackNodes"></g><g id="archWires"></g><g id="archNodes"></g><g id="archMarks"></g></g></svg><div class="arch-legend" aria-hidden="true"><span><i class="port"></i>port</span><span><i class="export"></i>export</span><span><i class="implementation"></i>imp</span><span><i class="analysis-line"></i>analysis</span><span><i class="seq-line"></i>seq item</span></div><div class="arch-empty" id="archEmpty" hidden>No inferred UVM component hierarchy.</div></div></section>
  <section class="view" id="wikiView"><div class="toolbar"><button class="active" data-graph-mode="extends">Inheritance</button><button data-graph-mode="topology">Topology</button><button data-graph-mode="all">All relations</button><button id="resetGraph">Reset view</button></div><canvas id="graph"></canvas><div class="graph-hud" id="graphHud"></div></section>
  <section class="view" id="tlmView"><div class="toolbar tlm-toolbar"><input id="tlmSearch" class="field tlm-search" placeholder="Search ports / instances"><select id="tlmContext" class="tlm-context" aria-label="Connection context"></select><select id="tlmKind" aria-label="Connection kind"><option value="">All connections</option><option value="tlm_connect">Analysis TLM</option><option value="seq_item_connect">Seq item</option></select><button id="fitTlm">Fit</button><span class="tlm-status" id="tlmStatus"></span></div><div class="tlm-stage" id="tlmStage"><svg id="tlmGraph" class="tlm-svg" role="img" aria-label="UVM TLM port connections"><defs><marker id="tlmArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 Z" fill="#0f766e"></path></marker><marker id="tlmSeqArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 Z" fill="#b45309"></path></marker></defs><g id="tlmLayer"></g></svg><div class="tlm-legend" id="tlmLegend" aria-hidden="true"><span><i class="port"></i>port</span><span><i class="export"></i>export</span><span><i class="implementation"></i>imp</span><span><i class="analysis-line"></i>analysis</span><span><i class="seq-line"></i>seq item</span></div><div class="tlm-empty" id="tlmEmpty" hidden>No inferred TLM connections.</div></div></section>
  <section class="view" id="codeView"><div class="toolbar"><input id="codeSearch" class="field" style="max-width:520px" placeholder="Search symbols or full source"><button id="runCodeSearch">Search</button><span class="hint" id="codeMode"></span></div><div class="code-layout"><div class="code-nav"><div class="code-results" id="codeResults"></div></div><div class="code-stage"><div class="code-head" id="codeHead">Select a symbol or source result</div><div class="code-box" id="codeBox"></div></div></div></section>
</main>
<aside class="right"><div class="section"><p class="section-title">Selection</p><div id="detail" class="muted">Select a node, connection, or relation.</div></div><div class="section" id="nodePanel" style="display:none"><p class="section-title">Visible nodes</p><div class="node-list" id="nodeList"></div></div><div class="section"><p class="section-title">Related</p><div id="relations"></div></div><div class="section"><p class="section-title">Source preview</p><div id="preview" class="muted">No source selected.</div></div></aside>
</div>
<script>__D3__</script>
<script>
const DATA=__DATA__;
const $=id=>document.getElementById(id),esc=value=>String(value??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const ARCH=DATA.uvm_architecture||{roots:[],components:{},default_root:null},D3_VERSION=d3.version;
const firstArchRoot=ARCH.default_root||(ARCH.roots||[])[0]?.type||null;
function fallbackTlmEndpoint(expression,context,direction,kind){const parts=String(expression||"").split(".").filter(Boolean),port=parts.pop()||String(expression||""),path=parts;return{expression,requested_path:path,instance_path:path,owner_type:path[path.length-1]||context,owner_role:"component",port,path_resolved:false,port_declared:false,confidence:"low",port_type:"",family:kind==="seq_item_connect"?"seq_item":"analysis",direction,transaction_types:[]}}
const TLM_CONNECTIONS=((ARCH.connections||[]).length?ARCH.connections:(DATA.tlm?.connections||[])).map((item,index)=>{const context=item.context||item.declared_in||"global",source_endpoint=item.source_endpoint||fallbackTlmEndpoint(item.lhs,context,"port",item.kind),target_endpoint=item.target_endpoint||fallbackTlmEndpoint(item.rhs,context,item.kind==="seq_item_connect"?"export":"implementation",item.kind);return{...item,context,source_endpoint,target_endpoint,_tlm_index:index,_key:[context,item.kind,item.lhs,item.rhs,item.file,item.line,index].join("|")}});
const tlmContextCounts=new Map();TLM_CONNECTIONS.forEach(item=>tlmContextCounts.set(item.context,(tlmContextCounts.get(item.context)||0)+1));
const TLM_CONTEXTS=[...tlmContextCounts].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])),firstTlmContext=TLM_CONTEXTS[0]?.[0]||"";
const state={view:"architecture",graphMode:"extends",query:"",role:"",selected:null,activeRelation:null,server:location.protocol==="http:"||location.protocol==="https:",tlmKind:"",tlmContext:firstTlmContext,tlm:{selectedKey:null,hoverKey:null},arch:{root:firstArchRoot,focus:firstArchRoot,instance:firstArchRoot,edge:null,path:[],selectedUid:null,selectedWire:null,showTlm:true,showInterfaces:true},graph:{nodes:[],edges:[],scale:window.innerWidth<720?.55:1,panX:0,panY:0,drag:null,panDrag:null,hover:null,running:false}};
const symbolByName=new Map();function symbolQuality(item){return[!item.pyslang_only,item.base,Number(item.line)>1].filter(Boolean).length}(DATA.symbols||[]).forEach(item=>{const prior=symbolByName.get(item.name);if(!prior||symbolQuality(item)>symbolQuality(prior))symbolByName.set(item.name,item)});
const relationsByName=new Map();function addRel(name,rel){if(!name)return;const list=relationsByName.get(name)||[];list.push(rel);relationsByName.set(name,list)}
(DATA.relations||[]).forEach(rel=>{addRel(String(rel.source||"").split(".")[0],rel);addRel(String(rel.target||"").split(".")[0],rel)});
function color(role){return DATA.role_colors?.[role]||"#64748b"}function text(value){return JSON.stringify(value).toLowerCase()}
function init(){renderHeader();bind();renderRoles();renderArchRoots();renderTlmContexts();renderArchitecture();renderWiki();renderTlm();renderCodeIndex();}
function renderHeader(){const s=DATA.stats||{};$("badges").innerHTML=[["files",s.files],["classes",s.classes],["relations",s.relations],["parser",DATA.metadata?.parser_effective]].map(([k,v])=>`<span class="badge">${esc(k)} ${esc(v)}</span>`).join("");$("stats").innerHTML=[["Files",s.files],["Classes",s.classes],["Ports",s.ports],["Connects",s.connections]].map(([k,v])=>`<div class="stat"><strong>${esc(v||0)}</strong>${k}</div>`).join("");$("parserInfo").textContent=`requested ${DATA.metadata?.parser_requested}; cache reused ${DATA.metadata?.cache?.reused_files||0}, reparsed ${DATA.metadata?.cache?.reparsed_files||0}`;$("sourceRoot").textContent=DATA.metadata?.source_root||"";$("codeMode").textContent=state.server?"full source mode":"embedded snippet mode"}
function bind(){document.querySelectorAll(".tab").forEach(button=>button.onclick=()=>switchView(button.dataset.view));document.querySelectorAll("[data-graph-mode]").forEach(button=>button.onclick=()=>{state.graphMode=button.dataset.graphMode;document.querySelectorAll("[data-graph-mode]").forEach(x=>x.classList.toggle("active",x===button));resetGraphView();renderWiki()});$("archRoot").onchange=event=>setArchitectureRoot(event.target.value);$("archBack").onclick=backArchitecture;$("fitArch").onclick=()=>fitArchitecture(true);$("archTlm").onchange=event=>{state.arch.showTlm=event.target.checked;renderArchitecture()};$("archInterfaces").onchange=event=>{state.arch.showInterfaces=event.target.checked;renderArchitecture()};$("resetGraph").onclick=()=>{resetGraphView();renderWiki()};$("globalSearch").oninput=event=>{state.query=event.target.value.trim().toLowerCase();$("tlmSearch").value=event.target.value;renderCurrent()};$("tlmSearch").oninput=event=>{state.query=event.target.value.trim().toLowerCase();$("globalSearch").value=event.target.value;renderTlm()};$("tlmContext").onchange=event=>{state.tlmContext=event.target.value;state.tlm.selectedKey=null;renderTlm()};$("tlmKind").onchange=event=>{state.tlmKind=event.target.value;state.tlm.selectedKey=null;renderTlm()};$("fitTlm").onclick=()=>fitTlm(true);$("runCodeSearch").onclick=runCodeSearch;$("codeSearch").onkeydown=event=>{if(event.key==="Enter")runCodeSearch()};window.addEventListener("resize",()=>{if(state.view==="wiki")resizeGraph();else if(state.view==="architecture")renderArchitecture();else if(state.view==="tlm")fitTlm(false)})}
function switchView(view){state.view=view;$("appLayout").classList.toggle("tlm-mode",view==="tlm");document.querySelectorAll(".tab").forEach(x=>x.classList.toggle("active",x.dataset.view===view));document.querySelectorAll(".view").forEach(x=>x.classList.toggle("active",x.id===`${view}View`));$("nodePanel").style.display=view==="wiki"?"block":"none";renderCurrent();if(view==="wiki")setTimeout(resizeGraph,0);if(view==="architecture")setTimeout(()=>fitArchitecture(false),0);if(view==="tlm")setTimeout(()=>fitTlm(false),0)}
function renderCurrent(){if(state.view==="architecture")renderArchitecture();else if(state.view==="wiki")renderWiki();else if(state.view==="tlm")renderTlm();else renderCodeIndex()}
function renderRoles(){const roles=[...new Set((DATA.symbols||[]).filter(x=>x.kind==="class").map(x=>x.role).filter(Boolean))].sort();$("roles").innerHTML=`<button class="role-chip active" data-role="">All</button>`+roles.map(role=>`<button class="role-chip" data-role="${esc(role)}">${esc(role)}</button>`).join("");$("roles").onclick=event=>{const button=event.target.closest("[data-role]");if(!button)return;state.role=button.dataset.role;document.querySelectorAll("[data-role]").forEach(x=>x.classList.toggle("active",x===button));renderCurrent()}}
function nodeMatches(name){const symbol=symbolByName.get(name)||{};return(!state.query||text({name,symbol,relations:relationsByName.get(name)||[]}).includes(state.query))&&(!state.role||symbol.role===state.role)}
function renderArchRoots(){const roots=ARCH.roots||[];$("archRoot").innerHTML=roots.map(root=>`<option value="${esc(root.type)}">${esc(root.type)} | ${esc(root.role)} | ${esc(root.descendant_type_count||root.child_count||0)}</option>`).join("")||'<option value="">No component roots</option>';if(state.arch.root&&roots.some(root=>root.type===state.arch.root))$("archRoot").value=state.arch.root;else if(roots.length)setArchitectureRoot(roots[0].type)}
function setArchitectureRoot(type){if(!type||!ARCH.components?.[type])return;const showTlm=state.arch.showTlm,showInterfaces=state.arch.showInterfaces;state.arch={root:type,focus:type,instance:type,edge:null,path:[],selectedUid:null,selectedWire:null,showTlm,showInterfaces};state.selected=null;state.activeRelation=null;$("archRoot").value=type;renderArchitecture(true)}
function shortLabel(value,limit=30){const textValue=String(value||"");return textValue.length<=limit?textValue:`${textValue.slice(0,limit-3)}...`}
function archPathKey(path){return(path||[]).join("\x1f")}
function nodeUid(type,instance,edge,path=[]){return`${archPathKey(path)}|${edge?.declared_in||"root"}|${type}|${instance||type}`}
function compactArchEdges(edges){const items=edges||[];if(items.length<=16)return items.map(edge=>({edge,instances:[edge.instance||edge.type]}));const groups=d3.groups(items,edge=>`${edge.type}|${edge.role||"component"}`).sort((a,b)=>b[1].length-a[1].length||a[0].localeCompare(b[0])),output=groups.slice(0,15).map(([,group])=>({edge:group[0],instances:group.map(item=>item.instance||item.type)}));if(groups.length>15)output.push({more:groups.slice(15).reduce((sum,item)=>sum+item[1].length,0)});return output}
function buildArchNode(type,instance,edge,path,depth=0,ancestry=new Set(),group=null,suppressExpand=false){const component=ARCH.components?.[type]||null,role=edge?.role||component?.role||symbolByName.get(type)?.role||"component",childCount=Number(component?.child_count||0),auxiliaryCount=Number(component?.auxiliary_count||0),expandable=childCount+auxiliaryCount>0,cycle=ancestry.has(type),expand=Boolean(component&&expandable&&!cycle&&!suppressExpand&&(depth===0||(depth<3&&["test","env","agent"].includes(role)))),instances=group?.instances||[instance||type],displayInstance=instances.length>1?`${instances[0]} x${instances.length}`:instance||type,node={uid:nodeUid(type,displayInstance,edge,path),type,instance:displayInstance,instanceAliases:instances,role,base:component?.base||symbolByName.get(type)?.base,file:edge?.file||component?.file||symbolByName.get(type)?.file,line:edge?.line||component?.line||symbolByName.get(type)?.line,edge,component,path,depth,childCount,auxiliaryCount,portCount:Number(component?.port_count||0),connectionCount:Number(component?.connection_count||0),expandable,expanded:false,collapsed:expandable,isFocus:depth===0,children:[]};if(expand){const nextAncestry=new Set(ancestry);nextAncestry.add(type);const compactChildren=compactArchEdges(component.children||[]),agentGroups=compactChildren.filter(item=>item.edge&&(item.edge.role||ARCH.components?.[item.edge.type]?.role)==="agent").length,collapseAgents=agentGroups>3||(component.children||[]).length>12;compactChildren.forEach(item=>{if(item.more){node.children.push({uid:`${node.uid}|more`,type:"",instance:`${item.more} more components`,role:"component",path:[...path,"@more"],depth:depth+1,synthetic:true,expandable:false,expanded:false,collapsed:false,children:[],childCount:0,portCount:0,connectionCount:0});return}const childEdge=item.edge,childInstance=item.instances[0]||childEdge.type,childRole=childEdge.role||ARCH.components?.[childEdge.type]?.role;node.children.push(buildArchNode(childEdge.type,childInstance,childEdge,[...path,childInstance],depth+1,nextAncestry,item,collapseAgents&&childRole==="agent"))});const auxiliaries=component.auxiliaries||[];if(auxiliaries.length>1){const first=auxiliaries[0],names=auxiliaries.map(item=>item.instance||item.type);node.children.push({uid:`${node.uid}|configuration`,type:"configuration",instance:"configuration",instanceAliases:names,role:"config",file:first.file,line:first.line,edge:first,component:null,path:[...path,"@configuration"],depth:depth+1,childCount:auxiliaries.length,auxiliaryCount:0,portCount:0,connectionCount:0,expandable:false,expanded:false,collapsed:false,isFocus:false,children:[],configItems:auxiliaries,auxiliaryGroup:true})}else if(auxiliaries.length===1){const childEdge=auxiliaries[0],childInstance=childEdge.instance||childEdge.type;node.children.push(buildArchNode(childEdge.type,childInstance,childEdge,[...path,childInstance],depth+1,nextAncestry,{edge:childEdge,instances:[childInstance]},true))}node.expanded=node.children.length>0;node.collapsed=!node.expanded&&node.expandable}return node}
function markArchMatches(node){const own=(!state.query||text({instance:node.instance,type:node.type,role:node.role,component:node.component,configItems:node.configItems}).includes(state.query))&&(!state.role||node.role===state.role),child=Boolean((node.children||[]).map(markArchMatches).find(Boolean));node.dim=Boolean((state.query||state.role)&&!own&&!child);return own||child}
const ARCH_GAP=26,ARCH_PAD=18,ARCH_HEADER=52,ARCH_LEAF_W=196,ARCH_LEAF_H=78;
function measureArchNode(node){if(!node.expanded){node.w=node.role==="config"?184:ARCH_LEAF_W;node.h=ARCH_LEAF_H;return node}node.children.forEach(measureArchNode);const innerLimit=node.role==="agent"?430:node.role==="env"?980:1100,rows=[],gap=ARCH_GAP;let row={items:[],width:0,height:0};node.children.forEach(child=>{const nextWidth=row.items.length?row.width+gap+child.w:child.w;if(row.items.length&&nextWidth>innerLimit){rows.push(row);row={items:[],width:0,height:0}}row.items.push(child);row.width=row.items.length===1?child.w:row.width+gap+child.w;row.height=Math.max(row.height,child.h)});if(row.items.length)rows.push(row);const minWidth=node.role==="test"?620:node.role==="env"?520:node.role==="agent"?440:420,rowWidth=d3.max(rows,item=>item.width)||0;node.rows=rows;node.w=Math.max(minWidth,rowWidth+ARCH_PAD*2);node.h=ARCH_HEADER+ARCH_PAD*2+d3.sum(rows,item=>item.height)+Math.max(0,rows.length-1)*gap;return node}
function positionArchNode(node,x=0,y=0){node.x=x;node.y=y;if(!node.expanded)return;let rowY=y+ARCH_HEADER+ARCH_PAD;node.rows.forEach(row=>{let rowX=x+(node.w-row.width)/2;row.items.forEach(child=>{positionArchNode(child,rowX,rowY+(row.height-child.h)/2);rowX+=child.w+ARCH_GAP});rowY+=row.height+ARCH_GAP})}
function flattenArch(node,output=[],parent=null){node.parentNode=parent;output.push(node);(node.children||[]).forEach(child=>flattenArch(child,output,node));return output}
function registerArchPaths(nodes){const paths=new Map();nodes.filter(node=>!node.synthetic&&!node.external).forEach(node=>{paths.set(archPathKey(node.path),node);const parent=node.path.slice(0,-1);(node.instanceAliases||[]).forEach(alias=>paths.set(archPathKey([...parent,alias]),node))});return paths}
function endpointArchNode(contextNode,endpoint,paths){const relative=endpoint?.instance_path||[];for(let length=relative.length;length>=0;length--){const found=paths.get(archPathKey([...contextNode.path,...relative.slice(0,length)]));if(found)return found}return contextNode}
function compactArchitecture(){return($("architecture")?.clientWidth||window.innerWidth)<760}
function buildArchInterfaces(nodes,root,rightOffset=0){
  if(!state.arch.showInterfaces)return{nodes:[],lane:null,wires:[]};
  const grouped=new Map();
  nodes.filter(node=>node.component&&!node.synthetic).forEach(owner=>(owner.component.virtual_interfaces||[]).forEach(access=>{
    const key=`${access.type}|${access.field||""}`,item=grouped.get(key)||{type:access.type,field:access.field||"virtual interface",access,owners:[]};
    if(!item.owners.some(node=>node.uid===owner.uid))item.owners.push(owner);
    grouped.set(key,item);
  }));
  const entries=[...grouped.values()].slice(0,12);
  if(!entries.length)return{nodes:[],lane:null,wires:[]};
  const compact=compactArchitecture(),contentHeight=58+entries.length*(ARCH_LEAF_H+14)+18,lane=compact?{x:root.x+(root.w-244)/2,y:root.y+root.h+72,w:244,h:contentHeight,external:true}:{x:root.w+92+rightOffset,y:0,w:244,h:Math.max(root.h,contentHeight),external:true};
  const externalNodes=entries.map((item,index)=>({uid:`vif|${item.type}|${item.field}`,type:item.type,instance:item.field,role:"interface",file:item.access.file,line:item.access.line,access:item.access,owners:item.owners,external:true,synthetic:false,expandable:false,expanded:false,collapsed:false,children:[],childCount:0,portCount:0,connectionCount:0,x:lane.x+22,y:lane.y+48+index*(ARCH_LEAF_H+14),w:200,h:ARCH_LEAF_H,path:[]})),wires=[];
  externalNodes.forEach(target=>target.owners.forEach(source=>wires.push({uid:`vif-wire|${source.uid}|${target.uid}`,kind:"virtual_interface",family:"virtual_interface",source,target,sourceEndpoint:{port:target.instance,direction:"port",family:"virtual_interface"},targetEndpoint:{port:target.type,direction:"interface",family:"virtual_interface"},file:target.access.file,line:target.access.line,lhs:`${source.instance}.${target.instance}`,rhs:target.type,context:source.type})));
  return{nodes:externalNodes,lane,wires};
}
function archConnectionWire(contextNode,connection,index,source,target,extra={}){
  const sourceEndpoint=connection.source_endpoint||{},targetEndpoint=connection.target_endpoint||{};
  return{uid:`${extra.boundary?"boundary":"wire"}|${contextNode.uid}|${connection.kind}|${connection.lhs}|${connection.rhs}|${connection.file}|${connection.line}|${index}`,kind:connection.kind,family:sourceEndpoint.family||targetEndpoint.family||connection.kind,source,target,sourceEndpoint,targetEndpoint,file:connection.file,line:connection.line,lhs:connection.lhs,rhs:connection.rhs,context:connection.context||contextNode.type,connection,...extra};
}
function addLocalArchConnections(componentNodes,paths,wires){
  if(!state.arch.showTlm)return;
  componentNodes.filter(node=>node.component&&!node.synthetic).forEach(contextNode=>(contextNode.component.connections||[]).forEach((connection,index)=>{
    const source=endpointArchNode(contextNode,connection.source_endpoint,paths),target=endpointArchNode(contextNode,connection.target_endpoint,paths);
    if(source&&target)wires.push(archConnectionWire(contextNode,connection,index,source,target));
  }));
}
function normalizedArchInstance(value){return String(value||"").replace(/\[[^\]]*\]/g,"")}
function endpointEntersFocus(endpoint,focusInstance){const path=endpoint?.instance_path||endpoint?.requested_path||[];return Boolean(path.length&&normalizedArchInstance(path[0])===normalizedArchInstance(focusInstance))}
function focusedEndpoint(endpoint){return{...(endpoint||{}),instance_path:(endpoint?.instance_path||[]).slice(1),requested_path:(endpoint?.requested_path||[]).slice(1)}}
function contextPeerLabel(endpoint,parent){const path=endpoint?.instance_path||endpoint?.requested_path||[];return path[0]||parent.instance||parent.type||"parent"}
function positionContextPeers(root,peers){
  if(compactArchitecture()){let cursor=root.y-80;peers.forEach(peer=>{cursor-=peer.h;peer.x=root.x+(root.w-peer.w)/2;peer.y=cursor;cursor-=24});return}
  ["left","right"].forEach(side=>{
    const items=peers.filter(peer=>peer.peerSide===side),gap=16,total=items.length*ARCH_LEAF_H+Math.max(0,items.length-1)*gap,start=root.y+(root.h-total)/2;
    items.forEach((peer,index)=>{peer.x=side==="left"?root.x-peer.w-230:root.x+root.w+230;peer.y=start+index*(ARCH_LEAF_H+gap)});
  });
}
function addFocusBoundaryConnections(descriptor,root,componentNodes,paths,wires){
  const parent=state.arch.path[state.arch.path.length-1];
  if(!parent||descriptor.type!==state.arch.focus||descriptor.instance!==state.arch.instance||!state.arch.showTlm)return[];
  const parentComponent=ARCH.components?.[parent.type],connections=parentComponent?.connections||[],peers=[],peerByKey=new Map(),focusInstance=descriptor.instance;
  const peerFor=(endpoint,side)=>{
    const label=contextPeerLabel(endpoint,parent),key=`${side}|${label}|${endpoint?.owner_type||""}`;
    if(peerByKey.has(key))return peerByKey.get(key);
    const known=symbolByName.get(endpoint?.owner_type)||{},peer={uid:`context-peer|${key}`,type:endpoint?.owner_type||"parent context",instance:label,role:endpoint?.owner_role||known.role||"component",file:known.file,line:known.line,contextPeer:true,peerSide:side,external:false,synthetic:true,expandable:false,expanded:false,collapsed:false,children:[],childCount:0,portCount:0,connectionCount:0,x:0,y:0,w:ARCH_LEAF_W,h:ARCH_LEAF_H,path:[]};
    peerByKey.set(key,peer);peers.push(peer);return peer;
  };
  connections.forEach((connection,index)=>{
    const sourceInside=endpointEntersFocus(connection.source_endpoint,focusInstance),targetInside=endpointEntersFocus(connection.target_endpoint,focusInstance);
    if(!sourceInside&&!targetInside)return;
    const source=sourceInside?endpointArchNode(root,focusedEndpoint(connection.source_endpoint),paths):peerFor(connection.source_endpoint,"left");
    const target=targetInside?endpointArchNode(root,focusedEndpoint(connection.target_endpoint),paths):peerFor(connection.target_endpoint,"right");
    if(source&&target)wires.push(archConnectionWire(root,connection,index,source,target,{boundary:true,parentContext:parent.type}));
  });
  positionContextPeers(root,peers);
  return peers;
}
function buildArchitectureScene(descriptor=null,{includeFocusBoundary=true}={}){
  descriptor=descriptor||{type:state.arch.focus,instance:state.arch.instance,edge:state.arch.edge};
  const component=ARCH.components?.[descriptor.type];
  if(!component)return null;
  const instance=descriptor.instance||descriptor.type,rootPath=[instance],root=buildArchNode(descriptor.type,instance,descriptor.edge,rootPath);
  markArchMatches(root);measureArchNode(root);positionArchNode(root,0,0);
  const componentNodes=flattenArch(root),paths=registerArchPaths(componentNodes),wires=[];
  addLocalArchConnections(componentNodes,paths,wires);
  const peers=includeFocusBoundary?addFocusBoundaryConnections(descriptor,root,componentNodes,paths,wires):[];
  const rightOffset=peers.some(peer=>peer.peerSide==="right")?ARCH_LEAF_W+104:0,external=buildArchInterfaces(componentNodes,root,rightOffset);
  wires.push(...external.wires);
  return{root,nodes:[...componentNodes,...peers,...external.nodes],wires,lane:external.lane,descriptor};
}
function archContains(outer,inner){return inner.x>=outer.x&&inner.y>=outer.y&&inner.x+inner.w<=outer.x+outer.w&&inner.y+inner.h<=outer.y+outer.h}
function archAnchorSide(node,toward){
  const cx=node.x+node.w/2,cy=node.y+node.h/2,tx=toward.x+toward.w/2,ty=toward.y+toward.h/2;
  if(archContains(node,toward)){
    const choices=[{side:"left",d:Math.abs(tx-node.x)},{side:"right",d:Math.abs(node.x+node.w-tx)},{side:"top",d:Math.abs(ty-node.y)},{side:"bottom",d:Math.abs(node.y+node.h-ty)}];
    return choices.sort((a,b)=>a.d-b.d)[0].side;
  }
  const dx=tx-cx,dy=ty-cy;
  return Math.abs(dx)>=Math.abs(dy)?(dx>=0?"right":"left"):(dy>=0?"bottom":"top");
}
function archAnchorForSlot(node,side,index,total){
  const margin=14;
  if(side==="left"||side==="right"){
    const available=Math.max(1,node.h-margin*2),y=node.y+margin+available*(index+1)/(total+1);
    return{x:side==="left"?node.x:node.x+node.w,y};
  }
  const available=Math.max(1,node.w-margin*2),x=node.x+margin+available*(index+1)/(total+1);
  return{x,y:side==="top"?node.y:node.y+node.h};
}
function layoutArchPorts(scene){
  const groups=new Map(),entries=[];
  scene.wires.forEach((wire,index)=>{
    let sourceSide,targetSide;
    if(wire.source.uid===wire.target.uid){sourceSide="right";targetSide="bottom"}else{sourceSide=archAnchorSide(wire.source,wire.target);targetSide=archAnchorSide(wire.target,wire.source)}
    wire.sourceSide=sourceSide;wire.targetSide=targetSide;
    [["source",wire.source,wire.sourceEndpoint,sourceSide],["target",wire.target,wire.targetEndpoint,targetSide]].forEach(([which,node,endpoint,side])=>{
      const item={wire,which,node,endpoint,side,index},key=`${node.uid}|${side}`,list=groups.get(key)||[];list.push(item);groups.set(key,list);entries.push(item);
    });
  });
  groups.forEach(list=>list.sort((a,b)=>String(a.endpoint?.port||"").localeCompare(String(b.endpoint?.port||""))||a.index-b.index).forEach((item,index)=>{item.anchor=archAnchorForSlot(item.node,item.side,index,list.length);item.wire[item.which==="source"?"startAnchor":"endAnchor"]=item.anchor;item.wire[item.which==="source"?"sourceSlot":"targetSlot"]={index,total:list.length}}));
  return entries;
}
function archWirePath(wire,index){
  const a=wire.startAnchor,b=wire.endAnchor,offset=(index%7-3)*6;
  if(wire.source.uid===wire.target.uid){const reach=30+Math.abs(offset);return`M${a.x},${a.y}H${a.x+reach}V${b.y+reach}H${b.x}V${b.y}`}
  if(Math.abs(b.x-a.x)>=Math.abs(b.y-a.y)){const middle=(a.x+b.x)/2+offset;return`M${a.x},${a.y}H${middle}V${b.y}H${b.x}`}
  const middle=(a.y+b.y)/2+offset;return`M${a.x},${a.y}V${middle}H${b.x}V${b.y}`;
}
function archWireRelation(wire){return{kind:wire.kind,source:wire.lhs,target:wire.rhs,context:wire.context,file:wire.file,line:wire.line}}
function archClassToken(value){return String(value||"").replace(/[^a-zA-Z0-9_-]/g,"-")}
function archMarker(wire){return wire.kind==="seq_item_connect"?"url(#archSeqArrow)":wire.kind==="virtual_interface"?"url(#archVifArrow)":"url(#archArrow)"}
function appendArchPortMark(layer,wire,endpoint,anchor){
  const direction=endpoint?.direction||"port",classes=`arch-port-mark ${archClassToken(wire.kind)} direction-${archClassToken(direction)}`;
  let mark;
  if(direction==="export")mark=layer.append("path").attr("d",`M${anchor.x},${anchor.y-5}L${anchor.x+5},${anchor.y}L${anchor.x},${anchor.y+5}L${anchor.x-5},${anchor.y}Z`);
  else if(direction==="implementation")mark=layer.append("rect").attr("x",anchor.x-4.5).attr("y",anchor.y-4.5).attr("width",9).attr("height",9).attr("rx",1);
  else mark=layer.append("circle").attr("cx",anchor.x).attr("cy",anchor.y).attr("r",4.5);
  mark.attr("class",classes).append("title").text(`${endpoint?.port||endpoint?.expression||"endpoint"}\n${endpoint?.port_type||direction}`);
}
function appendArchPortLabel(layer,endpoint,anchor,side,slot={index:0,total:1}){
  const label=shortLabel(endpoint?.port||endpoint?.expression||"endpoint",24),textNode=layer.append("text").attr("class","arch-port-label").text(label),gap=9;
  if(side==="left")textNode.attr("x",anchor.x-gap).attr("y",anchor.y+3).attr("text-anchor","end");
  else if(side==="right")textNode.attr("x",anchor.x+gap).attr("y",anchor.y+3).attr("text-anchor","start");
  else if(side==="top")textNode.attr("x",anchor.x).attr("y",anchor.y-gap-(slot.total-1-slot.index)*20).attr("text-anchor","middle");
  else textNode.attr("x",anchor.x).attr("y",anchor.y+gap+7+slot.index*20).attr("text-anchor","middle");
}
const archRuntime={svg:null,layer:null,backNodeLayer:null,wireLayer:null,nodeLayer:null,markLayer:null,context:{svg:null,layer:null,backNodeLayer:null,wireLayer:null,nodeLayer:null,markLayer:null},zoom:null,bound:false,motion:null,reducedMotion:window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches||false};
function ensureArchitecture(){
  if(archRuntime.bound)return;
  archRuntime.svg=d3.select("#archGraph");archRuntime.layer=d3.select("#archLayer");archRuntime.backNodeLayer=d3.select("#archBackNodes");archRuntime.wireLayer=d3.select("#archWires");archRuntime.nodeLayer=d3.select("#archNodes");archRuntime.markLayer=d3.select("#archMarks");
  archRuntime.context.svg=d3.select("#archContextGraph");archRuntime.context.layer=d3.select("#archContextLayer");archRuntime.context.backNodeLayer=d3.select("#archContextBackNodes");archRuntime.context.wireLayer=d3.select("#archContextWires");archRuntime.context.nodeLayer=d3.select("#archContextNodes");archRuntime.context.markLayer=d3.select("#archContextMarks");
  archRuntime.zoom=d3.zoom().scaleExtent([.16,4]).on("zoom",event=>archRuntime.layer.attr("transform",event.transform));
  archRuntime.svg.call(archRuntime.zoom).on("dblclick.zoom",null).on("click.arch-clear",event=>{if(event.defaultPrevented||event.target!==$("archGraph"))return;if(state.arch.path.length)backArchitecture();else clearSelection()});
  archRuntime.bound=true;
}
function clearArchRuntime(runtime){runtime.backNodeLayer.selectAll("*").remove();runtime.wireLayer.selectAll("*").remove();runtime.nodeLayer.selectAll("*").remove();runtime.markLayer.selectAll("*").remove()}
function drawArchBoundary(runtime,scene){
  if(!scene.lane)return;
  const boundary=runtime.backNodeLayer.append("g").attr("class","arch-external-boundary");
  boundary.append("rect").attr("class","arch-boundary").attr("x",scene.lane.x).attr("y",scene.lane.y).attr("width",scene.lane.w).attr("height",scene.lane.h).attr("rx",6);
  boundary.append("text").attr("class","arch-boundary-title").attr("x",scene.lane.x+14).attr("y",scene.lane.y+25).text("HDL boundary");
}
function drawArchWires(runtime,scene,{interactive=false,animate=false,contextual=false}={}){
  layoutArchPorts(scene);
  const selectedNode=interactive?state.arch.selectedUid:null,sparse=scene.wires.length<=8;
  scene.wires.forEach((wire,index)=>{
    const selected=interactive&&state.arch.selectedWire===wire.uid,dim=Boolean(selectedNode&&wire.source.uid!==selectedNode&&wire.target.uid!==selectedNode),path=archWirePath(wire,index),classes=`arch-wire ${archClassToken(wire.kind)} ${archClassToken(wire.family)}${wire.boundary?" boundary":""}${selected?" selected":""}${dim?" dim":""}`;
    runtime.wireLayer.append("path").attr("class","arch-wire-halo").attr("d",path);
    const visiblePath=runtime.wireLayer.append("path").attr("class",classes).attr("d",path);
    if(!contextual)visiblePath.attr("marker-end",archMarker(wire));
    if(animate&&!archRuntime.reducedMotion&&!contextual){
      const length=visiblePath.node()?.getTotalLength?.()||0;
      if(length)visiblePath.attr("stroke-dasharray",`${length} ${length}`).attr("stroke-dashoffset",length).transition().delay(Math.min(index*22,180)).duration(520).ease(d3.easeCubicOut).attr("stroke-dashoffset",0).on("end",function(){d3.select(this).attr("stroke-dasharray",null).attr("stroke-dashoffset",null)});
    }
    const interaction=runtime.markLayer.append("g"),detail=interaction.append("g").attr("class",`arch-wire-detail${sparse||selected?" visible":""}`);
    appendArchPortMark(interaction,wire,wire.sourceEndpoint,wire.startAnchor);appendArchPortMark(interaction,wire,wire.targetEndpoint,wire.endAnchor);
    if(!contextual){appendArchPortLabel(detail,wire.sourceEndpoint,wire.startAnchor,wire.sourceSide,wire.sourceSlot);appendArchPortLabel(detail,wire.targetEndpoint,wire.endAnchor,wire.targetSide,wire.targetSlot)}
    if(interactive){
      interaction.insert("path",":first-child").attr("class","arch-wire-hit").attr("d",path).on("pointerenter",()=>{visiblePath.classed("selected",true);detail.classed("visible",true)}).on("pointerleave",()=>{visiblePath.classed("selected",selected);detail.classed("visible",sparse||selected)}).on("click",event=>{event.stopPropagation();selectArchitectureWire(wire)}).append("title").text(`${wire.kind}\n${wire.lhs} -> ${wire.rhs}\n${wire.file||""}:${wire.line||""}`);
    }
  });
}
function drawArchNodes(runtime,scene,{interactive=false,animate=false,background=false}={}){
  const nodes=scene.nodes.filter(node=>background?node.expanded:!node.expanded),targetLayer=background?runtime.backNodeLayer:runtime.nodeLayer,groups=targetLayer.selectAll("g.arch-entity").data(nodes,node=>node.uid).enter().append("g").attr("class",node=>`arch-entity ${node.expanded?"arch-container":"arch-leaf"} ${node.external?"arch-external ":""}${node.contextPeer?"context-peer ":""}${node.uid===scene.root.uid?"arch-focus-root ":""}${node.role||"component"}${node.dim?" dim":""}${interactive&&state.arch.selectedUid===node.uid?" selected":""}`).attr("transform",node=>`translate(${node.x},${node.y})`).attr("tabindex",node=>interactive&&!node.synthetic?0:null).attr("role",node=>interactive&&!node.synthetic?"button":null).attr("aria-label",node=>`${node.instance}, ${node.type}, ${node.role}`);
  if(interactive)groups.on("click",(event,node)=>{event.stopPropagation();if(node.synthetic)return;selectArchitectureNode(node,false);if(node.expandable&&!node.isFocus&&!node.external)focusArchitecture(node);else renderArchitecture(false)}).on("keydown",(event,node)=>{if(node.synthetic||!(event.key==="Enter"||event.key===" "))return;event.preventDefault();selectArchitectureNode(node,false);if(node.expandable&&!node.isFocus&&!node.external)focusArchitecture(node);else renderArchitecture(false)});
  const surfaces=groups.append("g").attr("class","arch-entity-surface");
  surfaces.each(function(node){
    const surface=d3.select(this);
    if(node.expanded){
      surface.append("rect").attr("class","arch-container-box").attr("width",node.w).attr("height",node.h).attr("rx",6);surface.append("line").attr("class","arch-container-rule").attr("x1",0).attr("x2",node.w).attr("y1",ARCH_HEADER).attr("y2",ARCH_HEADER);surface.append("text").attr("class","arch-container-label").attr("x",14).attr("y",22).text(shortLabel(node.instance,42));surface.append("text").attr("class","arch-type").attr("x",14).attr("y",41).text(shortLabel(node.type,50));const badge=surface.append("g").attr("transform",`translate(${node.w-28},25)`);badge.append("rect").attr("class","arch-count").attr("x",-19).attr("y",-11).attr("width",38).attr("height",21).attr("rx",5);badge.append("text").attr("class","arch-count-text").attr("y",4).text(node.childCount+node.auxiliaryCount);
    }else{
      surface.append("rect").attr("class","arch-leaf-box").attr("width",node.w).attr("height",node.h).attr("rx",5);surface.append("rect").attr("class","arch-role-strip").attr("width",6).attr("height",node.h).attr("rx",3).attr("fill",color(node.role));surface.append("text").attr("class","arch-label").attr("x",16).attr("y",23).text(shortLabel(node.instance,25));surface.append("text").attr("class","arch-type").attr("x",16).attr("y",43).text(shortLabel(node.type||node.role,29));surface.append("text").attr("class","arch-meta").attr("x",16).attr("y",63).text(node.contextPeer?"parent context":[node.auxiliaryGroup?`${node.configItems.length} config objects`:node.role,node.portCount?`${node.portCount} ports`:"",node.connectionCount?`${node.connectionCount} connects`:""].filter(Boolean).join(" | "));if(node.collapsed){const badge=surface.append("g").attr("transform",`translate(${node.w-24},18)`);badge.append("rect").attr("class","arch-collapsed").attr("x",-17).attr("y",-10).attr("width",34).attr("height",20).attr("rx",5);badge.append("text").attr("class","arch-collapsed-text").attr("y",4).text(`+${node.childCount+node.auxiliaryCount}`)}
    }
  });
  groups.append("title").text(node=>`${(node.instanceAliases||[node.instance]).join(", ")}\n${node.type||node.role}\n${node.file||""}:${node.line||""}`);
  if(animate&&!archRuntime.reducedMotion)groups.attr("opacity",0).transition().delay((_node,index)=>Math.min(index*18,180)).duration(380).ease(d3.easeCubicOut).attr("opacity",1);
}
function drawArchitectureScene(runtime,scene,options={}){clearArchRuntime(runtime);drawArchBoundary(runtime,scene);drawArchNodes(runtime,scene,{...options,background:true});drawArchWires(runtime,scene,options);drawArchNodes(runtime,scene,options)}
function drawArchitecture(scene,animate=false){drawArchitectureScene(archRuntime,scene,{interactive:true,animate})}
function fitArchitectureContext(){
  const svgNode=archRuntime.context.svg.node(),layerNode=archRuntime.context.layer.node(),rect=svgNode?.getBoundingClientRect();
  if(!rect?.width||!rect?.height)return;
  let bounds;try{bounds=layerNode.getBBox()}catch(_error){return}
  if(!bounds.width&&!bounds.height)return;
  const padding=34,scale=Math.max(.16,Math.min(1.05,Math.min((rect.width-padding*2)/Math.max(bounds.width,1),(rect.height-padding*2)/Math.max(bounds.height,1)))),x=rect.width/2-scale*(bounds.x+bounds.width/2),y=rect.height/2-scale*(bounds.y+bounds.height/2);
  archRuntime.context.layer.attr("transform",`translate(${x},${y}) scale(${scale})`);
}
function renderArchitecture(fit=true){
  ensureArchitecture();
  const architecture=$("architecture"),focused=state.arch.path.length>0,motion=archRuntime.motion;archRuntime.motion=null;
  architecture.classList.toggle("is-focused",focused);architecture.classList.remove("focus-forward","focus-back");
  if(motion&&!archRuntime.reducedMotion){void architecture.offsetWidth;architecture.classList.add(motion==="back"?"focus-back":"focus-forward");setTimeout(()=>architecture.classList.remove("focus-forward","focus-back"),560)}
  const parent=state.arch.path[state.arch.path.length-1],contextScene=focused&&parent?buildArchitectureScene(parent,{includeFocusBoundary:false}):null;
  if(contextScene){drawArchitectureScene(archRuntime.context,contextScene,{interactive:false,animate:false,contextual:true});setTimeout(fitArchitectureContext,20)}else clearArchRuntime(archRuntime.context);
  const scene=buildArchitectureScene(),empty=$("archEmpty");empty.hidden=Boolean(scene);$("archBack").disabled=!focused;$("archTlm").checked=state.arch.showTlm;$("archInterfaces").checked=state.arch.showInterfaces;
  const trail=[...state.arch.path.map(item=>item.instance||item.type),state.arch.instance||state.arch.focus].filter(Boolean);$("archPath").textContent=trail.join(" > ");
  if(!scene){clearArchRuntime(archRuntime);$("archStatus").textContent="No topology";return}
  drawArchitecture(scene,fit);const interfaces=scene.nodes.filter(node=>node.external&&!node.contextPeer).length,boundary=scene.wires.filter(wire=>wire.boundary).length;$("archStatus").textContent=`${scene.nodes.filter(node=>!node.external&&!node.contextPeer).length} blocks | ${scene.wires.filter(wire=>wire.kind!=="virtual_interface").length} connects${boundary?` (${boundary} parent)`:""} | ${interfaces} interfaces`;
  if(fit)setTimeout(()=>fitArchitecture(true),40);
}
function selectArchitectureNode(item,rerender=true){const component=ARCH.components?.[item.type]||{},known=symbolByName.get(item.type)||{},symbol={...known,name:item.type||item.instance,role:item.role||component.role||known.role,base:component.base||known.base,file:component.file||known.file,line:component.line||known.line};state.selected=symbol;state.arch.selectedUid=item.uid;state.arch.selectedWire=null;const configRelations=(item.configItems||[]).map(config=>({kind:config.relation,source:config.declared_in,target:config.type,instance:config.instance,file:config.file,line:config.line})),edge=item.edge?{kind:item.edge.relation,source:item.edge.declared_in,target:item.type,instance:item.edge.instance||item.instance,file:item.edge.file,line:item.edge.line}:item.access?{kind:`config_db_${item.access.operation}`,source:item.owners?.[0]?.type||item.access.declared_in,target:item.access.field,file:item.access.file,line:item.access.line}:null,seen=new Set(),rels=[...configRelations,...(!configRelations.length&&edge?[edge]:[]),...(relationsByName.get(item.type)||[])].filter(rel=>{const key=relationKey(rel);if(seen.has(key))return false;seen.add(key);return true}).slice(0,120),file=edge?.file||component.file||known.file,line=edge?.line||component.line||known.line,objectNames=(item.configItems||[]).map(config=>config.instance||config.type),objectRow=objectNames.length?`<div>objects</div><div>${esc(objectNames.join(", "))}</div>`:"";$("detail").innerHTML=`<div class="detail-name">${esc(item.instance||item.type)}</div><div class="kv"><div>type</div><div>${esc(item.type||"")}</div><div>role</div><div>${esc(item.role||component.role||"")}</div><div>base</div><div>${esc(component.base||known.base||"")}</div>${objectRow}<div>children</div><div>${esc(component.child_count||0)} (${esc(component.inherited_child_count||0)} inherited)</div><div>ports</div><div>${esc(component.port_count||0)}</div><div>connects</div><div>${esc(component.connection_count||0)}</div><div>file</div><div>${esc(file||"")}${line?`:${line}`:""}</div></div>`;renderRelations(rels);showLocation(file,line,item.instance||item.type);if(rerender)renderArchitecture(false)}
function selectArchitectureWire(wire){
  state.arch.selectedWire=wire.uid;state.arch.selectedUid=null;
  const relation=archWireRelation(wire),source=wire.sourceEndpoint||{},target=wire.targetEndpoint||{};state.activeRelation=relationKey(relation);
  $("detail").innerHTML=`<div class="detail-name">${esc(wire.kind)}</div><div class="kv"><div>context</div><div>${esc(wire.context||"")}</div><div>source</div><div>${esc(wire.lhs||"")}</div><div>source port</div><div>${esc(source.port||"")} | ${esc(source.direction||"")}</div><div>target</div><div>${esc(wire.rhs||"")}</div><div>target port</div><div>${esc(target.port||"")} | ${esc(target.direction||"")}</div><div>type</div><div>${esc(source.port_type||target.port_type||wire.family||"")}</div><div>file</div><div>${esc(wire.file||"")}${wire.line?`:${wire.line}`:""}</div></div>`;
  renderRelations([relation]);showLocation(wire.file,wire.line,`${wire.kind}: ${wire.lhs} -> ${wire.rhs}`);renderArchitecture(false);
}
function focusArchitecture(item){
  archRuntime.motion="forward";
  const ancestors=[];for(let cursor=item.parentNode;cursor;cursor=cursor.parentNode)ancestors.unshift(cursor);
  ancestors.forEach(node=>state.arch.path.push({type:node.type,instance:node.instanceAliases?.[0]||node.instance||node.type,edge:node.edge||null}));
  state.arch.focus=item.type;state.arch.instance=item.instanceAliases?.[0]||item.instance||item.type;state.arch.edge=item.edge||null;state.arch.selectedUid=null;state.arch.selectedWire=null;renderArchitecture(true);
}
function backArchitecture(){const parent=state.arch.path.pop();if(!parent)return;archRuntime.motion="back";state.arch.focus=parent.type;state.arch.instance=parent.instance;state.arch.edge=parent.edge;state.arch.selectedUid=null;state.arch.selectedWire=null;renderArchitecture(true)}
function fitArchitecture(animate=true){
  if(!archRuntime.bound||state.view!=="architecture")return;
  const svgNode=archRuntime.svg.node(),layerNode=archRuntime.layer.node(),rect=svgNode.getBoundingClientRect();if(!rect.width||!rect.height)return;
  let bounds;try{bounds=layerNode.getBBox()}catch(_error){return}if(!bounds.width&&!bounds.height)return;
  const focused=state.arch.path.length>0,compact=compactArchitecture(),padding=compact?(focused?22:18):(focused?86:42),maxScale=compact?1.05:(focused?1.15:1.35),scale=Math.max(.16,Math.min(maxScale,Math.min((rect.width-padding*2)/Math.max(bounds.width,1),(rect.height-padding*2)/Math.max(bounds.height,1)))),x=rect.width/2-scale*(bounds.x+bounds.width/2),y=rect.height/2-scale*(bounds.y+bounds.height/2),transform=d3.zoomIdentity.translate(x,y).scale(scale),target=animate&&!archRuntime.reducedMotion?archRuntime.svg.transition().duration(480).ease(d3.easeCubicOut):archRuntime.svg;
  target.call(archRuntime.zoom.transform,transform);
}
function selectName(name){const symbol=symbolByName.get(name)||{name,role:"external"};state.selected=symbol;renderDetail(symbol);if(state.view==="architecture")renderArchitecture();if(state.view==="wiki"){renderNodeList(state.graph.nodes);drawGraph()}}
function clearSelection(){state.selected=null;state.activeRelation=null;state.arch.selectedUid=null;state.arch.selectedWire=null;$("detail").innerHTML='<div class="muted">Select a node, connection, or relation.</div>';$("relations").innerHTML="";$("preview").innerHTML='<div class="muted">No source selected.</div>';if(state.view==="architecture")renderArchitecture(false);if(state.view==="wiki"){renderNodeList(state.graph.nodes);drawGraph()}}
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
function renderTlmContexts(){const options=[`<option value="">All contexts (${TLM_CONNECTIONS.length})</option>`,...TLM_CONTEXTS.map(([context,count])=>`<option value="${esc(context)}">${esc(context)} | ${count}</option>`)];$("tlmContext").innerHTML=options.join("");$("tlmContext").value=state.tlmContext}
function tlmEndpointPath(endpoint){return(endpoint?.instance_path?.length?endpoint.instance_path:endpoint?.requested_path||[]).map(String)}
function tlmHierarchy(connection,endpoint){const parts=[connection.context||"global",...tlmEndpointPath(endpoint)].filter(Boolean);return parts.filter((part,index)=>index===0||part!==parts[index-1]).join(" > ")}
function tlmConnectionRelation(item){return{...item,source:item.lhs,target:item.rhs}}
const TLM_NODE_W=310,TLM_HEADER_H=70,TLM_PORT_H=34,TLM_NODE_GAP=24,TLM_COL_GAP=240;
function buildTlmScene(connections){
  const maps={source:new Map(),target:new Map()};
  const addEndpoint=(side,item,endpoint)=>{
    const path=tlmEndpointPath(endpoint),ownerType=endpoint?.owner_type||item.context||"unknown",key=[side,item.context,path.join("."),ownerType].join("|"),groups=maps[side];
    let group=groups.get(key);if(!group){group={key,side,context:item.context,path,instance:path[path.length-1]||"self",ownerType,role:endpoint?.owner_role||ARCH.components?.[ownerType]?.role||"component",hierarchy:tlmHierarchy(item,endpoint),rowByKey:new Map(),order:item._tlm_index};groups.set(key,group)}
    group.order=Math.min(group.order,item._tlm_index);const rowKey=[endpoint?.port,endpoint?.direction,endpoint?.port_type].join("|"),row=group.rowByKey.get(rowKey)||{key:`${key}|${rowKey}`,endpoint,connections:[],order:item._tlm_index};if(!group.rowByKey.has(rowKey))group.rowByKey.set(rowKey,row);row.connections.push(item);row.order=Math.min(row.order,item._tlm_index);
  };
  connections.forEach(item=>{addEndpoint("source",item,item.source_endpoint);addEndpoint("target",item,item.target_endpoint)});
  const prepare=side=>[...maps[side].values()].map(group=>{group.rows=[...group.rowByKey.values()].sort((a,b)=>a.order-b.order||String(a.endpoint?.port).localeCompare(String(b.endpoint?.port)));group.h=TLM_HEADER_H+group.rows.length*TLM_PORT_H+8;return group}).sort((a,b)=>a.order-b.order||a.hierarchy.localeCompare(b.hierarchy));
  const sources=prepare("source"),targets=prepare("target"),total=groups=>groups.reduce((sum,group)=>sum+group.h,0)+Math.max(0,groups.length-1)*TLM_NODE_GAP,leftTotal=total(sources),rightTotal=total(targets),contentHeight=Math.max(320,leftTotal,rightTotal),leftX=62,rightX=leftX+TLM_NODE_W+TLM_COL_GAP,top=102,width=rightX+TLM_NODE_W+62,height=top+contentHeight+46;
  const place=(groups,x,totalHeight)=>{let y=top+(contentHeight-totalHeight)/2;groups.forEach(group=>{group.x=x;group.y=y;group.rows.forEach((row,index)=>{row.x=x;row.y=y+TLM_HEADER_H+index*TLM_PORT_H;row.side=group.side;row.group=group});y+=group.h+TLM_NODE_GAP})};place(sources,leftX,leftTotal);place(targets,rightX,rightTotal);
  const anchors={source:new Map(),target:new Map()};[...sources,...targets].forEach(group=>group.rows.forEach(row=>row.connections.forEach(item=>anchors[group.side].set(item._key,{x:group.side==="source"?group.x+TLM_NODE_W:group.x,y:row.y+TLM_PORT_H/2,row,group}))));
  const edges=connections.map((connection,index)=>({connection,index,source:anchors.source.get(connection._key),target:anchors.target.get(connection._key)})).filter(edge=>edge.source&&edge.target);
  return{sources,targets,groups:[...sources,...targets],edges,width,height,contextLabel:state.tlmContext||"All indexed contexts"};
}
function tlmCurve(edge){const sx=edge.source.x,sy=edge.source.y,tx=edge.target.x,ty=edge.target.y,middle=(sx+tx)/2+((edge.index%7)-3)*8;return`M${sx},${sy} C${middle},${sy} ${middle},${ty} ${tx},${ty}`}
const tlmRuntime={bound:false,svg:null,layer:null,zoom:null,reducedMotion:window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches};
function ensureTlmRuntime(){if(tlmRuntime.bound)return;tlmRuntime.svg=d3.select("#tlmGraph");tlmRuntime.layer=d3.select("#tlmLayer");tlmRuntime.zoom=d3.zoom().scaleExtent([.18,2.5]).on("zoom",event=>tlmRuntime.layer.attr("transform",event.transform));tlmRuntime.svg.call(tlmRuntime.zoom).on("dblclick.zoom",null).on("click",event=>{if(!event.defaultPrevented&&event.target===tlmRuntime.svg.node())clearTlmSelection()});tlmRuntime.bound=true}
function drawTlmPortMark(rowSelection,side){rowSelection.each(function(row){const mark=d3.select(this),x=side==="source"?TLM_NODE_W:0,y=TLM_PORT_H/2,direction=row.endpoint?.direction||"port",klass=`tlm-port-mark ${row.endpoint?.family==="seq_item"?"seq_item_connect":"tlm_connect"} direction-${direction}`;if(direction==="port")mark.append("circle").attr("class",klass).attr("cx",x).attr("cy",y).attr("r",5);else mark.append("rect").attr("class",klass).attr("x",x-4.5).attr("y",y-4.5).attr("width",9).attr("height",9).attr("rx",direction==="implementation"?1:0).attr("transform",direction==="export"?`rotate(45 ${x} ${y})`:null)})}
function drawTlmScene(scene){
  ensureTlmRuntime();const layer=tlmRuntime.layer;layer.selectAll("*").remove();
  layer.append("rect").attr("class","tlm-frame").attr("x",18).attr("y",18).attr("width",scene.width-36).attr("height",scene.height-36).attr("rx",6).style("pointer-events","none");
  layer.append("text").attr("class","tlm-frame-title").attr("x",38).attr("y",46).text(scene.contextLabel);layer.append("text").attr("class","tlm-frame-meta").attr("x",38).attr("y",65).text(`${scene.edges.length} connect_phase connection(s)`);layer.append("text").attr("class","tlm-column-title").attr("x",62).attr("y",88).text("SOURCE PORTS");layer.append("text").attr("class","tlm-column-title").attr("x",scene.targets[0]?.x||658).attr("y",88).text("TARGET EXPORTS / IMPLEMENTATIONS");
  const wireLayer=layer.append("g").attr("class","tlm-wires"),halo=wireLayer.selectAll(".tlm-wire-halo").data(scene.edges).enter().append("path").attr("class","tlm-wire-halo").attr("data-tlm-edge",edge=>edge.connection._key).attr("d",tlmCurve),wires=wireLayer.selectAll(".tlm-wire").data(scene.edges).enter().append("path").attr("class",edge=>`tlm-wire ${edge.connection.kind||"tlm_connect"}`).attr("data-tlm-edge",edge=>edge.connection._key).attr("d",tlmCurve).attr("marker-end",edge=>edge.connection.kind==="seq_item_connect"?"url(#tlmSeqArrow)":"url(#tlmArrow)"),hits=wireLayer.selectAll(".tlm-wire-hit").data(scene.edges).enter().append("path").attr("class","tlm-wire-hit").attr("d",tlmCurve);
  hits.append("title").text(edge=>`${edge.connection.lhs} -> ${edge.connection.rhs}`);hits.on("mouseenter",(_event,edge)=>{state.tlm.hoverKey=edge.connection._key;updateTlmHighlight()}).on("mouseleave",()=>{state.tlm.hoverKey=null;updateTlmHighlight()}).on("click",(event,edge)=>{event.stopPropagation();selectTlmConnection(edge.connection)});
  const ownerLayer=layer.append("g").attr("class","tlm-owners"),owners=ownerLayer.selectAll(".tlm-owner").data(scene.groups).enter().append("g").attr("class","tlm-owner").attr("transform",group=>`translate(${group.x},${group.y})`).on("click",(event,group)=>{event.stopPropagation();if(group.ownerType)selectName(group.ownerType)});
  owners.append("rect").attr("class","tlm-owner-box").attr("width",TLM_NODE_W).attr("height",group=>group.h).attr("rx",6);owners.append("rect").attr("class","tlm-owner-strip").attr("width",5).attr("height",group=>group.h).attr("rx",2).attr("fill",group=>color(group.role));owners.append("line").attr("class","tlm-owner-rule").attr("x1",5).attr("x2",TLM_NODE_W).attr("y1",TLM_HEADER_H).attr("y2",TLM_HEADER_H);owners.append("text").attr("class","tlm-owner-name").attr("x",15).attr("y",22).text(group=>shortLabel(group.instance,34));owners.append("text").attr("class","tlm-owner-type").attr("x",15).attr("y",40).text(group=>shortLabel(group.ownerType,42));owners.append("text").attr("class","tlm-owner-path").attr("x",15).attr("y",57).text(group=>shortLabel(group.hierarchy,47));owners.append("title").text(group=>`${group.hierarchy}\n${group.ownerType}`);
  owners.each(function(group){const rows=d3.select(this).selectAll(".tlm-port-row").data(group.rows).enter().append("g").attr("class","tlm-port-row").attr("data-tlm-keys",row=>row.connections.map(item=>item._key).join(" ")).attr("transform",(_row,index)=>`translate(0,${TLM_HEADER_H+index*TLM_PORT_H})`).on("mouseenter",(_event,row)=>{state.tlm.hoverKey=row.connections[0]?._key||null;updateTlmHighlight()}).on("mouseleave",()=>{state.tlm.hoverKey=null;updateTlmHighlight()}).on("click",(event,row)=>{event.stopPropagation();if(row.connections[0])selectTlmConnection(row.connections[0])});rows.append("rect").attr("class","tlm-port-row-bg").attr("x",5).attr("width",TLM_NODE_W-10).attr("height",TLM_PORT_H);rows.append("line").attr("class","tlm-port-rule").attr("x1",5).attr("x2",TLM_NODE_W-5).attr("y1",TLM_PORT_H).attr("y2",TLM_PORT_H);rows.append("text").attr("class","tlm-port-name").attr("x",14).attr("y",21).text(row=>shortLabel(row.endpoint?.port||row.endpoint?.expression,28));rows.append("text").attr("class","tlm-port-direction").attr("x",TLM_NODE_W-13).attr("y",21).text(row=>row.endpoint?.direction==="implementation"?"imp":row.endpoint?.direction||"");rows.append("title").text(row=>`${row.endpoint?.expression||row.endpoint?.port}\n${row.endpoint?.port_type||""}`);drawTlmPortMark(rows,group.side)});
  if(!tlmRuntime.reducedMotion&&state.view==="tlm"){wires.each(function(){const path=d3.select(this),length=this.getTotalLength();path.attr("stroke-dasharray",`${length} ${length}`).attr("stroke-dashoffset",length).transition().duration(620).ease(d3.easeCubicOut).attr("stroke-dashoffset",0).on("end",()=>path.attr("stroke-dasharray",null).attr("stroke-dashoffset",null))});owners.attr("opacity",0).transition().duration(420).delay((_group,index)=>Math.min(index*24,180)).ease(d3.easeCubicOut).attr("opacity",1)}
  updateTlmHighlight();
}
function updateTlmHighlight(){if(!tlmRuntime.bound)return;const active=state.tlm.hoverKey||state.tlm.selectedKey,selected=state.tlm.selectedKey,hover=state.tlm.hoverKey;tlmRuntime.layer.selectAll(".tlm-wire-halo,.tlm-wire").classed("dim",edge=>Boolean(active&&edge.connection._key!==active)).classed("hot",edge=>Boolean(hover&&edge.connection._key===hover)).classed("selected",edge=>Boolean(selected&&edge.connection._key===selected));tlmRuntime.layer.selectAll(".tlm-port-row").classed("hot",row=>Boolean(hover&&row.connections.some(item=>item._key===hover))).classed("selected",row=>Boolean(selected&&row.connections.some(item=>item._key===selected)))}
function selectTlmConnection(item){state.tlm.selectedKey=item._key;state.tlm.hoverKey=null;const source=item.source_endpoint||{},target=item.target_endpoint||{},relation=tlmConnectionRelation(item),transactions=[...(source.transaction_types||[]),...(target.transaction_types||[])].filter((value,index,values)=>value&&values.indexOf(value)===index);state.activeRelation=relationKey(relation);$("detail").innerHTML=`<div class="detail-name">${esc(item.kind||"tlm_connect")}</div><div class="kv"><div>context</div><div>${esc(item.context||"")}</div><div>source path</div><div>${esc(tlmHierarchy(item,source))}</div><div>source port</div><div>${esc(source.port||item.lhs||"")} | ${esc(source.direction||"")}</div><div>source type</div><div>${esc(source.owner_type||"")}</div><div>target path</div><div>${esc(tlmHierarchy(item,target))}</div><div>target port</div><div>${esc(target.port||item.rhs||"")} | ${esc(target.direction||"")}</div><div>target type</div><div>${esc(target.owner_type||"")}</div><div>transaction</div><div>${esc(transactions.join(", ")||source.port_type||target.port_type||"")}</div><div>file</div><div>${esc(item.file||"")}${item.line?`:${item.line}`:""}</div></div>`;renderRelations([relation]);showLocation(item.file,item.line,`${item.kind}: ${item.lhs} -> ${item.rhs}`);updateTlmHighlight()}
function clearTlmSelection(){state.tlm.selectedKey=null;state.tlm.hoverKey=null;state.selected=null;state.activeRelation=null;$("detail").innerHTML='<div class="muted">Select a node, connection, or relation.</div>';$("relations").innerHTML="";$("preview").innerHTML='<div class="muted">No source selected.</div>';updateTlmHighlight()}
function fitTlm(animate=true){ensureTlmRuntime();if(state.view!=="tlm")return;const svgNode=tlmRuntime.svg.node(),layerNode=tlmRuntime.layer.node(),rect=svgNode.getBoundingClientRect();if(!rect.width||!rect.height)return;let bounds;try{bounds=layerNode.getBBox()}catch(_error){return}if(!bounds.width&&!bounds.height)return;const compact=rect.width<760,padding=compact?18:38,maxScale=compact?1.05:1.22,scale=Math.max(.14,Math.min(maxScale,Math.min((rect.width-padding*2)/Math.max(bounds.width,1),(rect.height-padding*2)/Math.max(bounds.height,1)))),x=rect.width/2-scale*(bounds.x+bounds.width/2),y=rect.height/2-scale*(bounds.y+bounds.height/2),transform=d3.zoomIdentity.translate(x,y).scale(scale),target=animate&&!tlmRuntime.reducedMotion?tlmRuntime.svg.transition().duration(480).ease(d3.easeCubicOut):tlmRuntime.svg;target.call(tlmRuntime.zoom.transform,transform)}
function renderTlm(){ensureTlmRuntime();const query=state.query,connections=TLM_CONNECTIONS.filter(item=>(!state.tlmContext||item.context===state.tlmContext)&&(!state.tlmKind||item.kind===state.tlmKind)&&(!query||text(item).includes(query))&&(!state.role||item.source_endpoint?.owner_role===state.role||item.target_endpoint?.owner_role===state.role||ARCH.components?.[item.context]?.role===state.role));if(state.tlm.selectedKey&&!connections.some(item=>item._key===state.tlm.selectedKey))state.tlm.selectedKey=null;$("tlmEmpty").hidden=connections.length>0;$("tlmLegend").style.display=connections.length?"flex":"none";if(!connections.length){tlmRuntime.layer.selectAll("*").remove();$("tlmStatus").textContent="0 connections";return}const scene=buildTlmScene(connections);drawTlmScene(scene);$("tlmStatus").textContent=`${connections.length} connections | ${scene.groups.length} component endpoints`;if(state.view==="tlm")setTimeout(()=>fitTlm(false),0)}
function localCodeItems(query=""){const symbols=(DATA.symbols||[]).filter(item=>(!state.role||item.role===state.role)&&(!query||text(item).includes(query))),files=state.role?[]:(DATA.files||[]).filter(item=>!query||item.path.toLowerCase().includes(query));return[...symbols.slice(0,220).map(item=>({type:item.kind,title:item.name,file:item.file,line:item.line})),...files.slice(0,120).map(item=>({type:"file",title:item.path,file:item.path,line:1}))]}
function renderCodeIndex(items=localCodeItems(state.query)){$("codeResults").innerHTML=items.map((item,index)=>`<button class="code-result" data-code-index="${index}"><strong>${esc(item.title)}</strong><span>${esc(item.type)} | ${esc(item.file||"")}${item.line?`:${item.line}`:""}</span></button>`).join("")||'<div class="empty">No matches.</div>';$("codeResults").querySelectorAll("[data-code-index]").forEach(button=>button.onclick=()=>{document.querySelectorAll(".code-result").forEach(x=>x.classList.toggle("active",x===button));const item=items[Number(button.dataset.codeIndex)];loadSource(item.file,item.line||1,item.title)})}
async function runCodeSearch(){const query=$("codeSearch").value.trim();if(!query){renderCodeIndex();return}if(state.server){$("codeResults").innerHTML='<div class="empty">Searching...</div>';try{const response=await fetch(`/api/search?q=${encodeURIComponent(query)}`),items=await response.json();renderCodeIndex(items)}catch(error){$("codeResults").innerHTML=`<div class="empty">${esc(error.message)}</div>`}}else renderCodeIndex(localCodeItems(query.toLowerCase()))}
init();
</script>
</body>
</html>'''


def render_html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</script>", "<\\/script>")
    d3_source = D3_PATH.read_text(encoding="utf-8").replace("</script>", "<\\/script>")
    return HTML_TEMPLATE.replace("__D3__", d3_source).replace("__DATA__", payload)


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
