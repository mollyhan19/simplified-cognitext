import wikipediaapi
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote

wiki_wiki = wikipediaapi.Wikipedia('fetching_wiki_samples')

def extract_title_from_url(url):
    """Extracts Wikipedia title from a given Wikipedia URL."""
    parsed_url = urlparse(url)

    # Wikipedia article titles are usually after '/wiki/'
    if "/wiki/" in parsed_url.path:
        title = parsed_url.path.split("/wiki/")[-1]
        return unquote(title.replace("_", " "))  # Convert URL encoding & underscores
    return None

def clean_wiki_text(text):
    """Clean wiki text by handling LaTeX and mathematical expressions."""
    text = re.sub(r'\{\\displaystyle (.*?)\}', r'\1', text)
    math_replacements = {
        '\\mathbf': '',
        '\\text': '',
        '\\in': '∈',
        '\\Sigma': 'Σ',
        '\\ast': '*',
        '^{*}': '*',
        '_{M}': '_M'
    }
    for old, new in math_replacements.items():
        text = text.replace(old, new)
    text = re.sub(r'\{\\.*?\}', '', text)
    return text.strip()


def split_into_paragraphs(text):
    """Split text into meaningful paragraphs while preserving formulas."""
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Normalize paragraph breaks
    text = re.sub(r' +', ' ', text)  # Normalize spaces
    potential_paragraphs = re.split(r'([.!?])\s*\n+', text)

    paragraphs = []
    current_para = ""
    for i in range(0, len(potential_paragraphs), 2):
        if i < len(potential_paragraphs):
            current_para += potential_paragraphs[i]
            if i + 1 < len(potential_paragraphs):
                current_para += potential_paragraphs[i + 1]
                if current_para.strip():
                    cleaned_para = clean_wiki_text(current_para)
                    if len(cleaned_para) > 20:
                        paragraphs.append(cleaned_para)
                current_para = ""
    if current_para.strip():
        cleaned_para = clean_wiki_text(current_para)
        if len(cleaned_para) > 20:
            paragraphs.append(cleaned_para)
    return paragraphs


def fetch_article_content(url, category="general"):
    """Fetch article content from Wikipedia given a URL."""
    title = extract_title_from_url(url)
    if not title:
        print("Invalid Wikipedia URL.")
        return None

    page = wiki_wiki.page(title)
    if not page.exists():
        print(f"Page {title} does not exist.")
        return None

    opening_section = {
        "section_title": "Introduction",
        "content": split_into_paragraphs(page.summary),
        "subsections": []
    }

    def extract_sections(section):
        sections_list = []
        for s in section.sections:
            sections_list.append({
                "section_title": s.title,
                "content": split_into_paragraphs(s.text),
                "subsections": extract_sections(s)
            })
        return sections_list

    sections = extract_sections(page)
    sections.insert(0, opening_section)

    article_data = {
        "schema": {
            "schema_type": "WikiArticles",
            "schema_version": "1.0"
        },
        "title": title,
        "category": category,
        "sections": sections
    }

    return article_data


def save_article(url, output_path):
    """Fetch a Wikipedia article from a URL and save it as JSON."""
    article_data = fetch_article_content(url)
    if article_data:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(article_data, f, indent=4, ensure_ascii=False)
        print(f"Article saved to {output_path}")
    else:
        print("Failed to fetch article.")

# Example usage
if __name__ == "__main__":
    url = "https://en.wikipedia.org/wiki/Artificial_intelligence"  # Example input
    save_article(url, "concept-map-generator/data/article.json")
