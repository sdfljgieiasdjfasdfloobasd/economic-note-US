// Keep workbook sibling order and put each descendant immediately after its parent.
export function orderedSeries(series,collapsed=new Set()){
 const ids=new Set(series.map(s=>s.id)),children=new Map(),roots=[];
 for(const s of series){const p=s.hierarchy?.parentId;if(p!=null&&ids.has(p)){if(!children.has(p))children.set(p,[]);children.get(p).push(s)}else roots.push(s)}
 const groups=[...new Set(roots.map(s=>s.hierarchy?.section||''))],out=[],seen=new Set();
 function walk(s){if(seen.has(s.id))return;seen.add(s.id);out.push(s);if(!collapsed.has(s.id))for(const child of children.get(s.id)||[])walk(child)}
 for(const group of groups)for(const root of roots.filter(s=>(s.hierarchy?.section||'')===group))walk(root);
 return out;
}
export function breadcrumb(s){return s.hierarchy?.path?.join(' › ')||s.hierarchy?.section||'';}
export function itemOptions(d,value,esc){
 const rows=orderedSeries(d.series),groups=[...new Set(rows.map(s=>s.hierarchy?.section||''))];
 const option=s=>`<option value="${esc(s.id)}" ${s.id===value?'selected':''} title="${esc(breadcrumb(s))}">${'　'.repeat(s.hierarchy?.depth||0)}${s.hierarchy?.depth?'↳ ':''}${esc(s.label+(s.name!==s.label?' / '+s.name:''))}</option>`;
 return groups.map(g=>g?`<optgroup label="${esc(g)}">${rows.filter(s=>s.hierarchy?.section===g).map(option).join('')}</optgroup>`:rows.filter(s=>!s.hierarchy?.section).map(option).join('')).join('');
}
