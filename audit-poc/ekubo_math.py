"""Bit-exact transcription of Ekubo math (commit 4a2e3ea / 195e0c0) + vault math."""
U128 = (1<<128)-1
U256 = (1<<256)-1
TWO128 = 1<<128
SCALE_18 = 10**18

MAX_TICK_MAGNITUDE = 88722883

MULS = [
 (0x1, 0xfffff79c8499329c7cbb2510d893283b),
 (0x2, 0xffffef390978c398134b4ff3764fe410),
 (0x4, 0xffffde72140b00a354bd3dc828e976c9),
 (0x8, 0xffffbce42c7be6c998ad6318193c0b18),
 (0x10, 0xffff79c86a8f6150a32d9778eceef97c),
 (0x20, 0xfffef3911b7cff24ba1b3dbb5f8f5974),
 (0x40, 0xfffde72350725cc4ea8feece3b5f13c8),
 (0x80, 0xfffbce4b06c196e9247ac87695d53c60),
 (0x100, 0xfff79ca7a4d1bf1ee8556cea23cdbaa5),
 (0x200, 0xffef3995a5b6a6267530f207142a5764),
 (0x400, 0xffde7444b28145508125d10077ba83b8),
 (0x800, 0xffbceceeb791747f10df216f2e53ec57),
 (0x1000, 0xff79eb706b9a64c6431d76e63531e929),
 (0x2000, 0xfef41d1a5f2ae3a20676bec6f7f9459a),
 (0x4000, 0xfde95287d26d81bea159c37073122c73),
 (0x8000, 0xfbd701c7cbc4c8a6bb81efd232d1e4e7),
 (0x10000, 0xf7bf5211c72f5185f372aeb1d48f937e),
 (0x20000, 0xefc2bf59df33ecc28125cf78ec4f167f),
 (0x40000, 0xe08d35706200796273f0b3a981d90cfd),
 (0x80000, 0xc4f76b68947482dc198a48a54348c4ed),
 (0x100000, 0x978bcb9894317807e5fa4498eee7c0fa),
 (0x200000, 0x59b63684b86e9f486ec54727371ba6ca),
 (0x400000, 0x1f703399d88f6aa83a28b22d4a1f56e3),
 (0x800000, 0x3dc5dac7376e20fc8679758d1bcdcfc),
 (0x1000000, 0xee7e32d61fdb0a5e622b820f681d0),
 (0x2000000, 0xde2ee4bc381afa7089aa84bb66),
 (0x4000000, 0xc0d55d4d7152c25fb139),
]

def unsafe_mul_shift(x, mul):
    return ((x * mul) % (1<<256)) >> 128

def tick_to_sqrt_ratio(mag, sign):
    assert mag <= MAX_TICK_MAGNITUDE, 'TICK_MAGNITUDE'
    ratio = TWO128
    if mag & 1:
        ratio = 0xfffff79c8499329c7cbb2510d893283b
    for bit, c in MULS[1:]:
        if mag & bit:
            ratio = unsafe_mul_shift(ratio, c)
    if not sign and mag != 0:
        ratio = U256 // ratio
    return ratio

def _div(x, z, round_up):
    q, r = divmod(x, z)
    return q + 1 if (round_up and r) else q

def muldiv(x, y, z, round_up):
    assert z != 0
    return _div(x*y, z, round_up)

def amount0_delta(a, b, L, round_up):
    lo, hi = (a, b) if a < b else (b, a)
    assert lo != 0
    if L == 0 or lo == hi:
        return 0
    r0 = muldiv(L << 128, hi - lo, hi, round_up)     # u256{low:0,high:L} * (hi-lo) / hi
    r = _div(r0, lo, round_up)
    assert r < (1<<256)
    return r  # fits u128 assumed

def amount1_delta(a, b, L, round_up):
    lo, hi = (a, b) if a < b else (b, a)
    assert lo != 0
    if L == 0 or lo == hi:
        return 0
    prod = (hi - lo) * L
    assert prod >> 256 == 0, 'OVERFLOW_AMOUNT1_DELTA'
    if round_up and (prod & U128):
        return (prod >> 128) + 1
    return prod >> 128

def liq_delta_to_amount_delta(price, L, sign, lo, hi):
    """sign False => positive delta (deposit, rounds up). sign True => removal, rounds down."""
    if L == 0:
        return (0, 0)
    round_up = not sign
    if price <= lo:
        return (amount0_delta(lo, hi, L, round_up), 0)
    elif price < hi:
        return (amount0_delta(price, hi, L, round_up), amount1_delta(lo, price, L, round_up))
    else:
        return (0, amount1_delta(lo, hi, L, round_up))

def max_liquidity_for_token0(lo, hi, amount):
    if amount == 0:
        return 0
    prod = lo * hi
    assert prod >> 384 == 0, 'OVERFLOW_MLFT0_0'   # limb3 must be zero
    # floor(floor(lo*hi / 2^128) * amount / (hi-lo))
    return ((prod >> 128) * amount) // (hi - lo)

def max_liquidity_for_token1(lo, hi, amount):
    if amount == 0:
        return 0
    return (amount << 128) // (hi - lo)

def max_liquidity(price, lo, hi, amount0, amount1):
    assert lo < hi
    if price <= lo:
        return max_liquidity_for_token0(lo, hi, amount0)
    elif price < hi:
        return min(max_liquidity_for_token0(price, hi, amount0),
                   max_liquidity_for_token1(lo, price, amount1))
    else:
        return max_liquidity_for_token1(lo, hi, amount1)

def compute_fee(amount, fee):
    p = amount * fee
    hi, lo = p >> 128, p & U128
    return hi if lo == 0 else hi + 1
