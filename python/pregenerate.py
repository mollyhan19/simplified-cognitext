import os
import json
import time
import dotenv
from pathlib import Path
from fetch_wiki import fetch_article_content
from entity_extraction import OptimizedEntityExtractor, TextChunk, RelationTracker
from network_generator import NetworkConceptMapGenerator

# Load environment variables for API key
dotenv.load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI API key not found. Please set the OPENAI_API_KEY environment variable.")

# Define directories
script_dir = Path(__file__).parent.absolute()
output_dir = os.path.join(script_dir, "output")
pregenerated_dir = os.path.join(script_dir, "pregenerated")

# Create directories if they don't exist
os.makedirs(output_dir, exist_ok=True)
os.makedirs(pregenerated_dir, exist_ok=True)

# Initialize generators
extractor = OptimizedEntityExtractor(api_key=openai_api_key, cache_version="1.0")
network_generator = NetworkConceptMapGenerator(api_key=openai_api_key, output_dir=output_dir)

# Define URLs to pre-generate
URLS_TO_GENERATE = [
    {
        "url": "https://en.wikipedia.org/wiki/Microchimerism",
        "name": "microchimerism"
    },
    {
        "url": "https://en.wikipedia.org/wiki/Grammaticalization",
        "name": "grammaticalization"
    }
]


def process_and_generate_files(url_info):
    """Process a Wikipedia URL and generate all necessary files using subsection processing."""
    url = url_info["url"]
    name = url_info["name"]

    print(f"\n=== Processing {name} ===")
    print(f"Fetching article from {url}...")

    # Fetch the article content
    article_data = fetch_article_content(url)
    if not article_data:
        print(f"Failed to fetch article from {url}")
        return False

    # Extract title and category
    title = article_data.get("title", "Untitled")
    category = article_data.get("category", "General")

    print(f"Successfully fetched article: {title}")

    # Reset extractor for new article
    extractor.reset_tracking()
    extractor.relation_tracker = RelationTracker()
    extractor.relation_tracker.periodic_extraction_threshold = 3

    # Process article by subsections
    sections = article_data.get('sections', [])
    sections_to_skip = {"See also", "Notes", "References", "Works cited", "External links"}

    # Count total processing units (sections without subsections + individual subsections)
    total_units = 0
    for section in sections:
        section_title = section.get('section_title', '')
        if section_title in sections_to_skip:
            continue

        subsections = section.get('subsections', [])
        if not subsections:
            # Count section with no subsections as one unit
            total_units += 1
        else:
            # Count each subsection as one unit
            total_units += len(subsections)

    print(f"Processing {total_units} units (sections/subsections)...")
    processed_units = 0

    # Process each section/subsection
    for section_idx, section in enumerate(sections, 1):
        section_title = section.get('section_title', '')

        if section_title in sections_to_skip:
            continue

        # Get subsections
        subsections = section.get('subsections', [])

        if not subsections:
            # Process section as a single unit if it has no subsections
            processed_units += 1
            print(f"Processing unit {processed_units}/{total_units}: Section '{section_title}'")

            # Get section content
            section_text = section.get('content', [])
            if section_text:
                combined_text = "\n".join(section_text)
                chunk = TextChunk(
                    content=combined_text,
                    section_name=section_title,
                    heading_level="main",
                    section_text=section_text,
                    section_index=section_idx
                )
                extractor.process_section(chunk)
        else:
            # Process each subsection separately
            for subsection_idx, subsection in enumerate(subsections, 1):
                processed_units += 1
                subsection_title = subsection.get('section_title', '')
                full_title = f"{section_title} - {subsection_title}"

                print(f"Processing unit {processed_units}/{total_units}: Subsection '{full_title}'")

                # Get subsection content
                subsection_text = subsection.get('content', [])
                if subsection_text:
                    combined_text = "\n".join(subsection_text)
                    chunk = TextChunk(
                        content=combined_text,
                        section_name=full_title,
                        heading_level="sub",
                        section_text=subsection_text,
                        section_index=section_idx,
                        paragraph_index=subsection_idx
                    )
                    extractor.process_section(chunk)

    # Get entities
    entities = extractor.get_sorted_entities()

    # Final global relation extraction
    print("Extracting final global relationships...")
    final_global_relations = extractor.extract_global_relations(entities)
    extractor.relation_tracker.add_global_relations(final_global_relations)
    extractor.relation_tracker.merge_relations()

    # Format relations
    relations = [
        {
            "source": rel.source,
            "relation_type": rel.relation_type,
            "target": rel.target,
            "evidence": rel.evidence,
            "section_name": rel.section_name,
            "section_index": rel.section_index
        }
        for rel in extractor.relation_tracker.master_relations
    ]

    print(f"Extracted {len(entities)} concepts and {len(relations)} relations")

    # Generate HTML content
    print("Generating network map...")
    map_data = network_generator.generate_network_map(
        title=title,
        entities=entities,
        relations=relations,
        detail_level="detailed"
    )

    # Save all files
    html_file = os.path.join(pregenerated_dir, f"{name}_network.html")
    entity_file = os.path.join(pregenerated_dir, f"{name}_entities.json")
    relation_file = os.path.join(pregenerated_dir, f"{name}_relations.json")

    # Save HTML
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(map_data["html_content"])

    # Save entities
    entity_data = {
        "metadata": {
            "processing_mode": "subsection",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000000")
        },
        title: {
            "category": category,
            "total_entities": len(entities),
            "entities": entities
        }
    }
    with open(entity_file, "w", encoding="utf-8") as f:
        json.dump(entity_data, f, indent=2, ensure_ascii=False)

    # Save relations
    relation_data = {
        "metadata": {
            "type": "master_relations",
            "processing_mode": "subsection",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000000")
        },
        "articles": {
            title: {
                "category": category,
                "relations": relations
            }
        }
    }
    with open(relation_file, "w", encoding="utf-8") as f:
        json.dump(relation_data, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated files:")
    print(f"- HTML: {html_file}")
    print(f"- Entities: {entity_file}")
    print(f"- Relations: {relation_file}")

    return True

# Process each URL
for url_info in URLS_TO_GENERATE:
    success = process_and_generate_files(url_info)
    if success:
        print(f"Successfully processed {url_info['name']}")
    else:
        print(f"Failed to process {url_info['name']}")

print("\nAll processing complete!")