import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {simulate,sellAxeCapacity,quoteGapPercent,CHEST_UNITS} from '../docs/assets/engine.mjs';

const here=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(fs.readFileSync(path.join(here,'../docs/assets/snapshot.json'),'utf8'));
const get=id=>data.items.find(i=>i.id===id);

test('snapshot has source-linked, typed price observations',()=>{
  assert.equal(data.status,'CURATED_HISTORICAL_SNAPSHOT_NOT_LIVE');
  assert.equal(data.items.length,6);
  for (const i of data.items) {
    assert.ok(i.snapshotAt&&i.source.startsWith('https://donutstats.io/'));
    assert.ok(i.historical>0&&i.bid>=0&&i.cheapest>0);
    assert.ok(Array.isArray(i.depth));
  }
});

test('one chest dried kelp routes at diminishing bids, then worth',()=>{
  const i=get('dried_kelp_block');
  const res=simulate({quantity:CHEST_UNITS,bids:i.depth,mode:'axe',worth:750,
                      feeRate:0,unitCost:0,axeCost:0});
  assert.equal(res.orderUnits,1443);
  assert.equal(res.worthUnits,285);
  assert.equal(res.unsold,0);
  assert.ok(Math.abs(res.totalGross-1308499.1)<1e-6);
  assert.ok(Math.abs(res.totalGross-CHEST_UNITS*750-12499.1)<1e-6);
});

test('24 hours production does not multiply the top bid infinitely',()=>{
  const i=get('dried_kelp_block');
  const cap=sellAxeCapacity({producedPerHour:1728,chestsPerHour:1,hours:24});
  assert.equal(cap.units,41472);
  const res=simulate({quantity:cap.units,bids:i.depth,mode:'axe',worth:750,feeRate:0});
  assert.equal(res.orderUnits,1443);
  assert.equal(res.worthUnits,41472-1443);
  assert.equal(res.net,null);
});

test('manual orders leave unfilled Elytras in inventory',()=>{
  const i=get('elytra');
  const out=simulate({quantity:20,bids:i.depth,mode:'orders',feeRate:0,unitCost:null});
  assert.equal(out.orderUnits,15);
  assert.equal(out.unsold,5);
  assert.equal(out.worthUnits,0);
  assert.equal(out.net,null);
  assert.ok(out.totalGross < 20*i.asking);
});

test('net is unknown without cost basis and explicit axle cost',()=>{
  const a=simulate({quantity:64,bids:[{p:500,q:64}],mode:'orders',feeRate:0.02});
  assert.equal(a.net,null);
  const b=simulate({quantity:64,bids:[{p:500,q:64}],mode:'orders',feeRate:0.02,unitCost:450});
  assert.equal(b.net,64*500*0.98-64*450);
  const c=simulate({quantity:64,bids:[],mode:'axe',worth:750,unitCost:450,axeCost:null});
  assert.equal(c.net,null);
});

test('invalid inputs and quoted percent comparability',()=>{
  assert.throws(()=>simulate({quantity:-1,bids:[]}),RangeError);
  assert.throws(()=>simulate({quantity:1.5,bids:[]}),RangeError);
  assert.throws(()=>simulate({quantity:1,bids:[{p:500,q:-3}]}),RangeError);
  assert.throws(()=>simulate({quantity:1,bids:[],mode:'axe'}),RangeError);
  assert.ok(quoteGapPercent(358999982,525000000)>46);
});
