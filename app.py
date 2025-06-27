## options_pricing/app.py
import math
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from models import BSM
from monte_carlo import monte_carlo_option_price
from models import binomial_tree_american_option, binomial_tree_call
from models import delta, gamma, vega, hedge_ratio
from models import protective_put_pl, covered_call_pl,collar_pl
import numpy as np 
from mangum import Mangum
import uuid, json, os
import boto3
from typing import Any, Optional
from decimal import Decimal

# https://www.deadbear.io/simple-serverless-fastapi-with-aws-lambda/
app = FastAPI(title="Options Pricing API")
REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"

class PriceRequest(BaseModel):
    model: str             # e.g. "bs", "mc_call", "mc_put", "bin_amer_call", "bin_eur_call", "bsm_eur_call", "cve_amer_call"
    spot: float
    strike: float
    rate: float            # risk-free rate
    vol: float             # volatility (as decimal, e.g. 0.2 for 20%)
    time: float            # time to maturity in years
    q: float = 0.0         # dividend yield, if needed
    sims: int = 100_000    # number of Monte Carlo simulations
    steps: int = 5_000     # number of steps for binomial trees
    option_type: str = 'call'  # 'call' or 'put'

class GreeksRequest(BaseModel):
    spot: float
    strike: float
    rate: float
    vol: float             # volatility (as decimal)
    time: float            # time to maturity in years

class HedgeRequest(BaseModel):
    delta: float           # option delta
    contracts: int = 1     # number of futures/options contracts
    contract_size: int = 100  # size per contract

class PayoffRequest(BaseModel):
    prices: list[float]
    S0: float
    K_put: Optional[float] = None
    premium_put: float = 0.0
    K_call: Optional[float] = None
    premium_call: float = 0.0

class JobStatus(BaseModel):
    status: str
    result: Optional[Any] = None
    
sqs = boto3.client("sqs",region_name=REGION)
QUEUE_URL    = os.environ["JOB_QUEUE_URL"]
dynamodb     = boto3.resource("dynamodb")
results_tab  = dynamodb.Table(os.environ["RESULTS_TABLE"])

def enqueue(job_type: str, payload: dict):
    job_id = str(uuid.uuid4())
    print(f"Enqueueing job {job_type} with ID {job_id}")
    message = {"jobId": job_id, "jobType": job_type, **payload}
    try:
        sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(message))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue {job_type} job: {e}")
    return {"jobId": job_id}

@app.post("/price")
async def submit_price(req: PriceRequest):
    return enqueue("price", req.dict())

@app.post("/greeks")
async def submit_greeks(req: GreeksRequest):
    return enqueue("greeks", req.dict())

@app.post("/hedge")
async def submit_hedge(req: HedgeRequest):
    return enqueue("hedge", req.dict())

@app.post("/payoff/protective_put")
async def submit_protective(req: PayoffRequest):
    if req.K_put is None:
        raise HTTPException(status_code=400, detail="K_put is required")
    return enqueue("protective_put", req.dict())

@app.post("/payoff/covered_call")
async def submit_covered(req: PayoffRequest):
    if req.K_call is None:
        raise HTTPException(status_code=400, detail="K_call is required")
    return enqueue("covered_call", req.dict())

@app.post("/payoff/collar")
async def submit_collar(req: PayoffRequest):
    if req.K_put is None or req.K_call is None:
        raise HTTPException(status_code=400, detail="K_put and K_call are required")
    return enqueue("collar", req.dict())

@app.get("/result/{job_id}", response_model=JobStatus)
async def get_result(job_id: str):
    resp = results_tab.get_item(Key={"jobId": job_id})
    if "Item" not in resp:
        return JobStatus(status="pending")

    item   = resp["Item"]
    status = item["status"]
    raw = item["result"]
    
    def convert(obj):
        # Recursively walk lists/dicts, converting Decimals to floats
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (int, float)):
            return obj
        elif isinstance(obj, list):
            return [convert(x) for x in obj]
        elif isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        else:
            return obj
    converted = convert(raw)
    return JobStatus(status=status, result=converted)
    # # Dynamo returns Decimal for numbers — convert them:
    # if isinstance(result, dict):
    #     result = {k: float(v) for k, v in result.items()}
    # elif isinstance(result, (int, float, Decimal)):
    #     result = float(result)

    # return JobStatus(status=status, result=result)

@app.get("/health")
async def health():
    return {"status": "ok"}


# @app.post("/price")
# async def price(req: PriceRequest):
#     try:
#         if req.model == "bs":
#             engine = BSM(S0=req.spot, K=req.strike, r=req.rate, vol=req.vol, T=req.time)
#             result = engine.european_call_option_price() if req.option_type=='call' else engine.european_put_option_price()

#         elif req.model in ("mc_call", "mc_put"):
#             result = monte_carlo_option_price(
#                 S=req.spot,
#                 sigma=req.vol,
#                 r=req.rate,
#                 q=req.q,
#                 T=req.time,
#                 K=req.strike,
#                 simulations=req.sims,
#                 option_type=req.option_type
#             )

#         elif req.model == "bin_amer_call" or req.model == "bin_amer_put":
#             result = binomial_tree_american_option(
#                 S=req.spot,
#                 K=req.strike,
#                 T=req.time,
#                 r=req.rate,
#                 sigma=req.vol,
#                 n=req.steps,
#                 option_type=req.option_type
#             )

#         elif req.model == "bin_eur_call" or req.model == "bin_eur_put":
#             result = binomial_tree_call(
#                 S=req.spot,
#                 K=req.strike,
#                 T=req.time,
#                 r=req.rate,
#                 sigma=req.vol,
#                 n=req.steps
#             )

#         elif req.model == "bsm_eur_call" or req.model == "bsm_eur_put":
#             engine = BSM(S0=req.spot, K=req.strike, r=req.rate, vol=req.vol, T=req.time)
#             result = engine.european_call_option_price() if req.option_type=='call' else engine.european_put_option_price()

#         elif req.model == "cve_amer_call":
#             # Control Variate: American binomial + (European BSM - European binomial)
#             amer = binomial_tree_american_option(req.spot, req.strike, req.time, req.rate, req.vol, req.steps, option_type='call')
#             eur_bsm = BSM(S0=req.spot, K=req.strike, r=req.rate, vol=req.vol, T=req.time).european_call_option_price()
#             eur_bin = binomial_tree_call(req.spot, req.strike, req.time, req.rate, req.vol, req.steps)
#             result = amer + (eur_bsm - eur_bin)

#         else:
#             raise ValueError(f"Unknown model: {req.model}")

#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

#     return {"model": req.model, "price": result}

# @app.post("/greeks")
# async def greeks(req: GreeksRequest):
#     try:
#         d = delta(S0=req.spot, K=req.strike, r=req.rate, vol=req.vol, T=req.time)
#         g = gamma(S0=req.spot, K=req.strike, r=req.rate, vol=req.vol, T=req.time)
#         v = vega(S0=req.spot, K=req.strike, r=req.rate, vol=req.vol, T=req.time)
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     return {"delta": d, "gamma": g, "vega": v}

# @app.post("/hedge")
# async def hedge(req: HedgeRequest):
#     try:
#         hedge_qty = hedge_ratio(delta=req.delta, contracts=req.contracts, contract_size=req.contract_size)
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     return {"delta": req.delta, "contracts": req.contracts, "contract_size": req.contract_size, "hedge_quantity": hedge_qty}


# # --- Payoff Endpoints ---
# @app.post("/payoff/protective_put")
# async def payoff_protective(req: PayoffRequest):
#     if req.K_put is None:
#         raise HTTPException(status_code=400, detail="K_put is required for protective_put_pl")
#     arr = np.array(req.prices)
#     vals = protective_put_pl(arr, req.S0, req.K_put, req.premium_put)
#     return {"payoffs": vals.tolist()}

# @app.post("/payoff/covered_call")
# async def payoff_covered(req: PayoffRequest):
#     if req.K_call is None:
#         raise HTTPException(status_code=400, detail="K_call is required for covered_call_pl")
#     arr = np.array(req.prices)
#     vals = covered_call_pl(arr, req.S0, req.K_call, req.premium_call)
#     return {"payoffs": vals.tolist()}

# @app.post("/payoff/collar")
# async def payoff_collar(req: PayoffRequest):
#     if req.K_put is None or req.K_call is None:
#         raise HTTPException(status_code=400, detail="Both K_put and K_call are required for collar_pl")
#     arr = np.array(req.prices)
#     vals = collar_pl(arr, req.S0, req.K_put, req.premium_put, req.K_call, req.premium_call)
#     return {"payoffs": vals.tolist()}


handler = Mangum(app)
