import os
import ssl
import warnings
from dotenv import load_dotenv

load_dotenv()

# ✅ Disable SSL verification globally for corporate environments
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['SSL_CERT_FILE'] = ''

# ✅ Create unverified SSL context
ssl._create_default_https_context = ssl._create_unverified_context

# Suppress warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# ✅ Corporate proxy configuration (Zscaler Client Connector on port 9000)
# Pass GENAI_CLIENT_ARGS to every ChatGoogleGenerativeAI(..., client_args=GENAI_CLIENT_ARGS).
#
# NOTE: We cannot pass `verify=False` (a falsy value) because the google-genai SDK's
# _maybe_set() treats it as "not set" and overwrites it with a strict SSL context.
# Instead we pass an unverified SSLContext object (truthy), which the SDK preserves.
_ZSCALER_PROXY = "http://127.0.0.1:9000"
_unverified_ssl_ctx = ssl._create_unverified_context()
GENAI_CLIENT_ARGS = {
    "proxy": _ZSCALER_PROXY,
    "verify": _unverified_ssl_ctx,   # truthy → not overwritten by SDK's _maybe_set
}

# LLM Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.0-flash")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))

# Agent Configuration
MAX_REGENERATION_ATTEMPTS = 5
OUTPUT_DIR = "output/generated_tests"

# Playwright Configuration
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TIMEOUT = int(os.getenv("TIMEOUT", "30000"))