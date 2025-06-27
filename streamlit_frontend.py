import time
import streamlit as st
import requests

st.set_page_config(page_title="Options Pricing Dashboard", layout="wide")

# Sidebar configuration
st.sidebar.title("Configuration")
api_url = st.sidebar.text_input(
    "API Base URL",
    value="https://<your-api-id>.execute-api.us-east-1.amazonaws.com"
).rstrip("/")

# Main title
st.title("📈 Options Pricing Dashboard")

# Page selection
page = st.sidebar.radio(
    "Select Function",
    ["Price", "Greeks", "Hedge", "Payoff"]
)

def submit_and_poll(endpoint: str, payload: dict):
    """Helper to POST payload, get jobId, then poll /result until done."""
    # 1) submit
    post_resp = requests.post(f"{api_url}/{endpoint}", json=payload)
    if not post_resp.ok:
        st.error(f"Submit error {post_resp.status_code}: {post_resp.text}")
        return None

    body = post_resp.json()
    job_id = body.get("jobId")
    if not job_id:
        st.error("No jobId returned by API!")
        return None

    # initialize our log
    log_container = st.empty()
    logs = [f"▶ {time.strftime('%H:%M:%S')} – Submitted job: {job_id}"]
    log_container.text_area("Job Log", "\n".join(logs), height=200)

    # 2) poll until done
    status = None
    data = {}
    while status != "done":
        get_resp = requests.get(f"{api_url}/result/{job_id}")
        if not get_resp.ok:
            st.error(f"Polling error {get_resp.status_code}: {get_resp.text}")
            return None

        data = get_resp.json()
        status = data.get("status", "")

        logs.append(f"▶ {time.strftime('%H:%M:%S')} – Status: {status}")
        log_container.text_area("Job Log", "\n".join(logs), height=200)

        if status == "done":
            st.success("✅ Done!")
            break

        time.sleep(2)

    # 3) pull your actual payload out of the "result" field
    result_payload = data.get("result")
    st.success(data)
    if endpoint == "price":
        return result_payload          # now this is your numeric price
    elif endpoint == "greeks":
        return result_payload          # dict with delta, gamma, vega
    elif endpoint == "hedge":
        return result_payload          # dict or int from your hedge job
    else:
        # payoff endpoints: assume result_payload == {"payoffs": [...]}
        return result_payload.get("payoffs")


if page == "Price":
    st.header("Option Pricing")
    col1, col2 = st.columns(2)
    with col1:
        model = st.selectbox(
            "Model",
            ["bs", "mc_call", "mc_put", 
             "bin_amer_call", "bin_amer_put",
             "bin_eur_call", "bin_eur_put",
             "bsm_eur_call", "bsm_eur_put",
             "cve_amer_call"]
        )
        option_type = st.selectbox("Option Type", ["call", "put"])
        spot = st.number_input("Spot Price", value=100.0)
        strike = st.number_input("Strike Price", value=100.0)
    with col2:
        rate = st.number_input("Risk-free Rate", value=0.01)
        vol = st.number_input("Volatility (decimal)", value=0.2)
        time_to_mat = st.number_input("Time to Maturity (years)", value=1.0)
        q = st.number_input("Dividend Yield", value=0.0)
        sims = st.number_input("MC Simulations", value=100_000, step=1_000)
        steps = st.number_input("Binomial Steps", value=5_000, step=100)

    if st.button("Calculate Price"):
        payload = {
            "model": model,
            "spot": spot,
            "strike": strike,
            "rate": rate,
            "vol": vol,
            "time": time_to_mat,
            "option_type": option_type,
            "q": q,
            "sims": int(sims),
            "steps": int(steps)
        }
        result = submit_and_poll("price", payload)
        if result is not None:
            st.subheader("Price Result")
            st.write(result)
        else:
            st.error("Failed to get price.")

elif page == "Greeks":
    st.header("Option Greeks Calculation")
    spot = st.number_input("Spot Price", value=100.0)
    strike = st.number_input("Strike Price", value=100.0)
    rate = st.number_input("Risk-free Rate", value=0.01)
    vol = st.number_input("Volatility (decimal)", value=0.2)
    time_to_mat = st.number_input("Time to Maturity (years)", value=1.0)

    if st.button("Calculate Greeks"):
        payload = {
            "spot": spot,
            "strike": strike,
            "rate": rate,
            "vol": vol,
            "time": time_to_mat
        }
        result = submit_and_poll("greeks", payload)
        if result is not None:
            st.subheader("Greeks")
            st.json(result)

elif page == "Hedge":
    st.header("Delta Hedge Calculation")
    delta = st.number_input("Option Delta", value=0.5)
    contracts = st.number_input("Number of Contracts", value=1, step=1)
    contract_size = st.number_input("Contract Size", value=100, step=1)

    if st.button("Calculate Hedge Ratio"):
        payload = {
            "delta": delta,
            "contracts": int(contracts),
            "contract_size": int(contract_size)
        }
        result = submit_and_poll("hedge", payload)
        if result is not None:
            st.subheader("Hedge Details")
            st.json(result)

elif page == "Payoff":
    st.header("Payoff Analysis")
    payoff_type = st.selectbox(
        "Strategy",
        ["protective_put", "covered_call", "collar"]
    )
    prices_input = st.text_input("Underlying Prices (comma-separated)", "90,95,100,105,110")
    S0 = st.number_input("Initial Spot (S0)", value=100.0)
    prem_put = st.number_input("Put Premium", value=0.0)
    prem_call = st.number_input("Call Premium", value=0.0)

    K_put = None
    K_call = None
    if payoff_type in ["protective_put", "collar"]:
        K_put = st.number_input("Put Strike (K_put)", value=95.0)
    if payoff_type in ["covered_call", "collar"]:
        K_call = st.number_input("Call Strike (K_call)", value=105.0)

    if st.button("Calculate Payoff"):
        prices = [float(x.strip()) for x in prices_input.split(",")]
        payload = {
            "prices": prices,
            "S0": S0,
            "premium_put": prem_put,
            "premium_call": prem_call
        }
        if K_put is not None:
            payload["K_put"] = K_put
        if K_call is not None:
            payload["K_call"] = K_call

        result = submit_and_poll(f"payoff/{payoff_type}", payload)
        if result is not None:
            st.subheader("Payoffs")
            st.line_chart(result)

# Footer
st.markdown("---")
st.markdown("Built with Streamlit & deployed on AWS Lambda + API Gateway.")  
