"""Ingestion dispatch for the WIRE events platform.

Registered per the PLAN.md onboarding playbook: the dispatcher knows the
full venue roster so a late parser is a one-line flip.
"""

from .sources import (
    alpha_feed, beta_feed, delta_feed, epsilon_feed, eta_feed, gamma_feed,
    iota_feed, kappa_feed, mu_feed, nu_feed, omicron_feed, sigma_feed,
    theta_feed, xi_feed, zeta_feed,
)

SOURCES = {
    "alpha": alpha_feed,
    "beta": beta_feed,
    "gamma": gamma_feed,
    "delta": delta_feed,
    "epsilon": epsilon_feed,
    "sigma": sigma_feed,
    "zeta": zeta_feed,
    "eta": eta_feed,
    "theta": theta_feed,
    "iota": iota_feed,
    "kappa": kappa_feed,
    "mu": mu_feed,
    "nu": nu_feed,
    "xi": xi_feed,
    "omicron": omicron_feed,
}


def ingest(source, payload, table=None, log=None, rebuild=False):
    """Dispatch one raw payload to its source parser."""
    table = [] if table is None else table
    log = [] if log is None else log
    if rebuild:
        del table[:]
        del log[:]
    return SOURCES[source].ingest(payload, table, log)
