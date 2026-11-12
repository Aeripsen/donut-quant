"""Browser-level smoke test for the public demo. Requires local HTTP server.
Run: python tests/browser_smoke.py
Uses system Edge through Playwright; screenshots and exports stay private.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import os

URL=os.environ.get("DONUT_QUANT_SITE_URL","http://127.0.0.1:8787/")
EDGE=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT=Path(__file__).resolve().parents[1]/"private"/"site_qa"
OUT.mkdir(parents=True,exist_ok=True)

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path=EDGE)
    page=browser.new_page(viewport={"width":1440,"height":1080},device_scale_factor=1,accept_downloads=True)
    errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.goto(URL,wait_until="networkidle")
    assert page.locator(".asset-row").count()==6, "Asset scanner failed to load"
    assert "Dried Kelp Block" in page.locator("#detailName").inner_text()
    print("DEFAULT GROSS:",page.locator("#revenueTotal").inner_text())
    print("FILLED:",page.locator("#orderUnits").inner_text(),
          "FALLBACK:",page.locator("#fallbackUnits").inner_text())
    assert page.locator("#orderUnits").inner_text()=="1,443"
    assert page.locator("#fallbackUnits").inner_text()=="285"
    assert "Cost basis needed" in page.locator("#profitNet").inner_text()
    page.screenshot(path=str(OUT/"desktop.png"),full_page=True)
    page.locator(".asset-row",has_text="Elytra").click()
    assert page.locator("#detailName").inner_text()=="Elytra"
    page.locator("#quantityInput").fill("20")
    assert page.locator("#unsoldUnits").inner_text()=="5"
    assert page.locator("#orderUnits").inner_text()=="15"
    page.locator("#modeAxe").click()
    assert "Enter the effective server" in page.locator("#resultContext").inner_text()
    page.locator("#worthInput").fill("90000")
    page.locator("#axeInput").fill("0")
    page.locator("#costInput").fill("100")
    assert page.locator("#profitNet").inner_text()!="Cost basis needed"
    page.locator("#modeOrders").click()
    page.locator("#quantityInput").fill("1")
    page.locator(".custom-book summary").click()
    page.locator("#customBids").fill("800000000,2\n750000000,1")
    page.locator("#applyBids").click()
    assert page.locator("#orderUnits").inner_text()=="1"
    assert "800M" in page.locator("#revenueTotal").inner_text(), (page.locator("#revenueTotal").inner_text(), page.locator("#customMessage").inner_text(), page.locator("#customBids").input_value())
    assert "Custom bid levels active" in page.locator("#customMessage").inner_text()
    page.locator("#clearBids").click()
    assert "525M" in page.locator("#revenueTotal").inner_text()
    with page.expect_download() as info:
        page.locator("#shareCard").click()
    d=info.value
    d.save_as(OUT/"downloaded_card.png")
    assert (OUT/"downloaded_card.png").stat().st_size>15000
    print("EXPORT:",d.suggested_filename)

    mobile=browser.new_page(viewport={"width":390,"height":844},device_scale_factor=1)
    mobile.goto(URL,wait_until="networkidle")
    assert mobile.locator(".asset-row").count()==6
    mobile.screenshot(path=str(OUT/"mobile.png"),full_page=True)
    print("JS ERRORS:",errors)
    assert not errors
    browser.close()
print("BROWSER SMOKE: PASS")
