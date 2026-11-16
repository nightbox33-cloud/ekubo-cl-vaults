import math
def priceToTick(price, isRoundDown, tickSpacing, d0, d1):
    adj = price * (10**d1) / (10**d0)
    v = math.floor(math.log(adj)/math.log(1.000001)) if isRoundDown else math.ceil(math.log(adj)/math.log(1.000001))
    t = math.floor(v/tickSpacing)*tickSpacing
    return -t if t<0 else t
lo=priceToTick(1.11776, False, 200, 18, 18)
hi=priceToTick(1.121,  False, 200, 18, 18)
print("deploy_cl_vault.ts computed bounds:", lo, hi, " (stored as i129 mag/sign)")
