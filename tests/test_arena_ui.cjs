const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'portfolio/dashboard.html'), 'utf8');
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
new vm.Script(script);
const context = vm.createContext({URLSearchParams, Intl, Date, AbortController, setTimeout, clearTimeout, location:{hash:''}});
vm.runInContext(script.split("\ndocument.addEventListener('click'")[0], context);
const run = code => vm.runInContext(code, context);

context.data = {experts:[
 {expert_id:'trend',name:'Trend',description:'Synthetic trend method',status:'fresh',cash:'600',total_value:'1000',return_pct:'0',
  research_status:'completed',positions:[{symbol:'GLD',shares:1,price:'400',average_buy_price:'390',cost_basis:'390',cost_basis_status:'reconciled',decision_ids:['d1'],status:'fresh'}],
  decisions:[{decision_id:'d1',action:'rebalance',sealed_at:'2026-09-09T15:00:00Z',status:'PASS_WITH_WARNINGS',review_status:'PASS_WITH_WARNINGS',rationale:'Synthetic allocation rationale',warnings:['Synthetic warning'],reading_url:'research/test/index.html',report_url:'evidence/test.json',execution_changes:[]}],
  trades:[],runtime:{schedule:{attempts:[]}},research_history:[{research_id:'r1',decision_id:'d1',decision_ids:['d1'],content_hash:'test',title:'Synthetic report',at:'2026-09-09T15:00:00Z',status:'PASS_WITH_WARNINGS',source:'sealed_decision',timestamp_basis:'decision_sealed_at',report_url:'research/test/index.html',artifact_url:'evidence/test.json'}]},
 {expert_id:'growth',name:'Growth',description:'Synthetic growth method',status:'cash_only',cash:'1000',total_value:'1000',positions:[],decisions:[],trades:[],
  runtime:{schedule:{attempts:[{id:'blocked1',outcome:'blocked',finished_at:'2026-09-09T14:00:00Z',report:{sha256:'blocked-hash'}}]}},
  research_history:[{research_id:'attempt:blocked1',title:'Synthetic blocked research',at:'2026-09-09T14:00:00Z',status:'blocked',source:'research_attempt',content_hash:'blocked-hash'}]}
]};
run('snapshot=data');
let passed = 0;
function check(name, fn) {fn(); console.log('PASS '+name); passed++;}
function route(hash) {context.location.hash=hash;run('readRoute()');}
check('legacy expert deep link and workspace tab routes',()=>{route('#trend');assert.equal(run('route.expert'),'trend');assert.equal(run('route.tab'),'holdings');route('#trend?tab=research&q=gold&page=2');assert.equal(run('route.tab'),'research');assert.equal(run('route.page'),2);assert.equal(run('routeURL()'),'#trend?tab=research&q=gold&page=2');});
check('overview includes actual methods, prices and return basis',()=>{route('#overview');const view=run('overview(data.experts)');assert.match(view,/Investment method/);assert.match(view,/Account value/);assert.match(view,/Since funding/);assert.match(view,/Trend/);assert.doesNotMatch(view,/expert-card|Refresh saved data|every 15 seconds/);});
check('report reader and sealed JSON remain distinct',()=>{const d=run('data.experts.find(x=>x.expert_id==="trend").decisions[0]');const view=run('decision(data.experts.find(x=>x.expert_id==="trend").decisions[0],data.experts.find(x=>x.expert_id==="trend"),"test")');assert.ok(view.includes(d.reading_url));assert.ok(view.includes(d.report_url));assert.match(view,/Sealed report \(JSON\)/);for(const warning of d.warnings)assert.ok(view.includes(run('esc('+JSON.stringify(warning)+')')));});
check('holding separates buy and observed prices and keeps acquisition rationale',()=>{route('#trend');const view=run('holdings(data.experts.find(x=>x.expert_id==="trend"))');assert.match(view,/Avg\. buy price/);assert.match(view,/Latest (?:market )?price/);assert.match(view,/Cost basis \(incl\. fees\)/);assert.match(view,/Why GLD/);assert.match(view,/Recorded allocation rationale/);});
check('research status and date basis are explicit',()=>{route('#research');const view=run('research(data.experts)');assert.match(view,/Blocked attempt/);assert.match(view,/Decision sealed/);assert.match(view,/Passed with warnings/);});
check('legacy report-only snapshots remain usable',()=>{context.legacy={expert_id:'legacy',name:'Legacy',report_url:'latest.html',runtime:{},decisions:[]};assert.equal(run('researchHistory(legacy).length'),1);assert.equal(run('researchHistory(legacy)[0].report_url'),'latest.html');});
check('blocked attempts and linked research are not duplicated',()=>{const events=run('allEvents(data.experts)');assert.equal(new Set(events.map(e=>e.id)).size,events.length);const count=events.filter(e=>e.expert.expert_id==='growth'&&e.attempt?.outcome==='blocked').length;assert.equal(count,1);const trend=events.filter(e=>e.expert.expert_id==='trend');assert.equal(trend.filter(e=>e.type==='decision').length,1);assert.ok(trend.some(e=>e.hasResearch));});
// Stress data remains only in this process: no snapshot, account or history writes.
context.synthetic={...context.data.experts.find(x=>x.expert_id==='trend'),expert_id:'stress',name:'Stress <script>',research_history:[],decisions:[],trades:[],runtime:{schedule:{attempts:[]}}};
for(let i=0;i<360;i++){
 const id='stress-'+i,at=new Date(Date.UTC(2026,8,9)-i*3600000).toISOString();
 context.synthetic.decisions.push({decision_id:id,action:'no_change',sealed_at:at,status:'PASS_WITH_WARNINGS',review_status:'PASS_WITH_WARNINGS',rationale:'Rationale '+i+' <img src=x>',warnings:['Warning '+i],reading_url:'reports/'+i+'.html',report_url:'sealed/'+i+'.json'});
 context.synthetic.research_history.push({research_id:'report-'+i,decision_id:id,decision_ids:[id],title:'Research '+i,at,status:'PASS_WITH_WARNINGS',source:'sealed_decision',timestamp_basis:'decision_sealed_at',report_url:'reports/'+i+'.html',artifact_url:'sealed/'+i+'.json'});
 context.synthetic.trades.push({fill_id:'fill-'+i,decision_id:id,symbol:'GLD',side:'buy',shares:1,fill_price:400,fees:0,filled_at:at});
}
check('720 synthetic events stay bounded by pagination',()=>{route('#activity');assert.equal(run('allEvents([synthetic]).length'),720);const view=run('activity([synthetic])');assert.equal((view.match(/class="event"/g)||[]).length,12);assert.match(view,/of 720 events/);assert.match(view,/Page 1 of 60/);assert.ok(view.length<70000);route('#activity?page=2');assert.match(run('activity([synthetic])'),/13–24 of 720 events/);});
check('research library handles 360 rows and shareable search/filters',()=>{route('#research');assert.match(run('research([synthetic])'),/Page 1 of 30/);route('#research?q=Research+359');assert.match(run('research([synthetic])'),/1–1 of 1 reports/);route('#research?filter=attempt');assert.match(run('research([synthetic])'),/No matching research/);});
check('historical no_change never implies cash or liquidation',()=>{route('#stress?tab=decisions');const view=run('activity([synthetic],synthetic,true)');assert.match(view,/No allocation change/);assert.doesNotMatch(view,/Hold cash|keeps the account in cash|liquidat/i);assert.match(view,/Rationale 0 &lt;img src=x&gt;/);});
check('escaped untrusted text and invalid protocol links',()=>{route('#activity');assert.match(run('activity([synthetic])'),/Stress &lt;script&gt;/);assert.match(run('activity([synthetic])'),/Rationale 0 &lt;img src=x&gt;/);assert.equal(run('link("javascript:alert(1)","bad")'),'');});
check('null returns sort after valid returns in both directions',()=>{context.sortData=[{name:'Missing',return_pct:null},{name:'Up',return_pct:'2'},{name:'Down',return_pct:'-1'}];route('#overview?sort=return&dir=desc');assert.equal(run('sortRows(sortData).map(x=>x.name).join()'),'Up,Down,Missing');route('#overview?sort=return');assert.equal(run('sortRows(sortData).map(x=>x.name).join()'),'Down,Up,Missing');});
check('research filter includes linked approved research and time filters apply',()=>{route('#activity?kind=research');assert.match(run('activity([synthetic])'),/360 events/);route('#activity?kind=fill&q=GLD');assert.match(run('activity([synthetic])'),/360 events/);route('#activity?period=7');assert.ok(run('allEvents([synthetic]).filter(e=>inPeriod(e.at)).length')<720);});
check('durable review failure cannot appear completed from stale registry notes',()=>{context.ops={research_status:'completed',runtime:{},operations:{status:'active',stages:{research:{status:'completed'},review:{status:'retryable'},approval:{status:'pending'}}}};assert.equal(run('researchState(ops).text'),'Waiting to retry review');});
check('financial approval does not imply presentation or publication completion',()=>{context.ops={expert_id:'x',runtime:{},positions:[],decisions:[],operations:{presentation:{status:'unverified'},stages:{research:{status:'completed'},review:{status:'completed'},approval:{status:'completed'},execution:{status:'waiting_price'},publication:{status:'retryable'}},execution_queue:[{status:'waiting_price',reason:'post-approval bar unavailable',expires_at:'2026-09-11T20:00:00Z',decision_id:'d'}]}};const view=run('operationStatus(ops)');assert.match(view,/unverified/);assert.match(view,/retryable/);assert.match(view,/Expires/);assert.match(view,/post-approval bar unavailable/);});
console.log(passed+' checks passed. Synthetic histories were not persisted.');
