"""
Bit-exact model of ConcLiquidityVault (troves_clvaults v2.0.0, commit aa77b9d) with the
Ekubo Positions/Core math it depends on.  Transcribed 1:1 from:
  /home/user/ekubo-cl-vaults/src/cl_vault/cl_vault.cairo
  ekubo-starknet-contracts src/{positions.cairo, math/{liquidity,delta,muldiv,ticks,max_liquidity,fee}.cairo}
No RPC, no fork: everything is integer arithmetic on the real configured parameters.
"""
import os
STRICT = os.environ.get('STRICT','1')=='1'
from ekubo_math import (tick_to_sqrt_ratio, liq_delta_to_amount_delta, max_liquidity,
                        compute_fee, TWO128, SCALE_18)

class PoolCfg:
    def __init__(self, token0, token1, dec0, dec1, fee, tick_spacing, lo, hi, price_tick):
        self.token0=token0; self.token1=token1; self.dec0=dec0; self.dec1=dec1
        self.fee=fee; self.tick_spacing=tick_spacing
        self.lo_tick=lo; self.hi_tick=hi; self.price_tick=price_tick
        self.lo = tick_to_sqrt_ratio(abs(lo), lo<0)
        self.hi = tick_to_sqrt_ratio(abs(hi), hi<0)
        self.price = tick_to_sqrt_ratio(abs(price_tick), price_tick<0)
    def __repr__(self): return f"Pool({self.token0}/{self.token1}, fee={self.fee}, ts={self.tick_spacing}, bounds=({self.lo_tick},{self.hi_tick}), tick={self.price_tick})"

class Ekubo:
    """Positions + Core state for the vault's positions."""
    def __init__(self, pools, withdrawal_fee):
        self.pools=pools
        self.n = len(pools)
        self.liquidity=[0]*self.n
        self.nft_id=[0]*self.n
        self.pos_bal={}           # token -> Positions contract balance
        self.withdrawal_fee = withdrawal_fee  # True: Core 4a2e3ea ; False: Core >= 47e9b24
        self.next_nft=1

    # Positions.get_token_info -> rounding DOWN (sign=True)
    def token_info(self, i):
        p=self.pools[i]
        a0,a1 = liq_delta_to_amount_delta(p.price, self.liquidity[i], True, p.lo, p.hi)
        return a0,a1,self.liquidity[i]

    def positions_deposit(self, i, recipient):
        """Positions.deposit(id,...): uses the WHOLE Positions balance; clears leftovers to recipient."""
        p=self.pools[i]
        b0=self.pos_bal.get(p.token0,0); b1=self.pos_bal.get(p.token1,0)
        L=max_liquidity(p.price,p.lo,p.hi,b0,b1)
        paid0,paid1 = liq_delta_to_amount_delta(p.price,L,False,p.lo,p.hi)  # round up
        assert paid0<=b0 and paid1<=b1
        self.pos_bal[p.token0]=b0-paid0
        self.pos_bal[p.token1]=b1-paid1
        self.liquidity[i]+=L
        left0=self.pos_bal.get(p.token0,0); left1=self.pos_bal.get(p.token1,0)
        self.pos_bal[p.token0]=0; self.pos_bal[p.token1]=0      # clear_minimum_to_recipient
        return L, paid0, paid1, left0, left1

    def positions_withdraw(self, i, L):
        """Positions.withdraw(id,...,liquidity,0,0,false) -> amounts actually transferred out."""
        p=self.pools[i]
        d0,d1 = liq_delta_to_amount_delta(p.price,L,True,p.lo,p.hi)   # round down
        if self.withdrawal_fee:
            d0 -= compute_fee(d0,p.fee); d1 -= compute_fee(d1,p.fee)
        assert L<=self.liquidity[i]
        self.liquidity[i]-=L
        return d0,d1

class Vault:
    def __init__(self, ekubo, init0, init1, fee_bps=1000):
        self.e=ekubo; self.supply=0; self.init=(init0,init1)
        self.free={}       # vault contract free token balance
        self.bal={}        # (holder, token) -> balance of arbitrary holders (for PoC accounting)
        self.shares={}
    # --- helpers
    def _get(self,who,tok): return self.bal.get((who,tok),0)
    def _set(self,who,tok,v):
        if v==0: self.bal.pop((who,tok),None)
        else: self.bal[(who,tok)]=v
    def total_supply(self): return self.supply

    def initial_shares(self,a0,a1):
        p=self.e.pools[0]
        s0=SCALE_18//(10**p.dec0); s1=SCALE_18//(10**p.dec1)
        a0n=a0*s0; a1n=a1*s1
        sh0=a0n*SCALE_18//self.init[0] if self.init[0]>0 else 0
        sh1=a1n*SCALE_18//self.init[1] if self.init[1]>0 else 0
        return (sh0+sh1)//2

    def convert_to_shares(self,a0,a1):
        tot0=tot1=0; ranges=[]
        for i in range(self.e.n):
            r0,r1,rl=self.e.token_info(i); tot0+=r0; tot1+=r1
            ranges.append((rl,r0,r1))
            if i==0 and rl==0 and self.supply>0:
                raise AssertionError("Errors::pool_0_has_no_liquidity")
        if self.supply==0:
            return self.initial_shares(a0,a1), [], [], tot0, tot1
        adj0,adj1=a0,a1
        if tot1==0:
            adj1=0
        else:
            vault_ratio = tot0*SCALE_18//tot1
            user_ratio  = a0*SCALE_18//a1           # ZeroDivisionError if a1 == 0
            if vault_ratio>user_ratio:
                adj0 = a1*vault_ratio//SCALE_18
                adj1 = a1
            else:
                adj0 = a0
                adj1 = a0*SCALE_18//vault_ratio     # ZeroDivisionError if vault_ratio == 0
        shares=0; user_pos=[]
        for i in range(self.e.n):
            p=self.e.pools[i]; rl,r0,r1=ranges[i]
            d0 = adj0*r0//tot0 if tot0>0 else 0
            d1 = adj1*r1//tot1 if tot1>0 else 0
            L  = max_liquidity(p.price,p.lo,p.hi,d0,d1)
            u0,u1 = liq_delta_to_amount_delta(p.price,L,False,p.lo,p.hi)
            user_pos.append((L,u0,u1))
            if i==0:
                shares = L*self.supply//rl
            else:
                s_other = L*self.supply//rl
                if s_other>0 and s_other//10**9 != shares//10**9:
                    raise AssertionError(f"Errors::shares_mismatch({s_other},{shares})")
        return shares,user_pos,ranges,tot0,tot1

    def _process_deposit(self,caller,a0,a1):
        assert a0>0 or a1>0,'amounts cannot be zero'
        shares,user_pos,vault_pos,tot0,tot1=self.convert_to_shares(a0,a1)
        assert shares>0,'zero shares'
        if self.supply>0: assert tot0>0 or tot1>0,'empty vault'
        if self.supply==0:
            assert len(vault_pos)==0,'unexpected flow'
            p=self.e.pools[0]
            self._set(caller,p.token0,self._get(caller,p.token0)-a0)   # transfer_from
            self._set(caller,p.token1,self._get(caller,p.token1)-a1)
            self.free[p.token0]=self.free.get(p.token0,0)+a0
            self.free[p.token1]=self.free.get(p.token1,0)+a1
            return shares
        assert len(vault_pos)==self.e.n,'unexpected flow'
        for i in range(self.e.n):
            p=self.e.pools[i]
            rl,r0,r1 = vault_pos[i]
            # _pay_ekubo(caller): amount0/amount1 come from vault_level_positions (VAULT totals),
            # NOT from the depositor's own user_level_positions -> BUG
            assert self._get(caller,p.token0)>=r0, f"insufficient {p.token0} balance for deposit: have {self._get(caller,p.token0)} need {r0}"
            assert self._get(caller,p.token1)>=r1, f"insufficient {p.token1}"
            self._set(caller,p.token0,self._get(caller,p.token0)-r0)
            self._set(caller,p.token1,self._get(caller,p.token1)-r1)
            self.e.pos_bal[p.token0]=self.e.pos_bal.get(p.token0,0)+r0
            self.e.pos_bal[p.token1]=self.e.pos_bal.get(p.token1,0)+r1
            L,paid0,paid1,left0,left1=self.e.positions_deposit(i,caller)
            self._set(caller,p.token0,self._get(caller,p.token0)+left0)
            self._set(caller,p.token1,self._get(caller,p.token1)+left1)
        return shares

    def deposit(self,caller,a0,a1,receiver):
        sh=self._process_deposit(caller,a0,a1)
        self.supply+=sh; self.shares[receiver]=self.shares.get(receiver,0)+sh
        return sh

    def rebalance(self, mint_liq, new_bounds=None):
        """rebalance_pool: burn=0, then mint liquidity per pool (relayer)."""
        for i in range(self.e.n):
            p=self.e.pools[i]
            liq=mint_liq[i]
            if liq==0: continue
            d0,d1=liq_delta_to_amount_delta(p.price,liq,False,p.lo,p.hi)
            assert self.free.get(p.token0,0)>=d0, f"insufficient_amt0_at_index: {self.free.get(p.token0,0)} < {d0}"
            assert self.free.get(p.token1,0)>=d1, f"insufficient_amt1_at_index: {self.free.get(p.token1,0)} < {d1}"
            self.free[p.token0]-=d0; self.free[p.token1]-=d1
            self.e.pos_bal[p.token0]=self.e.pos_bal.get(p.token0,0)+d0
            self.e.pos_bal[p.token1]=self.e.pos_bal.get(p.token1,0)+d1
            L,paid0,paid1,left0,left1=self.e.positions_deposit(i,'vault')
            if left0: self.free[p.token0]=self.free.get(p.token0,0)+left0
            if left1: self.free[p.token1]=self.free.get(p.token1,0)+left1

    def convert_to_assets(self,shares):
        out=[]
        for i,p in enumerate(self.e.pools):
            _=i
            L=shares*self.e.liquidity[i]//self.supply if self.supply else 0
            u0,u1=liq_delta_to_amount_delta(p.price,L,False,p.lo,p.hi)
            out.append((L,u0,u1))
        return out

    def withdraw(self,holder,shares,receiver):
        assert shares<=self.shares.get(holder,0),'insufficient shares'
        pos=self.convert_to_assets(shares)
        self.supply-=shares; self.shares[holder]-=shares
        out=[]
        for i,p in enumerate(self.e.pools):
            L,u0,u1=pos[i]
            a0,a1=self.e.positions_withdraw(i,L)
            pf=1000000-(p.fee*1000000//TWO128)
            c0=(u0*pf//1000000-1) if u0>0 else 0
            c1=(u1*pf//1000000-1) if u1>0 else 0
            if STRICT:
                if a0!=c0: raise AssertionError(f"'invalid amount0' got {a0} want {c0} (pool {i})")
                if a1!=c1: raise AssertionError(f"'invalid amount1' got {a1} want {c1} (pool {i})")
            self._set(receiver,p.token0,self._get(receiver,p.token0)+c0)
            self._set(receiver,p.token1,self._get(receiver,p.token1)+c1)
            out.append((c0,c1))
        return out
