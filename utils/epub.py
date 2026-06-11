import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from typing import Dict, Any, List

def extract_epub_metadata(file_path: str) -> Dict[str, Any]:
    \"\"\"
    Extracts bibliographic metadata from an EPUB file.
    \"\"\"
    try:
        book = epub.read_epub(file_path)

        # 1. Title
        title = book.get_metadata('DC', 'title')
        title = title[0][0] if title else \"Untitled Book\"

        # 2. Authors
        creators = book.get_metadata('DC', 'creator')
        authors = [c[0] for c in creators] if creators else []

        # 3. Description
        description = book.get_metadata('DC', 'description')
        if description:
            # Clean HTML tags if present in metadata
            desc_text = description[0][0]
            description = BeautifulSoup(desc_text, \"html.parser\").get_text()
        else:
            description = \"\"

        # 4. Language
        language = book.get_metadata('DC', 'language')
        language = language[0][0] if language else \"English\"

        # 5. Publisher
        publisher = book.get_metadata('DC', 'publisher')
        publisher = publisher[0][0] if publisher else \"Unknown Publisher\"

        # 6. Publication Date
        date = book.get_metadata('DC', 'date')
        pub_year = None
        if date:
            date_str = date[0][0]
            # Simple year extraction from ISO string or similar
            if '-' in date_str:
                pub_year = int(date_str.split('-')[0])
            elif len(date_str) >= 4:
                try:
                    pub_year = int(date_str[:4])
                except:
                    pass

        # 7. ISBN
        identifiers = book.get_metadata('DC', 'identifier')
        isbn = None
        if identifiers:
            for ident in identifiers:
                val = ident[0].lower()
                if 'isbn' in val:
                    isbn = val.replace('isbn:', '').replace('-', '').strip()
                    break

        return {
            \"title\": title,
            \"authors\": authors,
            \"description\": description,
            \"language\": language,
            \"publisher\": publisher,
            \"publication_year\": pub_year,
            \"isbn\": isbn,
            \"file_type\": \"epub\"
        }

    except Exception as e:
        print(f\"Error extracting EPUB metadata: {e}\")
        return {
            \"title\": os.path.basename(file_path).replace('.epub', ''),
            \"authors\": [],
            \"description\": \"\",
            \"file_type\": \"epub\"
        }
