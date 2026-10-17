"""可交互星盘(纯计算 + 一段自带的 HTML/JS, 不依赖 Streamlit)
Python 这边负责: 预先算好一串时间点("帧")的星体位置、宫头、宫位、尊贵状态;
网页这边(JS)负责: 画盘、算相位、悬停/点击、时间滑块和播放动画。
所有数据都嵌在一个 HTML 字符串里, 放进 st.components.v1.html 即可, 不需要服务器来回通信。
"""
import json
from calendar import monthrange
from datetime import timedelta

import core_astro as ca

# 步长: 名称 -> (类型, 数量)。"m"=分钟, "M"=日历月(按日历加减, 不是固定天数)
STEPS = {"1分钟": ("m", 1), "10分钟": ("m", 10), "1小时": ("m", 60), "1天": ("m", 1440),
         "1个月": ("M", 1), "1年": ("M", 12)}
EXTRA = ["凯龙星", "北交点", "南交点", "莉莉丝", "福点"]


def shift(dt, kind, n, k):
    """把 dt 向后(k>0)或向前(k<0)移 k 个步长。"""
    if kind == "m":
        return dt + timedelta(minutes=n * k)
    months = dt.year * 12 + (dt.month - 1) + n * k
    y, m = divmod(months, 12)
    m += 1
    return dt.replace(year=y, month=m, day=min(dt.day, monthrange(y, m)[1]))


def make_frames(dt, lon, lat, tz, hsys, step="10分钟", half=60):
    """以 dt 为中心, 前后各 half 帧, 共 2*half+1 帧。每帧用 core_astro.compute 现算。"""
    kind, n = STEPS[step]
    frames = []
    for k in range(-half, half + 1):
        t = shift(dt, kind, n, k)
        pts, cusps, asc, mc, day = ca.compute(t, lon, lat, tz, hsys)
        p = {}
        for name, v in pts.items():
            dig = ca.dignity(name, v["sign"]) if name in ca.MAIN else ""
            p[name] = [round(v["lon"], 4), 1 if v["retro"] else 0, v["house"], dig]
        frames.append({"t": t.strftime("%Y-%m-%d %H:%M"), "asc": round(asc, 4), "mc": round(mc, 4),
                       "cusps": [round(c, 4) for c in cusps], "p": p})
    return frames


def wheel_html(frames, start, step, hsys):
    glyph = {name: g for name, g, _ in ca.BODIES}
    glyph.update({"南交点": "☋", "福点": "⊗", "上升": "AC", "天顶": "MC"})
    data = {
        "frames": frames, "start": start, "step": step, "hsys": hsys,
        "signs": ca.SIGNS, "sglyph": ca.SGLYPH, "elemColor": ca.ELEM_COLOR, "elemName": ca.ELEM_NAME,
        "modeName": ca.MODE_NAME, "ruler": ca.RULER, "main": ca.MAIN, "extra": EXTRA, "glyph": glyph,
        "aspects": [[nm, sym, ang, orb, col] for nm, sym, ang, orb, col in ca.ASPECTS],
    }
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return _TEMPLATE.replace("__DATA__", blob)


_TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{margin:0;padding:8px;background:#fff;color:#222;font-size:14px;
 font-family:"Segoe UI Symbol","Noto Sans Symbols","Apple Symbols","PingFang SC","Microsoft YaHei",sans-serif}
button,select{font:inherit}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px}
.bar button{min-width:40px;height:36px;border:1px solid #bbb;border-radius:8px;background:#f6f6f6;cursor:pointer}
.bar button:active{background:#e4e4e4}
.bar input[type=range]{flex:1 1 220px;min-width:160px;height:28px}
.tm{font-weight:700;min-width:140px}
.sub{color:#777;font-size:12px}
.opts{display:flex;flex-wrap:wrap;gap:6px 14px;margin-bottom:8px;font-size:13px;align-items:center}
.opts label{cursor:pointer;white-space:nowrap}
.chip{display:inline-block;padding:1px 8px;border-radius:10px;border:1px solid;font-size:12px}
#main{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start}
#left{flex:1 1 440px;min-width:300px}
#right{flex:1 1 320px;min-width:280px;max-height:700px;overflow:auto;border:1px solid #e2e2e2;border-radius:10px}
#svgbox svg{width:100%;max-width:680px;display:block;margin:0 auto}
.tabs{display:flex;position:sticky;top:0;background:#fafafa;border-bottom:1px solid #e2e2e2}
.tabs div{flex:1;text-align:center;padding:8px 2px;cursor:pointer;color:#666}
.tabs div.on{color:#111;font-weight:700;border-bottom:2px solid #333}
#panel{padding:10px}
table{border-collapse:collapse;width:100%;font-size:13px}
td,th{border-bottom:1px solid #eee;padding:4px 3px;text-align:left}
th{color:#777;font-weight:600;font-size:12px}
tr.r{cursor:pointer}tr.r:hover{background:#f3f7ff}tr.r.sel{background:#fff3cd}
.card{padding:6px 2px}.bg{font-size:40px;line-height:1}.nm{font-size:20px;font-weight:700}
.kv{margin:3px 0}.kv b{color:#555;font-weight:600;margin-right:6px}
.pl{cursor:pointer}.pl .ring{fill:transparent;stroke:none}
.pl.hov .ring{fill:rgba(60,130,220,.18)}.pl.sel .ring{fill:rgba(255,190,0,.3);stroke:#333;stroke-width:1.6}
#tip{position:fixed;display:none;pointer-events:none;background:rgba(30,30,30,.92);color:#fff;
 padding:6px 9px;border-radius:7px;font-size:12.5px;line-height:1.5;z-index:9;max-width:230px}
.grid td,.grid th{border:1px solid #eee;text-align:center;padding:2px;font-size:12px;min-width:26px}
</style></head><body>
<div class="bar">
 <button id="b0" title="回到出生时刻">⏮</button><button id="b1" title="后退一步">◀</button>
 <button id="bp" title="播放/暂停">▶</button><button id="b2" title="前进一步">▶|</button>
 <input type="range" id="sl">
 <select id="sp" title="播放速度"><option value="1">慢</option><option value="2" selected>中</option>
  <option value="4">快</option><option value="8">很快</option></select>
</div>
<div class="bar"><span class="tm" id="tm"></span><span class="sub" id="off"></span></div>
<div class="opts" id="opts"></div>
<div id="main">
 <div id="left"><div id="svgbox"></div></div>
 <div id="right"><div class="tabs" id="tabs"></div><div id="panel"></div></div>
</div>
<div id="tip"></div>
<script>
const D=__DATA__;
const $=s=>document.querySelector(s), V="︎";
const S=680,cx=340,cy=340,R0=320,R1=280,R2=150;
const MAIN=D.main, EXTRA=D.extra, GL=D.glyph;
let idx=D.start, sel=null, hov=null, timer=null, tab="info";
const O={asp:true,extra:true,deg:true,aries:false,hide:{}};
const NOTASP=new Set(["南交点"]);
const pad=n=>String(n).padStart(2,"0");
const dms=L=>{const d=((L%30)+30)%30;return Math.floor(d)+"°"+pad(Math.floor((d%1)*60))+"'"};
const orbS=o=>Math.floor(o)+"°"+pad(Math.floor((o%1)*60))+"'";
const F=()=>D.frames[idx];
const sgn=L=>Math.floor((((L%360)+360)%360)/30);
function ang(L){return O.aries?(((L%360)+360)%360):((((L-F().asc)%360)+360)%360)}
function pos(L,r){const a=ang(L)*Math.PI/180;return [cx-r*Math.cos(a),cy+r*Math.sin(a)]}
function dig(n){return F().p[n][3]||""}
function shown(){const p=F().p;return Object.keys(p).filter(n=>{
 if(n==="上升"||n==="天顶")return false;
 if(EXTRA.includes(n))return O.extra;return true})}
function aspects(){
 const p=F().p, ns=MAIN.filter(n=>p[n]).concat(["上升","天顶"]);
 if(O.extra)EXTRA.forEach(n=>{if(p[n]&&!NOTASP.has(n))ns.push(n)});
 const out=[];
 for(let i=0;i<ns.length;i++)for(let j=i+1;j<ns.length;j++){
  const a=ns[i],b=ns[j];
  if(a==="上升"&&b==="天顶")continue;
  let d=Math.abs(p[a][0]-p[b][0])%360;d=Math.min(d,360-d);
  for(const A of D.aspects){const o=Math.abs(d-A[2]);
   if(o<=A[3])out.push({a,b,nm:A[0],sym:A[1],ang:A[2],orb:o,col:A[4]})}}
 return out}
function spread(items,gap){
 items=items.slice().sort((x,y)=>x[1]-y[1]);const disp=items.map(x=>x[1]);const n=items.length;
 for(let it=0;it<40;it++){let mv=false;
  for(let i=0;i<n;i++){const j=(i+1)%n;const d=(((disp[j]-disp[i])%360)+360)%360;
   if(d<gap&&n>1){const q=(gap-d)/2;disp[i]-=q;disp[j]+=q;mv=true}}
  if(!mv)break}
 const r={};items.forEach((x,i)=>{r[x[0]]=((disp[i]%360)+360)%360});return r}

function svg(){
 const f=F(), p=f.p, asps=aspects(), o=[];
 for(let i=0;i<12;i++){
  const a0=i*30,a1=a0+30,col=D.elemColor[i%4];
  const [x0,y0]=pos(a0,R0),[x1,y1]=pos(a1,R0),[x2,y2]=pos(a1,R1),[x3,y3]=pos(a0,R1);
  o.push(`<path d="M${x0},${y0} A${R0},${R0} 0 0 0 ${x1},${y1} L${x2},${y2} A${R1},${R1} 0 0 1 ${x3},${y3} Z" fill="${col}" fill-opacity=".14" stroke="#555" stroke-opacity=".5"/>`);
  const [gx,gy]=pos(a0+15,(R0+R1)/2);
  o.push(`<text x="${gx}" y="${gy}" text-anchor="middle" dominant-baseline="central" font-size="26" fill="${col}">${D.sglyph[i]}${V}</text>`)}
 [R1,R2].forEach(r=>o.push(`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#555" stroke-opacity=".5"/>`));
 f.cusps.forEach((cu,i)=>{
  const [x0,y0]=pos(cu,R2),[x1,y1]=pos(cu,R1),w=[0,3,6,9].includes(i)?1.8:.8;
  o.push(`<line x1="${x0}" y1="${y0}" x2="${x1}" y2="${y1}" stroke="#555" stroke-opacity=".55" stroke-width="${w}"/>`);
  const nx=f.cusps[(i+1)%12],mid=cu+((((nx-cu)%360)+360)%360)/2,[tx,ty]=pos(mid,R2+16);
  o.push(`<text x="${tx}" y="${ty}" text-anchor="middle" dominant-baseline="central" font-size="13" fill="#555">${i+1}</text>`)});
 if(O.asp)asps.forEach(a=>{
  if(a.col===null||O.hide[a.nm])return;
  const [x0,y0]=pos(p[a.a][0],R2-2),[x1,y1]=pos(p[a.b][0],R2-2),op=Math.max(.25,1-a.orb/8);
  o.push(`<line class="asp" data-a="${a.a}" data-b="${a.b}" data-o="${op}" x1="${x0}" y1="${y0}" x2="${x1}" y2="${y1}" stroke="${a.col}" stroke-width="1.3" stroke-opacity="${op}"/>`)});
 const names=shown(), disp=spread(names.map(n=>[n,p[n][0]]),8);
 names.forEach(n=>{
  const L=p[n][0],Dd=disp[n];
  const [x0,y0]=pos(L,R1),[x1,y1]=pos(L,R1-8);
  o.push(`<line x1="${x0}" y1="${y0}" x2="${x1}" y2="${y1}" stroke="#222"/>`);
  const [gx,gy]=pos(Dd,R1-34);
  if(Math.abs((((Dd-L+540)%360)+360)%360-180)>1){const [qx,qy]=pos(L,R1-8),[wx,wy]=pos(Dd,R1-20);
   o.push(`<line x1="${qx}" y1="${qy}" x2="${wx}" y2="${wy}" stroke="#999" stroke-width=".7"/>`)}
  let g=`<g class="pl" data-n="${n}"><circle class="ring" cx="${gx}" cy="${gy}" r="17"/>`+
   `<text x="${gx}" y="${gy}" text-anchor="middle" dominant-baseline="central" font-size="24" fill="#222">${GL[n]}${V}</text>`;
  if(O.deg){const [dx,dy]=pos(Dd,R1-64);
   g+=`<text x="${dx}" y="${dy}" text-anchor="middle" dominant-baseline="central" font-size="11" fill="#444">${dms(L)}${p[n][1]?"ᴿ":""}</text>`}
  o.push(g+"</g>")});
 [["AC",f.asc],["DC",f.asc+180],["MC",f.mc],["IC",f.mc+180]].forEach(([nm,L])=>{
  const [tx,ty]=pos(L,R0+14);
  o.push(`<text x="${tx}" y="${ty}" text-anchor="middle" dominant-baseline="central" font-size="12" font-weight="700" fill="#222">${nm}</text>`)});
 return `<svg viewBox="-18 -4 ${S+36} ${S+8}" xmlns="http://www.w3.org/2000/svg">${o.join("")}</svg>`}

function focus(){
 const f=hov||sel;
 document.querySelectorAll(".asp").forEach(e=>{
  const on=!f||e.dataset.a===f||e.dataset.b===f;
  e.style.opacity=f?(on?1:.07):1;e.style.strokeWidth=f&&on?2.4:1.3});
 document.querySelectorAll(".pl").forEach(e=>{
  e.classList.toggle("sel",e.dataset.n===sel);e.classList.toggle("hov",e.dataset.n===hov&&hov!==sel)});
 document.querySelectorAll("tr.r").forEach(e=>e.classList.toggle("sel",e.dataset.n===sel))}

function info(n){const p=F().p[n],L=p[0],s=sgn(L);return {n,L,s,retro:p[1],house:p[2],dig:p[3]}}
function line(n){const i=info(n);return `${D.sglyph[i.s]}${V} ${D.signs[i.s]} ${dms(i.L)}${i.retro?" 逆行":""}`}
function mine(n,asps){return asps.filter(a=>a.a===n||a.b===n).sort((x,y)=>x.orb-y.orb)}
function asp_li(a,n){const other=a.a===n?a.b:a.a;
 return `<tr class="r" data-n="${other}"><td>${a.sym}${V} ${a.nm}</td><td>${GL[other]}${V} ${other}</td><td>${orbS(a.orb)}</td></tr>`}

function tabInfo(){
 const asps=aspects();
 if(sel&&F().p[sel]){const i=info(sel),m=mine(sel,asps);
  let h=`<div class="card"><span class="bg">${GL[sel]}${V}</span> <span class="nm">${sel}</span>
   <div class="kv"><b>星座</b>${line(sel)}</div>
   <div class="kv"><b>元素</b>${D.elemName[i.s%4]}象 · ${D.modeName[i.s%3]}　<b>守护星</b>${D.ruler[i.s]}</div>
   <div class="kv"><b>宫位</b>${sel==="上升"||sel==="天顶"?"—":"第 "+i.house+" 宫"}${i.dig?"　<b>尊贵</b>"+i.dig:""}</div></div>`;
  h+=`<div class="kv"><b>相位</b>${m.length}个</div>`;
  if(m.length)h+="<table><tr><th>相位</th><th>对象</th><th>偏差</th></tr>"+m.map(a=>asp_li(a,sel)).join("")+"</table>";
  return h}
 const p=F().p,day=p["太阳"][2]>=7,ph=((p["月亮"][0]-p["太阳"][0])%360+360)%360;
 const phase=["新月","盈眉月","上弦月","盈凸月","满月","亏凸月","下弦月","残月"][Math.floor((ph+22.5)/45)%8];
 const el=[0,0,0,0],md=[0,0,0];MAIN.forEach(n=>{if(p[n]){const s=sgn(p[n][0]);el[s%4]++;md[s%3]++}});
 return `<div class="card"><div class="kv"><b>时刻</b>${F().t}</div>
  <div class="kv"><b>日夜盘</b>${day?"日盘":"夜盘"}　<b>月相</b>${phase}（日月夹角 ${ph.toFixed(1)}°）</div>
  <div class="kv"><b>四元素</b>${D.elemName.map((e,i)=>e+el[i]).join("　")}</div>
  <div class="kv"><b>三模式</b>${D.modeName.map((e,i)=>e+md[i]).join("　")}</div>
  <div class="kv"><b>上升</b>${line("上升")}</div><div class="kv"><b>天顶</b>${line("天顶")}</div>
  <div class="kv"><b>宫位制</b>${D.hsys}　<b>相位总数</b>${asps.length}</div>
  <p class="sub">点盘上的星体或下面表格里的一行，查看它的详细信息和相位；悬停时会高亮它的相位线。</p></div>`}
function tabPlanets(){
 const names=["上升","天顶"].concat(shown());
 return "<table><tr><th>天体</th><th>星座 度数</th><th>宫</th><th>尊贵</th></tr>"+names.map(n=>{
  const i=info(n);return `<tr class="r" data-n="${n}"><td>${GL[n]}${V} ${n}</td><td>${D.sglyph[i.s]}${V} ${D.signs[i.s]} ${dms(i.L)}${i.retro?" R":""}</td><td>${n==="上升"||n==="天顶"?"":i.house}</td><td>${i.dig}</td></tr>`}).join("")+"</table>"}
function tabHouses(){
 const f=F(),names=shown();
 return "<table><tr><th>宫</th><th>宫头</th><th>宫主星</th><th>宫内天体</th></tr>"+f.cusps.map((cu,i)=>{
  const s=sgn(cu),ins=names.filter(n=>f.p[n][2]===i+1).map(n=>GL[n]+V).join(" ");
  return `<tr><td>${i+1}</td><td>${D.sglyph[s]}${V} ${D.signs[s]} ${dms(cu)}</td><td>${D.ruler[s]}</td><td>${ins}</td></tr>`}).join("")+"</table>"}
function tabAspects(){
 const asps=aspects().filter(a=>!O.hide[a.nm]).sort((x,y)=>x.orb-y.orb);
 let h=`<div class="kv"><b>共</b>${asps.length}个（容许度：合/冲 8°，刑/拱 7°，六合 5°）</div>`;
 h+="<table><tr><th>天体 A</th><th>相位</th><th>天体 B</th><th>偏差</th></tr>"+asps.map(a=>
  `<tr class="r" data-n="${a.a}"><td>${GL[a.a]}${V} ${a.a}</td><td style="color:${a.col||"#222"}">${a.sym}${V} ${a.nm}</td><td>${GL[a.b]}${V} ${a.b}</td><td>${orbS(a.orb)}</td></tr>`).join("")+"</table>";
 const ns=MAIN.filter(n=>F().p[n]).concat(["上升","天顶"]),cell={};
 aspects().forEach(a=>{cell[a.a+"|"+a.b]=a;cell[a.b+"|"+a.a]=a});
 h+=`<p class="sub">相位格</p><table class="grid"><tr><th></th>${ns.map(n=>`<th>${GL[n]}${V}</th>`).join("")}</tr>`;
 ns.forEach((r,i)=>{h+=`<tr><th>${GL[r]}${V}</th>`+ns.map((c,j)=>{
  if(j>=i)return "<td></td>";const a=cell[r+"|"+c];
  return a?`<td style="color:${a.col||"#222"}" title="${r} ${a.nm} ${c} ${orbS(a.orb)}">${a.sym}${V}</td>`:"<td></td>"}).join("")+"</tr>"});
 return h+"</table>"}

function panel(){
 $("#panel").innerHTML={info:tabInfo,planets:tabPlanets,houses:tabHouses,aspects:tabAspects}[tab]();
 $("#tabs").innerHTML=[["info","详情"],["planets","行星"],["houses","宫位"],["aspects","相位"]]
  .map(([k,t])=>`<div class="${k===tab?"on":""}" data-t="${k}">${t}</div>`).join("")}
function render(){
 $("#svgbox").innerHTML=svg();panel();focus();
 $("#tm").textContent=F().t;
 const k=idx-D.start;$("#off").textContent=k===0?"出生时刻":(k>0?"+":"")+k+" × "+D.step;
 $("#sl").value=idx}

function setIdx(i){idx=Math.max(0,Math.min(D.frames.length-1,i));render()}
function play(on){
 if(timer){clearInterval(timer);timer=null}
 $("#bp").textContent=on?"⏸":"▶";
 if(on){const sp=+$("#sp").value;
  timer=setInterval(()=>{if(idx>=D.frames.length-1)idx=-1;setIdx(idx+1)},Math.round(800/sp))}}

// 选项
$("#opts").innerHTML=
 `<label><input type="checkbox" data-o="asp" checked> 相位线</label>
  <label><input type="checkbox" data-o="extra" checked> 凯龙/交点/莉莉丝/福点</label>
  <label><input type="checkbox" data-o="deg" checked> 度数</label>
  <label><input type="checkbox" data-o="aries"> 以白羊0°为起点（默认上升在左）</label>`+
 D.aspects.filter(a=>a[4]).map(a=>`<label><input type="checkbox" data-h="${a[0]}" checked>
  <span class="chip" style="color:${a[4]};border-color:${a[4]}">${a[1]}${V} ${a[0]}</span></label>`).join("");
$("#opts").addEventListener("change",e=>{const t=e.target;
 if(t.dataset.o)O[t.dataset.o]=t.checked;if(t.dataset.h)O.hide[t.dataset.h]=!t.checked;render()});

$("#sl").min=0;$("#sl").max=D.frames.length-1;
$("#sl").addEventListener("input",e=>{play(false);setIdx(+e.target.value)});
$("#b0").onclick=()=>{play(false);setIdx(D.start)};
$("#b1").onclick=()=>{play(false);setIdx(idx-1)};
$("#b2").onclick=()=>{play(false);setIdx(idx+1)};
$("#bp").onclick=()=>play(!timer);
$("#sp").onchange=()=>{if(timer)play(true)};
$("#tabs").addEventListener("click",e=>{if(e.target.dataset.t){tab=e.target.dataset.t;panel();focus()}});
$("#panel").addEventListener("click",e=>{const r=e.target.closest("tr.r");
 if(r){sel=r.dataset.n===sel&&tab==="planets"?null:r.dataset.n;tab=tab==="aspects"?"aspects":"info";panel();focus()}});
const box=$("#svgbox"),tip=$("#tip");
box.addEventListener("click",e=>{const g=e.target.closest(".pl");
 sel=g?(g.dataset.n===sel?null:g.dataset.n):null;if(g&&tab!=="info")tab="info";panel();focus()});
box.addEventListener("mouseover",e=>{const g=e.target.closest(".pl");
 if(g){hov=g.dataset.n;const i=info(hov),m=mine(hov,aspects()).length;
  tip.innerHTML=`<b>${GL[hov]}${V} ${hov}</b><br>${line(hov)}<br>`+
   (hov==="上升"||hov==="天顶"?"":`第 ${i.house} 宫`)+(i.dig?` · ${i.dig}`:"")+`<br>相位 ${m} 个`;
  tip.style.display="block";focus()}});
box.addEventListener("mousemove",e=>{tip.style.left=Math.min(e.clientX+14,innerWidth-240)+"px";tip.style.top=(e.clientY+14)+"px"});
box.addEventListener("mouseout",e=>{if(e.target.closest(".pl")){hov=null;tip.style.display="none";focus()}});
render();
</script></body></html>
"""
