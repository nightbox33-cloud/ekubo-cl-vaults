from ekubo_math import *
TWO128=1<<128
FEE_01=34028236692093847977029636859101184
LO=tick_to_sqrt_ratio(104000,False); HI=tick_to_sqrt_ratio(124000,False); PX=tick_to_sqrt_ratio(114000,False)
def expected(up,fee):
    pf=1000000-(fee*1000000//TWO128)
    return (up*pf//1000000-1) if up>0 else 0
def d0(L): return liq_delta_to_amount_delta(PX,L,True,LO,HI)[0]
def u0(L): return liq_delta_to_amount_delta(PX,L,False,LO,HI)[0]
print(f"{'L':>26}{'amount0(round-up)':>26}{'new_core_pay':>26}{'expected':>26}{'new':>7}{'old_pay':>26}{'old':>6}")
for base in (10**12,10**15,10**18,10**20,10**21,10**22,10**23,10**24,10**25):
    L=base; up=u0(L); d=d0(L)
    new_ok = d==expected(up,FEE_01)
    old_pay=d-compute_fee(d,FEE_01); old_ok = old_pay==expected(up,FEE_01)
    print(f"{L:>26}{up:>26}{d:>26}{expected(up,FEE_01):>26}{str(new_ok):>7}{old_pay:>26}{str(old_ok):>6}")
print("\nrevert fraction over 2000 consecutive L (old core) / (new core):")
for base in (10**15,10**18,10**20,10**21,10**22,10**23):
    o=n=0
    for L in range(base,base+2000):
        up=u0(L); d=d0(L); e=expected(up,FEE_01)
        o += (d-compute_fee(d,FEE_01))!=e
        n += d!=e
    print(f"  L~1e{len(str(base))-1:<2}: old {o:>5}/2000   new {n:>5}/2000")
