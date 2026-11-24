// A recommendation is a starting point; the entire registered library remains available.
export function searchCatalog(items,{query='',category='',collection='all',offset=0,limit=24}={}) {
  const words=String(query).trim().toLocaleLowerCase().split(/\s+/u).filter(Boolean);
  const matches=items.filter(item=>(collection!=='recommended' || item.recommended!==false) &&
    (!category || item.category===category || item.sourceCategory===category) && words.every(word=>
      [item.title,item.category,item.sourceCategory,item.style,item.summary,item.description].join(' ').toLocaleLowerCase().includes(word)));
  return {total:matches.length,offset,limit,hasMore:offset+limit<matches.length,items:matches.slice(offset,offset+limit)};
}

export function modelTemplates(items,plan) {
  const chosen=new Set([plan?.template,...(plan?.pageTemplates || []).map(p=>p.template)].filter(Boolean));
  const selected=items.filter(t=>chosen.has(t.id) || ['本次上传','共享模板'].includes(t.category));
  const rest=items.filter(t=>!selected.includes(t) && t.recommended!==false).slice(0,32);
  return [...selected,...rest].map(({cover,motion,referencePages,visual,pages,...t})=>({...t,
    samplePages:(referencePages || pages || []).map(p=>p.page),
    ...(visual && chosen.has(t.id)?{visual}:{})}));
}
