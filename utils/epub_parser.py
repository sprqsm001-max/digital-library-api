import zipfile
import xml.etree.ElementTree as ET
import io
import re
import urllib.parse

def find_element_by_tag(parent, tag_name):
    """Namespace-agnostic search for a single element by its tag name."""
    if parent is None:
        return None
    for el in parent.iter():
        if el.tag == tag_name or el.tag.endswith("}" + tag_name):
            return el
    return None

def find_elements_by_tag(parent, tag_name):
    """Namespace-agnostic search for all elements by their tag name."""
    results = []
    if parent is None:
        return results
    for el in parent.iter():
        if el.tag == tag_name or el.tag.endswith("}" + tag_name):
            results.append(el)
    return results

def parse_epub_metadata(epub_bytes: bytes) -> dict:
    """
    Parses metadata and content from an EPUB file in bytes.
    Returns a dictionary of extracted fields, or None if parsing fails.
    """
    try:
        # Load zip from bytes
        z = zipfile.ZipFile(io.BytesIO(epub_bytes))
        
        # 1. Find and parse container.xml
        try:
            container_xml = z.read("META-INF/container.xml")
        except KeyError:
            print("EPUB missing META-INF/container.xml")
            return None
            
        container_root = ET.fromstring(container_xml)
        rootfile = find_element_by_tag(container_root, "rootfile")
        if rootfile is None:
            print("container.xml contains no rootfile reference")
            return None
            
        opf_path = rootfile.attrib.get("full-path")
        if not opf_path:
            print("rootfile has no full-path attribute")
            return None
            
        # Unquote URL encoding in path if any
        opf_path = urllib.parse.unquote(opf_path)
            
        # Determine the parent directory of the OPF file inside the zip
        opf_dir = "/".join(opf_path.split("/")[:-1])
        if opf_dir:
            opf_dir += "/"
            
        # 2. Read OPF file
        try:
            opf_content = z.read(opf_path)
        except KeyError:
            print(f"Could not find OPF file at: {opf_path}")
            return None
            
        opf_root = ET.fromstring(opf_content)
        
        # Find metadata element
        metadata = find_element_by_tag(opf_root, "metadata")
        if metadata is None:
            print("OPF contains no metadata element")
            return None
            
        # Helper to get first text value of Dublin Core tag
        def get_dc_value(tag_name, default=""):
            el = find_element_by_tag(metadata, tag_name)
            if el is not None and el.text:
                return el.text.strip()
            return default

        title = get_dc_value("title", "Unknown Title")
        author = get_dc_value("creator", "Unknown Author")
        language = get_dc_value("language", "English")
        publisher = get_dc_value("publisher", "Unknown Publisher")
        description = get_dc_value("description", "")
        
        # Parse Year
        date_str = get_dc_value("date", "")
        year = None
        if date_str:
            match = re.search(r"\b\d{4}\b", date_str)
            if match:
                year = int(match.group(0))
                
        # Parse ISBN
        isbn = None
        identifiers = find_elements_by_tag(metadata, "identifier")
        for id_el in identifiers:
            if id_el.text:
                text = id_el.text.strip()
                clean_id = re.sub(r"[-\s]", "", text)
                if re.match(r"^(978|979)?\d{9}[\dX]$", clean_id):
                    isbn = clean_id
                    break
                    
        # Parse subjects (genres)
        subjects = []
        subject_els = find_elements_by_tag(metadata, "subject")
        for s in subject_els:
            if s.text:
                # Split compound categories like "Fiction / General"
                parts = [p.strip() for p in s.text.split("/") if p.strip()]
                subjects.extend(parts)
        # Unique list
        subjects = list(dict.fromkeys(subjects))
        
        # 3. Locate Manifest items
        manifest = find_element_by_tag(opf_root, "manifest")
        items = find_elements_by_tag(manifest, "item")
        
        items_map = {} # id -> href
        items_type = {} # id -> media-type
        for item in items:
            item_id = item.attrib.get("id")
            href = item.attrib.get("href")
            media_type = item.attrib.get("media-type", "")
            if item_id and href:
                # URL decode href
                href = urllib.parse.unquote(href)
                items_map[item_id] = href
                items_type[item_id] = media_type

        # 4. Search cover image
        cover_href = None
        cover_image_type = "image/jpeg"
        
        # Check EPUB2 style: <meta name="cover" content="item_id" />
        meta_els = find_elements_by_tag(metadata, "meta")
        for meta in meta_els:
            if meta.attrib.get("name") == "cover":
                cover_item_id = meta.attrib.get("content")
                if cover_item_id in items_map:
                    cover_href = items_map[cover_item_id]
                    cover_image_type = items_type.get(cover_item_id, "image/jpeg")
                    break
                    
        # Check EPUB3 style: <item properties="cover-image" ... />
        if not cover_href:
            for item in items:
                if item.attrib.get("properties") == "cover-image":
                    cover_href = urllib.parse.unquote(item.attrib.get("href"))
                    cover_image_type = item.attrib.get("media-type", "image/jpeg")
                    break
                    
        # Check fallback: items with id = 'cover' or 'cover-image'
        if not cover_href:
            for item_id, href in items_map.items():
                if item_id.lower() in ["cover", "cover-image", "coverimage", "book-cover"]:
                    cover_href = href
                    cover_image_type = items_type.get(item_id, "image/jpeg")
                    break
                    
        # Check ultimate fallback: filename containing 'cover' and image mime
        if not cover_href:
            for item_id, href in items_map.items():
                mtype = items_type.get(item_id, "")
                if "cover" in href.lower() and ("image" in mtype or href.lower().endswith((".jpg", ".jpeg", ".png"))):
                    cover_href = href
                    cover_image_type = mtype if mtype else "image/jpeg"
                    break
                    
        # Extract cover image bytes
        cover_image_bytes = None
        if cover_href:
            cover_zip_path = cover_href
            if opf_dir:
                cover_zip_path = opf_dir + cover_href
                # Clean up path traversal
                parts = []
                for p in cover_zip_path.split("/"):
                    if p == "..":
                        if parts: parts.pop()
                    elif p != "." and p != "":
                        parts.append(p)
                cover_zip_path = "/".join(parts)
                
            try:
                cover_image_bytes = z.read(cover_zip_path)
            except KeyError:
                # Try reading cover_href directly
                try:
                    cover_image_bytes = z.read(cover_href)
                except KeyError:
                    pass

        # 5. Extract text content from Spine
        spine = find_element_by_tag(opf_root, "spine")
        content_text_list = []
        if spine is not None:
            itemrefs = find_elements_by_tag(spine, "itemref")
            for ref in itemrefs:
                idref = ref.attrib.get("idref")
                if idref in items_map:
                    html_href = items_map[idref]
                    html_zip_path = html_href
                    if opf_dir:
                        html_zip_path = opf_dir + html_href
                        # Clean up path traversal
                        parts = []
                        for p in html_zip_path.split("/"):
                            if p == "..":
                                if parts: parts.pop()
                            elif p != "." and p != "":
                                parts.append(p)
                        html_zip_path = "/".join(parts)
                        
                    try:
                        html_bytes = z.read(html_zip_path)
                        try:
                            html_str = html_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            html_str = html_bytes.decode("latin-1")
                            
                        # Extract inner <body> to prevent multiple <html>/<head> nesting
                        body_match = re.search(r"<body[^>]*>(.*?)</body>", html_str, re.DOTALL | re.IGNORECASE)
                        if body_match:
                            content_text_list.append(body_match.group(1))
                        else:
                            content_text_list.append(html_str)
                    except KeyError:
                        pass
                        
        # Merge all spine HTML sections
        content_text = "\n".join(content_text_list) if content_text_list else ""
        
        # Return extracted dictionary
        return {
            "title": title,
            "author": author,
            "language": language,
            "publisher": publisher,
            "publication_year": year,
            "isbn": isbn,
            "description": description,
            "subjects": subjects,
            "cover_image_bytes": cover_image_bytes,
            "cover_image_type": cover_image_type,
            "content_text": content_text
        }
    except Exception as e:
        print(f"Error parsing EPUB file: {e}")
        return None
