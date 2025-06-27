import os
import json
import time
import boto3
import numpy as np
from decimal import Decimal
from models import (
    BSM,
    binomial_tree_american_option,
    binomial_tree_call,
    delta, gamma, vega, hedge_ratio,
    protective_put_pl, covered_call_pl, collar_pl
)
from monte_carlo import monte_carlo_option_price

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
results_table = dynamodb.Table(os.environ["RESULTS_TABLE"])
sqs = boto3.client("sqs")  # if you ever need to send downstream

# Compute functions

def compute_price(params):
    S = params["spot"]
    K = params["strike"]
    r = params["rate"]
    sigma = params["vol"]
    T = params["time"]
    q = params.get("q", 0.0)
    sims = params.get("sims", 100_000)
    steps = params.get("steps", 5_000)
    opt = params.get("option_type", "call")
    model = params["model"]

    if model == "bs":
        eng = BSM(S0=S, K=K, r=r, vol=sigma, T=T)
        return eng.european_call_option_price() if opt == "call" else eng.european_put_option_price()

    if model in ("mc_call", "mc_put"):
        return monte_carlo_option_price(
            S0=S, sigma=sigma, r=r, q=q, T=T,
            K=K, simulations=sims, option_type=opt
        )

    if model in ("bin_amer_call", "bin_amer_put"):
        return binomial_tree_american_option(
            S=S, K=K, T=T, r=r, sigma=sigma,
            n=steps, option_type=opt
        )

    if model in ("bin_eur_call", "bin_eur_put"):
        return binomial_tree_call(
            S=S, K=K, T=T, r=r, sigma=sigma,
            n=steps
        )

    if model in ("bsm_eur_call", "bsm_eur_put"):
        eng = BSM(S0=S, K=K, r=r, vol=sigma, T=T)
        return eng.european_call_option_price() if opt == "call" else eng.european_put_option_price()

    if model == "cve_amer_call":
        amer = binomial_tree_american_option(S=S, K=K, T=T, r=r, sigma=sigma, n=steps, option_type="call")
        eur_bsm = BSM(S0=S, K=K, r=r, vol=sigma, T=T).european_call_option_price()
        eur_bin = binomial_tree_call(S=S, K=K, T=T, r=r, sigma=sigma, n=steps)
        return amer + (eur_bsm - eur_bin)

    raise ValueError(f"Unknown price model: {model}")


def compute_greeks(params):
    S = params["spot"]
    K = params["strike"]
    r = params["rate"]
    sigma = params["vol"]
    T = params["time"]
    return {
        "delta": delta(S0=S, K=K, r=r, vol=sigma, T=T),
        "gamma": gamma(S0=S, K=K, r=r, vol=sigma, T=T),
        "vega":  vega(S0=S, K=K, r=r, vol=sigma, T=T),
    }


def compute_hedge(params):
    hed_qty = hedge_ratio(
        delta=params["delta"],
        contracts=params.get("contracts", 1),
        contract_size=params.get("contract_size", 100)
    )
    return {"hedge_quantity": hed_qty}


def compute_payoff(params, job_type):
    S0 = params["S0"]
    prices = params["prices"]
    prem_put = params.get("premium_put", 0.0)
    prem_call = params.get("premium_call", 0.0)
    K_put = params.get("K_put")
    K_call = params.get("K_call")
    arr = np.array(prices)

    if job_type == "protective_put":
        if K_put is None:
            raise ValueError("K_put is required for protective_put")
        payoffs = protective_put_pl(arr, S0, K_put, prem_put)

    elif job_type == "covered_call":
        if K_call is None:
            raise ValueError("K_call is required for covered_call")
        payoffs = covered_call_pl(arr, S0, K_call, prem_call)

    elif job_type == "collar":
        if K_put is None or K_call is None:
            raise ValueError("Both K_put and K_call are required for collar")
        payoffs = collar_pl(arr, S0, K_put, prem_put, K_call, prem_call)
    else:
        raise ValueError(f"Unknown payoff type: {job_type}")

    return {"payoffs": payoffs.tolist()}

def _to_decimal(obj):
    if isinstance(obj, float):
        # use str() to avoid binary‐float artifacts
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_to_decimal(v) for v in obj]
    else:
        return obj
    
def lambda_handler(event, context):
    for record in event.get("Records", []):
        body   = json.loads(record["body"])
        job_id = body.pop("jobId")
        job_type = body.pop("jobType")

        # Dispatch compute
        if job_type == "price":
            raw = compute_price(body)
        elif job_type == "greeks":
            raw = compute_greeks(body)
        elif job_type == "hedge":
            raw = compute_hedge(body)
        elif job_type in ("protective_put", "covered_call", "collar"):
            raw = compute_payoff(body, job_type)
        else:
            raw = {"error": f"Unknown job type: {job_type}"}

        # convert any floats in the result into Decimal
        result = _to_decimal(raw)

        # now safe to store in DynamoDB
        results_table.put_item(
            Item={
                "jobId":    job_id,
                "status":    "done", 
                "result":   result,
                "expiresAt": int(time.time()) + 86400
            }
        )

    return {"status": "processed"}