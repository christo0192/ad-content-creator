"""Emerging-AI-role scoring + skills extraction (from the validated
emerging-roles run). Gives each title an emerging/seniority/canonical bucket
and pulls a tools/skills list from the description -> rich dashboard signal.
"""
import re

EMERGING = [
    (r"\b(agentic|ai agent|agent engineer|multi[\s-]?agent)\b", "AI Agent / Agentic AI Engineer"),
    (r"\bllm\s?ops\b",                                          "LLMOps Engineer"),
    (r"\b(rag|retrieval[\s-]?augmented)\b",                     "RAG / Retrieval Engineer"),
    (r"\bprompt engineer",                                       "Prompt Engineer"),
    (r"\b(genai|gen[\s-]?ai|generative ai|llm engineer|large language model)\b", "GenAI / LLM Engineer"),
    (r"\b(applied ai|applied scientist)\b",                     "Applied AI / Scientist"),
    (r"\b(ai eval|evals|model evaluation|llm evaluation)\b",    "AI Evaluation Engineer"),
    (r"\b(ai safety|ai alignment|responsible ai|ai governance|ai ethics)\b", "AI Safety / Governance"),
    (r"\bforward[\s-]?deployed\b",                              "Forward-Deployed AI Engineer"),
    (r"\b(conversational ai|voice ai|chatbot)\b",              "Conversational / Voice AI Engineer"),
    (r"\b(ai|ml) platform\b|\b(ai|ml) infra",                  "AI Platform / Infra Engineer"),
    (r"\bcontext engineer",                                     "Context Engineer"),
    (r"\bmlops\b",                                              "MLOps Engineer"),
]
SENIORITY = [
    (r"\b(head of (ai|data science|machine learning|ml))\b",   "Head of AI / DS"),
    (r"\b(chief ai|chief data|caio)\b",                        "Chief AI Officer"),
    (r"\b(vp|director|director of)\s+(ai|ml|data science|machine learning)\b", "AI/ML Director / VP"),
    (r"\b(principal|staff)\s+(ai|ml|machine learning|data scien)", "Principal / Staff AI"),
    (r"\b(ai|ml|genai)\s+(architect)\b",                       "AI / ML Architect"),
    (r"\b(ai|ml|genai)\s+(lead|manager)\b",                    "AI/ML Lead / Manager"),
    (r"\b(ai|genai)\s+product\s+(manager|lead|owner)\b",       "AI Product Manager / Lead"),
]
CANONICAL = [
    (r"\bdata scientist\b",          "Data Scientist"),
    (r"\bmachine learning engineer\b|\bml engineer\b", "Machine Learning Engineer"),
    (r"\bdata engineer\b",           "Data Engineer"),
    (r"\bdata analyst\b",            "Data Analyst"),
    (r"\b(computer vision|cv engineer)\b", "Computer Vision Engineer"),
    (r"\b(nlp|natural language)\b",  "NLP Engineer"),
    (r"\bdeep learning\b",           "Deep Learning Engineer"),
    (r"\b(ai engineer|artificial intelligence engineer)\b", "AI Engineer (generic)"),
    (r"\b(ai|ml)\b",                 "Other AI/ML"),
]
SKILLS = {
    "LangChain": r"langchain", "LangGraph": r"langgraph", "LlamaIndex": r"llama\s?index",
    "CrewAI": r"crew\s?ai", "AutoGen": r"autogen", "Semantic Kernel": r"semantic kernel",
    "OpenAI API": r"openai", "Anthropic/Claude": r"anthropic|claude", "Gemini": r"gemini",
    "Llama": r"\bllama\b", "Mistral": r"mistral", "Hugging Face": r"hugging\s?face|transformers",
    "RAG": r"\brag\b|retrieval[\s-]?augmented", "Vector DB": r"vector (db|database|store)|faiss|chroma|qdrant|pinecone|weaviate|pgvector",
    "Fine-tuning": r"fine[\s-]?tun|lora|peft|rlhf|sft", "Prompt Eng": r"prompt engineer|prompt design",
    "MCP": r"\bmcp\b|model context protocol", "Agents": r"\bagent(s|ic)?\b|tool use|function calling",
    "Embeddings": r"embedding", "vLLM/Serving": r"vllm|ollama|triton|tgi",
    "LLM Eval": r"langsmith|langfuse|ragas|deepeval|evals?\b", "Guardrails": r"guardrail",
    "MLflow": r"mlflow", "Kubeflow": r"kubeflow", "SageMaker": r"sagemaker", "Vertex AI": r"vertex ai",
    "PyTorch": r"pytorch", "TensorFlow": r"tensorflow", "Kubernetes": r"kubernetes|k8s",
    "AWS": r"\baws\b", "Azure": r"\bazure\b", "GCP": r"\bgcp\b|google cloud",
}
_SK = {k: re.compile(v, re.I) for k, v in SKILLS.items()}
_EM = [(re.compile(p, re.I), b) for p, b in EMERGING]
_SR = [(re.compile(p, re.I), b) for p, b in SENIORITY]
_CN = [(re.compile(p, re.I), b) for p, b in CANONICAL]


def canonicalize(title):
    t = (title or "").lower()
    t = re.sub(r"[\(\[].*?[\)\]]", " ", t)
    t = re.sub(r"\b(senior|sr|junior|jr|lead|staff|principal|i|ii|iii|associate|"
               r"intern|trainee|fresher|remote|hybrid|onsite|contract|full[\s-]?time|"
               r"\d+\+?\s*years?|exp|years|new|urgent|immediate|hiring)\b", " ", t)
    t = re.sub(r"[^a-z0-9/ +]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def score_title(title):
    t = (title or "").lower()
    em = next((b for rx, b in _EM if rx.search(t)), None)
    sr = next((b for rx, b in _SR if rx.search(t)), None)
    cn = next((b for rx, b in _CN if rx.search(t)), None)
    lenses = set()
    if em:
        lenses.add("L1_genai_emerging")
    if sr:
        lenses.add("L4_seniority_hybrid")
    novel = (em is None and sr is None and (cn is None or cn == "Other AI/ML"))
    if novel:
        lenses.add("novel_unmapped")
    return {
        "emerging_bucket": em,
        "seniority_bucket": sr,
        "canonical_bucket": cn,
        "is_emerging": bool(em or sr or novel),
        "lenses": sorted(lenses),
    }


def extract_skills(text):
    if not text:
        return []
    return sorted(k for k, rx in _SK.items() if rx.search(text))
