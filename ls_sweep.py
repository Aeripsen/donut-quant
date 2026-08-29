import json, os, time, urllib.parse, urllib.request
items=json.load(open("mcdata/items.json",encoding="utf-8"))
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
out={}
tracked=0
for it in items:
    dn=it["displayName"]; name=it["name"]
    path=f"api/lootseller/{name}.json"
    if os.path.exists(path):
        d=json.load(open(path,encoding="utf-8"))
    else:
        url="https://www.lootseller.io/api/prices?item="+urllib.parse.quote(dn)+"&tf=1d"
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=25) as r: d=json.loads(r.read().decode("utf-8"))
        except Exception as e:
            d={"error":str(e)[:100]}
        json.dump(d,open(path,"w",encoding="utf-8"))
        time.sleep(0.25)
    c=d.get("candles") or []; oc=d.get("orderCandles") or []
    if c or oc:
        tracked+=1
        out[name]={"display":dn,"ah_floor_close":c[-1]["c"] if c else None,"ah_floor_low":c[-1]["l"] if c else None,"ah_floor_t":c[-1]["t"] if c else None,"ah_n":c[-1]["n"] if c else None,"order_bid_close":oc[-1]["c"] if oc else None,"order_bid_high":oc[-1]["h"] if oc else None,"order_bid_t":oc[-1]["t"] if oc else None,"lastUpdated":d.get("lastUpdated"),"ah_candles":len(c),"order_candles":len(oc)}
json.dump(out,open("api/lootseller_summary.json","w",encoding="utf-8"),indent=1)
print("tracked items:",tracked,"of",len(items))
