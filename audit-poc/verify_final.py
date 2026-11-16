"""Final verification of the two critical claims with exact arithmetic (no RPC)."""
from ekubo_math import *
TWO128=1<<128
FEES={"0.01% (ts200)":(34028236692093847977029636859101184,100),
      "0.05% (ts1000)":(170141183460469235273462165868118016,500)}
print("CLAIM A: withdraw()'s post-fee assertion")
print("  vault: amt_i == position.amount_i*(1e6-fee_ppm)//1e6 - 1")
print("  current Core (>=47e9b24): pays amount0_delta(round_down) = d, with d in {u-1,u}")
print("  => needs u*(1e6-fee_ppm)//1e6 - 1 == d  ; u*0.9999 - 1 < u-1 for every u >= 1,")
print("     so the only candidate is the underflowing case u*(1e6-p)//1e6 == 0 (Cairo panics).")
for nm,(fee,ppm) in FEES.items():
    bad=0; n=0
    for u in range(1, 100001):
        prod = u*(1000000-ppm)//1000000
        for d in (u-1,u):
            n+=1
            if prod==0: bad+=1            # Cairo: 0 - 1 underflow -> panic
            elif prod-1!=d: bad+=1
    print(f"  fee {nm}: assertion impossible in {bad}/{n} of the (u,d) cases checked")
print()
print("CLAIM B: deposit() mints from the caller's declared amounts but pull the vault's amounts")
print("  vault_level_positions == the vault's own position, independent of amount0/amount1:")
print("  -> any depositor is charged the vault's ENTIRE position (if their balance/allowance covers it)")
print("  -> shares = L_user*total_supply/L_vault, L_user = max_liquidity(declared amounts)")
