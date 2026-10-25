"""Session HTTP partagée : certificats du système, User-Agent Wikimedia, retries."""
import os

import truststore

# Avast définit SSLKEYLOGFILE vers un pipe Windows, ce qui fait planter OpenSSL
# dans Python (« no OPENSSL_Applink »).
os.environ.pop("SSLKEYLOGFILE", None)
truststore.inject_into_ssl()

import requests  # noqa: E402
from requests.adapters import HTTPAdapter  # noqa: E402
from urllib3.util.retry import Retry  # noqa: E402

from .config import USER_AGENT  # noqa: E402


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retry = Retry(
        total=8,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=None,  # POST compris (requêtes SPARQL)
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=8)
    session.mount("https://", adapter)
    return session
