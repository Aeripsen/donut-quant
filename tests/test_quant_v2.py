"""Regression tests for source classification, unit discipline and sale routing."""
import sys
import tempfile
import unittest
import gzip
from contextlib import closing
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"quant"))
from personal_ledger import money,classify,read_observations,report
from sell_routing import Bid,route_sale,simulate_axe,capacity_24h,breakeven_units,CHEST_UNITS
from donutstats_snapshot import plan,get_json

class TestLedger(unittest.TestCase):
    def test_money_suffix(self):
        self.assertEqual(money("29.5K"),29_500)
        self.assertEqual(money("1.8M"),1_800_000)
        self.assertEqual(money("1,000"),1000)
        with self.assertRaises(ValueError):
            money("maybe 4M")
    def test_listing_is_not_revenue_and_tax_is_quoted(self):
        e=classify("You listed 1 Shulker Box for $ 25M (+$ 500K tax)")
        self.assertEqual(e["type"],"ah_listing")
        self.assertEqual(e["amount"],25_000_000)
        self.assertEqual(e["tax_quote"],500_000)
        self.assertNotEqual(e["certainty"],"observed_cash_inflow")
    def test_purchase_sale_order_and_aggregate(self):
        self.assertEqual(classify("You bought 16 Spruce Signs for $ 29.5K")["type"],"ah_purchase")
        self.assertEqual(classify("xDocked bought your Gravel for $ 50K")["type"],"ah_sale")
        self.assertEqual(classify("DlcGumChew delivered you 26 Shulker Boxes")["quantity"],26)
        self.assertEqual(classify("Your Shulker Box order is complete!")["type"],"order_completed")
        self.assertEqual(classify("You earned $ 8.7M from auction")["type"],"ah_earnings_summary")
        self.assertIsNone(classify("Players delivered you 65")) # no item identification
    def test_duplicate_profile_copy_is_not_double_counted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for prof in ("DonutSMP","DonutSMP (1)"):
                p=root/prof/"logs";p.mkdir(parents=True)
                with gzip.open(p/"2026-09-01-1.log.gz","wt",encoding="utf-8") as f:
                    f.write("[11:22:33] [Render thread/INFO]: [System] [CHAT] You bought 1 Stone for $ 4K\n")
            ev,m=read_observations([root/"DonutSMP",root/"DonutSMP (1)"])
            self.assertEqual(len(ev),1)
            self.assertEqual(m["raw_chat_lines"],2)
            self.assertEqual(m["deduplicated_chat_lines"],1)
    def test_no_double_counted_auction_summary(self):
        rows=[dict(type="ah_sale",amount=100,item="Gravel",quantity=None,date="2026-11-12"),
              dict(type="ah_earnings_summary",amount=100,item=None,quantity=None,date="2026-11-12")]
        r=report(rows,{"files_read":1})
        self.assertEqual(r["observed_auction_sales_gross"],100)
        self.assertIsNone(r["net_profit"])

class TestRouting(unittest.TestCase):
    def test_depth_fallback_and_sorted_bids(self):
        result=route_sale("diamond",8,100,[Bid("diamond",110,3),Bid("diamond",120,2),Bid("stone",999,100)])
        self.assertEqual((result.order_units,result.server_units),(5,3))
        self.assertAlmostEqual(result.net_revenue,870)
    def test_exact_variant_match(self):
        result=route_sale("elytra",1,100,[Bid("elytra[mending]",1000,1)])
        self.assertEqual(result.order_units,0)
    def test_fees_only_when_explicit(self):
        r=route_sale("glass",10,100,[Bid("glass",200,6)],.02,.03)
        self.assertAlmostEqual(r.tax_cost,6*200*.02+4*100*.03)
    def test_axe_cost_and_capacity(self):
        n=CHEST_UNITS*2
        r=simulate_axe("kelp",n,2,750,[],axe_money_equivalent=1_500_000)
        self.assertEqual(r.chests,2)
        self.assertAlmostEqual(r.net_profit,n*750-1_500_000)
        self.assertEqual(capacity_24h(CHEST_UNITS,1), (24,CHEST_UNITS*24))
        self.assertEqual(breakeven_units(1000,250),4)
        self.assertIsNone(breakeven_units(1000,0))
    def test_validation(self):
        with self.assertRaises(ValueError): route_sale("glass",-1,100,[])
        with self.assertRaises(ValueError): route_sale("glass",1,100,[],order_fee_rate=1)

class TestAPI(unittest.TestCase):
    def test_allowed_endpoints(self):
        p=plan("SamplePlayer",["elytra[mending,unbreaking:3]"])
        self.assertEqual(p[0],("status","/status"))
        self.assertIn("%5B",p[-2][1])
    def test_reject_external_host(self):
        with self.assertRaises(ValueError):
            get_json("//evil.example", "dummy")
        with self.assertRaises(ValueError):
            get_json("/../key","dummy")

class TestEvidenceDatabase(unittest.TestCase):
    def test_schema_ingests_verified_fill_but_not_sale_from_closure(self):
        from linked_db import connect
        from import_market import ingest_payload
        with tempfile.TemporaryDirectory() as d:
            with closing(connect(Path(d)/"test.sqlite")) as con:
                with con:
                    con.execute("""INSERT INTO source
                    (source_id,source_kind,file_path,sha256,imported_utc)
                    VALUES('test-source','fixture','fixture.json','hash','2026-11-12T00:00Z')""")
                    t="2026-11-12T00:00:00Z"
                    product={"key":"elytra[mending]","item":"elytra","variant":"mending","details":None}
                    fills={"entries":[{"orderId":98,"product":product,"at":1794441600000,
                                      "quantity":2,"paid":900000000}]}
                    result=ingest_payload(con,"global_order_fills",fills,"test-source",t)
                    self.assertEqual(result["fills"],1)
                    closed={"entries":[{"id":17,"product":product,"count":1,
                                        "price":800000000,"seller":"Trader"}]}
                    ingest_payload(con,"global_auction_closures",closed,"test-source",t)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM order_fill").fetchone()[0],1)
                self.assertEqual(con.execute("SELECT lifecycle FROM auction_listing_observation").fetchone()[0],
                                 "closed_unknown")
                self.assertEqual(con.execute("SELECT COUNT(*) FROM personal_event").fetchone()[0],0)
    def test_order_conservation_rejects_mismatch(self):
        from linked_db import connect
        from import_market import ingest_payload
        with tempfile.TemporaryDirectory() as d:
            with closing(connect(Path(d)/"test.sqlite")) as con:
                con.execute("""INSERT INTO source
                   (source_id,source_kind,file_path,sha256,imported_utc)
                   VALUES('s','fixture','f','h','2026-11-12')""")
                p={"key":"glass","item":"glass","variant":""}
                wrong={"entries":[{"id":1,"product":p,"unitPrice":900,
                                   "amount":10,"delivered":3,"remaining":8}]}
                r=ingest_payload(con,"player_orders",wrong,"s","2026-11-12")
                self.assertEqual(r["invalid"],1)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM order_observation").fetchone()[0],0)
    def test_global_endpoint_selection(self):
        from donutstats_snapshot import plan
        tasks=dict(plan("SamplePlayer",[],include_global=True))
        self.assertEqual(tasks["global_order_fills"],"/orders/fills?limit=1000")
        self.assertEqual(tasks["global_closed_orders"],"/orders/history?limit=1000")

if __name__=="__main__":
    unittest.main()
