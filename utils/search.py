import re

def sanitize_search_query(query: str) -> str:
    """
    Cleans up user queries for PostgreSQL Full-Text Search.
    Uses alphanumeric characters and spaces only, then joins terms with '&'
    to construct a valid plain-text search query.
    """
    if not query:
        return ""
    
    # Remove special characters to prevent injection/syntax issues, keeping spaces
    cleaned = re.sub(r'[^\w\s]', '', query)
    
    # Split into words
    words = [word.strip() for word in cleaned.split() if word.strip()]
    
    # If no words, return empty
    if not words:
        return ""
        
    # Join words with standard '&' for to_tsquery, or return space-separated for plainto_tsquery
    # Using simple space-separated list is ideal for plainto_tsquery
    return " ".join(words)
