'use strict';
let D, F, E, S, C, activeCompany='MSFT';
const selected=new Set(['NVDA','GOOGL','MSFT','META','AMZN','AAPL']);
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const bn=v=>(v/1000).toLocaleString('zh-CN',{minimumFractionDigits:1,maximumFractionDigits:1});
const pct=v=>Number(v).toFixed(1)+'%';
const series=c=>D.observations.filter(o=>o.company===c);
const latest=c=>series(c).at(-1);
const val=(id,display)=>`<button class="value" data-fact="${id}" title="查看原始披露与计算">${display??bn(F[id].value)}</button>`;
const num=(o,m)=>o.fact_ids[m]?val(o.fact_ids[m],m.includes('_revenue')||m==='capex_cfo'?pct(o.values[m]):bn(o.values[m])):'<span class="na">未拆分</span>';
const cLabel=c=>`<span class="dot" style="background:${c.color}"></span>${esc(c.name)}`;
const badge=s=>`<span class="tag">${s}</span>`;

function renderHero(){
 $('summary').textContent=D.executive_view.summary;$('scope').textContent=D.meta.scope_note;
 const ms=latest('MSFT'),g=latest('GOOGL'),a=latest('AAPL');
 $('takeaways').innerHTML=[
  ['微软 · FY2022 → FY2026','资本开支 / 收入',`${num(series('MSFT')[0],'capex_revenue')} → ${num(ms,'capex_revenue')}`,'五年窗口内，现金资本投入强度上升。'],
  ['谷歌 · FY2025','资本开支与回购',`${num(g,'capex')} / ${num(g,'buybacks')}`,'十亿美元；现金资本开支已高于回购。'],
  ['Apple · FY2025','回购 + 股息',`${num(a,'shareholder')}`,'十亿美元；股东回报与业务再投资分开衡量。']
 ].map(([label,title,value,note])=>`<article class="takeaway"><div class="label">${label} · ${title}</div><strong>${value}</strong><p>${note}</p></article>`).join('');
}

function renderChart(){
 const metric=$('metric').value; const percent=['capex_revenue','capex_cfo','rd_revenue'].includes(metric);
 const cs=D.companies.filter(c=>selected.has(c.id));
 $('companyFilters').innerHTML=D.companies.map(c=>`<button class="chip" data-toggle="${c.id}" aria-pressed="${selected.has(c.id)}">${cLabel(c)}</button>`).join('');
 const data=cs.flatMap(c=>series(c.id).filter(o=>Number.isFinite(o.values[metric])));
 $('chartNote').textContent=metric.startsWith('rd')?'Amazon 未披露可直接比较的纯研发金额，故不加入研发曲线；技术与基础设施费用在公司详情单列。':metric==='ma'?'并购金额不具连续性：Amazon 含非上市投资及其他净额；Apple 未单列；不能把曲线当作同口径并购排名。':metric==='cash_left'?'现金余量 = 经营现金流 − 现金资本开支；未扣融资租赁本金，不等同于所有公司的官方 FCF。':'现金资本开支按各公司报告口径展示；购置净额、无形资产和融资租赁差异见口径说明。';
 const W=1120,H=350,L=58,R=24,T=30,B=40;
 const start=Date.parse('2021-06-30'),end=Date.parse('2026-09-01');
 const x=o=>L+(Date.parse(o.end)-start)/(end-start)*(W-L-R);
 const values=data.map(o=>o.values[metric]/(percent?1:1000));
 const min=Math.min(0,...values),max=Math.max(1,...values)*1.12;
 const y=v=>T+(max-v)/(max-min)*(H-T-B);
 let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(D.metric_labels[metric])}五年趋势，按财年结束日绘图"><title>${esc(D.metric_labels[metric])}，${percent?'百分比':'十亿美元'}</title>`;
 for(let i=0;i<=4;i++){const v=min+(max-min)*i/4,yy=y(v);svg+=`<line class="grid" x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}"/><text x="${L-10}" y="${yy+4}" text-anchor="end">${v.toFixed(0)}${percent?'%':''}</text>`;}
 for(let yr=2021;yr<=2026;yr++){const xx=x({end:`${yr}-12-31`});if(xx<W-R)svg+=`<text x="${xx}" y="${H-9}" text-anchor="middle">${yr} 年末</text>`;}
 svg+=`<text x="${x({end:'2026-06-30'})}" y="${H-9}" text-anchor="middle">2026-06</text>`;
 for(const c of cs){const os=series(c.id).filter(o=>Number.isFinite(o.values[metric])); if(!os.length)continue;
  svg+=`<path d="${os.map((o,i)=>`${i?'L':'M'}${x(o)},${y(o.values[metric]/(percent?1:1000))}`).join(' ')}" fill="none" stroke="${c.color}" stroke-width="2.5"/>`;
  for(const o of os){const amount=percent?pct(o.values[metric]):bn(o.values[metric])+' 十亿美元';svg+=`<circle class="chart-point" role="button" tabindex="0" data-fact="${o.fact_ids[metric]}" aria-label="${c.name} FY${o.year} ${amount}，查看来源" cx="${x(o)}" cy="${y(o.values[metric]/(percent?1:1000))}" r="5.5" fill="${c.color}"><title>${c.name} · FY${o.year}\n截至 ${o.end}\n${amount}</title></circle>`;}
 }
 $('chart').innerHTML=svg+'</svg>';$('chartUnit').textContent='纵轴：'+(percent?'百分比':'十亿美元')+' · 连线仅帮助观察，不代表季度路径';
 $('growthTable').innerHTML=`<table><thead><tr><th>公司 / 五年窗口</th><th>资本开支年复合增速</th><th>收入年复合增速</th><th>经营现金流年复合增速</th><th>最近财年资本开支同比</th></tr></thead><tbody>${cs.map(c=>`<tr><td>${cLabel(c)}<small>${c.range}</small></td>${['capex_cagr','revenue_cagr','cfo_cagr','capex_yoy'].map(m=>`<td>${val(c.stat_fact_ids[m],pct(c.stats[m]))}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

function renderAllocation(){
 const mode=$('window').value;
 $('allocationTable').innerHTML=`<table><thead><tr><th>公司 / 期间</th><th>现金资本开支</th><th>研发费用</th><th>并购 / 无形资产等</th><th>非上市投资</th><th>回购 + 股息</th></tr></thead><tbody>${D.companies.map(c=>{
 const o=mode==='first'?series(c.id)[0]:latest(c.id);
 const value=m=>mode==='total'?(c.total_fact_ids[m]?val(c.total_fact_ids[m],bn(c.totals[m])):'<span class="na">无法完整累计</span>'):num(o,m);
 return `<tr><td>${cLabel(c)}<small>${mode==='total'?c.range:`FY${o.year} · ${o.end}`}</small></td><td>${value('capex')}</td><td>${c.id==='AMZN'?'<span class="na">非同口径，见详情</span>':value('rd')}</td><td>${value('ma')}${c.id==='AMZN'?'<small>含非上市投资及其他净额</small>':''}</td><td>${c.id==='AMZN'?'<span class="na">已含在左栏</span>':value('equity')}</td><td>${value('shareholder')}</td></tr>`;
 }).join('')}</tbody></table><p class="caption-note">单位：十亿美元。未拆分／无法完整累计 ≠ 没有投入。NVIDIA 的 Groq 许可支付在公司详情单列；未塞入常规资本开支或股权投资。</p>`;
 $('definitions').innerHTML=D.companies.map(c=>`<div><strong>${cLabel(c)}</strong><p>${esc(c.capex_note)} ${esc(c.ma_note)} ${esc(c.equity_note)}</p></div>`).join('');
}

function renderCompany(){
 const c=D.companies.find(c=>c.id===activeCompany),s=D.sections.find(s=>s.company===c.id),os=series(c.id),last=os.at(-1);
 $('companyTabs').innerHTML=D.companies.map(x=>`<button role="tab" data-company="${x.id}" aria-selected="${x.id===c.id}">${cLabel(x)}</button>`).join('');
 let extra='';
 if(c.id==='NVDA')extra=`<div class="bridge"><h4>常规购置、股权、许可，三项分列 · FY2026</h4><p>固定资产与无形资产现金购置 ${num(last,'capex')}；非上市股权证券 ${num(last,'equity')}；Groq 许可安排现金 ${num(last,'license')}（十亿美元）。</p><p>许可安排的后续应付金额不计入本期现金，不把交易总对价当成本年支出。</p></div>`;
 if(c.id==='AMZN')extra=`<div class="bridge"><h4>技术与基础设施费用，不等于研发</h4><p>${os.map(o=>`FY${o.year}：${num(o,'tech')}`).join(' · ')}（十亿美元）。</p><p>${esc(c.rd_note)}</p></div>`;
 $('companyDetail').innerHTML=`<div class="detail-head"><div><h3>${esc(c.name)}：${esc(s.title)}</h3><p>${c.english} · ${esc(c.role)}</p></div><span class="pill">${c.range} / 完整年度</span></div><div class="detail-grid"><div><h4>公司披露与财务变化</h4><p>${esc(s.summary)}</p><p class="caption-note">${val(s.fact_ids[0],'查看依据 ↗')}</p></div><div class="opinion"><h4>分析判断 · 不是公司指引</h4><p>${esc(s.view)}</p></div></div><div class="timeline">${os.map(o=>`<div class="year-step"><div class="year">FY${o.year}</div><div class="date">截至 ${o.end}</div><strong>${num(o,'capex')}</strong><div class="caption">资本开支 / 十亿美元</div><div class="caption">占收入 ${num(o,'capex_revenue')}</div></div>`).join('')}</div>${extra}<div class="watch"><strong>后续检验：</strong>${esc(s.watch)}</div><div class="detail-foot">${esc(c.capex_note)}</div>`;
}

function renderCash(){
 $('cashBars').innerHTML=[...D.companies].sort((a,b)=>latest(b.id).values.capex_cfo-latest(a.id).values.capex_cfo).map(c=>{const o=latest(c.id);return `<div class="cash-row"><div class="cash-label">${cLabel(c)}<small>FY${o.year} · ${o.end}</small></div><div class="cash-track" aria-label="资本开支占经营现金流 ${pct(o.values.capex_cfo)}"><div class="cash-fill" style="width:${Math.min(100,o.values.capex_cfo)}%;background:${c.color}"></div></div><div class="cash-number">${num(o,'capex_cfo')}</div></div>`;}).join('');
 const a=latest('AMZN'),m=latest('META');
 $('bridges').innerHTML=`<div class="bridge"><h4>Amazon · FY2025：先统一净额</h4><p>固定资产购置总额 − 出售及激励回款 = 净现金资本开支</p><div class="formula">${num(a,'gross_capex')} − ${num(a,'proceeds')} = ${num(a,'capex')}</div><p>经营现金流 ${num(a,'cfo')} − 净资本开支 ${num(a,'capex')} = 现金余量 ${num(a,'cash_left')}。</p><p>单位：十亿美元。与本期公司 FCF 口径一致，但未扣融资租赁本金。</p></div><div class="bridge"><h4>Meta · FY2025：租赁本金不能漏掉</h4><p>经营现金流 − 固定资产现金购置 = 本报告现金余量</p><div class="formula">${num(m,'cfo')} − ${num(m,'capex')} = ${num(m,'cash_left')}</div><p>官方 FCF 还需扣除融资租赁本金 ${num(m,'lease')}（十亿美元）。主图未将其与非现金租赁新增混合。</p><p>因此，不能直接把本报告现金余量叫作 Meta 官方自由现金流。</p></div>`;
}

function openDialog(title,html){$('drawerTitle').textContent=title;$('drawerBody').innerHTML=html;if(!$('drawer').open)$('drawer').showModal();}
function showFact(id){
 const f=F[id];if(!f)return;
 let html=`<article class="evidence-block">${badge(f.status==='inferred'?'分析判断':f.status==='calculated'?'计算值':'公司披露')}<h3>${esc(f.statement)}</h3><p>${esc(f.period||'')} · ${esc(f.basis||'')}</p><code>${f.id}</code></article>`;
 if(f.calculation_id){const c=C[f.calculation_id];html+=`<article class="evidence-block"><h3>计算过程</h3><p>${esc(c.description)}</p><pre>${esc(c.expression)}\n结果：${c.result} ${esc(c.units)}</pre>${c.input_fact_ids.map((x,i)=>`<p>input[${i}]：${val(x,esc(F[x].statement))}</p>`).join('')}</article>`;}
 if(f.reasoning)html+=`<p>${esc(f.reasoning)}</p>`;
 for(const eid of f.evidence_ids||[]){const e=E[eid],s=S[e.source_id];html+=`<article class="evidence-block"><a href="${esc(s.url)}" target="_blank" rel="noreferrer">${esc(s.title)} ↗</a><p>定位：${esc(e.locator)}</p><pre>${esc(e.content)}</pre><small>${s.id} · ${eid}</small></article>`;}
 openDialog('证据、口径与计算',html);
}
function sources(){openDialog('来源与结构化数据',`<p>12 份一手披露，已保存原文件与 SHA-256。Microsoft 最新两年使用未经审计的全年业绩公告。</p><p><a href="report-data.json" download>报告数据 JSON ↓</a> · <a href="../research-record.json" download>完整研究记录 ↓</a></p><input class="source-search" id="sourceSearch" aria-label="搜索来源" placeholder="搜索公司、财年或文件"><div id="sourceResults"></div>`);sourceResults('');$('sourceSearch').addEventListener('input',e=>sourceResults(e.target.value));}
function sourceResults(query){$('sourceResults').innerHTML=D.sources.filter(s=>`${s.title} ${s.company} ${D.companies.find(c=>c.id===s.company).name}`.toLowerCase().includes(query.toLowerCase())).map(s=>`<article class="source"><a href="${esc(s.url)}" target="_blank" rel="noreferrer">${esc(s.title)} ↗</a><small>${s.id} · ${esc(s.publisher)} · 获取日期 ${s.retrieved_at.slice(0,10)}</small><small>本地原始副本：<a href="../${s.raw_path}">${s.raw_path}</a></small><small>${s.unaudited?'全年业绩公告，未经审计':'公司正式年度披露'}</small></article>`).join('');}

fetch('report-data.json').then(r=>{if(!r.ok)throw Error('数据加载失败');return r.json();}).then(data=>{
 D=data;F=Object.fromEntries(D.facts.map(f=>[f.id,f]));E=Object.fromEntries(D.evidence.map(e=>[e.id,e]));S=Object.fromEntries(D.sources.map(s=>[s.id,s]));C=Object.fromEntries(D.calculations.map(c=>[c.id,c]));
 renderHero();renderChart();renderAllocation();renderCompany();renderCash();
 $('methodology').innerHTML=D.methodology.map(m=>`<li>${esc(m)}</li>`).join('');
 $('sourceList').innerHTML=D.sources.map(s=>`<a href="${s.url}" target="_blank" rel="noreferrer">${s.id} · ${esc(s.title)} ↗</a>`).join('');
 $('quality').textContent=D.validation.status==='NOT_RUN'?'草稿 · 尚未完成验证':`已完成来源定位、期间与计算复核、中文语气审校及页面检查。结构检查：${D.validation.status}。同一代理复核，非独立审计；未披露项及非同口径项已明确标出。`;
 $('metric').addEventListener('change',renderChart);$('window').addEventListener('change',renderAllocation);$('sourcesButton').addEventListener('click',sources);$('closeDrawer').addEventListener('click',()=>$('drawer').close());
 document.addEventListener('click',e=>{const fact=e.target.closest('[data-fact]'),toggle=e.target.closest('[data-toggle]'),company=e.target.closest('[data-company]');if(fact)showFact(fact.dataset.fact);if(toggle){const id=toggle.dataset.toggle;if(selected.has(id)){if(selected.size>1)selected.delete(id);}else selected.add(id);renderChart();}if(company){activeCompany=company.dataset.company;renderCompany();}});
 document.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches('circle[data-fact]')){e.preventDefault();showFact(e.target.dataset.fact);}});
 document.documentElement.dataset.ready='true';
}).catch(e=>{$('summary').innerHTML=`<span class="error">${esc(e.message)}。请通过本地 HTTP 服务打开本报告。</span>`;console.error(e);});
