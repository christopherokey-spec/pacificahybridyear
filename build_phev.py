#!/usr/bin/env python3
"""Build the Pacifica website from tank and narrative CSV files (stdlib + bs4)."""
import csv, math, re, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from bs4 import BeautifulSoup
P=Path(__file__).resolve().parent
D=lambda x: Decimal(str(x))
def fmt(x,n=2): return f'{x:,.{n}f}'
def money(x):return '$'+fmt(x)
def cents(x):return fmt(x*100)+'¢'
def pct(x):
 value=fmt(x*100,1)
 return (value[:-2] if value.endswith('.0') else value)+'%'
def short_date(value):
 return re.sub(r'^(January|February|March|April|June|July|August|September|October|November|December)',lambda m:m.group(1)[:3],value).replace(', 2026','').replace(', 2027','')
def set_text(el,value):
 if el is None:raise ValueError('Missing expected HTML element')
 el.clear();el.append(str(value))
def find_row(panel,label):
 for r in panel.select('.row'):
  sp=r.find('span')
  if sp and sp.get_text(' ',strip=True).startswith(label):return r
 raise ValueError(f'Missing row {label}')
def row_value(panel,label,value):set_text(find_row(panel,label).find('b'),value)
def load():
 with (P/'tanks.csv').open(encoding='utf-8-sig',newline='') as f: raw=list(csv.DictReader(f))
 with (P/'narratives.csv').open(encoding='utf-8-sig',newline='') as f: notes={int(x['tank']):x for x in csv.DictReader(f)}
 if not raw:raise ValueError('No tank data')
 out=[]
 for i,r in enumerate(raw,1):
  t=int(r['tank'])
  if t!=i:raise ValueError('Tanks must be consecutive starting at 1')
  x={k:D(r[k]) for k in ('electric_miles','gas_miles','gas_gallons','home_kwh','public_kwh','gas_cost','home_cost','public_cost')}
  if any(v<0 for v in x.values()):raise ValueError(f'Tank {t}: negative input')
  miles=x['electric_miles']+x['gas_miles'];cost=x['gas_cost']+x['home_cost']+x['public_cost']
  if miles<=0:raise ValueError(f'Tank {t}: no miles')
  gasbuddy=r.get('gasbuddy_avg_price','').strip(); override=r.get('benchmark_cost_override','').strip()
  if gasbuddy:
   bench=miles/D(22)*D(gasbuddy)
   bench=bench.quantize(D('.01'),rounding=ROUND_HALF_UP)
  elif override:bench=D(override)
  else:raise ValueError(f'Tank {t}: supply GasBuddy average OR historical benchmark override')
  x.update(tank=t,start=r['start_date'],end=r['end_date'],miles=miles,cost=cost,bench=bench,ev_share=x['electric_miles']/miles,cpmi=cost/miles,oldcpmi=bench/miles,savings=bench-cost,save_pct=(bench-cost)/bench if bench else D(0),note=notes.get(t,{}))
  out.append(x)
 return out

def main():
 tanks=load();last=tanks[-1];n=len(tanks)
 soup=BeautifulSoup((P/'template.html').read_text(encoding='utf-8'),'html.parser')
 # Keep original styling and layout; clone Tank 6 as the template for new tank pages.
 panels=soup.select_one('.panels'); sample=soup.select_one('#tank6')
 for t in tanks:
  if not soup.select_one('#tank'+str(t['tank'])):
   clone=BeautifulSoup(str(sample),'html.parser').section
   clone['id']='tank'+str(t['tank']);panels.insert_before(clone) if False else sample.insert_after(clone)
   sample=clone
  p=soup.select_one('#tank'+str(t['tank']))
  set_text(p.select_one('.section-title'),f"Tank #{t['tank']} — {t['start']} to {t['end']}")
  for label,v in [('Electric driving',fmt(t['electric_miles'],1)),('Gas‑engine miles',fmt(t['gas_miles'],1)),('Total miles',fmt(t['miles'],1)),('Electric share',pct(t['ev_share'])),('Gasoline purchased',fmt(t['gas_gallons'],3)+' gal'),('Home charging total',fmt(t['home_kwh'],3)+' kWh'),('Public charging total',(fmt(t['public_kwh'],3) if t['public_kwh'] else '0')+' kWh'),('Total charging',fmt(t['home_kwh']+t['public_kwh'],3)+' kWh')]:row_value(p,label,v)
  set_text(p.select_one('.big-number'),cents(t['cpmi']))
  small=p.select_one('.big-number').parent.select_one('div[style*="font-size:.68rem"]')
  if small:set_text(small,f"{money(t['cost'])} ÷ {fmt(t['miles'],1)} miles")
  result=p.select_one('.big-number').parent.find('p')
  note=t['note']
  if note.get('tank_result_comment'):set_text(result,note['tank_result_comment'])
  else:set_text(result,f"{pct(t['ev_share'])} electric driving held energy cost to {cents(t['cpmi'])} per mile — {pct(t['save_pct'])} below the 2018 Pacifica benchmark.")
  cost_card=[c for c in p.select('.card.rows') if c.select_one('.total')][0]
  for label,v in [('Gasoline',t['gas_cost']),('Home charging',t['home_cost']),('Public charging',t['public_cost'])]:row_value(cost_card,label,money(v))
  set_text(cost_card.select_one('.total strong'),money(t['cost']))
  sav=p.select_one('.card.savings');set_text(sav.select_one('.amount'),money(t['savings'])+' saved');set_text(sav.select_one('.pct'),pct(t['save_pct'])+' lower energy cost')
  set_text(sav.select_one('p'),f"2018 benchmark: {money(t['bench'])} total, or {cents(t['oldcpmi'])}/mile, using 22 MPG and the Twin Cities gas-price benchmark for {t['start']}–{t['end']}.")
  ctx=p.select_one('.note');set_text(ctx,f"Tank #{t['tank']} context: {note.get('tank_context','')}")
 # Build history cards from one source, on every tank page.
 for t in tanks:
  p=soup.select_one('#tank'+str(t['tank'])); strip=p.select_one('.history-strip');strip.clear()
  for other in tanks:
   tag=soup.new_tag('label',attrs={'class':f"tank-link tank{other['tank']}"+(' current' if other['tank']==t['tank'] else ''),'for':f"tab-tank{other['tank']}",'title':f"Open Tank #{other['tank']}"})
   h=soup.new_tag('h3');h.string=f"Tank #{other['tank']} →";tag.append(h)
   d=soup.new_tag('div',attrs={'class':'mini-copy'})
   for j,line in enumerate([fmt(other['miles'],1)+' mi',pct(other['ev_share'])+' EV',money(other['cost']),cents(other['cpmi'])+'/mi']):
    if j:d.append(soup.new_tag('br'))
    d.append(line)
   tag.append(d);strip.append(tag)
  nextlabel=p.select_one('.nextrow label')
  if t['tank']<n:nextlabel['for']=f"tab-tank{t['tank']+1}";set_text(nextlabel,f"See Tank #{t['tank']+1} →")
  else:nextlabel['for']='tab-year';set_text(nextlabel,'See project-to-date details →')
 # Radio inputs and tabs
 tabs=soup.select_one('.tabs');bar=soup.select_one('.tabbar')
 for t in tanks:
  ident=f"tab-tank{t['tank']}"
  if not soup.select_one('#'+ident):
   inp=soup.new_tag('input',attrs={'id':ident,'name':'tabs','type':'radio'});bar.insert_before(inp)
  if not bar.select_one(f'label[for="{ident}"]'):
   label=soup.new_tag('label',attrs={'for':ident});label.string=f"Tank #{t['tank']}";bar.select_one('label[for="tab-year"]').insert_before(label)
 # CSS rules for dynamic tank selectors and accents (new tanks only)
 css=soup.style
 extra=['\n/* Generated tank navigation and accent rules */']
 for t in tanks[6:]:
  k=t['tank'];c='var(--tank1)' if k%2 else 'var(--tank2)'
  extra.extend([f'.tank-link.tank{k}{{border-top:5px solid {c}}}',f'.note.tank{k}-context{{border-left-color:{c}}}',f'#tab-tank{k}:checked ~ .tabbar label[for=tab-tank{k}]{{background:var(--midnight);color:#fff}}',f'#tab-tank{k}:checked ~ .panels #tank{k}{{display:block}}'])
 css.append('\n'.join(extra))
 # totals
 total=lambda k:sum((t[k] for t in tanks),D(0))
 miles=total('miles');ev=total('electric_miles');gas=total('gas_miles');cost=total('cost');bench=total('bench');saved=bench-cost;share=ev/miles;cpmi=cost/miles
 ov=soup.select_one('#overview');set_text(ov.select_one('.hero-stat .big'),fmt(miles,1))
 for el,val in zip(ov.select('.grid4 .metric strong'),[fmt(miles,1),pct(share),money(cost),cents(cpmi)]):set_text(el,val)
 progress=ov.select_one('.progress');progress.select_one('.ev')['style']=f'width:{pct(share)}';progress.select_one('.gas')['style']=f'width:{pct(1-share)}'
 for el,val in zip(ov.select('.legend span'),[fmt(ev,1)+' electric miles',fmt(gas,1)+' gas‑engine miles']):
  icon=el.find('i');el.clear();el.append(icon);el.append(val)
 savings=ov.select_one('.card.savings');set_text(savings.select_one('.amount'),money(saved)+' saved');set_text(savings.select_one('.pct'),pct(saved/bench)+' lower energy cost')
 for el in savings.find_all('div'):
  if 'vs. the 2018' in el.get_text():set_text(el,f'vs. the 2018 Pacifica benchmark through Tank #{n}')
 quick=ov.select_one('.quick-tanks')
 # Reuse the original outlined gas pump SVG; never substitute emoji.
 original_icon=soup.select_one('#overview .quick-tanks .quick-btn.tank .ico')
 if original_icon is None or original_icon.find('svg') is None:raise ValueError('Missing original gas pump SVG')
 quick.clear()
 for t in tanks:
  tag=soup.new_tag('label',attrs={'class':'quick-btn tank','for':f"tab-tank{t['tank']}"})
  ico=BeautifulSoup(str(original_icon),'html.parser').span;tag.append(ico)
  label=soup.new_tag('span',attrs={'class':'tank-label'})
  for line in ['Tank',f"#{t['tank']}"]:
   sp=soup.new_tag('span');sp.string=line;label.append(sp)
  tag.append(label);quick.append(tag)
 # Project to Date
 year=soup.select_one('#year');set_text(year.select_one('.section-title'),f'Project to Date — Through Tank #{n}')
 for el,val in zip(year.select('.grid4 .metric strong'),[fmt(miles,1),pct(share),money(cost),money(saved)]):set_text(el,val)
 for label,val in [('Electric driving',fmt(ev,1)),('Gas‑engine miles',fmt(gas,1)),('Gasoline purchased',fmt(total('gas_gallons'),3)+' gal'),('Average energy cost per mile',cents(cpmi))]:row_value(year,label,val)
 small=find_row(year,'Average energy cost per mile').select_one('span span');
 if small:set_text(small,f'{money(cost)} ÷ {fmt(miles,1)} miles')
 # Tank board
 board=year.select_one('.tank-board');board.clear()
 for t in tanks:
  tag=soup.new_tag('label',attrs={'class':f"tank-link tank{t['tank']}",'for':f"tab-tank{t['tank']}",'title':f"Open Tank #{t['tank']}"})
  h=soup.new_tag('h3');h.string=f"Tank #{t['tank']} →";tag.append(h)
  div=soup.new_tag('div',attrs={'class':'mini-copy'})
  for i,line in enumerate([short_date(t['start'])+'–'+short_date(t['end']),fmt(t['miles'],1)+' mi',pct(t['ev_share'])+' EV',money(t['cost'])]):
   if i:div.append(soup.new_tag('br'))
   div.append(line)
  tag.append(div);board.append(tag)
 # Chart SVG: fixed plot height, grows horizontally as tanks increase, scrollable on mobile.
 svg=year.select_one('.chart-wrap svg');svg.clear();width=max(650,100*n+50);svg['viewbox']=f'0 0 {width} 270';svg['aria-label']=f'Line chart showing PHEV and 2018 benchmark energy cost per mile for Tanks 1 through {n}'
 maxv=max(float(max(t['cpmi'],t['oldcpmi'])*100) for t in tanks);minv=min(float(min(t['cpmi'],t['oldcpmi'])*100) for t in tanks)
 ymin=5 if minv>=5 else math.floor(minv)
 ymax=21 if maxv<=21 else math.ceil(maxv+1)
 if ymax<=ymin:ymax=ymin+4
 def y(v):return 240-(float(v)*100-ymin)/(ymax-ymin)*200
 xs=[75+100*i for i in range(n)];right=xs[-1]+35
 def svg_tag(name,attrs,parent=svg,string=None):
  tag=soup.new_tag(name,attrs={k:str(v) for k,v in attrs.items()});parent.append(tag)
  if string is not None:tag.string=str(string)
  return tag
 for i in range(5):
  val=ymin+(ymax-ymin)*i/4;yy=240-i*50
  svg_tag('line',{'x1':58,'x2':right,'y1':yy,'y2':yy,'stroke':'var(--chart-grid)'})
  svg_tag('text',{'x':47,'y':yy+4,'text-anchor':'end','fill':'var(--chart-axis)','font-size':12},string=f'{val:g}¢')
 for x,t in zip(xs,tanks):svg_tag('text',{'x':x,'y':260,'text-anchor':'middle','fill':'var(--chart-axis)','font-size':12},string=f"Tank #{t['tank']}")
 for key,color,rad,stroke in [('cpmi','var(--aurora)',7,5),('oldcpmi','var(--lake)',6,4)]:
  points=' '.join(f'{x},{y(t[key]):.1f}' for x,t in zip(xs,tanks))
  svg_tag('polyline',{'points':points,'fill':'none','stroke':color,'stroke-width':stroke,'stroke-linejoin':'round','stroke-linecap':'round'})
  for x,t in zip(xs,tanks):svg_tag('circle',{'cx':x,'cy':f'{y(t[key]):.1f}','r':rad,'fill':color,'stroke':'var(--panel)','stroke-width':3})
 for x,t in zip(xs,tanks):svg_tag('text',{'x':x,'y':f'{y(t["cpmi"])-13:.1f}','text-anchor':'middle','fill':'var(--chart-label)','font-size':12,'font-weight':800},string=cents(t['cpmi']))
 # costs
 costs=soup.select_one('#costs');set_text(costs.select_one('.section-title'),f'Cumulative real‑world energy cost — Through Tank #{n}')
 first=costs.select_one('.card.rows');totaldiv=first.select_one('.total');scroll=first.select_one('.cost-tank-scroll');
 for r in scroll.select('.row'):r.decompose()
 for t in tanks:
  r=soup.new_tag('div',attrs={'class':'row'});sp=soup.new_tag('span');sp.string=f"Tank #{t['tank']}";b=soup.new_tag('b');b.string=money(t['cost']);r.extend([sp,b]);scroll.append(r)
 set_text(totaldiv.select_one('strong'),money(cost));set_text(costs.select_one('.big-number'),cents(cpmi))
 for p in costs.select('p'):
  if 'PHEV:' in p.get_text():set_text(p,f'PHEV: {money(cost)} energy cost ÷ {fmt(miles,1)} tracked miles')
 for el in costs.select('.section-title'):
  if 'Cumulative through Tank' in el.get_text():set_text(el,f'Cumulative through Tank #{n}')
 blocks=costs.select('.grid3 .card')
 for el,v in zip(blocks,[fmt(total('gas_gallons'),3),fmt(miles/D(22),1),fmt(miles/D(22)-total('gas_gallons'),1)]):
  target=el.select_one('div[style*="font-size:2.4rem"]')
  if target:
   span=target.find('span');target.clear();target.append(v);target.append(' ');target.append(span)
 for p in blocks[0].select('p'):set_text(p,f'Actual gasoline purchased across all {n} completed tanks.')
 for p in blocks[1].select('p'):set_text(p,f'Estimated gasoline a 2018 Pacifica at 22 MPG would have used across the same {fmt(miles,1)} miles.')
 # compare
 compare=soup.select_one('#compare');table=compare.select('tbody tr')
 for r,values in zip(table[:4],[(fmt(miles,1),fmt(miles,1)),(money(cost),money(bench)),(cents(cpmi),cents(bench/miles)),(str(n),f'about {round(float(miles/D(22)/D(19)))}')]):
  cells=r.select('td');set_text(cells[1],values[0]);set_text(cells[2],values[1]);
  if r==table[1] or r==table[2]:
   dagger=soup.new_tag('span',attrs={'class':'est'});dagger.string='†';cells[2].append(dagger)
 savedstack=table[4].select_one('.saved-stack');savedstack.clear();savedstack.append(money(saved));dagger=soup.new_tag('span',attrs={'class':'est'});dagger.string='†';savedstack.append(dagger);word=soup.new_tag('span',attrs={'class':'saved-word'});word.string='saved';savedstack.append(word)
 gallons=fmt(miles/D(22)-total('gas_gallons'),1)
 old=table[4].select('td')[2];oldspan=old.find('span');set_text(oldspan,gallons);dagger=soup.new_tag('span',attrs={'class':'est'});dagger.string='†';oldspan.append(dagger)
 set_text(compare.select('.grid2 .amount')[0],money(saved));set_text(compare.select('.grid2 .pct')[0],f'saved through Tank #{n}')
 set_text(compare.select('.grid2 .big-number')[0],pct(saved/bench))
 for p in compare.select('.grid2 p'):
  if 'than the combined' in p.get_text():set_text(p,f'than the combined 2018 Pacifica benchmark across the same {fmt(miles,1)} miles.')
 # footer and date
 set_text(soup.select_one('.footer'),f"Pacifica PHEV real‑world cost tracker through Tank #{n} • {last['end']}")
 date=soup.select_one('.date-badge span');set_text(date,f'(data through {last["end"]})')
 # update chart mobile min width for larger chart
 css.append(f'\n@media(max-width:520px){{.chart-wrap svg{{width:{width}px}}}}')
 if n>10:css.append(f'\n@media(min-width:521px){{.chart-wrap svg{{width:max(100%, {width}px)}}}}')
 (P/'index.html').write_text(str(soup),encoding='utf-8')
 print(f'Built index.html: {n} tanks, {fmt(miles,1)} miles, {money(cost)} cost, {money(saved)} saved')
if __name__=='__main__':
 try:main()
 except Exception as e:print('BUILD FAILED:',e,file=sys.stderr);sys.exit(1)
