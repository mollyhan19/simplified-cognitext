import os
import json
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import networkx as nx
import matplotlib.pyplot as plt
from pathlib import Path

from fetch_wiki import fetch_article_content
from entity_extraction import OptimizedEntityExtractor, TextChunk, RelationTracker
from entity_linking_main import process_article_by_sections, process_article_by_paragraphs

class ConceptMapProcessor:
    """Central controller for concept map generation pipeline."""

    def __init__(self, api_key: str, output_dir: str = "output"):
        self.api_key = api_key
        self.output_dir = output_dir
        self.entity_extractor = OptimizedEntityExtractor(api_key=api_key, cache_version="14.0")

        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Set up temporary directory for intermediate files
        self.temp_dir = tempfile.mkdtemp()

    def process_article(self, url: str, processing_mode: str = "section", map_type: str = "hierarchical",
                        root_concept: str = None) -> Dict:
        """
        Process a Wikipedia article and generate concept maps.

        Args:
            url: Wikipedia article URL
            processing_mode: 'section' or 'paragraph' mode for extraction
            map_type: 'hierarchical', 'network', or 'cyclic'
            root_concept: Optional root concept for hierarchical maps

        Returns:
            Dictionary with results and file paths
        """
        # 1. Fetch Wikipedia content
        print(f"Fetching article content from: {url}")
        article_data = fetch_article_content(url)

        if not article_data:
            raise ValueError(f"Failed to fetch article from {url}")

        title = article_data.get("title", "Untitled")
        category = article_data.get("category", "general")

        print(f"Processing article: {title} ({category})")

        # 2. Extract entities and relations
        print(f"Extracting entities and relations using {processing_mode} mode")
        entities, relations = self._extract_concepts_and_relations(title, article_data, processing_mode)

        # 3. Save extraction results
        timestamp = datetime.now().isoformat().replace(":", "-")
        entity_file, relation_file = self._save_extraction_results(
            title, category, entities, relations, processing_mode, timestamp
        )

        # 4. Generate the specified concept map type
        print(f"Generating {map_type} concept map")
        map_file = self._generate_concept_map(
            title, category, entities, relations, map_type, root_concept, timestamp
        )

        # 5. Return results dictionary
        return {
            "title": title,
            "category": category,
            "total_entities": len(entities),
            "total_relations": len(relations),
            "entity_file": entity_file,
            "relation_file": relation_file,
            "map_file": map_file,
            "map_type": map_type,
            "timestamp": timestamp,
            "entities": entities,
            "relations": relations
        }

    def _extract_concepts_and_relations(self, title: str, article_data: Dict,
                                        processing_mode: str) -> Tuple[List[Dict], List[Dict]]:
        """Extract concepts and relations from article data."""
        # Reset entity tracking for new article
        self.entity_extractor.reset_tracking()
        self.entity_extractor.relation_tracker = RelationTracker()

        # Process by section or paragraph based on mode
        if processing_mode == "section":
            # Process sections
            entities = process_article_by_sections(title, article_data, self.entity_extractor)
        else:
            # Process paragraphs
            entities = process_article_by_paragraphs(title, article_data, self.entity_extractor)

        # Final global relation extraction
        final_global_relations = self.entity_extractor.extract_global_relations(entities)
        self.entity_extractor.relation_tracker.add_global_relations(final_global_relations)

        # Format relations for return
        relations = [
            {
                "source": rel.source,
                "relation_type": rel.relation_type,
                "target": rel.target,
                "evidence": rel.evidence,
                "section_name": rel.section_name,
                "section_index": rel.section_index
            }
            for rel in self.entity_extractor.relation_tracker.master_relations
        ]

        return entities, relations

    def _save_extraction_results(self, title: str, category: str, entities: List[Dict],
                                 relations: List[Dict], processing_mode: str,
                                 timestamp: str) -> Tuple[str, str]:
        """Save extraction results to files."""
        # Create filenames
        entity_file = os.path.join(self.output_dir, f"entity_analysis_{title}_{timestamp}.json")
        relation_file = os.path.join(self.output_dir, f"relations_{title}_{timestamp}.json")

        # Save entity results directly
        with open(entity_file, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": {
                    "processing_mode": processing_mode,
                    "timestamp": timestamp
                },
                title: {
                    "category": category,
                    "total_entities": len(entities),
                    "entities": entities
                }
            }, f, indent=4, ensure_ascii=False)

        # Save relation results directly
        with open(relation_file, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": {
                    "type": "master_relations",
                    "processing_mode": processing_mode,
                    "timestamp": timestamp
                },
                "articles": {
                    title: {
                        "category": category,
                        "relations": relations
                    }
                }
            }, f, indent=4, ensure_ascii=False)

        return entity_file, relation_file

    def _generate_concept_map(self, title: str, category: str, entities: List[Dict],
                              relations: List[Dict], map_type: str, root_concept: str,
                              timestamp: str) -> str:
        """Generate the specified type of concept map."""
        map_type = map_type.lower()

        if map_type == "hierarchical":
            return self._generate_hierarchical_map(title, category, relations, root_concept, timestamp)
        elif map_type == "network":
            return self._generate_network_map(title, category, entities, relations, timestamp)
        elif map_type == "cyclic":
            return self._generate_cyclic_map(title, category, entities, relations, timestamp)
        else:
            raise ValueError(f"Unsupported map type: {map_type}")

    def _generate_hierarchical_map(self, title: str, category: str, relations: List[Dict],
                                   root_concept: str, timestamp: str) -> str:
        """Generate hierarchical concept map."""
        # Create output path
        output_path = os.path.join(self.output_dir, f"hierarchical_{title}_{timestamp}.html")

        # Create hierarchical structure
        hierarchy = create_hierarchical_structure(relations, root_concept)

        # Generate HTML visualization
        generate_html_visualization(hierarchy, output_path)

        return output_path

    def _generate_network_map(self, title: str, category: str, entities: List[Dict],
                              relations: List[Dict], timestamp: str) -> str:
        """Generate network concept map using NetworkX."""
        # Create a NetworkX graph
        G = nx.DiGraph()

        # Add nodes with attributes based on entity properties
        for entity in entities[:30]:  # Limit to top 30 for clarity
            G.add_node(entity["id"],
                       weight=entity["frequency"],
                       layer=entity["layer"])

        # Add edges from relations
        for rel in relations:
            if G.has_node(rel["source"]) and G.has_node(rel["target"]):
                G.add_edge(rel["source"], rel["target"], relation=rel["relation_type"])

        # Create figure for visualization
        fig, ax = plt.subplots(figsize=(12, 8))

        # Use spring layout for network visualization
        pos = nx.spring_layout(G)

        # Draw the graph with different node colors based on layer
        colors = {
            "priority": "lightcoral",
            "secondary": "lightblue",
            "tertiary": "lightgreen"
        }

        node_colors = [colors.get(G.nodes[node].get('layer', 'tertiary'), 'lightgray') for node in G.nodes()]

        # Size nodes by frequency
        node_sizes = [G.nodes[node].get('weight', 1) * 100 + 300 for node in G.nodes()]

        nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=node_sizes,
                font_size=8, font_weight="bold", ax=ax, arrows=True)

        # Draw edge labels
        edge_labels = {(u, v): d['relation'] for u, v, d in G.edges(data=True)}
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=6)

        # Set plot title
        plt.title(f"Network Concept Map: {title}")

        # Save figure
        output_path = os.path.join(self.output_dir, f"network_{title}_{timestamp}.png")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        return output_path

    def _generate_cyclic_map(self, title: str, category: str, entities: List[Dict],
                             relations: List[Dict], timestamp: str) -> str:
        """Generate cyclic concept map focusing on cycles in the network."""
        # Create a NetworkX graph
        G = nx.DiGraph()

        # Add nodes with attributes based on entity properties
        for entity in entities[:30]:  # Limit to top 30 for clarity
            G.add_node(entity["id"],
                       weight=entity["frequency"],
                       layer=entity["layer"])

        # Add edges from relations
        for rel in relations:
            if G.has_node(rel["source"]) and G.has_node(rel["target"]):
                G.add_edge(rel["source"], rel["target"], relation=rel["relation_type"])

        # Create figure for visualization
        fig, ax = plt.subplots(figsize=(12, 8))

        # Try to find cycles
        try:
            cycles = list(nx.simple_cycles(G))
            if cycles:
                # Use kamada_kawai_layout for better cycle visualization
                pos = nx.kamada_kawai_layout(G)

                # Highlight cycle edges
                cycle_edges = set()
                for cycle in cycles:
                    for i in range(len(cycle)):
                        cycle_edges.add((cycle[i], cycle[(i + 1) % len(cycle)]))
            else:
                # Fallback to spring layout
                pos = nx.spring_layout(G)
                cycle_edges = set()
        except:
            pos = nx.spring_layout(G)
            cycle_edges = set()

        # Colors based on layer
        colors = {
            "priority": "lightcoral",
            "secondary": "lightblue",
            "tertiary": "lightgreen"
        }

        node_colors = [colors.get(G.nodes[node].get('layer', 'tertiary'), 'lightgray') for node in G.nodes()]

        # Size nodes by frequency
        node_sizes = [G.nodes[node].get('weight', 1) * 100 + 300 for node in G.nodes()]

        # Draw regular edges
        regular_edges = [(u, v) for u, v in G.edges() if (u, v) not in cycle_edges]
        nx.draw_networkx_edges(G, pos, edgelist=regular_edges, arrows=True, edge_color='gray')

        # Draw cycle edges with different color if any
        if cycle_edges:
            nx.draw_networkx_edges(G, pos, edgelist=cycle_edges, arrows=True,
                                   edge_color='red', width=2.0)

        # Draw nodes
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes)

        # Draw labels
        nx.draw_networkx_labels(G, pos, font_size=8, font_weight="bold")

        # Draw edge labels
        edge_labels = {(u, v): d['relation'] for u, v, d in G.edges(data=True)}
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=6)

        # Set plot title
        plt.title(f"Cyclic Concept Map: {title}")

        # Save figure
        output_path = os.path.join(self.output_dir, f"cyclic_{title}_{timestamp}.png")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        return output_path

    # Method to get the generated graph for direct use in Streamlit
    def get_graph_for_streamlit(self, title: str, entities: List[Dict],
                                relations: List[Dict], map_type: str):
        """
        Generate a graph that can be directly displayed in Streamlit.
        Returns the graph object and matplotlib figure instead of saving to file.
        """
        map_type = map_type.lower()

        # Create a NetworkX graph
        G = nx.DiGraph()

        # Add nodes with attributes based on entity properties
        for entity in entities[:30]:  # Limit to top 30 for clarity
            G.add_node(entity["id"],
                       weight=entity["frequency"],
                       layer=entity["layer"])

        # Add edges from relations
        for rel in relations:
            if G.has_node(rel["source"]) and G.has_node(rel["target"]):
                G.add_edge(rel["source"], rel["target"], relation=rel["relation_type"])

        # Create figure for visualization
        fig, ax = plt.subplots(figsize=(12, 8))

        # Use appropriate layout based on map type
        if map_type == "hierarchical":
            # For hierarchical, we'll use a specialized tree layout if possible
            try:
                pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
            except:
                pos = nx.spring_layout(G)
        elif map_type == "cyclic":
            # For cyclic, try to highlight cycles
            try:
                cycles = list(nx.simple_cycles(G))
                if cycles:
                    pos = nx.kamada_kawai_layout(G)

                    # Highlight cycle edges
                    cycle_edges = set()
                    for cycle in cycles:
                        for i in range(len(cycle)):
                            cycle_edges.add((cycle[i], cycle[(i + 1) % len(cycle)]))

                    # Draw regular edges
                    regular_edges = [(u, v) for u, v in G.edges() if (u, v) not in cycle_edges]
                    nx.draw_networkx_edges(G, pos, edgelist=regular_edges, arrows=True, edge_color='gray')

                    # Draw cycle edges with different color
                    nx.draw_networkx_edges(G, pos, edgelist=cycle_edges, arrows=True,
                                           edge_color='red', width=2.0)
                else:
                    pos = nx.spring_layout(G)
                    nx.draw_networkx_edges(G, pos, arrows=True)
            except:
                pos = nx.spring_layout(G)
                nx.draw_networkx_edges(G, pos, arrows=True)
        else:
            # Default to spring layout for network
            pos = nx.spring_layout(G)
            nx.draw_networkx_edges(G, pos, arrows=True)

        # Colors based on layer
        colors = {
            "priority": "lightcoral",
            "secondary": "lightblue",
            "tertiary": "lightgreen"
        }

        node_colors = [colors.get(G.nodes[node].get('layer', 'tertiary'), 'lightgray') for node in G.nodes()]

        # Size nodes by frequency
        node_sizes = [G.nodes[node].get('weight', 1) * 100 + 300 for node in G.nodes()]

        # Draw nodes if not already drawn
        if map_type != "cyclic" or not any(cycles):
            nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=node_sizes,
                    font_size=8, font_weight="bold", ax=ax, arrows=True)
        else:
            # Draw nodes and labels separately for cyclic (since edges are already drawn)
            nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes)
            nx.draw_networkx_labels(G, pos, font_size=8, font_weight="bold")

        # Draw edge labels if not too many edges
        if len(G.edges()) <= 50:
            edge_labels = {(u, v): d['relation'] for u, v, d in G.edges(data=True)}
            nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=6)

        # Set plot title
        plt.title(f"{map_type.capitalize()} Concept Map: {title}")

        return G, fig


def process_article(url: str, api_key: str, processing_mode: str = "section",
                    map_type: str = "hierarchical", root_concept: str = None,
                    output_dir: str = "output") -> Dict:
    """
    Process a Wikipedia article and generate concept maps.
    Main entry point for the module.

    Args:
        url: Wikipedia article URL
        api_key: OpenAI API key
        processing_mode: 'section' or 'paragraph' mode for extraction
        map_type: 'hierarchical', 'network', or 'cyclic'
        root_concept: Optional root concept for hierarchical maps
        output_dir: Directory to save output files

    Returns:
        Dictionary with results and file paths
    """
    processor = ConceptMapProcessor(api_key=api_key, output_dir=output_dir)
    return processor.process_article(url, processing_mode, map_type, root_concept)


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    # Load environment variables from .env file
    load_dotenv()

    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI API key not found. Please set OPENAI_API_KEY environment variable.")

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Process Wikipedia article and generate concept maps.')
    parser.add_argument('url', help='Wikipedia article URL')
    parser.add_argument('--mode', choices=['section', 'paragraph'], default='section',
                        help='Processing mode (section or paragraph)')
    parser.add_argument('--map-type', choices=['hierarchical', 'network', 'cyclic'], default='hierarchical',
                        help='Type of concept map to generate')
    parser.add_argument('--root', help='Root concept for hierarchical map')
    parser.add_argument('--output-dir', default='output', help='Output directory for files')

    args = parser.parse_args()

    # Process the article
    result = process_article(
        url=args.url,
        api_key=api_key,
        processing_mode=args.mode,
        map_type=args.map_type,
        root_concept=args.root,
        output_dir=args.output_dir
    )

    # Print results
    print("\nProcessing complete!")
    print(f"Title: {result['title']}")
    print(f"Category: {result['category']}")
    print(f"Entities extracted: {result['total_entities']}")
    print(f"Relations extracted: {result['total_relations']}")
    print(f"Map type: {result['map_type']}")
    print(f"Output files:")
    print(f"  - Entity file: {result['entity_file']}")
    print(f"  - Relation file: {result['relation_file']}")
    print(f"  - Map file: {result['map_file']}")