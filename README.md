# options_pricing

docker build -t options_pricing:dev .  
docker run --rm -p 8000:8000 options_pricing:dev

docker build -t options_pricing:dev .  
docker build -f Dockerfile.submitter -t options_pricing:dev .

# Worker image (SQS handler + numeric libs)

docker build -f Dockerfile.worker -t options_pricing:dev .

docker run --rm -it \
 -p 8000:8000 \
 --entrypoint uvicorn \
 options_pricing:dev \
 app:app --host 0.0.0.0 --port 8000 --reload

# fetch the JSON

RESP=$(curl -s "$API/result/$JOB_ID")
echo "Raw response: $RESP"

# safely extract .status (or blank if missing)

STATUS=$(echo "$RESP" | jq -r '.status // empty')
echo "Status: $STATUS"

# if there's an error field, bail out

ERR=$(echo "$RESP" | jq -r '.error // empty')
if [ -n "$ERR" ]; then
echo "Error from API: $ERR"
exit 1
fi

sleep 2
done

echo "Job $JOB_ID finished!"

# Once done, print the price

echo "Price result: $(echo "$RESP" | jq .result.price)"

curl -X POST http://localhost:8000/price \
 -H "Content-Type: application/json" \
 -d '{
"model": "bs",
"spot": 100,
"strike": 105,
"rate": 0.01,
"vol": 0.2,
"time": 1.0,
"option_type": "call"
}'

curl -X POST http://localhost:8000/greeks \
 -H "Content-Type: application/json" \
 -d '{
"spot": 100,
"strike": 105,
"rate": 0.01,
"vol": 0.2,
"time": 1.0
}'

curl -X POST http://localhost:8000/hedge \
 -H "Content-Type: application/json" \
 -d '{
"delta": 0.5,
"contracts": 1,
"contract_size": 100
}'

curl -X POST http://localhost:8000/payoff/protective_put \
 -H "Content-Type: application/json" \
 -d '{
"prices": [90, 95, 100, 105, 110],
"S0": 100,
"K_put": 95,
"premium_put": 2
}'

curl -X POST http://localhost:8000/payoff/covered_call \
 -H "Content-Type: application/json" \
 -d '{
"prices": [90, 95, 100, 105, 110],
"S0": 100,
"K_call": 105,
"premium_call": 3
}'

curl -X POST http://localhost:8000/payoff/collar \
 -H "Content-Type: application/json" \
 -d '{
"prices": [90, 95, 100, 105, 110],
"S0": 100,
"K_put": 95,
"premium_put": 2,
"K_call": 105,
"premium_call": 3
}'

curl -X POST http://host.docker.internal:8000/price \
 -H "Content-Type: application/json" \
 -d '{
"model": "cve_amer_call",
"spot": 100,
"strike": 105,
"rate": 0.01,
"vol": 0.2,
"time": 1.0,
"option_type": "call"
}'
