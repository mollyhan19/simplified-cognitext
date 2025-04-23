import streamlit as st
import os
import json
from datetime import datetime
import openai
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import base64
import subprocess
import time
import io

from fetch_wiki import fetch_article_content
from entity_extraction import OptimizedEntityExtractor, TextChunk, RelationTracker
from entity_linking_main import process_article_by_subsections, save_entity_results, save_relation_results
from network_generator import NetworkConceptMapGenerator

# Get the directory of the current script
script_dir = Path(__file__).parent.absolute()
env_path = script_dir.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Define output directory
output_dir = os.path.join(script_dir, "output")
os.makedirs(output_dir, exist_ok=True)

# Define pregenerated content directory
pregenerated_dir = os.path.join(script_dir, "pregenerated")
os.makedirs(pregenerated_dir, exist_ok=True)

# Define the pre-generated content URLs and their corresponding files
PREGENERATED_CONTENT = {
    "https://en.wikipedia.org/wiki/Microchimerism": {
        "title": "Microchimerism",
        "html_file": os.path.join(pregenerated_dir, "microchimerism_network.html"),
        "entity_file": os.path.join(pregenerated_dir, "microchimerism_entities.json"),
        "relation_file": os.path.join(pregenerated_dir, "microchimerism_relations.json"),
        "detail_level": "detailed"
    },
    "https://en.wikipedia.org/wiki/Quantum_supremacy": {
        "title": "Quantum supremacy",
        "html_file": os.path.join(pregenerated_dir, "quantum_supremacy_network.html"),
        "entity_file": os.path.join(pregenerated_dir, "quantum_supremacy_entities.json"),
        "relation_file": os.path.join(pregenerated_dir, "quantum_supremacy_relations.json"),
        "detail_level": "detailed"
    },
    "https://en.wikipedia.org/wiki/Grammaticalization": {
        "title": "Grammaticalization",
        "html_file": os.path.join(pregenerated_dir, "grammaticalization_network.html"),
        "entity_file": os.path.join(pregenerated_dir, "grammaticalization_entities.json"),
        "relation_file": os.path.join(pregenerated_dir, "grammaticalization_relations.json"),
        "detail_level": "detailed"
    },
    "https://en.wikipedia.org/wiki/P_versus_NP_problem": {
        "title": "P versus NP problem",
        "html_file": os.path.join(pregenerated_dir, "p_versus_np_problem_network.html"),
        "entity_file": os.path.join(pregenerated_dir, "p_versus_np_problem_entities.json"),
        "relation_file": os.path.join(pregenerated_dir, "p_versus_np_problem_relations.json"),
        "detail_level": "detailed"
    }
}

# Set up session state variables
if "api_key" not in st.session_state:
    st.session_state.api_key = os.getenv("OPENAI_API_KEY", "")

if "api_key_valid" not in st.session_state:
    st.session_state.api_key_valid = False

if "extractor" not in st.session_state:
    st.session_state.extractor = None

# Create session state for chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "extracted_data" not in st.session_state:
    st.session_state.extracted_data = {
        "entities": [],
        "relations": [],
        "title": "",
        "category": ""
    }

if "map_data" not in st.session_state:
    st.session_state.map_data = {
        "map_type": None,
        "map_file": None,
        "title": None,
        "html_content": None,
        "entity_file": None,
        "relation_file": None
    }

if "selected_concept" not in st.session_state:
    st.session_state.selected_concept = None

if "network_fig" not in st.session_state:
    st.session_state.network_fig = None

if "selected_focus_concept" not in st.session_state:
    st.session_state.selected_focus_concept = None

if "openai_client" not in st.session_state:
    st.session_state.openai_client = None

if "network_generator" not in st.session_state:
    st.session_state.network_generator = None


def validate_openai_key(api_key):
    """Validate OpenAI API key by making a test request"""
    if not api_key or len(api_key) < 20:  # Basic check for key format
        return False

    try:
        # Initialize the client with the provided key
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
        return True
    except Exception as e:
        print(f"API key validation error: {str(e)}")
        return False


def check_url_params():
    """Check URL parameters for concept selection."""
    # Access query parameters using the current Streamlit API
    query_params = st.query_params
    if 'concept' in query_params:
        concept_name = query_params['concept']

        # Generate explanation for the selected concept
        explain_concept(concept_name)

        new_params = {}
        for key in query_params:
            if key != 'concept':
                new_params[key] = query_params[key]

        # Update the query parameters
        st.query_params.update(**new_params)


def load_pregenerated_content(url_data):
    """Load pre-generated content for a specific URL."""
    status_placeholder = st.empty()
    status_placeholder.info(f"Loading pre-generated content for {url_data['title']}...")

    try:
        # Load HTML content
        if os.path.exists(url_data['html_file']):
            with open(url_data['html_file'], 'r', encoding='utf-8') as f:
                html_content = f.read()
        else:
            status_placeholder.error(f"Pre-generated HTML file not found: {url_data['html_file']}")
            return False

        # Load entities
        if os.path.exists(url_data['entity_file']):
            with open(url_data['entity_file'], 'r', encoding='utf-8') as f:
                entity_data = json.load(f)

                # Extract entities from the file structure
                if url_data['title'] in entity_data:
                    entities = entity_data[url_data['title']].get('entities', [])
                else:
                    entities = []
                    for article_title in entity_data:
                        if isinstance(entity_data[article_title], dict) and 'entities' in entity_data[article_title]:
                            entities = entity_data[article_title]['entities']
                            break
                    if not entities and 'entities' in entity_data:
                        entities = entity_data['entities']
        else:
            status_placeholder.error(f"Pre-generated entity file not found: {url_data['entity_file']}")
            return False

        # Load relations
        if os.path.exists(url_data['relation_file']):
            with open(url_data['relation_file'], 'r', encoding='utf-8') as f:
                relation_data = json.load(f)

                # Extract relations from the file structure (might need adjustment)
                if 'articles' in relation_data and url_data['title'] in relation_data['articles']:
                    relations = relation_data['articles'][url_data['title']].get('relations', [])
                elif 'relations' in relation_data:
                    relations = relation_data['relations']
                else:
                    relations = []
        else:
            status_placeholder.error(f"Pre-generated relation file not found: {url_data['relation_file']}")
            return False

        # Update session state
        st.session_state.extracted_data = {
            "entities": entities,
            "relations": relations,
            "title": url_data['title'],
            "category": "Pre-generated"
        }

        st.session_state.map_data = {
            "map_type": "network",
            "title": url_data['title'],
            "html_content": html_content,
            "detail_level": url_data['detail_level'],
            "entities": entities,
            "relations": relations
        }

        status_placeholder.success(f"Successfully loaded pre-generated content for {url_data['title']}")
        return True

    except Exception as e:
        status_placeholder.error(f"Error loading pre-generated content: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return False


# Function to query LLM with context
def query_llm(question, context):
    try:
        if not st.session_state.openai_client:
            return "Sorry, I need a valid OpenAI API key to answer questions. Please provide your API key in the sidebar."

        if st.session_state.extracted_data["entities"]:
            system_prompt = f"""You are a helpful expert assistant for the topic {st.session_state.extracted_data['title']}. 
            Your knowledge is based on a concept map extracted from a Wikipedia article. 
            Use the provided concepts and relationships to answer the user's questions accurately.
            If the information isn't available in the provided context, use your general knowledge but make it clear when you're doing so.
            Be concise but informative in your responses."""
        else:
            system_prompt = """You are a helpful assistant. Answer the user's questions based on your general knowledge.
            Be concise but informative in your responses."""

        response = st.session_state.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",
                 "content": f"Here is the context information (if available):\n{context}\n\nUser question: {question}"}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"I'm having trouble generating a response right now. Error: {str(e)}"


def explain_concept(concept_name):
    """Generate an explanation for a concept and add it to the chat history."""
    if not st.session_state.extracted_data["entities"]:
        return

    # Generate a prompt for concept explanation
    prompt = f"""
    Please explain the concept "{concept_name}" in the context of {st.session_state.extracted_data['title']}.
    Keep it concise (2-3 sentences) but informative. Your explanation should be suitable for an average undergraduate with moderate prior knowledge. 
    """

    st.session_state.chat_history.append({
        "role": "user",
        "content": f"What is **{concept_name}**?"
    })
    context = generate_context(concept_name)
    explanation = query_llm(f"Explain {concept_name}", context)
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": explanation
    })


def generate_context(focus_concept=None):
    """Generate context for LLM, optionally focused on a specific concept."""
    if not st.session_state.extracted_data["entities"]:
        return "No specific concept data is loaded. Answer based on your general knowledge."

    # Get top entities and relations
    top_entities = st.session_state.extracted_data["entities"][:20]

    if focus_concept:
        relevant_relations = [
            r for r in st.session_state.extracted_data["relations"]
            if r.get("source", "").lower() == focus_concept.lower() or
               r.get("target", "").lower() == focus_concept.lower()
        ]

        focus_entity = None
        for entity in st.session_state.extracted_data["entities"]:
            if entity.get("id", "").lower() == focus_concept.lower():
                focus_entity = entity
                break

        context = f"""
        Topic: {st.session_state.extracted_data['title']}
        Category: {st.session_state.extracted_data['category']}

        Focus Concept: {focus_concept}

        Concept Information:
        {json.dumps(focus_entity, indent=2) if focus_entity else "No detailed information available"}

        Related Concepts:
        {json.dumps(relevant_relations[:10], indent=2)}
        """
    else:
        top_relations = st.session_state.extracted_data["relations"][:30]
        context = f"""
        Topic: {st.session_state.extracted_data['title']}
        Category: {st.session_state.extracted_data['category']}

        Key Concepts:
        {json.dumps([{"id": e.get("id", ""), "layer": e.get("layer", ""), "frequency": e.get("frequency", 0)} for e in top_entities], indent=2)}

        Key Relationships:
        {json.dumps([{"source": r.get("source", ""), "relation_type": r.get("relation_type", ""), "target": r.get("target", "")} for r in top_relations], indent=2)}
        """

    return context


def init_api_services():
    """Initialize API services with the provided key"""
    if st.session_state.api_key and st.session_state.api_key_valid:
        st.session_state.openai_client = openai.OpenAI(api_key=st.session_state.api_key)
        st.session_state.extractor = OptimizedEntityExtractor(api_key=st.session_state.api_key, cache_version="1.0")
        st.session_state.network_generator = NetworkConceptMapGenerator(api_key=st.session_state.api_key,
                                                                        output_dir=output_dir)
        return True
    return False


st.set_page_config(layout="wide", page_title="Concept Map Generator")

hide_streamlit_style = """
    <style>
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}

    /* Hide GitHub corner link - adjust selector as needed */
    .github-corner, .github-fork-ribbon, a[href*="github.com"] {
        visibility: hidden !important;
    }
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Sidebar for API key input
with st.sidebar:
    st.title("API Key Configuration")

    # API key input with mask_text=True for security
    api_key = st.text_input(
        "Enter your OpenAI API key:",
        value=st.session_state.api_key if st.session_state.api_key_valid else "",
        type="password",
        help="Your OpenAI API key is required to extract concepts and generate maps"
    )

    # Validate key button
    if st.button("Validate and Save API Key"):
        if validate_openai_key(api_key):
            st.session_state.api_key = api_key
            st.session_state.api_key_valid = True
            init_api_services()
            st.success("✅ API key is valid! You can now use the application.")
        else:
            st.session_state.api_key_valid = False
            st.error("❌ Invalid API key. Please check your key and try again.")

    # Show key status
    if st.session_state.api_key_valid:
        st.success("API key status: Valid ✅")
    else:
        st.error("API key status: Not configured or invalid ❌")

    st.info("""
    **Note:** Your API key is stored only in your browser's session and is not saved on our servers.
    You will need to re-enter it if you refresh the page or close your browser.

    To get an OpenAI API key, sign up at https://platform.openai.com/
    """)

# Main title
st.title("Cognitext: Enhanced Concept Map Generator")

# API key check before showing content
if not st.session_state.api_key_valid:
    st.warning("⚠️ Please enter your OpenAI API key in the sidebar to use this application.")
    st.markdown("""
    This tool uses OpenAI's APIs to analyze Wikipedia articles and generate concept maps. 
    To protect your privacy, we require you to use your own API key instead of a shared one.

    **Getting Started:**
    1. Sign up for an OpenAI account at [platform.openai.com](https://platform.openai.com)
    2. Create an API key in your account dashboard
    3. Enter the key in the sidebar and click "Validate and Save API Key"
    """)

    st.subheader("Example of what you can create:")
    st.image("python/pregenerated/sample_networkvis.png",
             caption="Example concept map visualization")

else:
    # Initialize services if needed
    if not st.session_state.openai_client:
        init_api_services()

    st.markdown("""
    Turn Wikipedia into a playground of ideas! We take complex articles and transform them into interactive concept maps that show how ideas connect, bounce off each other, and build deeper understanding. Explore knowledge in a whole new way—no linear reading required.

    **Key features:**
    - **Node sizes** represent concept importance (based on frequency and total connections)
    - **Color coding** distinguishes between priority, secondary, and tertiary concept layers
    - **Default view** shows only priority concepts for clarity
    - **Glowing nodes** indicate hidden connections to secondary or tertiary concepts

    **Tips for exploration:**
    1. Start with the big central nodes and work your way out! Examine relationships between priority concepts first, and progressively explore deeper connections. 
    2. Click any node for a closer look; Right-click a node to peek at its concept explanation; Click glowing nodes to reveal secret relationships.
    3. Hover over links to uncover connections with evidence from the text. 
    4. Feel free to drag nodes around and make the map your own.
    5. Use the chat panel to ask questions about any concept.

    (Psst: This map was pre-generated to keep things zippy. Feel free to tryout your own wiki article favorites, but might take a bit longer to map out.)
    """)

    check_url_params()
    # Create columns layout
    col1, col2 = st.columns([2, 1])  # Left (Concept Map) | Right (Chatbot)

    with col1:
        # Display current map if available
        if st.session_state.map_data["map_type"] == "network" and st.session_state.network_generator:
            st.subheader(f"Network Concept Map for {st.session_state.map_data['title']}")

            component_value = st.session_state.network_generator.display_network_map(st.session_state.map_data)

            buffer = io.StringIO()
            buffer.write(st.session_state.map_data["html_content"])
            html_bytes = buffer.getvalue().encode()
            st.download_button(
                label="Download Network Map (HTML)",
                data=html_bytes,
                file_name=f"network_{st.session_state.map_data['title']}_{st.session_state.map_data.get('detail_level', 'detailed')}.html",
                mime="text/html"
            )

        st.divider()
        tab1, tab2 = st.tabs(["📚 Pre-generated Concept Maps", "🔍 Generate Your Own"])

        # Tab 1: Pre-generated content
        with tab1:
            st.header("Explore Pre-generated Concept Maps")
            st.info(
                "These concept maps are ready to explore! Select one to get started immediately, no waiting required.")

            pregenerated_options = {
                "Microchimerism": "https://en.wikipedia.org/wiki/Microchimerism",
                "Quantum Supremacy": "https://en.wikipedia.org/wiki/Quantum_supremacy",
                "Grammaticalization": "https://en.wikipedia.org/wiki/Grammaticalization",
                "P versus NP Problem": "https://en.wikipedia.org/wiki/P_versus_NP_problem"
            }

            selected_pregenerated = st.selectbox(
                "Select a pre-generated concept map to explore:",
                options=list(pregenerated_options.keys()),
                index=0,
                help="Choose from these pre-generated concept maps for instant exploration"
            )

            if st.button("Load Pre-generated Concept Map", key="load_pregenerated"):
                url = pregenerated_options[selected_pregenerated]
                url_data = PREGENERATED_CONTENT[url]

                with st.spinner(f"Loading {selected_pregenerated} concept map..."):
                    success = load_pregenerated_content(url_data)
                    if success:
                        st.success(f"Successfully loaded concept map for {selected_pregenerated}!")
                        st.rerun()
                    else:
                        st.error("Failed to load pre-generated content. Please try another option.")

        # Tab 2: Custom content
        with tab2:
            st.header("Generate Your Own Concept Map")
            st.warning("""
            **Note**: Generating a new concept map requires processing the entire Wikipedia article and may take 
            5-10 minutes depending on article length. Your OpenAI API key will be charged for the processing.
            """)

            url = st.text_input("Enter Wikipedia URL:")

            col1_options1, col1_options2 = st.columns(2)
            with col1_options1:
                processing_mode = st.selectbox(
                    "Processing Mode",
                    ["section"],
                    help="Section mode processes entire sections at once."
                )
            with col1_options2:
                map_type = st.selectbox("Select Concept Map Structure", ["Network"])

            if st.button("Generate from Wikipedia", key="generate_custom"):
                if not url:
                    st.error("Please enter a Wikipedia URL.")
                    st.stop()

                is_pregenerated = False
                for pregenerated_url, url_data in PREGENERATED_CONTENT.items():
                    if pregenerated_url == url:
                        is_pregenerated = True
                        st.info("This article has a pre-generated concept map available! Loading the faster version...")
                        success = load_pregenerated_content(url_data)
                        if success:
                            st.success(
                                "Pre-generated content loaded successfully! You can explore the concept map now.")
                            st.rerun()
                        else:
                            st.error("Failed to load pre-generated content. Falling back to real-time processing.")
                            is_pregenerated = False
                            break

                if not is_pregenerated:
                    status_placeholder = st.empty()
                    status_placeholder.info("Fetching article...")

                    try:
                        # Fetch the article content
                        article_data = fetch_article_content(url)

                        if not article_data:
                            status_placeholder.error(
                                f"Failed to fetch article from {url}. Please check the URL and try again.")
                            st.stop()

                        # Extract the title and create an articles dictionary
                        title = article_data.get("title", "Untitled")
                        category = article_data.get("category", "General")

                        status_placeholder.success(f"Successfully fetched article: {title}")

                        process_placeholder = st.empty()

                        progress_bar = st.progress(0)

                        st.session_state.extractor.reset_tracking()
                        st.session_state.extractor.relation_tracker = RelationTracker()
                        st.session_state.extractor.relation_tracker.periodic_extraction_threshold = 3

                        sections = article_data.get('sections', [])
                        sections_to_skip = {"See also", "Notes", "References", "Works cited", "External links"}

                        total_units = 0
                        for section in sections:
                            section_title = section.get('section_title', '')
                            if section_title in sections_to_skip:
                                continue

                            subsections = section.get('subsections', [])
                            if not subsections:
                                total_units += 1
                            else:
                                total_units += len(subsections)

                        processed_units = 0

                        with st.spinner("Processing article..."):
                            units_label = st.empty()

                            for section_idx, section in enumerate(sections, 1):
                                section_title = section.get('section_title', '')

                                if section_title in sections_to_skip:
                                    continue

                                subsections = section.get('subsections', [])

                                if not subsections:
                                    processed_units += 1
                                    progress_bar.progress(processed_units / total_units)
                                    units_label.info(
                                        f"Processing unit {processed_units}/{total_units}: Section '{section_title}'")

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
                                        st.session_state.extractor.process_section(chunk)
                                else:
                                    # Process each subsection separately
                                    for subsection_idx, subsection in enumerate(subsections, 1):
                                        processed_units += 1
                                        subsection_title = subsection.get('section_title', '')
                                        full_title = f"{section_title} - {subsection_title}"

                                        progress_bar.progress(processed_units / total_units)
                                        units_label.info(
                                            f"Processing unit {processed_units}/{total_units}: Subsection '{full_title}'")

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
                                            st.session_state.extractor.process_section(chunk)

                            # Get entities after processing is done
                            entities = st.session_state.extractor.get_sorted_entities()

                            # Final global relation extraction
                            process_placeholder.info("Final global relationships extraction...")
                            final_global_relations = st.session_state.extractor.extract_global_relations(entities)
                            st.session_state.extractor.relation_tracker.add_global_relations(final_global_relations)
                            st.session_state.extractor.relation_tracker.merge_relations()

                        relations = [
                            {
                                "source": rel.source,
                                "relation_type": rel.relation_type,
                                "target": rel.target,
                                "evidence": rel.evidence,
                                "section_name": rel.section_name,
                                "section_index": rel.section_index
                            }
                            for rel in st.session_state.extractor.relation_tracker.master_relations
                        ]

                        # Save results
                        timestamp = datetime.now().isoformat().replace(":", "-")
                        entity_file = os.path.join(output_dir, f"entity_analysis_{title}_{timestamp}.json")
                        relation_file = os.path.join(output_dir, f"relations_{title}_{timestamp}.json")

                        save_entity_results(entities, entity_file, processing_mode, title, category)

                        all_relations = {
                            title: st.session_state.extractor.get_all_relations()
                        }

                        articles_data = {
                            title: {
                                "category": category
                            }
                        }

                        save_relation_results(all_relations, articles_data, processing_mode)

                        # Store extracted data in session state for chatbot
                        st.session_state.extracted_data = {
                            "entities": entities,
                            "relations": relations,
                            "title": title,
                            "category": category
                        }

                        process_placeholder.success(f"Extracted {len(entities)} concepts and {len(relations)} relations")

                        # Generate concept map based on selected type
                        with st.spinner("Generating network concept map..."):

                            detail_level = processing_mode.split()[
                                0].lower() if "pruned" not in processing_mode else "intermediate"
                            map_data = st.session_state.network_generator.generate_network_map(
                                title=title,
                                entities=entities,
                                relations=relations,
                                detail_level=detail_level
                            )
                            st.session_state.map_data = {
                                "map_type": "network",
                                "title": title,
                                "entities": entities,
                                "relations": relations,
                                "detail_level": detail_level,
                                "html_content": map_data["html_content"]
                            }
                            st.subheader(f"Network Concept Map: {title}")
                            st.session_state.network_generator.display_network_map(map_data)
                            buffer = io.StringIO()
                            buffer.write(map_data["html_content"])
                            html_bytes = buffer.getvalue().encode()
                            st.download_button(
                                label="Download Network Map (HTML)",
                                data=html_bytes,
                                file_name=f"network_{title}_{detail_level}.html",
                                mime="text/html"
                            )

                        # Display concepts and relations in expandable sections
                        with st.expander("View Extracted Concepts", expanded=False):
                            st.subheader("Top Concepts")

                            top_concepts = sorted(
                                entities,
                                key=lambda x: x.get("frequency", 0),
                                reverse=True
                            )[:10]

                            concepts_df = pd.DataFrame([
                                {
                                    "Concept": entity.get("id", ""),
                                    "Layer": entity.get("layer", ""),
                                    "Frequency": entity.get("frequency", 0),
                                    "Sections": entity.get("section_count", 0)
                                }
                                for entity in top_concepts
                            ])

                            st.dataframe(concepts_df)

                        with st.expander("View Extracted Relations", expanded=False):
                            st.subheader("Key Relations")

                            relations_df = pd.DataFrame([
                                {
                                    "Source": rel.get("source", ""),
                                    "Relation": rel.get("relation_type", ""),
                                    "Target": rel.get("target", ""),
                                    "Section": rel.get("section_name", "")
                                }
                                for rel in relations[:20]
                            ])

                            st.dataframe(relations_df)

                        st.subheader("Download Results")
                        col_download1, col_download2 = st.columns(2)

                        with col_download1:
                            if os.path.exists(entity_file):
                                with open(entity_file, "rb") as file:
                                    st.download_button(
                                        label="Download Entities (JSON)",
                                        data=file,
                                        file_name=f"entities_{title}.json",
                                        mime="application/json"
                                    )

                        with col_download2:
                            if os.path.exists(relation_file):
                                with open(relation_file, "rb") as file:
                                    st.download_button(
                                        label="Download Relations (JSON)",
                                        data=file,
                                        file_name=f"relations_{title}.json",
                                        mime="application/json"
                                    )

                    except Exception as e:
                        st.error(f"Error processing article: {str(e)}")
                        import traceback

                        st.error(traceback.format_exc())

    # Right column: Chatbot
    with col2:
        st.header("Concept Chatbot")

        if st.session_state.extracted_data["entities"]:
            st.success(f"Currently loaded: {st.session_state.extracted_data['title']}")
        elif not st.session_state.api_key_valid:
            st.warning("Enter your OpenAI API key in the sidebar to use the chatbot")

        if st.session_state.api_key_valid:
            st.markdown("Ask me anything!")

            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            user_question = st.chat_input("Ask a question")
            if user_question:
                with st.chat_message("user"):
                    st.markdown(user_question)

                st.session_state.chat_history.append({"role": "user", "content": user_question})

                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        context = generate_context()
                        response = query_llm(user_question, context)
                        st.markdown(response)

                st.session_state.chat_history.append({"role": "assistant", "content": response})

            if st.button("Clear Chat History"):
                st.session_state.chat_history = []
                st.rerun()
        else:
            st.info("Please provide a valid OpenAI API key in the sidebar to use the chatbot functionality.")