'use strict';
const examples = {
  data: {scope:'NVIDIA · FY2000 onward', format:'Excel workbook', kind:'FINANCIAL DATA SHEET', title:'NVIDIA, in numbers.', badge:'XLSX', description:'Annual financials, source references, and explicit gaps in one workbook.', caveat:'FY2000–FY2026 + latest interim in the saved workbook. Early-year coverage gaps are disclosed.', link:'assets/NVIDIA_FY2000-FY2026_Latest_Interim.xlsx', linkText:'Download the workbook', prompt:'@Finrun Create an Excel sheet of NVIDIA’s key financial metrics from 2000 to today.'},
  business: {scope:'Apple · FY2021–FY2025',format:'Interactive report',kind:'BUSINESS QUALITY',title:'Beyond the iPhone.',badge:'HTML',description:'A saved analysis of Apple’s growth drivers, business quality, and financial risks.',caveat:'Saved FY2021–FY2025 research. Review the report’s evidence and dates before relying on its conclusions.',link:'examples/apple-business-quality/report/',linkText:'Open the Apple report',prompt:'@Finrun Assess Apple’s business quality and risks over FY2021–FY2025 in an interactive report.',rows:[['Business mix','Hardware, services, and their different economics'],['Cash generation','Earnings quality and capital returns'],['Key risks','Where the investment thesis needs scrutiny']]},
  industry: {scope:'Cloud · FY2021–FY2025',format:'Interactive report',kind:'INDUSTRY COMPARISON',title:'One industry. Different economics.',badge:'HTML',description:'Compare cloud businesses without treating every reported segment as equivalent.',caveat:'Saved 2021–2025 study. Fiscal periods and segment definitions differ; growth is not proof of market-share transfer.',link:'examples/cloud-computing/report/',linkText:'Open the cloud report',prompt:'@Finrun Compare AWS, Microsoft Azure, and Google Cloud over FY2021–FY2025 in an interactive report.',rows:[['Growth','Compare disclosed businesses and periods'],['Economics','Profitability and investment intensity'],['Comparability','Flag differences in segment definitions']]}
};
const tabs = [...document.querySelectorAll('[data-example]')];
const promptField = document.getElementById('prompt');
const visual = document.getElementById('result-visual');
const chart = visual.cloneNode(true);
let selected = 'data';
function selectExample(key) {
  selected = key;
  const item = examples[key];
  tabs.forEach(tab => {const active = tab.dataset.example === key;tab.setAttribute('aria-selected',String(active));tab.tabIndex = active ? 0 : -1;});
  document.getElementById('example-panel').setAttribute('aria-labelledby', 'tab-'+key);
  promptField.value = item.prompt;
  for(const [id,value] of Object.entries({'scope-tag':item.scope,'format-tag':item.format,'result-kind':item.kind,'result-title':item.title,'file-badge':item.badge,'result-description':item.description,'result-caveat':item.caveat})) document.getElementById(id).textContent=value;
  const link = document.getElementById('result-link');link.href=item.link;link.textContent=item.linkText+' ↗';
  if(key==='data') link.setAttribute('download',''); else link.removeAttribute('download');
  visual.replaceChildren();
  if(key==='data') [...chart.childNodes].forEach(node=>visual.append(node.cloneNode(true)));
  else item.rows.forEach(([heading,text])=>{const row=document.createElement('div');row.className='comparison-row';const title=document.createElement('strong');title.textContent=heading;const description=document.createElement('span');description.textContent=text;row.append(title,description);visual.append(row);});
  document.getElementById('copy-status').textContent='Adapt this prompt, then run it in your agent.';
}
tabs.forEach((tab,index)=>{
  tab.addEventListener('click',()=>selectExample(tab.dataset.example));
  tab.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight') next=(index+1)%tabs.length;if(event.key==='ArrowLeft') next=(index+tabs.length-1)%tabs.length;if(event.key==='Home') next=0;if(event.key==='End') next=tabs.length-1;if(next!==undefined){event.preventDefault();selectExample(tabs[next].dataset.example);tabs[next].focus();}});
});
async function copyText(text,status,message){try{await navigator.clipboard.writeText(text);status.textContent=message;}catch{status.textContent='Clipboard unavailable. Select the text and copy it manually.';}}
document.getElementById('copy-prompt').addEventListener('click',()=>{const status=document.getElementById('copy-status');if(!promptField.value.trim()){status.textContent='Add a research question first.';promptField.focus();return;}copyText(promptField.value,status,'Prompt copied. Select the Finrun plugin in your agent, then paste your question.');});
document.getElementById('reset-prompt').addEventListener('click',()=>selectExample(selected));
examples.data.prompt='@Finrun Build NVIDIA’s financial data sheet from 2000 to today as an Excel workbook.';
examples.business.prompt='@Finrun Assess Apple’s business quality and risks.';
examples.industry.prompt='@Finrun Compare AWS, Azure and Google Cloud.';
