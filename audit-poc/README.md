# PoC locales — Auditoría Troves.fi Ekubo CL Vaults

Modelo bit-exacto en Python del contrato `ConcLiquidityVault` (`src/cl_vault/cl_vault.cairo`,
commit `aa77b9d`) y de las dependencias Ekubo `Positions`/`Core` + `math/*`
(commits `4a2e3ea` con fee de retirada y `195e0c0` sin ella). **No requiere RPC ni fork.**

| Archivo | Contenido |
|---|---|
| `ekubo_math.py` | `tick_to_sqrt_ratio`, `amount0_delta`, `amount1_delta`, `liquidity_delta_to_amount_delta`, `muldiv`, `max_liquidity`, `compute_fee` (transcripción 1:1) |
| `cl_vault_poc.py` | `Ekubo` (Positions+Core), `Vault` (`deposit`, `rebalance`, `withdraw`, `convert_to_*`, `_process_deposit`) |
| `run_final.py` | **PoC C-1 y C-2**: minteo de K×supply por 1× de coste, drenaje, y reversión de redención |
| `measure.py` | Tabla `L / position.amount / pago de Ekubo / exigido por la vault` para 1e12…1e25 de liquidez |
| `final_poc2.py` | Redenciones del 100 %, 50 %, 25 %, 10 %, 1 %, 0.1 % sobre Core actual y Core histórico |
| `verify_final.py` | Prueba algebraica de que la aserción de `withdraw` es insatisfacible |
| `out_final.txt`, `out_verify.txt` | Salidas reales |

Ejecutar:

```bash
python3 run_final.py      # STRICT=0 en cl_vault_poc.py relaja la aserción de C-2 para medir C-1
python3 measure.py
python3 final_poc2.py
python3 verify_final.py
```
