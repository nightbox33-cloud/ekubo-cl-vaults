"""FINDING 2 -- withdraw()'s post-fee assertion. Each redemption uses a fresh vault+position."""
import sys
from ekubo_math import SCALE_18, max_liquidity, liq_delta_to_amount_delta, TWO128, compute_fee
from cl_vault_poc import PoolCfg, Ekubo, Vault
FEE_01=34028236692093847977029636859101184
XSTRK,STRK='xSTRK','STRK'
def fresh(wf, h):
    ek=Ekubo([PoolCfg(XSTRK,STRK,18,18,FEE_01,200,104000,124000,114000)],wf)
    v=Vault(ek,SCALE_18,SCALE_18)
    v.bal[('victim',XSTRK)]=h; v.bal[('victim',STRK)]=h
    s=v.deposit('victim',h,h,'victim')
    L=max_liquidity(ek.pools[0].price,ek.pools[0].lo,ek.pools[0].hi,v.free[XSTRK],v.free[STRK])
    v.rebalance([L])
    return v,ek,s
h=200000*10**18
for wf,label in ((False,"CURRENT Ekubo Core (>= 47e9b24, withdrawal fee REMOVED)"),
                 (True ,"HISTORICAL Ekubo Core (4a2e3ea, withdrawal fee charged)")):
    print("="*95); print(label); print("="*95)
    v,ek,s=fresh(wf,h)
    P0,P1,liq=ek.token_info(0)
    print(f"vault: {h/1e18:g}+{h/1e18:g} deposited -> {s/1e18:g} shares, Ekubo liquidity {liq}")
    print(f"position: {P0/1e18:.6f} xSTRK + {P1/1e18:.6f} STRK")
    for frac in (1,2,4,10,100,1000):
        v,ek,s=fresh(wf,h)
        sh=s//frac
        d0=liq_delta_to_amount_delta(ek.pools[0].price,sh*liq//s,True,ek.pools[0].lo,ek.pools[0].hi)[0]
        u0=liq_delta_to_amount_delta(ek.pools[0].price,sh*liq//s,False,ek.pools[0].lo,ek.pools[0].hi)[0]
        pf=1000000-(FEE_01*1000000//TWO128); exp=u0*pf//1000000-1
        pay = d0 - (compute_fee(d0,FEE_01) if wf else 0)
        try:
            v.withdraw('victim',sh,'victim'); res="OK"
        except AssertionError as e:
            res=f"REVERT ({e})"
        print(f"  redeem {sh:>26} shares (1/{frac:<5}) -> core pays {pay:<22} vault expects {exp:<22} {res}")
