"""Pure, testable economics of /sell and chest Sell Axe routing.

This simulator makes no claim about whether a specific in-game interface
currently implements this policy. Inputs MUST be externally verified.
Server 'worth' is the effective currently shown price, including any active
multiplier. Orders MUST be compatible product variants, not just item names.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence

CHEST_STACKS=27
STACK_SIZE=64
CHEST_UNITS=CHEST_STACKS*STACK_SIZE
AXE_HOURS=24.0

@dataclass(frozen=True)
class Bid:
    product_key: str
    unit_price: float
    remaining: int
    def __post_init__(self):
        if not self.product_key or self.unit_price < 0 or self.remaining < 0:
            raise ValueError("Invalid bid")

@dataclass(frozen=True)
class SaleResult:
    units: int
    order_units: int
    server_units: int
    order_gross: float
    server_gross: float
    tax_cost: float
    net_revenue: float
    def __post_init__(self):
        if self.units != self.order_units+self.server_units:
            raise ValueError("Conservation failure")

def route_sale(product_key: str, quantity: int, server_unit_value: float,
               bids: Sequence[Bid], order_fee_rate: float=0.0,
               server_fee_rate: float=0.0) -> SaleResult:
    """Highest compatible orders above the server value get filled first.

    Fees are scenario parameters, not assumed server rules. We do not mutate
    bid objects, and quantity cannot exceed order capacity without fallback.
    """
    if not isinstance(quantity,int) or quantity<0 or server_unit_value<0:
        raise ValueError("Invalid quantity/worth")
    if any(not 0<=v<1 for v in (order_fee_rate,server_fee_rate)):
        raise ValueError("Fee rates must be in [0,1)")
    remaining=quantity;order_gross=0.0;order_units=0
    for bid in sorted((b for b in bids if b.product_key==product_key and b.unit_price>server_unit_value),
                      key=lambda b:-b.unit_price):
        take=min(remaining,bid.remaining)
        order_gross+=take*bid.unit_price
        order_units+=take
        remaining-=take
        if remaining==0:
            break
    server_gross=remaining*server_unit_value
    tax=order_gross*order_fee_rate+server_gross*server_fee_rate
    return SaleResult(quantity,order_units,remaining,order_gross,
                      server_gross,tax,order_gross+server_gross-tax)

@dataclass(frozen=True)
class AxeRun:
    chests: int
    units: int
    gross_revenue: float
    order_units: int
    server_units: int
    variable_cost: float
    axe_cost: float
    other_cost: float
    net_profit: float
    revenue_per_chest: float | None

def simulate_axe(product_key: str, available_units: int, chest_cycles: int,
                 server_unit_value: float, bids: Sequence[Bid],
                 unit_acquisition_cost: float=0.0,
                 axe_money_equivalent: float=0.0,
                 other_cost: float=0.0,
                 order_fee_rate: float=0.0,
                 server_fee_rate: float=0.0) -> AxeRun:
    """Full 27x64 chests only. Farm rate and axe lifespan constrain input.

    The full chest restriction is for comparison, not a rule of the plugin.
    Treat axe_money_equivalent as the shadow price of 1500 shards or its
    observed AH acquisition cost, not both.
    """
    if any(v<0 for v in (available_units,chest_cycles,unit_acquisition_cost,
                        axe_money_equivalent,other_cost)):
        raise ValueError("Negative costs/capacities are invalid")
    if not isinstance(available_units,int) or not isinstance(chest_cycles,int):
        raise ValueError("Quantities must be integer")
    chests=min(chest_cycles,available_units//CHEST_UNITS)
    qty=chests*CHEST_UNITS
    result=route_sale(product_key,qty,server_unit_value,bids,order_fee_rate,server_fee_rate)
    input_cost=qty*unit_acquisition_cost
    net=result.net_revenue-input_cost-axe_money_equivalent-other_cost
    return AxeRun(chests,qty,result.order_gross+result.server_gross,
                  result.order_units,result.server_units,input_cost,
                  axe_money_equivalent,other_cost,net,
                  result.net_revenue/chests if chests else None)

def capacity_24h(production_units_per_hour: float, chest_cycles_per_hour: float) -> tuple[int,int]:
    """Physical upper bound with no assumptions about sale demand."""
    if production_units_per_hour<0 or chest_cycles_per_hour<0:
        raise ValueError("Negative rates")
    physical_chests=int(min(production_units_per_hour*AXE_HOURS/CHEST_UNITS,
                            chest_cycles_per_hour*AXE_HOURS))
    return physical_chests,physical_chests*CHEST_UNITS

def breakeven_units(axe_money_equivalent:float,unit_net_margin:float)->int|None:
    """Number of items required to recover a one-day axe cost."""
    if axe_money_equivalent<0:
        raise ValueError("negative cost")
    if unit_net_margin<=0:
        return None
    import math
    return math.ceil(axe_money_equivalent/unit_net_margin)

if __name__=="__main__":
    r=simulate_axe("dried_kelp_block",CHEST_UNITS,1,750,[],
                    axe_money_equivalent=0)
    print(f"Illustrative scenario ONLY: 1 chest at effective $750 worth -> gross ${r.gross_revenue:,.0f}")
