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
import plotly.graph_objects as go
import io

# Import the needed modules for entity extraction
from fetch_wiki import fetch_article_content
from entity_extraction import OptimizedEntityExtractor, TextChunk, RelationTracker
from entity_linking_main import process_article_by_sections, process_article_by_paragraphs, save_entity_results, save_relation_results
from cyclic_generator import CyclicConceptMapGenerator
from network_generator import NetworkConceptMapGenerator


# Get the directory of the current script
script_dir = Path(__file__).parent.absolute()
# Path to .env file (assuming it's in the parent directory)
env_path = script_dir.parent / '.env'
# Load the .env file
load_dotenv(dotenv_path=env_path)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    st.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    st.stop()

# Initialize the entity extractor with your API key
extractor = OptimizedEntityExtractor(api_key=openai_api_key, cache_version="1.0")

# Initialize OpenAI client for chatbot
openai_client = openai.OpenAI(api_key=openai_api_key)

# Define output directory
output_dir = os.path.join(script_dir, "output")
os.makedirs(output_dir, exist_ok=True)

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

if "cyclic_constellations" not in st.session_state:
    st.session_state.cyclic_constellations = []

if "current_constellation_idx" not in st.session_state:
    st.session_state.current_constellation_idx = 0

if "cyclic_fig" not in st.session_state:
    st.session_state.cyclic_fig = None

if "last_displayed_idx" not in st.session_state:
    st.session_state.last_displayed_idx = 0

if "selected_concept" not in st.session_state:
    st.session_state.selected_concept = None

if "network_fig" not in st.session_state:
    st.session_state.network_fig = None

if "selected_focus_concept" not in st.session_state:
    st.session_state.selected_focus_concept = None

cyclic_generator = CyclicConceptMapGenerator(api_key=openai_api_key, output_dir=output_dir)
network_generator = NetworkConceptMapGenerator(api_key=openai_api_key, output_dir=output_dir)


def check_url_params():
    """Check URL parameters for concept selection."""
    # Access query parameters using the current Streamlit API
    query_params = st.query_params
    if 'concept' in query_params:
        concept_name = query_params['concept']

        # Generate explanation for the selected concept
        explain_concept(concept_name)

        # Clear the URL parameter to prevent repeated explanations
        # We need to use the new way to manage query parameters
        # Create a new dict without the 'concept' key
        new_params = {}
        for key in query_params:
            if key != 'concept':
                new_params[key] = query_params[key]

        # Update the query parameters
        st.query_params.update(**new_params)

# Function to query LLM with context
def query_llm(question, context):
    try:
        if st.session_state.extracted_data["entities"]:
            system_prompt = f"""You are a helpful expert assistant for the topic {st.session_state.extracted_data['title']}. 
            Your knowledge is based on a concept map extracted from a Wikipedia article. 
            Use the provided concepts and relationships to answer the user's questions accurately.
            If the information isn't available in the provided context, use your general knowledge but make it clear when you're doing so.
            Be concise but informative in your responses."""
        else:
            system_prompt = """You are a helpful assistant. Answer the user's questions based on your general knowledge.
            Be concise but informative in your responses."""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",
                 "content": f"Here is the context information (if available):\n{context}\n\nUser question: {question}"}
            ],
            temperature=0.2
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

    # Add user "question" to chat history
    st.session_state.chat_history.append({
        "role": "user",
        "content": f"What is **{concept_name}**?"
    })

    # Generate context for better explanation
    context = generate_context(concept_name)

    # Get the explanation from LLM
    explanation = query_llm(f"Explain {concept_name}", context)

    # Add assistant response to chat history
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
        # Get relations relevant to the focus concept
        relevant_relations = [
            r for r in st.session_state.extracted_data["relations"]
            if r.get("source", "").lower() == focus_concept.lower() or
               r.get("target", "").lower() == focus_concept.lower()
        ]

        # Find the entity info for the concept
        focus_entity = None
        for entity in st.session_state.extracted_data["entities"]:
            if entity.get("id", "").lower() == focus_concept.lower():
                focus_entity = entity
                break

        # Build focused context
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
        # Regular context
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

# Streamlit layout
st.set_page_config(layout="wide", page_title="Concept Map Generator")

st.title("Enhanced Concept Map Generator")
st.markdown("Generate concept maps from Wikipedia articles and chat with the knowledge graph")

check_url_params()
# Create columns layout
col1, col2 = st.columns([2, 1])  # Left (Concept Map) | Right (Chatbot)

# Left column: Concept Extraction
with col1:
    if st.session_state.map_data["map_type"] is not None:
        st.subheader(
            f"{st.session_state.map_data['map_type'].capitalize()} Concept Map for {st.session_state.map_data['title']}")

        if st.session_state.map_data["map_type"] == "hierarchical" and st.session_state.map_data["html_content"]:
            concept_capture_js = """
                <script>
                document.addEventListener('concept-selected', function(event) {
                    const data = event.detail;
                    // Use Streamlit's setComponentValue to communicate with Python
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        value: {
                            concept: data.name,
                            layer: data.layer
                        }
                    }, '*');
                });
                </script>
                """

            # Inject the JS into your page
            st.components.v1.html(concept_capture_js, height=0)

            # Use components.v1.html to display the map with event listening capability
            components_value = st.components.v1.html(
                st.session_state.map_data["html_content"],
                height=600,
                scrolling=True
            )

            # Check if a concept was selected via double-click
            if components_value and 'concept' in components_value:
                st.session_state.selected_concept = components_value['concept']

                # Trigger the chatbot to explain the concept
                with col2:
                    if st.session_state.selected_concept:
                        explain_concept(st.session_state.selected_concept)

            # Provide download link if map file exists
            if os.path.exists(st.session_state.map_data["map_file"]):
                with open(st.session_state.map_data["map_file"], "rb") as file:
                    st.download_button(
                        label="Download Hierarchical Map (HTML)",
                        data=file,
                        file_name=f"hierarchical_{st.session_state.map_data['title']}.html",
                        mime="text/html"
                    )

        elif st.session_state.map_data["map_type"] == "cyclic":
            if "cyclic_constellations" in st.session_state and st.session_state.cyclic_constellations:
                # Get current constellation
                current_idx = st.session_state.current_constellation_idx
                constellations = st.session_state.cyclic_constellations
                if 0 <= current_idx < len(constellations):
                    current_constellation = constellations[current_idx]
                    st.subheader(f"Cyclic Concept Map: {current_constellation['name']}")
                    # Check if we have a stored figure or need to regenerate
                    if st.session_state.cyclic_fig is None or current_idx != st.session_state.last_displayed_idx:
                        # Generate the Plotly figure
                        fig = cyclic_generator.generate_cyclic_map(
                            title=st.session_state.map_data["title"],
                            constellation=current_constellation,
                            entities=st.session_state.map_data["entities"],
                            relations=st.session_state.map_data["relations"]
                        )
                        st.session_state.cyclic_fig = fig
                        st.session_state.last_displayed_idx = current_idx
                    else:
                        # Use the stored figure
                        fig = st.session_state.cyclic_fig

                    # Display the figure
                    st.plotly_chart(fig, use_container_width=True)

                    # Navigation controls
                    if len(constellations) > 1:
                        cols = st.columns([1, 2, 1])
                        with cols[0]:
                            prev_disabled = current_idx <= 0
                            if st.button("← Previous", disabled=prev_disabled, key="prev_persistent"):
                                st.session_state.current_constellation_idx -= 1
                                st.rerun()
                        with cols[1]:
                            st.markdown(f"**Constellation {current_idx + 1} of {len(constellations)}**")
                        with cols[2]:
                            next_disabled = current_idx >= len(constellations) - 1
                            if st.button("Next →", disabled=next_disabled, key="next_persistent"):
                                st.session_state.current_constellation_idx += 1
                                st.rerun()
                    # Add option to save the visualization as HTML
                    buffer = io.StringIO()
                    fig.write_html(buffer)
                    html_bytes = buffer.getvalue().encode()
                    st.download_button(
                        label="Download Interactive Map (HTML)",
                        data=html_bytes,
                        file_name=f"cyclic_{st.session_state.map_data['title']}_{current_constellation['name']}.html",
                        mime="text/html",
                        key="download_persistent"
                    )
            else:
                st.info("No cyclic concept map data is available.")

        elif st.session_state.map_data["map_type"] == "network":
            st.subheader(f"Network Concept Map for {st.session_state.map_data['title']}")

            component_value = network_generator.display_network_map(st.session_state.map_data)

            with st.expander("Explore Concepts", expanded=False):
                # Get all concepts in the map
                all_concepts = [entity["id"] for entity in st.session_state.extracted_data["entities"]]

                # Create a searchable dropdown
                selected_concept = st.selectbox(
                    "Select a concept to explain:",
                    all_concepts,
                    index=0,
                    key="network_concept_selector"
                )

                # Add an explain button
                if st.button("Explain Selected Concept", key="explain_network_concept"):
                    with st.spinner(f"Generating explanation for '{selected_concept}'..."):
                        explain_concept(selected_concept)
                    st.rerun()

            # Provide download link
            buffer = io.StringIO()
            buffer.write(st.session_state.map_data["html_content"])
            html_bytes = buffer.getvalue().encode()
            st.download_button(
                label="Download Network Map (HTML)",
                data=html_bytes,
                file_name=f"network_{st.session_state.map_data['title']}_{st.session_state.map_data.get('detail_level', 'detailed')}.html",
                mime="text/html"
            )

        # Add a divider to separate the existing map from the new map form
        st.divider()

    st.header("Concept Map Generator")
    url = st.text_input("Enter Wikipedia URL:")

    col1_options1, col1_options2 = st.columns(2)
    with col1_options1:
        processing_mode = st.selectbox("Processing Mode",
                                       ["section", "paragraph (pruned)"],
                                       help="Section mode processes entire sections at once. Paragraph mode processes individual paragraphs with pruning for better results.")
    with col1_options2:
        map_type = st.selectbox("Select Concept Map Structure", ["Hierarchical", "Cyclic", "Network"])

    # Optional root concept input for hierarchical maps
    if map_type == "Hierarchical":
        root_concept = st.text_input("Root Concept (optional):", "",
                                     help="Central concept for the hierarchical map. Leave empty to auto-detect.")
    else:
        root_concept = None

    if st.button("Generate from Wikipedia"):
        # Create a placeholder for status messages
        status_placeholder = st.empty()
        status_placeholder.info("Fetching article...")

        try:
            # Fetch the article content
            article_data = fetch_article_content(url)

            # Extract the title and create an articles dictionary
            title = article_data.get("title", "Untitled")
            category = article_data.get("category", "General")

            # Update status message to success
            status_placeholder.success(f"Successfully fetched article: {title}")

            # Create a new placeholder for processing status
            process_placeholder = st.empty()
            process_placeholder.info(f"Extracting concepts and relations ({processing_mode} mode)...")

            # Create progress bar
            progress_bar = st.progress(0)

            # Reset extractor for new article
            extractor.reset_tracking()
            extractor.relation_tracker = RelationTracker()
            extractor.relation_tracker.periodic_extraction_threshold = 1  # Extract global relations after each section

            # Determine actual processing mode - convert UI selection to internal mode
            actual_processing_mode = "section" if processing_mode == "section" else "paragraph"

            if actual_processing_mode == "section":
                # Process by sections
                sections_label = st.empty()
                sections_label.info("Processing article by sections...")

                # Count the total number of sections to process
                sections = article_data.get('sections', [])
                sections_to_skip = {"See also", "Notes", "References", "Works cited", "External links"}
                total_sections = len([s for s in sections if s.get('section_title', '') not in sections_to_skip])

                # Process each section and update progress
                processed_sections = 0

                # Modified version of process_article_by_sections
                for section_idx, section in enumerate(sections, 1):
                    section_title = section.get('section_title', '')

                    if section_title in sections_to_skip:
                        continue

                    section_text = []
                    main_content = section.get('content', [])
                    section_text.extend(main_content)

                    # Add subsection content
                    for subsection in section.get('subsections', []):
                        section_text.extend(subsection.get('content', []))

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

                        # Update progress
                        processed_sections += 1
                        progress_bar.progress(processed_sections / total_sections)

                entities = extractor.get_sorted_entities()

            else:
                # Process by paragraphs with pruning
                para_label = st.empty()
                para_label.info("Processing article by paragraphs with pruning...")

                # Count total paragraphs
                total_paragraphs = 0
                sections_to_skip = {"See also", "Notes", "References", "Works cited", "External links"}
                for section in article_data.get('sections', []):
                    if section.get('section_title', '') not in sections_to_skip:
                        total_paragraphs += len(section.get('content', []))
                        for subsection in section.get('subsections', []):
                            total_paragraphs += len(subsection.get('content', []))

                # Process paragraphs with progress updates
                processed_paragraphs = 0

                # Modified version of process_article_by_paragraphs
                for section_idx, section in enumerate(article_data.get('sections', []), 1):
                    section_title = section.get('section_title', '')

                    if section_title in sections_to_skip:
                        continue

                    # Process main content paragraphs
                    for para_idx, paragraph in enumerate(section.get('content', []), 1):
                        chunk = TextChunk(
                            content=paragraph,
                            section_name=section_title,
                            heading_level="main",
                            section_text=[paragraph],
                            section_index=section_idx,
                            paragraph_index=para_idx
                        )
                        extractor.process_paragraph(chunk)

                        # Update progress
                        processed_paragraphs += 1
                        progress_bar.progress(processed_paragraphs / total_paragraphs)

                    # Process subsection paragraphs
                    for subsection in section.get('subsections', []):
                        subsection_title = subsection.get('title', '')
                        for para_idx, paragraph in enumerate(subsection.get('content', []), 1):
                            chunk = TextChunk(
                                content=paragraph,
                                section_name=f"{section_title} - {subsection_title}",
                                heading_level="sub",
                                section_text=[paragraph],
                                section_index=section_idx,
                                paragraph_index=para_idx
                            )
                            extractor.process_paragraph(chunk)

                            # Update progress
                            processed_paragraphs += 1
                            progress_bar.progress(processed_paragraphs / total_paragraphs)

                entities = extractor.get_sorted_entities()

            # Set progress to 100% when done
            progress_bar.progress(1.0)
            process_placeholder.success("Concept extraction complete!")

            # Final global relation extraction
            final_global_relations = extractor.extract_global_relations(entities)
            extractor.relation_tracker.add_global_relations(final_global_relations)

            # Format relations for use
            relations = [
                {
                    "source": rel.source,
                    "type": rel.relation_type,
                    "target": rel.target,
                    "evidence": rel.evidence,
                    "section_name": rel.section_name,
                    "section_index": rel.section_index
                }
                for rel in extractor.relation_tracker.master_relations
            ]

            # Save results
            timestamp = datetime.now().isoformat().replace(":", "-")
            entity_file = os.path.join(output_dir, f"entity_analysis_{title}_{timestamp}.json")
            relation_file = os.path.join(output_dir, f"relations_{title}_{timestamp}.json")

            # Save entity results
            save_entity_results(entities, entity_file, actual_processing_mode, title, category)

            # Get and save relation results
            all_relations = {
                title: extractor.get_all_relations()
            }

            # Format article data for relation saving
            articles_data = {
                title: {
                    "category": category
                }
            }

            save_relation_results(all_relations, articles_data, actual_processing_mode)

            # Store extracted data in session state for chatbot
            st.session_state.extracted_data = {
                "entities": entities,
                "relations": relations,
                "title": title,
                "category": category
            }

            st.success(f"Extracted {len(entities)} concepts and {len(relations)} relations")

            # Generate concept map based on selected type
            with st.spinner(f"Generating {map_type} concept map..."):
                if map_type == "Hierarchical":
                    # Prepare data for hierarchical map
                    relation_data = {
                        title: {
                            "category": category,
                            "relations": relations
                        }
                    }

                    # Define output file path for hierarchical map
                    map_file = os.path.join(output_dir, f"hierarchical_{title}_{timestamp}.html")

                    # Call the hierarchical generator script
                    temp_json_path = os.path.join(output_dir, f"temp_relations_{timestamp}.json")
                    with open(temp_json_path, 'w') as f:
                        json.dump(relation_data, f, indent=2)

                    cmd = [
                        "python",
                        os.path.join(script_dir, "hierarchical_generator.py"),
                        temp_json_path,
                        map_file
                    ]

                    # Add root concept if provided
                    if root_concept:
                        cmd.extend(["--root", root_concept])

                    # Run the hierarchical generator
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = process.communicate()

                    # Clean up temporary file
                    if os.path.exists(temp_json_path):
                        os.unlink(temp_json_path)

                    if process.returncode != 0:
                        st.error(f"Error generating hierarchical map: {stderr}")
                    elif os.path.exists(map_file):
                        st.subheader("Hierarchical Concept Map")

                        # Store map data in session state
                        st.session_state.map_data = {
                            "map_type": "hierarchical",
                            "map_file": map_file,
                            "title": title,
                            "html_content": open(map_file, 'r', encoding='utf-8').read(),
                            "entity_file": entity_file,
                            "relation_file": relation_file
                        }

                        # Display the hierarchical map in an iframe
                        st.components.v1.html(st.session_state.map_data["html_content"], height=600)

                        # Provide download link
                        with open(map_file, "rb") as file:
                            st.download_button(
                                label="Download Hierarchical Map (HTML)",
                                data=file,
                                file_name=f"hierarchical_{title}.html",
                                mime="text/html"
                            )

                elif map_type == "Cyclic":
                    with st.spinner("Generating concept constellations with LLM..."):

                        # Generate concept constellations
                        constellations = cyclic_generator.generate_constellations(
                            title=title,
                            category=category,
                            entities=entities,
                            relations=relations,
                            num_constellations=3
                        )
                        # Store constellations in session state
                        st.session_state.cyclic_constellations = constellations
                        st.session_state.current_constellation_idx = 0
                        # Store basic map data in session state
                        st.session_state.map_data = {
                            "map_type": "cyclic",
                            "title": title,
                            "entities": entities,
                            "relations": relations
                        }
                        if constellations:
                            # Generate map for the first constellation
                            current_constellation = constellations[0]
                            st.subheader(f"Cyclic Concept Map: {current_constellation['name']}")

                            # Generate the plotly figure
                            fig = cyclic_generator.generate_cyclic_map(
                                title=title,
                                constellation=current_constellation,
                                entities=entities,
                                relations=relations
                            )
                            # Store the figure in session state
                            st.session_state.cyclic_fig = fig

                            # Display the figure
                            st.plotly_chart(fig, use_container_width=True)
                            # Create navigation for multiple constellations
                            if len(constellations) > 1:
                                cols = st.columns([1, 2, 1])

                                with cols[0]:
                                    prev_disabled = st.session_state.current_constellation_idx <= 0
                                    if st.button("← Previous", disabled=prev_disabled):
                                        st.session_state.current_constellation_idx -= 1
                                        st.rerun()
                                with cols[1]:
                                    st.markdown(
                                        f"**Constellation {st.session_state.current_constellation_idx + 1} of {len(constellations)}**")
                                with cols[2]:
                                    next_disabled = st.session_state.current_constellation_idx >= len(
                                        constellations) - 1
                                    if st.button("Next →", disabled=next_disabled):
                                        st.session_state.current_constellation_idx += 1
                                        st.rerun()

                            # Add option to save the visualization as HTML
                            buffer = io.StringIO()
                            fig.write_html(buffer)
                            html_bytes = buffer.getvalue().encode()

                            st.download_button(
                                label="Download Interactive Map (HTML)",
                                data=html_bytes,
                                file_name=f"cyclic_{title}_{current_constellation['name']}.html",
                                mime="text/html"
                            )

                        else:

                            st.error("Failed to generate concept constellations.")

                elif map_type == "Network":
                    with st.spinner("Generating network concept map..."):

                        # Get detail level
                        detail_level = processing_mode.split()[
                            0].lower() if "pruned" not in processing_mode else "intermediate"
                        # Generate the network map
                        map_data = network_generator.generate_network_map(
                            title=title,
                            entities=entities,
                            relations=relations,
                            detail_level=detail_level
                        )
                        # Store map data in session state
                        st.session_state.map_data = {
                            "map_type": "network",
                            "title": title,
                            "entities": entities,
                            "relations": relations,
                            "detail_level": detail_level,
                            "html_content": map_data["html_content"]
                        }
                        # Display the network map
                        st.subheader(f"Network Concept Map: {title}")
                        network_generator.display_network_map(map_data)
                        # Provide download link for HTML
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
                # Show top concepts
                st.subheader("Top Concepts")

                # Get top concepts by frequency
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

                # Create a DataFrame for relations
                relations_df = pd.DataFrame([
                    {
                        "Source": rel.get("source", ""),
                        "Relation": rel.get("relation_type", ""),
                        "Target": rel.get("target", ""),
                        "Section": rel.get("section_name", "")
                    }
                    for rel in relations[:20]  # Display top 20 relations
                ])

                st.dataframe(relations_df)

            # Provide download links for raw entity and relation data
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

    # Show information about extracted data if available
    if st.session_state.extracted_data["entities"]:
        st.success(f"Currently loaded: {st.session_state.extracted_data['title']}")

    # Simple chatbot interface that's always available
    st.markdown("Ask me anything!")

    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Get user input
    user_question = st.chat_input("Ask a question")
    if user_question:
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_question)

        # Add to chat history
        st.session_state.chat_history.append({"role": "user", "content": user_question})

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                context = generate_context()
                response = query_llm(user_question, context)
                st.markdown(response)

        # Add assistant response to chat history
        st.session_state.chat_history.append({"role": "assistant", "content": response})

    # Option to clear chat history
    if st.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()