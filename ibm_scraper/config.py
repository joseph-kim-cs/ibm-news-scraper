"""Package-wide configuration: constants and dotenv bootstrapping."""

from __future__ import annotations

# ── optional dotenv loading ────────────────────────────────────────────────
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

# ── scraping constants ─────────────────────────────────────────────────────
IBM_RSS_URL = "https://newsroom.ibm.com/rss"
LOOKBACK_DAYS = 7

# Keywords that flag eye-catching IBM headlines.
# Matched case-insensitively against headline text.
KEYWORDS = [
    # AI / ML / research
    "ai", "artificial intelligence", "watson", "watsonx", "genai", "llm",
    "foundation model", "large language model", "machine learning", "deep learning",
    "neural network", "natural language processing", "nlp", "computer vision",
    "generative ai", "agentic", "autonomous", "inference", "fine-tuning",
    "retrieval-augmented", "rag", "transformer", "diffusion model",
    # Quantum
    "quantum", "qubit", "quantum computing", "quantum advantage",
    "quantum error correction", "quantum network", "quantum safe",
    "post-quantum", "lattice cryptography",
    # Semiconductors / hardware
    "chip", "semiconductor", "processor", "mainframe", "z16", "telum",
    "power10", "power processor", "accelerator", "gpu", "npu", "fpga",
    # Cloud & infrastructure
    "cloud", "hybrid cloud", "multicloud", "cloud native", "red hat",
    "openshift", "kubernetes", "container", "serverless", "edge computing",
    "data center", "infrastructure",
    # Security & trust
    "security", "cybersecurity", "zero trust", "encryption", "threat",
    "vulnerability", "ransomware", "breach", "compliance", "governance",
    "identity", "authentication", "siem", "qradar",
    # Data & analytics
    "data", "analytics", "data fabric", "data lakehouse", "database",
    "db2", "instana", "observability", "monitoring", "telemetry",
    "business intelligence", "dashboard", "insight",
    # Automation & software
    "automation", "rpa", "workflow", "devops", "devsecops", "gitops",
    "api", "integration", "middleware", "ansible", "terraform",
    "open-source", "open source", "linux",
    # Industry / consulting
    "consulting", "digital transformation", "modernization",
    "banking", "financial services", "healthcare", "life sciences",
    "manufacturing", "supply chain", "retail", "telecom", "government",
    "public sector", "energy", "utilities",
    # Sustainability & social
    "sustainability", "climate", "green", "carbon", "net zero",
    "renewable", "environmental", "social impact", "diversity",
    "inclusion", "equity", "ethics", "responsible ai",
    # Space, science & moonshots
    "moon", "lunar", "space", "nasa", "astronomy", "satellite",
    "breakthrough", "milestone", "discovery", "record",
    # Sports / consumer-facing / events
    "us open", "usta", "tennis", "sports", "fan engagement",
    "formula 1", "f1", "nfl", "nba", "grand slam", "olympics",
    "esports", "gaming",
    # Business & partnerships
    "partnership", "collaboration", "acquisition", "investment",
    "venture", "startup", "ecosystem", "alliance", "joint venture",
    "expansion", "launch", "announcement",
    # Awards & recognition
    "award", "patent", "recognition", "ranked", "leader", "gartner",
    "forrester", "idc", "analyst", "innovation",
]

# Phrases that mark boilerplate / investor-relations noise to exclude.
STOP_PHRASES = [
    "dividends", "quarterly earnings", "financial results",
    "board of directors", "leadership appointment", "earnings per share",
]
