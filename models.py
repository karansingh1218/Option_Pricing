import math
from scipy.stats import norm
import pandas as pd
import numpy as np
import statistics
from random import gauss
import pandas as pd

class BSM:
    def __init__(self, S0  = 50, K   = 51, r   = 0.05, vol = 0.45, T   = 0.5):
        self.S0  = S0
        self.K   = K
        self.r   = r
        self.vol = vol
        self.T   = T

    def calculate_d1(self,):
        S0 = self.S0
        K = self.K
        r = self.r
        vol = self.vol
        T = self.T

        a = 1 / (vol * math.sqrt(T))
        b = math.log(S0/K) + (r + (1/2)*vol**2)*T
        d1 = a * b
        return d1

    def calculate_d2(self):
        S0 = self.S0
        K = self.K
        r = self.r
        vol = self.vol
        T = self.T

        a = 1 / (vol * math.sqrt(T))
        b = math.log(S0/K) + (r - (1/2)*vol**2)*T
        d1 = a * b
        return d1

    def cumulative_distribution(self,d):
        result = norm.cdf(d)
        #print(f"Cumulative probability for d={d}: {result}")
        return result

    def european_call_option_price(self,):
        S0 = self.S0
        K = self.K
        r = self.r
        vol = self.vol
        T = self.T

        d1 = self.calculate_d1()
        d2 = self.calculate_d2()
        c = S0 * self.cumulative_distribution(d1) - (K * math.exp(-r*T))* self.cumulative_distribution(d2)
        return c

    def european_put_option_price(self,):
        S0 = self.S0
        K = self.K
        r = self.r
        vol = self.vol
        T = self.T

        d1 = self.calculate_d1()
        d2 = self.calculate_d2()
        p = (K*math.exp(-r*T) * self.cumulative_distribution(-d2)) - (S0 * self.cumulative_distribution(-d1))
        return p

def binomial_tree_call(S, K, T, r, sigma, n):
    """
    Calculates the price of a European call option using the binomial tree model.

    S: Current stock price
    K: Strike price
    T: Time to expiration (in years)
    r: Risk-free interest rate
    sigma: Volatility of the stock price
    n: Number of time steps

    Returns:
        The price of the European call option
    """
    dt = T / n
    u = math.exp(sigma * math.sqrt(dt))
    d = 1 / u
    p = (math.exp(r * dt) - d) / (u - d)

    # Initialize option values at expiration
    option_values = [max(0, S * (u ** (n - i)) * (d ** i) - K) for i in range(n + 1)]

    # Backward induction to calculate option values at earlier nodes
    for step in range(n - 1, -1, -1):
        for i in range(step + 1):
            option_values[i] = math.exp(-r * dt) * (p * option_values[i] + (1 - p) * option_values[i + 1])

    return option_values[0]

def binomial_tree_european_put(S, K, T, r, sigma, n):
    """
    Calculates the price of a European put option using the binomial tree model.

    S: Current stock price
    K: Strike price
    T: Time to expiration (in years)
    r: Risk-free interest rate
    sigma: Volatility of the underlying asset
    n: Number of time steps

    Returns:
        The price of the European put option
    """

    dt = T / n
    u = math.exp(sigma * math.sqrt(dt))
    d = 1 / u
    p = (math.exp(r * dt) - d) / (u - d)

    # Initialize option values at expiration
    option_values = [max(0, K - S * (u ** (n - i)) * (d ** i)) for i in range(n + 1)]

    # Backward recursion to calculate option values at earlier nodes
    for j in range(n - 1, -1, -1):
        for i in range(j + 1):
            option_values[i] = math.exp(-r * dt) * (p * option_values[i] + (1 - p) * option_values[i + 1])

    return option_values[0]

def binomial_tree_american_option(S, K, T, r, sigma, n, option_type='put'):
    """
    Prices an American option using the binomial tree method.

    S (float): Current stock price
    K (float): Strike price
    T (float): Time to expiration (in years)
    r (float): Risk-free interest rate
    sigma (float): Volatility of the underlying asset
    n (int): Number of time steps
    option_type (str): 'put' or 'call'

    Returns:
        float: The price of the American option
    """
    dt = T / n
    u = math.exp(sigma * math.sqrt(dt))
    d = 1 / u
    p = (math.exp(r * dt) - d) / (u - d)

    # Initialize option values at expiration
    option_values = []
    for i in range(n + 1):
        ST = S * (u ** (n - i)) * (d ** i)
        if option_type == 'call':
            option_values.append(max(0, ST - K))
        else:  # put
            option_values.append(max(0, K - ST))

    # Backward induction
    for j in range(n - 1, -1, -1):
        for i in range(j + 1):
            ST = S * (u ** (j - i)) * (d ** i)
            continuation_value = math.exp(-r * dt) * (
                p * option_values[i] + (1 - p) * option_values[i + 1]
            )
            if option_type == 'call':
                exercise_value = max(0, ST - K)
            else:
                exercise_value = max(0, K - ST)
            option_values[i] = max(continuation_value, exercise_value)

    return option_values[0]

def calculate_d1(S0, K, r, vol, T):
    a = 1 / (vol * math.sqrt(T))
    b = math.log(S0/K) + (r + (1/2)*vol**2)*T
    d1 = a * b
    return d1
def cumulative_distribution(d):
    result = norm.cdf(d)
    #print(f"Cumulative probability for d={d}: {result}")
    return result
def delta(S0, K, r, vol, T):
    d1 = calculate_d1(S0, K, r, vol, T)
    cumul_dist = cumulative_distribution(d1)
    #print(f"DELTA = : {cumul_dist}")
    return cumul_dist
def probability_density(x):
    N = (1/ math.sqrt(2 * math.pi)) * math.exp((-x**2)/2)
    return N
def gamma(S0, K, r, vol, T):
    d1 = calculate_d1(S0, K, r, vol, T)
    N  = probability_density(d1)
    gamma = N / (S0*vol*math.sqrt(T))
    #print(f"GAMMA = : {gamma}")
    return gamma
def vega(S0, K, r, vol, T):
    d1 = calculate_d1(S0, K, r, vol, T)
    N  = probability_density(d1)
    vega = S0 * math.sqrt(T) * N
    #print(f"VEGA = : {vega}")
    return vega

def hedge_ratio(delta: float, contracts: int, contract_size: int = 100) -> float:
    """
    Hedge ratio (position delta) = Δ_option × #contracts × contract_size.
    """
    return delta * contracts * contract_size


def generate_asset_price(S,v,r,q,T):
    return S * math.exp((r - q - 0.5 * v**2) * T + v * math.sqrt(T) * gauss(0,1.0))

def call_payoff(S_T,K):
    return max(0.0,S_T - K)

def monte_carlo_simulation(S0, v, r, q ,T ,K ,simulations, is_call = True):
    payoffs = []
    discount_factor = math.exp(-r * T)

    for i in range(simulations):
        S_T = generate_asset_price(S0,v,r,q,T)
        payoffs.append(
            call_payoff(S_T, K)
        )
    if is_call:
        call_price = discount_factor * (sum(payoffs) / float(simulations))
        return call_price
    else:
        # From Put Call Parity
        call_price = discount_factor * (sum(payoffs) / float(simulations))
        put_price = call_price + K * math.exp(-r * T) - S0 * math.exp(-q * T)
        return put_price

def estimate_statistical_error(S0, v, r, q ,T ,K ,simulations, is_call, num_runs):
    """
    Estimates the statistical error of a Monte Carlo simulation.
    """
    results = []
    for _ in range(num_runs):
        result = monte_carlo_simulation(S0, v, r, q ,T ,K ,simulations, is_call)
        results.append(result)

    results = np.array(results)
    mean_result = np.mean(results)
    std_dev_result = np.std(results)
    standard_error = std_dev_result / np.sqrt(num_runs)

    return mean_result, standard_error


def protective_put_pl(S, S0, K_put, premium_put):
    """Profit/Loss for Protective Put at expiration."""
    return (S - S0) + np.maximum(K_put - S, 0) - premium_put

def covered_call_pl(S, S0, K_call, premium_call):
    """Profit/Loss for Covered Call at expiration."""
    return (S - S0) - np.maximum(S - K_call, 0) + premium_call

def collar_pl(S, S0, K_put, premium_put, K_call, premium_call):
    """Profit/Loss for Collar at expiration."""
    return (S - S0) + np.maximum(K_put - S, 0) - np.maximum(S - K_call, 0) - (premium_put - premium_call)





