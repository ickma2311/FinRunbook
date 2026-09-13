import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';

const root=path.resolve('dist');
const pages=['index.html','setup/index.html','support/index.html','privacy/index.html','terms/index.html','404.html'];
for(const page of pages){
  const file=path.join(root,page), text=fs.readFileSync(file,'utf8');
  assert.match(text,/<html lang="en">/);
  assert.match(text,/<title>[^<]+<\/title>/);
  const ids=[...text.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
  assert.equal(ids.length,new Set(ids).size,`Duplicate ID in ${page}`);
  for(const match of text.matchAll(/\b(?:href|src)="([^"]+)"/g)){
    const url=match[1];
    if(/^(https?:|mailto:)/.test(url))continue;
    if(url.startsWith('#')){assert(ids.includes(url.slice(1)),`Broken anchor ${page}: ${url}`);continue;}
    const clean=url.split(/[?#]/)[0];
    let target=clean.startsWith('/')?path.join(root,clean):path.resolve(path.dirname(file),clean);
    assert(target===root||target.startsWith(root+path.sep));
    if(fs.existsSync(target)&&fs.statSync(target).isDirectory())target=path.join(target,'index.html');
    assert(fs.existsSync(target),`Missing local link ${page}: ${url}`);
  }
}
const main=fs.readFileSync(path.join(root,'index.html'),'utf8');
const js=fs.readFileSync(path.join(root,'app.js'),'utf8');
for(const match of js.matchAll(/getElementById\('([^']+)'\)/g)){
  assert(main.includes(`id="${match[1]}"`),`Missing script target: ${match[1]}`);
}
assert(!/data-account|account-dialog|connection-preview|LOCAL PREVIEW/.test(main));
assert(!/account-dialog|show-connection|setup-dialog/.test(js));
for(const report of ['apple-business-quality','cloud-computing']){
  for(const file of ['index.html','app.js','style.css','report-data.json'])
    assert(fs.statSync(path.join(root,'examples',report,'report',file)).size>0);
  JSON.parse(fs.readFileSync(path.join(root,'examples',report,'report/report-data.json'),'utf8'));
}
console.log('PASS: six routes, local links, HTML anchors, script targets, two saved reports, and removed sign-in preview.');
