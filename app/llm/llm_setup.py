from langchain_ollama import ChatOllama

def get_llm():
    """Get configured LLM instance"""
    return ChatOllama(model="mistral", temperature=0.0)
