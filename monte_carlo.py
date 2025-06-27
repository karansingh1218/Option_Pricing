import math, random

def generate_asset_price(S0, sigma, r, q, T):
    """
    Simulate one path endpoint S(T) under risk‑neutral GBM with 
    continuous dividend yield q.
    """
    z = random.gauss(0, 1)
    drift = (r - q - 0.5 * sigma**2) * T
    diffusion = sigma * math.sqrt(T) * z
    return S0 * math.exp(drift + diffusion)

def payoff(S_T, K, option_type):
    """Simple payoff function for call or put."""
    if option_type == "call":
        return max(S_T - K, 0)
    else:
        return max(K - S_T, 0)

def monte_carlo_option_price(
    S0: float,
    sigma: float,
    r: float,
    q: float,
    T: float,
    K: float,
    simulations: int,
    option_type: str = "call"
) -> float:
    """
    Monte Carlo pricing of a European option with dividend yield q.
    
    Parameters
    ----------
    S0 : float
        Initial spot price.
    sigma : float
        Volatility (decimal).
    r : float
        Continuously‑compounded risk‑free rate (decimal).
    q : float
        Continuously‑compounded dividend yield (decimal).
    T : float
        Time to expiration in years.
    K : float
        Strike price.
    simulations : int
        Number of Monte Carlo trials.
    option_type : {'call', 'put'}
        Option type.
    
    Returns
    -------
    float
        Monte Carlo estimate of option price.
    """
    discount = math.exp(-r * T)
    total_payoff = 0.0

    for _ in range(simulations):
        S_T = generate_asset_price(S0, sigma, r, q, T)
        total_payoff += payoff(S_T, K, option_type)

    return discount * (total_payoff / simulations)
