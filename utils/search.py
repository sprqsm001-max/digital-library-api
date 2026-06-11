import re

def sanitize_search_query(query: str) -> str:
    """
    Sanitizes search query for PostgreSQL Full Text Search
    Removes special characters and handles empty queries
    """
    if not query:
        return ""
    
    # Remove special characters that could break FTS query
    # Keep alphanumeric and spaces
    clean_query = re.sub(r'[^\w\s]', ' ', query)
    
    # Normalize spaces
    clean_query = " ".join(clean_query.split())
    
    # Replace spaces with & for to_tsquery if needed,
    # but we usually use plainto_tsquery which handles spaces.
    # For plainto_tsquery, we just return the clean string.
    return clean_query

def setup_fts_sql():
    """
    Returns the SQL to setup Full Text Search on the books table.
    This should be run manually or via a migration script.
    """
    return """
    -- Create a function to update the search_vector
    CREATE OR REPLACE FUNCTION books_search_vector_update() RETURNS trigger AS $BODY$
    BEGIN
      new.search_vector :=
        setweight(to_tsvector('english', coalesce(new.title,'')), 'A') ||
        setweight(to_tsvector('english', coalesce(new.author,'')), 'B') ||
        setweight(to_tsvector('english', coalesce(new.description,'')), 'C');
      return new;
    END
    $BODY$ LANGUAGE plpgsql;

    -- Create the trigger
    DROP TRIGGER IF EXISTS tsvectorupdate ON books;
    CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE
    ON books FOR EACH ROW EXECUTE PROCEDURE books_search_vector_update();

    -- Update existing rows to populate search_vector
    UPDATE books SET title = title;
    """
