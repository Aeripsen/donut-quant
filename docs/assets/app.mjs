import {simulate,sellAxeCapacity,quoteGapPercent,shareableSummary,CHEST_UNITS} from './engine.mjs';

const $ = id => document.getElementById(id);
const fmt = n => {
  if (n === null || n === undefined || !Number.isFinite(n)) return '—';
  const abs = Math.abs(n),sign=n < 0 ? '-' : '';
  if (abs >= 1e12) return sign+'$'+(abs/1e12).toFixed(2)+'T';
  if (abs >= 1e9) return sign+'$'+(abs/1e9).toFixed(abs>=1e10?1:2)+'B';
  if (abs >= 1e6) return sign+'$'+(abs/1e6).toFixed(abs>=1e8?0:2)+'M';
  if (abs >= 1e3) return sign+'$'+(abs/1e3).toFixed(abs>=1e5?0:abs>=1e4?1:2)+'K';
  return sign+'$'+abs.toLocaleString('en-US',{maximumFractionDigits:2});
};
const number = n => Number(n||0).toLocaleString('en-US',{maximumFractionDigits:2});
const pct = n => n===null?'—':(n>=0?'+':'')+n.toFixed(1)+'%';
const parsedOptional = element => element.value.trim()===''?null:Number(element.value);
const state = {data:null,item:null,mode:'orders',result:null,customBids:null};
let lastToast;
const toast = text => {
  const button=$('copyResult'); if(!button)return;
  clearTimeout(lastToast); const prior=button.dataset.original||button.textContent;
  button.dataset.original=prior; button.textContent=text;
  lastToast=setTimeout(()=>{button.textContent=prior},1800);
};

function createElement(tag,cls,text) {
  const el=document.createElement(tag); if(cls) el.className=cls;
  if(text!==undefined) el.textContent=text;
  return el;
}

function select(id) {
  const item=state.data.items.find(x=>x.id===id);
  if(!item)return;
  state.item=item;
  state.customBids=null;
  $('customBids').value='';
  $('customMessage').textContent='Using the curated dated order levels.';
  state.mode=item.worth!==null?'axe':'orders';
  $('quantityInput').value=item.defaultQuantity;
  $('costInput').value='';
  $('axeInput').value='';
  $('feeInput').value='0';
  $('worthInput').value=item.worth??'';
  $('farmRate').value=CHEST_UNITS;
  $('chestRate').value=1;
  redrawAll();
}

function fillAssetList() {
  const container=$('assetList'),q=$('search').value.toLowerCase().trim();
  container.replaceChildren();
  const matches=state.data.items.filter(i=>(i.name+' '+i.category).toLowerCase().includes(q));
  if(!matches.length){container.append(createElement('p','empty','No matching items in this curated sample.'));return;}
  for (const item of matches) {
    const button=createElement('button','asset-row'+(state.item?.id===item.id?' selected':''));button.type='button';
    button.setAttribute('aria-pressed',String(state.item?.id===item.id));
    const left=createElement('span','asset-text');
    const glyph=createElement('span','asset-glyph',item.symbol);
    const titleWrap=createElement('span');
    titleWrap.append(createElement('span','asset-title',item.name),createElement('span','asset-caption',item.category));
    left.append(glyph,titleWrap);
    const price=createElement('span','num',fmt(item.bid));
    const delta=quoteGapPercent(item.historical,item.bid);
    const change=createElement('span','change '+(delta>=0?'positive':'negative'),pct(delta)+(item.comparable?'':'*'));
    button.append(left,price,change);
    button.addEventListener('click',()=>select(item.id));
    container.append(button);
  }
}

function updateAssetDetails() {
  const i=state.item;
  $('detailCategory').textContent='MARKET / '+i.category.toUpperCase();
  $('detailSource').href=i.source;
  $('detailName').textContent=i.name;
  $('detailSymbol').textContent=i.symbol;
  const date=new Date(i.snapshotAt).toLocaleString('en-CA',{dateStyle:'medium',timeStyle:'short',timeZone:'UTC'});
  $('detailDate').textContent=date+' UTC · dated observation';
  $('histValue').textContent=fmt(i.historical);
  $('askValue').textContent=fmt(i.cheapest);
  $('bidValue').textContent=fmt(i.bid);
  const delta=quoteGapPercent(i.historical,i.bid);
  $('histChange').textContent=pct(delta)+(i.comparable?'':' · not directly comparable');
  $('histChange').style.color=i.comparable?(delta>=0?'var(--teal)':'var(--danger)'):'var(--amber)';
  $('detailWarning').textContent=i.warning+' Historical method: '+i.historicalBasis;
  $('liquidityText').textContent='24H ORDER FILLS: '+number(i.unitsFilled24h)+' UNITS';
  const max=Math.max(i.historical,i.cheapest,i.bid);
  const chart=$('comparisonBars');chart.replaceChildren();
  for(const [label,value,color] of [['Aug sold',i.historical,'hist'],['Nov ask',i.cheapest,'ask'],['Nov bid',i.bid,'bid']]){
    const line=createElement('div','compare-bar-line');
    const labelEl=createElement('span','',label);
    const track=createElement('div','track');
    const fill=createElement('div','fill '+color);
    fill.style.width=Math.max(0.2,100*value/max)+'%';
    track.append(fill);
    const val=createElement('span','compare-val',fmt(value));
    line.append(labelEl,track,val);chart.append(line);
  }
}

function updateModes() {
  const axe=state.mode==='axe';
  $('modeAxe').classList.toggle('active',axe);
  $('modeOrders').classList.toggle('active',!axe);
  $('modeAxe').setAttribute('aria-pressed',String(axe));
  $('modeOrders').setAttribute('aria-pressed',String(!axe));
  $('worthField').hidden=!axe;
  $('axeField').hidden=!axe;
  $('capacityBox').hidden=!axe;
  $('scenarioHelp').textContent=axe
    ?'Conditional model: top matching orders above current /worth, then server fallback. Check the Sell Axe behavior and active multiplier in-game.'
    :'Only the displayed order depth is modeled. Unsold items remain yours. Ask prices are deliberately not counted as proceeds.';
}

function putResultUnavailable(message) {
  state.result=null;
  $('revenueTotal').textContent='—';
  $('resultContext').textContent=message;
  for(const id of ['orderUnits','fallbackUnits','unsoldUnits','profitNet','coverageText']) $(id).textContent='—';
  $('stackedChart').replaceChildren();
  $('depthList').replaceChildren(createElement('p','empty',message));
  $('assumptionNotice').textContent='No transaction was submitted. Values are a simulation only.';
}

function renderOutcome() {
  const i=state.item,qty=Number($('quantityInput').value);
  const fee=Number($('feeInput').value)/100;
  const worth=parsedOptional($('worthInput'));
  const cost=parsedOptional($('costInput'));
  const axeCost=parsedOptional($('axeInput'));
  if(!Number.isInteger(qty)||qty<0||!Number.isSafeInteger(qty)){
    putResultUnavailable('Enter a valid, non-negative whole-item quantity.');return;
  }
  if(state.mode==='axe'&&worth===null){
    putResultUnavailable('Enter the effective server /worth for this exact item. It is not in this dated snapshot.');return;
  }
  let result;
  try{result=simulate({quantity:qty,bids:state.customBids??i.depth,mode:state.mode,worth,feeRate:fee,unitCost:cost,axeCost});}
  catch(error){putResultUnavailable(error.message);return;}
  state.result=result;
  $('revenueTotal').textContent=fmt(result.cashProceeds);
  $('resultContext').textContent=(state.mode==='axe'
    ?'Limited order bids, then server fallback at your entered /worth.'
    :'Only available sampled buy orders pay cash; unfilled items remain in inventory.');
  $('orderUnits').textContent=number(result.orderUnits);
  $('fallbackUnits').textContent=number(result.worthUnits);
  $('unsoldUnits').textContent=number(result.unsold);
  $('profitNet').textContent=result.net===null?'Cost basis needed':fmt(result.net);
  $('profitNet').style.color=result.net===null?'var(--muted)':result.net>=0?'var(--teal)':'var(--danger)';
  $('coverageText').textContent=qty?((result.orderUnits/qty)*100).toFixed(1)+'% at observed bids':'No units to sell';

  const chart=$('stackedChart');chart.replaceChildren();
  for(const [n,key] of [[result.orderUnits,'order'],[result.worthUnits,'fallback'],[result.unsold,'unsold']]){
    if(n<=0 || qty<=0)continue;
    const segment=createElement('div','seg-'+key);
    segment.style.width=(n/qty*100)+'%';
    segment.title=key+': '+number(n)+' units';
    chart.append(segment);
  }
  const list=$('depthList');list.replaceChildren();
  const agg=new Map();
  for(const f of result.fills){
    const key=f.price;
    const a=agg.get(key)||{units:0,revenue:0,approx:false};
    a.units+=f.units;a.revenue+=f.revenue;a.approx ||= f.approximate;agg.set(key,a);
  }
  for(const [price,a] of agg){
    const row=createElement('div','depth-level');
    row.append(createElement('span','level-name',(a.approx?'≈ ':'')+number(a.units)+' @ '+fmt(price)),
      createElement('strong','level-value',fmt(a.revenue)));
    list.append(row);
  }
  if(result.worthUnits>0){
    const r=createElement('div','depth-level fallback');
    r.append(createElement('span','level-name',number(result.worthUnits)+' @ '+fmt(worth)+' server fallback'),
      createElement('strong','level-value',fmt(result.worthRevenue)));list.append(r);
  }
  if(result.unsold>0){
    const r=createElement('div','depth-level unsold');
    r.append(createElement('span','level-name',number(result.unsold)+' unfilled / no buyer'),
      createElement('strong','level-value','NOT SOLD'));list.append(r);
  }
  if(qty===0) list.append(createElement('div','empty','Enter a quantity to explore the order book.'));
  const extras=[];
  if(state.customBids)extras.push('Bid levels were entered by you and have not been independently verified.');
  if(result.approximate)extras.push('Some order quantities were rounded on the source page.');
  if(state.mode==='axe')extras.push('Routing and current /worth are unverified in game.');
  if(cost===null)extras.push('Acquisition cost is unknown, so net profit is not calculated.');
  else if(state.mode==='axe'&&axeCost===null)extras.push('Enter the actual monetary value of the time-limited axe.');
  if(i.id==='shulker_box')extras.push('Container contents are not price-matched.');
  $('assumptionNotice').textContent=(extras.join(' ')||'Recheck the order book before acting.')+' All observations are dated '+i.snapshotAt.slice(0,10)+'.';
}

function updateCapacity() {
  if(state.mode!=='axe')return;
  const farm=Number($('farmRate').value),clears=Number($('chestRate').value);
  if(!Number.isFinite(farm)||!Number.isFinite(clears)||farm<0||clears<0){
    $('capacityResult').textContent='Enter valid rates';return;
  }
  const out=sellAxeCapacity({producedPerHour:farm,chestsPerHour:clears,hours:24});
  $('capacityResult').textContent=number(out.chests)+' chests / '+number(out.units)+' items';
}

function redrawAll() {
  fillAssetList();updateAssetDetails();updateModes();updateCapacity();renderOutcome();
}

function paintRoundedRect(ctx,x,y,w,h,r,fill){
  ctx.fillStyle=fill;ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fill();
}

function makeShareCard() {
  if(!state.result)return;
  const c=document.createElement('canvas');c.width=1200;c.height=675;
  const x=c.getContext('2d');if(!x)return;
  const bg=x.createLinearGradient(0,0,1200,675);bg.addColorStop(0,'#0a171c');bg.addColorStop(1,'#152b2d');x.fillStyle=bg;x.fillRect(0,0,1200,675);
  x.strokeStyle='#204b49';x.lineWidth=1;
  for(let i=40;i<1200;i+=55){x.beginPath();x.moveTo(i,0);x.lineTo(i,675);x.stroke()}
  for(let i=30;i<675;i+=55){x.beginPath();x.moveTo(0,i);x.lineTo(1200,i);x.stroke()}
  paintRoundedRect(x,52,49,1096,576,24,'#0d1c22eF');
  x.fillStyle='#86f4bf';x.font='bold 25px ui-monospace, monospace';x.fillText('◩  DONUT / QUANT',95,105);
  x.font='bold 17px ui-monospace, monospace';x.fillStyle='#91b0b5';x.fillText('EXIT-PRICE CALCULATOR • DATED MARKET SCENARIO',95,153);
  x.fillStyle='#f2f6f6';x.font='bold 53px system-ui, sans-serif';x.fillText(state.item.name,95,231);
  x.fillStyle='#9cbbbc';x.font='22px system-ui, sans-serif';x.fillText(number(state.result.quantity)+' items  ·  '+state.mode.toUpperCase()+' scenario',95,269);
  x.fillStyle='#89f4b9';x.font='bold 72px system-ui, sans-serif';x.fillText(fmt(state.result.cashProceeds),95,383);
  x.fillStyle='#abc2c0';x.font='20px system-ui, sans-serif';x.fillText('CASH AFTER ASSUMED FEES',100,414);
  paintRoundedRect(x,95,450,990,93,12,'#173430');
  x.font='bold 27px ui-monospace, monospace';x.fillStyle='#e9fbf3';
  x.fillText('ORDER: '+number(state.result.orderUnits),121,489);
  x.fillText('UNSOLD: '+number(state.result.unsold),540,489);
  x.font='19px ui-monospace, monospace';x.fillStyle='#b4d3c9';
  x.fillText('NET AFTER COSTS: '+(state.result.net===null?'UNKNOWN':fmt(state.result.net)),121,520);
  x.fillStyle='#8fa9ad';x.font='16px system-ui, sans-serif';
  x.fillText(state.customBids?'Manual order levels (user supplied), no trade executed.':'Not live. Historical bids may be gone. No trade executed.',95,587);
  x.fillStyle='#91aab0';x.font='16px ui-monospace, monospace';
  x.fillText('SOURCE • github.com/Aeripsen/donut-quant',95,614);
  const a=document.createElement('a');a.download='donut-quant-'+state.item.id+'-scenario.png';
  a.href=c.toDataURL('image/png');a.click();
}

async function copySummary(){
  if(!state.result)return;
  const text=shareableSummary(state.item,state.result)+(state.customBids?'\nOrder levels: user-entered, not independently verified.':'');
  try{await navigator.clipboard.writeText(text);toast('Copied ✓');}
  catch{toast('Copy unavailable');}
}

function applyCustomBids() {
  const raw=$('customBids').value;
  const lines=raw.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  if(!lines.length || lines.length>50){
    $('customMessage').textContent='Enter between 1 and 50 order levels.';
    return;
  }
  const bids=[];
  for(let n=0;n<lines.length;n++){
    const parts=lines[n].split(',');
    if(parts.length!==2){$('customMessage').textContent='Line '+(n+1)+': use price,remaining_units';return;}
    const p=Number(parts[0].trim()),q=Number(parts[1].trim());
    if(!Number.isFinite(p)||p<=0||!Number.isSafeInteger(q)||q<=0||q>100000000){
      $('customMessage').textContent='Line '+(n+1)+': positive numeric price and whole quantity required.';return;
    }
    bids.push({p,q});
  }
  state.customBids=bids;
  $('customMessage').textContent='Custom bid levels active ('+bids.length+'). Your data stays on this page.';
  renderOutcome();
}

async function start(){
  try {
    const response=await fetch('./assets/snapshot.json',{cache:'no-cache'});
    if(!response.ok)throw new Error('Market snapshot cannot be read (HTTP '+response.status+').');
    const data=await response.json();
    if(!Array.isArray(data.items)||!data.items.length)throw new Error('Market snapshot is empty.');
    state.data=data;
    $('numberItems').textContent=data.items.length;
    const requested=new URLSearchParams(location.search).get('item');
    select(data.items.find(i=>i.id===requested)?.id||'dried_kelp_block');
    $('search').addEventListener('input',fillAssetList);
    $('modeOrders').addEventListener('click',()=>{state.mode='orders';updateModes();renderOutcome();});
    $('modeAxe').addEventListener('click',()=>{state.mode='axe';updateModes();renderOutcome();});
    for(const id of ['quantityInput','costInput','feeInput','worthInput','axeInput']){
      $(id).addEventListener('input',renderOutcome);
    }
    for(const id of ['farmRate','chestRate'])$(id).addEventListener('input',updateCapacity);
    $('useCapacity').addEventListener('click',()=>{
      const cap=sellAxeCapacity({producedPerHour:Number($('farmRate').value),
        chestsPerHour:Number($('chestRate').value),hours:24});
      $('quantityInput').value=cap.units;renderOutcome();
    });
    $('applyBids').addEventListener('click',applyCustomBids);
    $('clearBids').addEventListener('click',()=>{
      state.customBids=null;$('customBids').value='';
      $('customMessage').textContent='Using the curated dated order levels.';renderOutcome();
    });
    $('reset').addEventListener('click',()=>select(state.item.id));
    $('copyResult').addEventListener('click',copySummary);
    $('shareCard').addEventListener('click',makeShareCard);
  } catch(error) {
    $('assetList').replaceChildren(createElement('p','empty','Data unavailable: '+error.message+'. Open this site over HTTPS or use a local web server.'));
    $('resultContext').textContent='The market snapshot could not be loaded.';
  }
}
start();
