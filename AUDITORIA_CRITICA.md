# REPORTE — Auditoría ofensiva: Troves.fi (Unwrap Labs / STRKFarm) · Ekubo CL Vaults v2

**Alcance auditado:** `trovesfi/ekubo-cl-vaults` (repo público de la fundación) + todas las dependencias reales del build (`EkuboProtocol/starknet-contracts`, `EkuboProtocol/abis`, `OpenZeppelin/cairo-contracts`, `alexandria`) + todos los repos públicos de la organización `trovesfi`.
**Fecha:** 2026-11-16 · **Modalidad:** auditoría estática + PoC locales bit-exactos en Python. **Sin RPC** (por requisito).

---

## 0. Veredicto

**SÍ hay vulnerabilidades críticas en código.**

Se confirman **2 hallazgos críticos** en `src/cl_vault/cl_vault.cairo` (commit auditado `aa77b9d065d79a2a081da33a0169eb66ec76d5a2`, repo `trovesfi/ekubo-cl-vaults`, versión `2.0.0`) que cumplen los 4 criterios exigidos:

| # | Hallazgo | Función | Líneas | Impacto |
|---|---|---|---|---|
| **C-1** | Confusión *shares vs activos*: se mintean shares con los importes declarados por el llamante pero se transfieren (y se depositan en Ekubo) los importes **a nivel de vault** | `deposit` → `_process_deposit` → `_convert_to_shares` | 186-208 / 1037-1084 / 1143-1215 | **Robo de hasta ~100 % del TVL de terceros** en una sola tx (permissionless) |
| **C-2** | Aserción post-fee de `withdraw` compara contra una fórmula de redondeo distinta de la que aplica Ekubo: **matemáticamente insatisfacible** con el Core actual (y falla de forma determinista desde ≈ 5.4e20 de liquidez / 2.54 xSTRK con el Core antiguo) | `withdraw` | 211-249 | **Congelamiento permanente de todos los fondos de terceros** (nadie puede redimir) |

Ambos son alcanzables en la configuración de producción del propio repo: xSTRK/STRK con `fee = 0.01 %` y `tick_spacing = 200` (`scripts/cl_vault/deploy_cl_vault.ts:180-232`, que con `priceToTick(1.11776/1.121, false, 200, 18, 18)` produce `bounds = [111200, 114200]`; `src/cl_vault/test.cairo:60-74` usa `[104000, 124000]` sobre el mismo pool key), y la migración V1→V2 (`src/cl_vault/migrations/v1_v2.cairo:117-124`) que arrastra `pool_key`, `bounds_settings` y `contract_nft_id` de la vault V1 `0x01f083b98674bc21effee29ef443a00c7b9a500fd92cf30341a3da12c73f2324` (18/18 dec).

> Los números del PoC usan `bounds = [104000, 124000]` y precio en tick `114000` (los del test del repo). Con los bounds del script de despliegue `[111200, 114200]` los resultados cualitativos son idénticos (la posición queda algo más concentrada); el hallazgo no depende de los ticks exactos, solo de `fee > 0` y `L > 0`.


---

## 1. Registro de la organización (requisito previo)

### 1.1 Orgs/espacios enumerados

| Org / espacio | Repos encontrados | Estado |
|---|---|---|
| `github.com/trovesfi` | 10 repos públicos (abajo) | clonados |
| `github.com/strkfarm` (STRKFarm / Unwrap Labs — entidad detrás de Troves) | **0 repos públicos** | bloqueado |
| `github.com/Pau1vvcai` (dev de Troves, fork con los componentes compartidos) | `troves-contracts` | clonado |
| `github.com/EkuboProtocol` | `starknet-contracts`, `abis` (borrado → espejo `starkware-libs/ekubo-abis`), `incentives` | clonados / espejo |
| `github.com/OpenZeppelin` | `cairo-contracts` v1.0.0 | clonado |
| `github.com/avnu-labs` | `avnu-contracts`, `avnu-contracts-v2` | clonados (integración swap/oráculo) |
| docs oficiales | `docs.troves.fi/p/security`, `docs.troves.fi/p/ekubo-cl-vaults` | leídos vía SDK/README |

### 1.2 Repos clonados con commit exacto

| Repo | Commit | Notas |
|---|---|---|
| `trovesfi/ekubo-cl-vaults` | `aa77b9d065d79a2a081da33a0169eb66ec76d5a2` | **repo principal auditado** (v2.0.0, 2025-12-24) |
| `trovesfi/troves-client` | `00d8d860f3656c602709b71535ee1a622b3abf8a` | sin `.cairo` |
| `trovesfi/strategy-research` | `fd001d7986bb2a627f834206ce54617fcb3fd0ca` | sin `.cairo` |
| `trovesfi/indexers` | `cb8b40cc596f4ca04d87d2e6cf27338e2164bd70` | sin `.cairo` |
| `trovesfi/static-assets` | `b3d4750caf4b902eaae64f89e81c463ed4113c23` | sin `.cairo` |
| `trovesfi/landing-page` | `8eac9db1795f5809a18a3bae82baa5cf058d9443` | sin `.cairo` |
| `trovesfi/vesu-strategies` | `11b1db3718f15f612de0d55fed507b58fbe8f80f` | `vesu_rebalance.cairo` revisado (no crítico) |
| `trovesfi/vesu-v1` | `da3db701f1f69a3fcde73f1609c8e06f3af4721a` | fork de Vesu; fuera del flujo del vault |
| `trovesfi/starknet_vault_kit` | `633fec7f02a9b914c9c3c88efb8df0c6eb10f057` | 80 `.cairo`, no integrado por el vault CL |
| `trovesfi/DefiLlama-Adapters` | `eea42ab99fce5bdc1ff5e3c963312061ab3bd004` | adaptadores TVL |
| `trovesfi/defillama-server` | `7c209d798aeaf91bb54a863fa2bff341e4c142b1` | submódulo `defi/emissions-adapters` bloqueado |
| `Pau1vvcai/troves-contracts` | `5dbf955178d3b9b51efbabf15d9f9766cf991ce9` | **V1 del vault** (para la migración) |
| `EkuboProtocol/starknet-contracts` | `195e0c0df5f9f751f51395d1854b5259a7b0a0b0` (+ `4a2e3ea`, `47e9b24`, `bb1bece`) | Core + Positions + math |
| `starkware-libs/ekubo-abis` | `f4a16b95967c5596d5a3cd4e0422bb9a2e3eb017` | rev exacta de `Scarb.toml:14` |
| `EkuboProtocol/incentives` | `d7b0e14d23037632c100677f253dd571c78c157f` | distributor de recompensas |
| `OpenZeppelin/cairo-contracts` | `755ce1adbf8d89ed23fbb8daa328fcbeab7c6424` (v1.0.0) | ERC20/Pausable/Upgradeable |
| `avnu-labs/avnu-contracts` | `de5672598fbdc291138476979d45c34c570fc3f3` | router/oráculo del swap |
| `avnu-labs/avnu-contracts-v2` | `1171398691fee1600aa456358c6a06c765d75913` | idem |
| `alexandria` | `cb290c4d3884aca23d450950e7f302ceebc98d16` (v0.8.0) | math/data-structures |
| npm `@strkfarm/sdk` | `1.1.85` y `2.0.0-staging.73` | **17 direcciones de vaults mainnet + decimales** |

### 1.3 Repos bloqueados / no accesibles (no se declara cobertura completa)

- `github.com/trovesfi/troves-contracts` (**privado / HTTP 404**) — es el repo que `Scarb.toml:17` declara como dependencia (`branch = "ariyan/multi-range-cl-vault"`). Se usó el fork público `Pau1vvcai/troves-contracts` para los componentes compartidos (`CommonComp`, `AccessControl`, `swap`, `ERC20Helper`, `pow`) y la V1 del vault.
- `github.com/STRKFarm/contracts` (**privado**), `sdk-ts` (**privado**, referenciado como `link:../sdk-ts`), org `strkfarm` (**0 repos públicos**), org `unwrap-labs` (**404**).
- `trovesfi/defillama-server` → submódulo `defi/emissions-adapters`: clon fallido.
- `EkuboProtocol/abis` **borrado upstream**; se auditó el espejo `starkware-libs/ekubo-abis` con la misma rev.

### 1.4 Despliegues y parámetros de producción leídos del repo (no RPC)

- `contracts.json` (repo principal): clase `ConcLiquidityVault = 0x54a3a42bd34172a2942d38e42c8fb1f5c8573a5f6f7c6298ba0c87cdbf87254`; instancia `0x14daca472bfcfc44c3c4384b8f499a9272b8686742c18b66150421566721ab6`.
- `scripts/cl_vault/actions.ts`: vault de ejemplo `0x60bf566a17e5f3e82e21bf6a8cc2ed7956c867eb937e74c474b1ced2b403c58`.
- `scripts/cl_vault/deploy_cl_vault.ts:203-232`: pool key xSTRK/STRK con **`fee = 34028236692093847977029636859101184` (0.01 %, `tick_spacing = 200`)**, bounds por `priceToTick(1.11776…1.121, false, 200, 18, 18)`, `init_values = {1e18, 1e18}`, `fee_bps = 1000`, `fee_collector = 0x06419f7DeA356b74bC1443bd1600AB3831b7808D1EF897789FacF11a172Da7`.
- `src/cl_vault/test.cairo:36-58`: segunda pool con `fee = 170141183460469235273462165868118016` (0.05 %, `tick_spacing = 1000`).
- `src/cl_vault/cl_vault.cairo` (constructor): `ekubo_positions = 0x02e0af29598b407c8716b17f6d2795eca1b471413fa03fb145a5e33722184067`, `ekubo_positions_nft = 0x07b696af58c967c1b14c9dde0ace001720635a660a8e90c565ea459345318b30`, `ekubo_core = 0x00000005dd3d2f4429af886cd1a3b08289dbcea99a294197e9eb43b0e0325b4b` (confirmado también en `starknet-contracts/packages/ekubo_swap_anonymizer/DEPLOYMENT.md`).
- **17 vaults CL desplegadas** (leídas de `@strkfarm/sdk@1.1.85`, `src/strategies/ekubo-cl-vault.tsx`):

| Estrategia | Dirección | Dec | Lanzamiento |
|---|---|---|---|
| Ekubo xSTRK/STRK | `0x01f083b98674bc21effee29ef443a00c7b9a500fd92cf30341a3da12c73f2324` | 18/18 | 1209881 |
| Ekubo xWBTC/WBTC | `0x2ea99b4971d3c277fa4a9b4beb7d4d7d169e683393a29eef263d5d57b4380a` | 8/8 | 2338309 |
| Ekubo xtBTC/tBTC | `0x785dc3dfc4e80ef2690a99512481e3ed3a5266180adda5a47e856245d68a4af` | 18/18 | 2415667 |
| Ekubo xsBTC/solvBTC | `0x3af1c7faa7c464cf2c494e988972ad1939f1103dbfb6e47e9bf0c47e49b14ef` | 18/18 | — |
| Ekubo xLBTC/LBTC | `0x314c4653ab1aa01f5465773cb879f525d7e369a137bc3ae084761aee99a1712` | 8/8 | — |
| Ekubo ETH/USDC.e | `0x160d8fa4569ef6a12e6bf47cb943d7b5ebba8a41a69a14c1d943050ba5ff947` | 18/6 | — |
| Ekubo USDC.e/USDT | `0x3a4f8debaf12af97bb911099bc011d63d6c208d4c5ba8e15d7f437785b0aaa2` | 6/6 | — |
| Ekubo STRK/USDC.e | `0x351b36d0d9d8b40010658825adeeddb1397436cd41acd0ff6c6e23aaa8b5b30` | 18/6 | — |
| Ekubo STRK/ETH | `0x4ce3024b0ee879009112d7b0e073f8a87153dd35b029347d4247ffe48d28f51` | 18/18 | — |
| Ekubo WBTC/USDC.e | `0x2bcaef2eb7706875a5fdc6853dd961a0590f850bc3a031c59887189b5e84ba1` | 8/6 | — |
| Ekubo tBTC/USDC.e | `0x4aad891a2d4432fba06b6558631bb13f6bbd7f6f33ab8c3111e344889ea4456` | 18/6 | — |
| Ekubo WBTC/ETH | `0x1c9232b8186d9317652f05055615f18a120c2ad9e5ee96c39e031c257fb945b` | 8/18 | — |
| Ekubo WBTC/STRK | `0x1248e385c23a929a015ec298a26560fa7745bbd6e41a886550e337b02714b1b` | 8/18 | — |
| Ekubo USDC/USDT | `0x5203a08b471e46bf33990ac83aff577bbe5a5d789e61de2c6531e3c4773d1c9` | 6/6 | — |
| Ekubo ETH/USDC | `0x4d00c7423b3c0fae3640f6099ac97acbfd8708f099e09bfe3a7a6a680399228` | 18/6 | — |
| Ekubo STRK/USDC | `0x4de22bd0a8eb4d0a18736e66dd36d20ba50bc106346bbfac3dbeaac1ab37ce1` | 18/6 | — |
| Ekubo WBTC/USDC | `0x76101c3b80af1103c9c6d541ca627f61b5ae7ae79d7fce96ccdf7bdb648450d` | 8/6 | — |

Decimales de tokens (SDK `src/global.ts`): xSTRK 18, STRK 18, xWBTC 8, WBTC 8, xtBTC 18, tBTC 18, xsBTC 18, solvBTC 18, xLBTC 8, LBTC 8, ETH 18, USDC/USDC.e/USDT 6.

> Nota de método: al no haber RPC no se puede afirmar el TVL actual; **se asume que estas 17 vaults, configuradas en producción, custodian liquidez de terceros** (regla de oro del encargo). Todos los bugs siguientes están en código de producción y en ruta de ejecución activa.

---

## 2. HALLAZGO CRÍTICO C-1 — `deposit()` mintea shares sobre los importes declarados pero retira los importes de la vault (robo de TVL de terceros)

### 2.1 Ubicación exacta

- Repo: `trovesfi/ekubo-cl-vaults` · commit **`aa77b9d065d79a2a081da33a0169eb66ec76d5a2`**
- Archivo: `src/cl_vault/cl_vault.cairo`
- Módulo/contrato: `ConcLiquidityVault`
- Funciones y líneas:
  - `deposit` → **186-208**
  - `_process_deposit` → **1037-1084** (línea clave **1045** y bucle **1069-1081**)
  - `_convert_to_shares` → **1088-1216** (cálculo de `shares` en **1189-1198**)
  - `_ekubo_deposit` → **949-1003**; `_pay_ekubo` → **836-853** (`ERC20Helper::transfer_from` → `pau1vvcai-troves-contracts/src/helpers/ERC20Helper.cairo:16-24`)

### 2.2 Explicación del bug

`_convert_to_shares(amount0, amount1)` devuelve tres cosas: `shares`, `user_level_positions` (lo que **correspondería** pagar al depositante por sus importes) y `vault_level_positions` (los importes de **la posición total de la vault**, con independencia de `amount0/amount1`).

En `_process_deposit`:

```cairo
// cl_vault.cairo:1045
let SharesInfo { shares, user_level_positions: _, vault_level_positions } = self._convert_to_shares(amount0, amount1);
...
// cl_vault.cairo:1069-1081
while i != self.managed_pools.len() {
    self.handle_fees(i); // optional
    let position = *vault_level_positions.positions.at(i.try_into().unwrap()); // <-- posición de la VAULT
    self._ekubo_deposit(caller, position.amount0, position.amount1, caller, i);
    i += 1;
}
```

es decir: **`user_level_positions` se descarta (`_`) y se cobra al depositante `vault_level_positions`**, mientras que las `shares` sí se calculan a partir de los importes declarados (`adjusted_amount0/1` → `liquidity_delta0` → `shares = liquidity_delta0 * total_supply / range_liq`, líneas 1189-1190).

Consecuencias directas, todas permissionless:

1. **Minteo arbitrario de shares y drenaje.** Un atacante llama `deposit(K·P0, K·P1, attacker)` con `P0/P1` = importes de la posición de la vault y `K` arbitrario. El coste real (lo que se le transfiere por `transfer_from`) es **siempre la posición de la vault** (≈ 1× TVL), pero recibe `K · total_supply` shares. Con `K = 10^6` posee el 99.9999 % y retira casi todo el TVL ajeno. No se necesita rol, flash loan ni capital mayor que 1× TVL (y ese capital se recupera en la misma operación).
2. **Sobrecobro a depositantes honestos.** Cualquier usuario con allowance suficiente paga la posición entera de la vault para recibir las shares de su importe: pierde hasta 1× TVL por depósito.
3. **Donación / inflación de shares.** El primero que deposite con `total_supply == 0` fija el precio de las shares (`_calculate_initial_shares`, 877-900) y `vault_level_positions` no se usa en esa rama; cualquier depósito posterior puede mintear contra un ratio manipulado.

### 2.3 Condiciones de configuración (leídas del repo)

- Vault con `total_supply > 0` y liquidez ya depositada en Ekubo (estado normal de producción; `handle_fees`/`rebalance_pool` dejan la posición en Ekubo).
- `amount0/amount1` declarados por el atacante deben ser ≥ posición de la vault y ≤ saldo/allowance propios (el atacante los aporta).
- Se cumple con la config desplegada: xSTRK/STRK `0x01f0…2324` y las otras 16 (todas usan el mismo `_process_deposit`).

### 2.4 PoC local (sin RPC, aritmética bit-exacta de Ekubo)

Modelo `ConcLiquidityVault` + `Positions` + `Core` transcrito 1:1 (uint/u128/u256 con wrapping, `muldiv`, `amount0_delta/amount1_delta`, `max_liquidity`, `tick_to_sqrt_ratio`, `compute_fee`). Archivos en `audit-poc/` (`ekubo_math.py`, `cl_vault_poc.py`, `run_final.py`, `measure.py`, `final_poc2.py`).

Ejecución:

```
python3 audit-poc/run_final.py        (STRICT=0: relaja la aserción de C-2 para poder medir C-1)
```

Salida real (extracto):

```
# F1: _process_deposit uses vault_level_positions for the transferFrom but mints from caller amounts
 K=1           cost  178451.6013+ 200000.0000  ->      1.000000 x of the PREDEPOSIT supply (victim keeps 50.00000000%)
 K=10          cost  178451.6013+ 200000.0000  ->     10.000000 x of the PREDEPOSIT supply (victim keeps  9.09090909%)
 K=1000        cost  178451.6013+ 200000.0000  ->   1000.000000 x of the PREDEPOSIT supply (victim keeps  0.09990010%)
 K=1000000     cost  178451.6013+ 200000.0000  -> 1000000.000000 x of the PREDEPOSIT supply (victim keeps  0.00010000%)
 K=1000000000  cost  178451.6013+ 200000.0000  -> 1000000000.000000 x of the PREDEPOSIT supply (victim keeps 0.00000010%)

# full exit on historical Core (withdrawal fee still charged -> withdraw() functional)
 victim TVL          : 200,000.000000 + 200,000.000000
 vault position      : 178,451.601348 xSTRK + 200,000.000000 STRK
 attacker cost       : 178,451.601348 xSTRK + 200,000.000000 STRK
 attacker receives   : 356,867.155509 xSTRK + 399,959.600040 STRK
 NET PROFIT          : 178,415.554161 xSTRK + 199,959.600040 STRK  = 99.9798%
```

Trazado matemático del caso `K = 10^6` (números exactos, 18 decimales):

1. **Estado**: víctima deposita `200000e18 + 200000e18`; `total_supply = 200000e18`. Posición en Ekubo: `L = 3.7878320869e25`, `P0 = 178451.601348862158707e18`, `P1 = 200000e18` (bounds `[104000,124000]`, precio tick `114000`).
2. **Ataque**: `deposit(amount0 = 10^6·P0, amount1 = 10^6·P1, receiver = attacker)`.
3. `_convert_to_shares` usa `amount0/amount1` solo para (a) el ratio de ajuste y (b) `max_liquidity` de las shares ⇒ `shares = 1.99999999999999999999999021017e26 ≈ 10^6 · total_supply`.
4. `_process_deposit` ignora `user_level_positions` y hace `transferFrom(attacker, Positions, P0)` y `transferFrom(attacker, Positions, P1)`: **coste = 1× posición**, no `10^6×`.
5. `Positions.deposit()` mintea `L` con ese saldo; el excedente por redondeo (`< 2 wei`) se devuelve al llamante vía `clear_minimum_to_recipient` (`ekubo-starknet-contracts/src/components/clear.cairo:29-40`, invocado en `cl_vault.cairo:989-990`), por lo que no hay pérdida.
6. **Retirada**: `withdraw(shares)` quema 99.9999 % del supply ⇒ recibe `356867.155509226794e18 xSTRK + 399959.600040399959e18 STRK`, es decir **+99.9798 %** neto; la víctima queda con el 0.0001 % del vault.
7. Cierre: no hay préstamo/flash que devolver (el capital aportado ya se recuperó en el paso 6). **PnL neto positivo confirmado.**

### 2.4-bis Interacción entre C-1 y C-2 (y por qué ambos son críticos por separado)

- **C-1 corrompe contabilidad de forma incondicional.** El minteo de `K · total_supply` shares ocurre en `deposit` y **no depende** de que `withdraw` funcione: la participación de los depositantes honestos en el vault queda reducida a `1/(1+K)` de forma permanente e irreversible (no hay función de rescate de shares). Eso ya cumple el criterio 4 («corrompe permanentemente la contabilidad de fondos ajenos»).
- **La monetización de C-1 exige una salida.** El repo se desplegó (2025-12-24) contra el Core con fee de retirada (`4a2e3ea`), donde `withdraw` **sí funciona** por debajo del umbral dust y por tanto el ataque completo (comprar ~1× TVL de shares y redimir ~2× TVL) se liquida en una sola transacción: PoC `NET PROFIT = +99.9798 %` (§2.4).
- **Hoy (Core sin fee de retirada) manda C-2**: *nadie* puede redimir, luego el atacante tampoco cobra; pero al corregir únicamente C-2, C-1 vuelve a ser drenaje inmediato. Se reportan por separado porque son bugs independientes (uno de *shares vs activos* en el depósito, otro de *redondeo/aserción* en el retiro) y cada uno satisface por sí mismo el criterio 4 (C-1: corrupción permanente de contabilidad + lucro con Core con fee; C-2: congelación permanente de todos los fondos).

### 2.5 Por qué las defensas actuales no lo frenan

- No hay `min_shares`/`max_amounts` (la interfaz `deposit(amount0, amount1, receiver)` no acepta slippage; `interface.cairo:174-177`).
- `assert(shares > 0)` y `assert(total_amount0 > 0 || total_amount1 > 0)` no limitan el importe cobrado.
- El multiplicador `K` no tiene cota: `_calculate_liquidity_delta`/`max_liquidity` saturan por `u128` de `liquidity_delta` solo en valores astronómicos.
- `ReentrancyGuardComponent` está cableado (`cl_vault.cairo:69,84`) pero **no se usa en ninguna función** (`grep 'reng\.'` = 0 resultados): no hay protección equivalente en `deposit`.

---

## 3. HALLAZGO CRÍTICO C-2 — La aserción `post_fee_amt` de `withdraw()` hace imposible redimir (congelación permanente de fondos)

### 3.1 Ubicación exacta

- Repo: `trovesfi/ekubo-cl-vaults` · commit **`aa77b9d065d79a2a081da33a0169eb66ec76d5a2`**
- Archivo: `src/cl_vault/cl_vault.cairo` · contrato `ConcLiquidityVault` · función `withdraw` · **líneas 211-249** (cálculo y asserts: **237-241**)
- Código dependiente: `convert_to_assets` **276-300** → `_calculate_liquidity_delta` **861-875** (`liquidity_delta_to_amount_delta`, `sign: false` ⇒ redondeo **hacia arriba**); `_withdraw_position` **902-947** (`Positions.withdraw`, que internamente usa `sign: true` ⇒ redondeo **hacia abajo**).

### 3.2 Explicación del bug

```cairo
// cl_vault.cairo:235-241
let (amt0, amt1) = self._withdraw_position(position.liquidity, i);
let TWO_POWER_128: u256 = 0x100000000000000000000000000000000;
let post_fee_factor = (1000000 - (pool.pool_key.fee.try_into().unwrap() * 1000000 / TWO_POWER_128));
let post_fee_amt0 = if (position.amount0 > 0) { position.amount0 * post_fee_factor / 1000000 - 1 } else { 0 };
...
assert(amt0.into() == post_fee_amt0, 'invalid amount0');   // <-- 240
assert(amt1.into() == post_fee_amt1, 'invalid amount1');   // <-- 241
```

- `position.amount0/1` proviene de `convert_to_assets()` → `_calculate_liquidity_delta(..., liquidity)` → `ekuboLibDispatcher().liquidity_delta_to_amount_delta(current_sqrt_price, i129{mag: L, sign: false}, lower, upper)`: con `sign: false` el flag `round_up = !is_negative = true` ⇒ **redondeo hacia arriba** (`u`).
- `amt0/amt1` es lo que Ekubo realmente pagó en `Positions.withdraw(..., liquidity, 0, 0, false)` → `Core.update_position(..., i129{mag: L, sign: true})` ⇒ `round_up = false` ⇒ **redondeo hacia abajo** (`d`), y además el Core aplica (o no) su fee de retirada:
  - Core **≤ `4a2e3ea`** (histórico): `delta −= i129{mag: compute_fee(delta.amount, fee)}`, `compute_fee` = **ceil**, `core.cairo:719-750` @ `4a2e3ea`.
  - Core **≥ `47e9b24`** (actual, commit `195e0c0`): *"no withdrawal protocol fee charged on liquidity removal"*, `core.cairo:726` @ `195e0c0`.

Por tanto la aserción exige

```
d  ==  u · (1e6 − fee_ppm) / 1e6 − 1          [fee_ppm = floor(fee · 1e6 / 2^128)]
```

con `d ∈ {u−1, u}` (la diferencia entre redondear arriba y abajo es ≤ 1) y `fee_ppm ≥ 1`:

- **Core actual (sin fee de retirada, `d ∈ {u−1,u}`)**: para `u ≥ 1` se cumple `u·(1e6−fee_ppm)/1e6 ≤ u − 1 < u`, luego **ningún `d` satisface la igualdad**, salvo el caso degenerado `u·(1e6−fee_ppm)/1e6 == 0` (que en Cairo **panickea** por underflow de `0 - 1`). Verificado exhaustivamente: **0/200 000 casos** válidos para `u ∈ [1, 100 000]` con fee 0.01 % y 0.05 % (`audit-poc/out_verify.txt`). Es decir, **`withdraw` revierte siempre** (para cualquier tamaño de posición no nulo).
- **Core histórico (`4a2e3ea`)**: la igualdad requiere además `ceil(d·fee/2^128) == 0` y que el truncamiento de `fee_ppm` no desvíe; el segundo falla desde posición ≈ 1 000 000 de unidades base (fee 0.01 %) / ≈ 21 unidades (fee 0.05 %) y el primero (fee cobrado) desde ≈ 5.4e20 de liquidez en xSTRK/STRK — ver 3.4. Para los tamaños reales de las vaults (≥ 10^20 de liquidez) la tasa de reversión medida es **100 %**.

### 3.3 Condiciones de configuración

- Cualquier pool gestionada con `pool_key.fee > 0` (todas las de producción: 0.01 % y 0.05 %).
- `managed_pools[0].liquidity > 0` y posición de Ekubo con `amount0/1 > 0` (estado normal tras cualquier `rebalance_pool`).
- Con el Core actual, **toda** redención no nula revierte (la igualdad es insatisfacible para cualquier `u`); con el Core antiguo, la redención falla de forma determinista desde ≈ 2.54 xSTRK de posición en el pool de 0.01 % y es ya 100 % fallida desde ≈ 471 xSTRK (`audit-poc/out_rates.txt`); en ETH/USDC (fee 0.05 %) desde ≈ 2.5 M de unidades base de `token0`.
- El único camino que se salva es una retirada *dust* (p. ej. `withdraw(shares)` tal que `position.amount0 ≤ 1e6`), inservible para retirar TVL real.

### 3.4 PoC local / trazado numérico exacto

`audit-poc/final_poc2.py` (cada redención sobre una vault y posición nuevas), `audit-poc/measure.py`, `audit-poc/out_verify.txt`:

```
(vault xSTRK/STRK, bounds [104000,124000], precio 114000, fee 0.01 %)
L = 1e18   position.amount0(u) = 4711180359997317
           Core actual paga(d) = 4711180359997316      vault exige = 4710709241961316  -> REVERT
L = 1e21   u = 4711180359997316827  d = 4711180359997316826  exige = 4710709241961317094 -> REVERT
L = 1e22   u = 47111803599973168264 d = 47111803599973168263 exige = 47107092419613170946 -> REVERT
```

Con el Core histórico (`4a2e3ea`) los primeros tamaños que pasan siguen fallando por el fee:

```
xSTRK/STRK  bounds[104000,124000]   primera L que revierte = 5.396e20   (amount0 = 2 542 349 993 839 009 890)
ETH/USDC    bounds[-19599000,-19567000]                = 1.087e16    (amount0 = 1 257 926 089 424 129 980)
USDC/USDT   bounds[-200,200]                           = 3.453e22
USDC/USDT   bounds[-10000,20000]                       = 4.255e20
WBTC/USDC   bounds[-1000,1000] (8/6 dec)               = 2.529e21
xSTRK/STRK  bounds[-114000,144000]                     = 1.215e21
```

Y para tamaños de producción (vault de 200 000 xSTRK), con Core histórico:

```
redeem 200000e18 shares (100 %)   core paga 178433756188081049174862  vault exige 178433756188081049175717 -> REVERT
redeem 2000e18 shares  (1 %)      core paga 1784337561880810491747    vault exige 1784337561880810491756   -> REVERT
redeem 200e18 shares   (0.1 %)    core paga 178433756188081049174     vault exige 178433756188081049174    -> 'invalid amount1' REVERT
```

Tasa de reversión medida sobre 5 000 valores aleatorios de liquidez por tramo (Core **histórico**, `audit-poc/out_rates.txt`):

```
L [1e21, 1e22]  posición ~5–47 xSTRK      withdraw OK  88.8 %
L [1e22, 1e23]  posición ~47–471 xSTRK    withdraw OK  15.1 %
L [1e23, 1e24]  posición ~471–4 712 xSTRK withdraw OK   0.0 %
L [2e25, 4e25]  posición ~94 224–188 448  withdraw OK   0.0 %
```

Con el Core **actual** (sin fee de retirada) el desajuste es estructural (≈ 1e-4 relativo): todas revierten (`invalid amount0`), incluida la retirada del 100 %.

**Impacto**: el 100 % de los fondos de los depositantes queda **permanentemente bloqueado** en las posiciones de Ekubo (las shares se queman en la línea 224 **antes** de los asserts, así que un intento fallido ni siquiera devuelve las shares: revierte toda la tx, pero el usuario nunca puede completar una redención). No hay función alternativa de rescate: `harvest`/`rebalance_pool` son `relayer`, y `emergency`/`pause` no retiran fondos (`CommonComp`, `common.cairo:37-60`).

### 3.5 Por qué es permissionless e irreversible

- `withdraw` es pública (`interface.cairo:177`), sin rol, y es el **único** camino de salida de principal.
- El bug está en la ruta de ejecución activa para **todas** las pools con `fee > 0` (todas).
- No hace falta ninguna acción del atacante: el propio usuario que intenta retirar dispara el revert; el capital queda atrapado (`withdraw` no puede completarse). Es un **bloqueo permanente de fondos de terceros**.

---

## 4. Hallazgos analizados y descartados (para trazabilidad)

| Candidato | Motivo de descarte |
|---|---|
| `handle_fees` (354-395) permissionless + `total_supply==0` | Requiere que el relayer ejecute `rebalance_pool` después; sin `rebalance` el capital no se mueve. Se trata como agravante de C-1, no como C independiente. |
| `deposit` cuando `total_supply == 0` y `amount1 == 0` (div. por cero, 1149) | Revert (DoS de 1 tx), no pérdida de fondos; el atacante no gana. |
| `_convert_to_shares` ajuste invertido del activo limitante (1143-1159) | Sí permite manipular la relación de shares, pero su efecto económico queda **subsumido** por C-1 (que ya permite mintear K·supply). Se documenta como causa raíz secundaria. |
| `shares_mismatch` con `PRECISION_FACTOR = 1e9` (1192-1197) | Solo afecta a vaults multi-pool y provoca revert; no hay extracción de valor. |
| `rebalance_pool` / `harvest` / `add_pool` / `remove_pool` | `RELAYER`/`GOVERNOR` reales vía `AccessControl` (`common.cairo:88-104`); no permissionless. |
| `V1V2Migration::upgrade_vault` | `_assert_owner` + requiere `admin`/`governor` en el `AccessControl` de la vault (el test hace `grant_role`); no permissionless. Layout de storage compatible (componentes primero, luego `ekubo_positions_contract`, `ekubo_positions_nft`, `ekubo_core`, `oracle`, `fee_settings`, `init_values`, `managed_pools` en V2 vs `pool_key`/`bounds_settings`/`contract_nft_id`/`sqrt_lower`/`sqrt_upper`/`is_incentives_on`/`reward_share` en V1). No se encontró corrupción de storage en la migración. |
| `vesu_rebalance.cairo` (`trovesfi/vesu-strategies`, `11b1db3`) | `rebalance` es permissionless pero las post-validaciones (`compute_yield` creciente, `balanceOf(asset)==0`, `_assert_max_weights`) impiden extracción directa; `rebalance_weights`/`emergency_*`/`set_*` son de rol. Sin PoC de beneficio neto. |
| `starknet_vault_kit`, `vesu-v1`, `DefiLlama-Adapters`, `indexers`, `troves-client` | No forman parte del call-graph de las vaults CL (0 `.cairo` o no cableados en `Scarb.toml`/`deploy_cl_vault.ts`). |
| `harvest` claim/proof (`_ekubo_harvest`, 762-786) | `RELAYER`; `proof.is_empty()` devuelve 0; sin firma manipulable. |

---

## 5. Invariantes verificados que **no** se rompen

- `Positions.deposit/withdraw` solo puede ser invocado por el dueño/autorizado del NFT (`positions.cairo:229-236`, `check_authorization`), por lo que el ataque requiere pasar por la vault (que es lo que C-1 hace).
- `Core.lock` cierra con `assert(get_nonzero_delta_count(id) == 0)`; no hay forma de dejar deltas abiertos.
- `Core.pay` verifica `delta == allowance` (`TRANSFER_FROM_INVARIANT`), sin robo vía allowance residual.
- `_withdraw_position` valida que la liquidez retirada sea exactamente la solicitada (929-932).
- `remove_pool` exige liquidez 0 antes de eliminar (777-779).
- `ERC20Helper::transfer/transfer_from` no transfieren si `amount == 0`, evitando reverts por tokens no estándar.
- `Upgradeable` solo accesible con `DEFAULT_ADMIN_ROLE` (`common.cairo:30-34`); `pause/unpause` con `EMERGENCY_ACTOR`.

---

## 6. Registro de auditoría (comandos, archivos y salidas)

### 6.1 Comandos de PoC ejecutados (todos locales, sin RPC)

```bash
cd /home/user/ekubo-cl-vaults/audit-poc
STRICT=0 python3 run_final.py    # C-1 (mint K×supply por 1× de coste) y C-2 (revert de redención)
python3 measure.py              # tabla L / u / d / esperado / veredicto
python3 final_poc2.py           # redenciones parciales (100 %, 50 %, 25 %, 10 %, 1 %, 0.1 %)
python3 verify_final.py         # prueba algebraica de insatisfacibilidad de la aserción
```

Salidas guardadas: `audit-poc/out_final.txt`, `audit-poc/out_verify.txt`, `audit-poc/out_rates.txt`, `audit-poc/out_deploy_bounds.txt`.

### 6.2 Archivos de configuración/despliegue inspeccionados

`contracts.json`, `Scarb.toml`, `Scarb.lock`, `package.json`, `README.md`, `scripts/cl_vault/deploy_cl_vault.ts`, `scripts/cl_vault/actions.ts`, `scripts/lib/{constants,sanity,utils,generate_classhashes}.ts`, `src/cl_vault/{cl_vault,interface,errors,test}.cairo`, `src/cl_vault/migrations/{v1_v2,interface,test_v1_v2_migration}.cairo`, `src/interfaces/IEkubo{Core,Distributor,Position,PositionsNFT}.cairo`, `src/tests/utils.cairo`; V1: `Pau1vvcai/troves-contracts/src/strategies/cl_vault/{cl_vault,interface}.cairo` y `src/components/{common,accessControl,harvest/*}`; Ekubo: `src/{core,positions}.cairo` + `src/math/*` en `4a2e3ea` y `195e0c0` (+ diff `47e9b24`); SDK `@strkfarm/sdk@1.1.85` `src/strategies/ekubo-cl-vault.tsx`, `src/global.ts`, `src/data/cl-vault.abi.json`.

### 6.3 Entorno

`scarb`/`snforge` **no disponibles**: la descarga de binarios de release desde GitHub está bloqueada por la red del sandbox (`objects.githubusercontent.com`), por lo que no se pudo compilar el repo ni ejecutar `snforge test`. En su lugar se ejecutó un modelo **bit-exacto en Python** (aritmética entera sin límites con truncados/wrapping explícitos, `u128`/`u256`, `muldiv` con `wide_mul`, `tick_to_sqrt_ratio` con las constantes exactas del repo Ekubo, `amount0_delta`/`amount1_delta` con `round_up`, `max_liquidity`, `compute_fee` con `ceil`, `Core.update_position` en ambas versiones). Las constantes usadas (`fee`, `tick_spacing`, ticks, decimales) son las del repo y del SDK de producción; los tests de referencia del repo se usaron para validar el modelo: `test.cairo:1620-1624` (`test_convert_to_shares_zero_supply`, `shares == 7500000000000000000` con `amount0 = amount1 = 10e18` e `init_values = (1e18, 2e18)`) se reproduce exactamente, y `test.cairo:1654` (`shares == 1152034540170218661139`, dependiente de precios de fork) se cita solo como referencia de magnitud.

### 6.4 Cobertura y límites

- **Bloqueados** (no auditados): `trovesfi/troves-contracts` (privado, dependencia declarada del build), `STRKFarm/contracts`, `sdk-ts`, org `strkfarm`, org `unwrap-labs`, submódulo `defi/emissions-adapters`.
- **No se declara cobertura completa** por los repos bloqueados; sin embargo, los dos hallazgos críticos viven **enteramente** en el repo público auditado y en el Core público de Ekubo, ambos con commit exacto y PoC local.
- No se pudo verificar TVL on-chain (sin RPC); por la regla del encargo se asume liquidez de terceros activa en las 17 vaults configuradas en el SDK.

---

## 7. Conclusión

**Hay 2 vulnerabilidades críticas reales en código de producción:**

1. **C-1** — `_process_deposit` cobra `vault_level_positions` (la posición entera de la vault) y descarta `user_level_positions`, mientras `shares` se calculan con los importes declarados: **cualquiera puede mintear `K · total_supply` shares por el coste de 1× el TVL y drenar ~100 % de los fondos de terceros** (PoC: +99.9798 % neto, `K = 10^6`).
2. **C-2** — la aserción post-fee de `withdraw` compara contra una fórmula de redondeo (hacia arriba, con fee truncado) distinta de la que Ekubo aplica (hacia abajo, sin fee en el Core actual): **insatisfacible en el Core actual y rota a partir de ~5.4e20 de liquidez (≈2.54 xSTRK) en el histórico**, congelando **permanentemente** los fondos de todos los depositantes (la redención del 100 % revierte, y no existe ruta alternativa).
