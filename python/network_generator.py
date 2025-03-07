"""
Network Concept Map Generator

Implements a D3.js-based network concept map for visualizing concepts and their relationships
with progressive disclosure functionality. Aligns with the existing Streamlit-Cognitext app structure.
"""

import os
import json
import time

import streamlit as st
import streamlit.components.v1 as components
from typing import List, Dict, Any, Optional, Set

class NetworkConceptMapGenerator:
    """
    Generator for network concept maps that show interconnected concepts
    with progressive disclosure of connections.
    """

    def __init__(self, api_key: str = None, output_dir: str = "output"):
        """
        Initialize the NetworkConceptMapGenerator.

        Args:
            api_key: Optional API key (for consistency with other generators)
            output_dir: Directory for output files
        """
        self.api_key = api_key
        self.output_dir = output_dir

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

    def generate_network_map(
            self,
            title: str,
            entities: List[Dict],
            relations: List[Dict],
            detail_level: str = "detailed"
    ) -> Dict:
        """
        Generate a network concept map based on entities and relations.

        Args:
            title: Title for the concept map
            entities: List of entity objects
            relations: List of relation objects
            detail_level: Level of detail to show (summary, intermediate, detailed)

        Returns:
            Dictionary with map data and HTML content
        """
        # Format entities and relations for the network map
        formatted_entities = self._format_entities(entities)
        formatted_relations = self._format_relations(relations)

        # Apply detail level filtering
        if detail_level == "summary":
            # Keep only priority concepts and their direct connections
            formatted_entities, formatted_relations = self._filter_for_summary(
                formatted_entities, formatted_relations
            )
        elif detail_level == "intermediate":
            # Keep priority and secondary concepts
            formatted_entities, formatted_relations = self._filter_for_intermediate(
                formatted_entities, formatted_relations
            )

        entity_degrees = self._calculate_entity_degrees(formatted_entities, formatted_relations)
        for entity in formatted_entities:
            entity_id = entity.get("id", "")
            if entity_id in entity_degrees:
                # Make sure the degree is set in the entity
                entity["degree"] = entity_degrees[entity_id]

        # Generate HTML for the D3 visualization
        html_content = self._generate_html(title, formatted_entities, formatted_relations)

        # Prepare result
        timestamp = title.replace(" ", "_").lower() + "_" + detail_level

        result = {
            "title": title,
            "map_type": "network",
            "detail_level": detail_level,
            "entities": formatted_entities,
            "relations": formatted_relations,
            "entity_degrees": entity_degrees,
            "html_content": html_content,
            "timestamp": timestamp
        }

        return result

    def display_network_map(self, map_data: Dict, height: int = 700) -> Dict:
        """
        Display the network concept map in a Streamlit app.

        Args:
            map_data: Map data dictionary from generate_network_map
            height: Height of the map in pixels

        Returns:
            Component value with expanded nodes information
        """
        # Set up session state for tracking expanded nodes if not exists
        if "network_expanded_nodes" not in st.session_state:
            st.session_state.network_expanded_nodes = []

        # Show control panel
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"### {map_data['title']}")

            # Show expanded nodes information if any
            if st.session_state.network_expanded_nodes:
                expanded_text = ", ".join(st.session_state.network_expanded_nodes[:3])
                if len(st.session_state.network_expanded_nodes) > 3:
                    expanded_text += f" (+{len(st.session_state.network_expanded_nodes) - 3} more)"
                st.info(f"Expanded concepts: {expanded_text}")
            else:
                st.info("Click on nodes with coral outlines to expand hidden connections")

        with col2:
            # Reset button
            if st.button("Reset View", key="network_reset"):
                st.session_state.network_expanded_nodes = []
                st.rerun()

        updated_html = self._inject_expanded_nodes(
            map_data["html_content"],
            st.session_state.network_expanded_nodes
        )

        # Use our custom HTML component instead of the standard one
        component_value = components.html(
            updated_html,
            height=height,
            scrolling=True
        )

        # Update expanded nodes based on component value
        if component_value and isinstance(component_value, dict) and "expandedNodes" in component_value:
            st.session_state.network_expanded_nodes = component_value["expandedNodes"]
            st.rerun()

        return component_value

    def _inject_expanded_nodes(self, html: str, expanded_nodes: List[str]) -> str:
        """
        Inject expanded nodes into the HTML.

        Args:
            html: Original HTML content
            expanded_nodes: List of expanded node IDs

        Returns:
            Updated HTML with expanded nodes injected
        """
        # Convert expanded nodes to JSON
        expanded_json = json.dumps(expanded_nodes)

        # Replace the placeholder in the HTML
        updated_html = html.replace('"expandedNodes": []', f'"expandedNodes": {expanded_json}')

        return updated_html

    def _format_entities(self, entities: List[Dict]) -> List[Dict]:
        """
        Format entities for the network map visualization.
        """
        formatted_entities = []

        for entity in entities:
            # Extract key attributes
            entity_id = entity.get("id", "")
            frequency = entity.get("frequency", 0)
            section_count = entity.get("section_count", 0)
            layer = entity.get("layer", "tertiary")

            evidence = ""
            if entity.get("appearances"):
                for appearance in entity.get("appearances"):
                    # First try evidence field
                    if "evidence" in appearance and appearance["evidence"]:
                        evidence = appearance["evidence"]
                        break

                # If no evidence found, fall back to context
                if not evidence:
                    for appearance in entity.get("appearances"):
                        if "context" in appearance and appearance["context"]:
                            evidence = appearance["context"]
                            break

            formatted_entity = {
                "id": entity_id,
                "name": entity_id,
                "frequency": frequency,
                "degree": 0,
                "layer": layer,
                "evidence": evidence
            }

            formatted_entities.append(formatted_entity)

        return formatted_entities

    def _format_relations(self, relations: List[Dict]) -> List[Dict]:
        """
        Format relations for the network map visualization.

        Args:
            relations: Relations from extracted_data

        Returns:
            Formatted relations for D3 visualization
        """
        formatted_relations = []

        for relation in relations:
            # Extract key attributes
            source = relation.get("source", "")
            target = relation.get("target", "")
            relation_type = relation.get("type", "")
            evidence = relation.get("evidence", "")

            # Only add if source and target are non-empty
            if source and target:
                # Format for network map
                formatted_relation = {
                    "source": source,
                    "target": target,
                    "type": relation_type, # Using 'type' for D3 compatibility
                    "evidence": evidence
                }

                formatted_relations.append(formatted_relation)

        return formatted_relations

    def _calculate_entity_degrees(self, entities: List[Dict], relations: List[Dict]) -> Dict[str, int]:
        """
        Calculate actual degrees (number of connections) for each entity.

        Args:
            entities: Formatted entity objects
            relations: Formatted relation objects

        Returns:
            Dictionary mapping entity IDs to degree counts
        """
        degrees = {}

        # Initialize degrees for all entities
        for entity in entities:
            entity_id = entity.get("id", "")
            degrees[entity_id] = 0

        # Count connections in relations
        for relation in relations:
            source = relation.get("source", "")
            target = relation.get("target", "")

            if source in degrees:
                degrees[source] += 1

            if target in degrees:
                degrees[target] += 1

        # Update entity objects with accurate degrees
        for entity in entities:
            entity_id = entity.get("id", "")
            if entity_id in degrees:
                entity["degree"] = degrees[entity_id]

        return degrees

    def _filter_for_summary(self, entities: List[Dict], relations: List[Dict]) -> tuple:
        """
        Filter entities and relations for summary view.

        Args:
            entities: Formatted entity objects
            relations: Formatted relation objects

        Returns:
            Tuple of (filtered_entities, filtered_relations)
        """
        # Keep only priority entities
        priority_entities = [e for e in entities if e.get("layer") == "priority"]
        priority_ids = {e.get("id") for e in priority_entities}

        # Keep relations between priority entities
        filtered_relations = [
            r for r in relations
            if r.get("source") in priority_ids and r.get("target") in priority_ids
        ]

        return priority_entities, filtered_relations

    def _filter_for_intermediate(self, entities: List[Dict], relations: List[Dict]) -> tuple:
        """
        Filter entities and relations for intermediate view.

        Args:
            entities: Formatted entity objects
            relations: Formatted relation objects

        Returns:
            Tuple of (filtered_entities, filtered_relations)
        """
        # Keep priority and secondary entities
        filtered_entities = [
            e for e in entities
            if e.get("layer") in ("priority", "secondary")
        ]
        filtered_ids = {e.get("id") for e in filtered_entities}

        # Keep relations between these entities
        filtered_relations = [
            r for r in relations
            if r.get("source") in filtered_ids and r.get("target") in filtered_ids
        ]

        return filtered_entities, filtered_relations

    def _generate_html(self, title: str, entities: List[Dict], relations: List[Dict]) -> str:
        """
        Generate HTML with D3.js visualization for the network concept map.
        """
        # Create the initial data dictionary with properly formatted links
        formatted_links = []
        for relation in relations:
            formatted_links.append({
                "source": relation.get("source"),
                "target": relation.get("target"),
                "type": relation.get("type", ""),
                "evidence": relation.get("evidence", "")  # Make sure this is correct
            })

        data_dict = {
            "nodes": entities,
            "links": formatted_links,
            "expandedNodes": []
        }

        # Convert to JSON for embedding
        data_json = json.dumps(data_dict)

        # Generate unique ID for this visualization to avoid caching issues
        unique_id = int(time.time() * 1000)

        # HTML template with D3 visualization
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{title}</title>
            <script src="https://d3js.org/d3.v7.min.js"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    overflow: hidden;
                }}
                .explanation-panel {{
                    position: absolute;
                    padding: 15px;
                    background: white;
                    border: 1px solid #ccc;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                    max-width: 300px;
                    z-index: 1000;
                    font-size: 14px;
                    line-height: 1.4;
                    opacity: 0;
                    transition: opacity 0.3s;
                    pointer-events: auto;
                }}
                
                .explanation-panel.visible {{
                    opacity: 1;
                }}
                
                .explanation-title {{
                    margin-top: 0;
                    margin-bottom: 10px;
                    color: #2196F3;
                    font-size: 16px;
                    font-weight: bold;
                }}
                
                .explanation-content {{
                    margin-bottom: 10px;
                }}
                
                .explanation-footer {{
                    display: block;
                    margin-top: 8px;
                    font-style: italic;
                    color: #666;
                    font-size: 12px;
                }}
                
                .close-explanation {{
                    position: absolute;
                    top: 5px;
                    right: 5px;
                    background: none;
                    border: none;
                    font-size: 16px;
                    cursor: pointer;
                    color: #666;
                }}
                .node {{
                    cursor: pointer;
                }}
                .node circle {{
                    stroke-width: 2px;
                    transition: all 0.3s ease;
                }}
                .node.has-explanation circle {{
                    stroke-dasharray: 3, 3;
                }}
                .node--pinned circle {{
                    stroke-width: 3px;
                    stroke-dasharray: none;
                    stroke: #f06292;
                }}
                .node--priority circle {{
                    stroke: #7E57C2;
                }}
                .node--secondary circle {{
                    stroke: #6596B5;
                }}
                .node--tertiary circle {{
                    stroke: #8FC2B9;
                }}
                .hidden-connections-highlight {{
                    stroke: #FF8A65 !important;
                    stroke-width: 3px !important;
                }}
                .node--expanded circle {{
                    stroke-width: 3px;
                }}
                .node text {{
                    font: 12px sans-serif;
                    pointer-events: none;
                }}
                .link {{
                    fill: none;
                    stroke-width: 1.5px;
                    cursor: pointer;
                    transition: stroke 0.3s ease;
                }}
                .link:hover {{
                    stroke-width: 2.5px;
                    stroke-opacity: 0.9 !important;
                }}
                .link-label {{
                    font-size: 10px;
                    fill: #666;
                    pointer-events: none;
                }}
                .tooltip {{
                    position: absolute;
                    padding: 8px;
                    background: rgba(255, 255, 255, 0.95);
                    color: #333;
                    border-radius: 4px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                    pointer-events: none;
                    font-size: 12px;
                    max-width: 300px;
                    z-index: 1000;
                    border: 1px solid #ddd;
                }}
                .evidence-tooltip {{
                    max-width: 350px;
                    line-height: 1.4;
                }}
                .tooltip .right-click-instruction {{
                    display: block;
                    margin-top: 5px;
                    font-style: italic;
                    color: #2196F3;
                }}
                .legend {{
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    background: rgba(255, 255, 255, 0.8);
                    border-radius: 4px;
                    padding: 8px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                }}
                .legend-item {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 5px;
                }}
                .legend-color {{
                    width: 15px;
                    height: 15px;
                    border-radius: 50%;
                    margin-right: 8px;
                }}
                .priority-color {{
                    background-color: #9575CD;
                    border: 1.5px solid #7E57C2;
                }}
                .secondary-color {{
                    background-color: #97C0DB;
                    border: 1.5px solid #6596B5;
                }}
                .tertiary-color {{
                    background-color: #D1EDE8;
                    border: 1.5px solid #ABD9D1;
                }}
                @keyframes pulse-{unique_id} {{
                    0% {{ transform: scale(1); opacity: 0.5; }}
                    50% {{ transform: scale(1.2); opacity: 0.2; }}
                    100% {{ transform: scale(1); opacity: 0.5; }}
                }}
                .pulse-{unique_id} {{
                    animation: pulse-{unique_id} 2s infinite;
                }}
                .controls {{
                    position: absolute;
                    top: 10px;
                    left: 10px;
                    display: flex;
                    gap: 10px;
                }}
                button {{
                    background-color: white;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    padding: 5px 10px;
                    cursor: pointer;
                    font-size: 12px;
                }}
                button:hover {{
                    background-color: #f0f0f0;
                }}
                .center-node circle {{
                    stroke-width: 3px;
                }}
                .highlight {{
                    font-weight: bold;
                    color: #006400;
                }}
            </style>
        </head>
        <body>
            <div class="controls">
                <button id="reset-btn">Reset</button>
                <button id="expand-all-btn">Expand All</button>
                <button id="recenter-btn">Recenter</button>
                <button id="unpin-btn">Unpin All</button>
            </div>
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color priority-color"></div>
                    <span>Priority Concepts</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color secondary-color"></div>
                    <span>Secondary Concepts</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color tertiary-color"></div>
                    <span>Tertiary Concepts</span>
                </div>
                <div class="legend-item">
                    <div style="width:15px; height:15px; margin-right:8px; border:1.5px solid #FF8A65; border-radius:50%; background-color: rgba(255, 0, 0, 0.3);" class="pulse-{unique_id}"></div>
                    <span>Has Hidden Connections</span>
                </div>
            </div>

            <svg id="concept-map" width="800" height="600"></svg>
            <div id="tooltip" class="tooltip" style="display: none;"></div>
            <div id="evidence-tooltip" class="tooltip evidence-tooltip" style="display: none;"></div>

            <script>
            // Load the data
            const networkData = {data_json};

            document.addEventListener('DOMContentLoaded', function() {{
                // Set up variables
                let expandedNodes = new Set(networkData.expandedNodes || []);
                let pinnedNodes = new Set(); // Track pinned/fixed nodes
                const width = 800;
                const height = 600;
                const centerX = width / 2;
                const centerY = height / 2;

                // Color scheme - shades of green from lightest to darkest
                const colorScheme = [
                    "#D1EDE8", "#ABD9D1", "#97C0DB", "#6596B5", "#9C82DE", "#9575CD"
                ];

                // Set up SVG and tooltips
                const svg = d3.select("#concept-map");
                const tooltip = d3.select("#tooltip");
                const evidenceTooltip = d3.select("#evidence-tooltip");

                // Create a group for zooming
                const g = svg.append("g");

                // Set up zoom behavior
                const zoom = d3.zoom()
                    .scaleExtent([0.5, 5])
                    .on("zoom", function(event) {{
                        g.attr("transform", event.transform);
                    }});

                svg.call(zoom);

                // Ensure nodes have string IDs and links reference those IDs
                networkData.nodes.forEach(node => {{
                    node.id = String(node.id);
                }});

                networkData.links.forEach(link => {{
                    link.source = String(link.source);
                    link.target = String(link.target);
                }});

                // Validate links - only keep links where both source and target nodes exist
                const validNodeIds = new Set(networkData.nodes.map(node => node.id));
                networkData.links = networkData.links.filter(link => 
                    validNodeIds.has(link.source) && validNodeIds.has(link.target)
                );

                // Function to highlight terms in evidence text
                function highlightTermsInEvidence(evidence, source, target, relation) {{
                    if (!evidence) return "No evidence available";
                    
                    try {{
                        // Simple HTML display without attempting to highlight terms
                        return evidence;
                    }} catch(e) {{
                        console.error("Error in evidence:", e);
                        return "No evidence available";
                    }}
                }}

                // Function to calculate importance score
                function calculateImportanceScore(node) {{
                    const frequencyWeight = 0.6;
                    const maxFrequency = Math.max(...networkData.nodes.map(n => n.frequency || 0), 1);
                    const maxDegree = Math.max(...networkData.nodes.map(n => n.degree || 0), 1);
                    const normalizedFrequency = (node.frequency || 0) / maxFrequency;
                    const normalizedDegree = (node.degree || 0) / maxDegree;
                    return (normalizedFrequency * frequencyWeight) + (normalizedDegree * (1 - frequencyWeight));
                }}

                // Find the most important concept to place at the center
                function findCentralNode(nodes) {{
                    return nodes.reduce((max, node) => {{
                        const score = calculateImportanceScore(node);
                        return (score > calculateImportanceScore(max)) ? node : max;
                    }}, nodes[0]);
                }}

                // Function to get node size based on importance
                function getNodeSize(node) {{
                    const score = calculateImportanceScore(node);
                    return 10 + (score * 30);  // Min 10, max 40
                }}

                // Function to get node color based on layer
                function getNodeColor(node) {{
                    let baseIntensity;
                    switch(node.layer) {{
                        case 'priority':
                            baseIntensity = 5; // Darkest shade
                            break;
                        case 'secondary':
                            baseIntensity = 2; // Medium shade
                            break;
                        case 'tertiary':
                        default:
                            baseIntensity = 0; // Lightest shade
                    }}

                    const score = calculateImportanceScore(node);
                    const intensityVariation = Math.min(Math.floor(score * 2), 1);
                    const colorIndex = Math.min(Math.max(baseIntensity - intensityVariation, 0), colorScheme.length - 1);

                    return colorScheme[colorIndex];
                }}

                // Function to get visible data based on expanded nodes
                function getVisibleData() {{
                    console.log("Getting visible data with expanded nodes:", Array.from(expandedNodes));
                    
                    // Priority nodes are always visible
                    const visibleNodeIds = new Set(
                        networkData.nodes
                            .filter(node => node.layer === "priority" || expandedNodes.has(node.id))
                            .map(node => node.id)
                    );
                    
                    console.log(`Initial visible nodes (priority + expanded): ${{visibleNodeIds.size}}`);
                    
                    // Keep track of how many nodes we add in this expansion pass
                    let nodesAdded = 0;
                    
                    // Find all nodes connected to expanded nodes
                    expandedNodes.forEach(expandedId => {{
                        networkData.links.forEach(link => {{
                            let sourceId, targetId;
                            
                            // Handle both string and object formats
                            if (typeof link.source === 'object') {{
                                sourceId = link.source.id;
                            }} else {{
                                sourceId = String(link.source);
                            }}
                            
                            if (typeof link.target === 'object') {{
                                targetId = link.target.id;
                            }} else {{
                                targetId = String(link.target);
                            }}
                            
                            if (sourceId === expandedId && !visibleNodeIds.has(targetId)) {{
                                visibleNodeIds.add(targetId);
                                nodesAdded++;
                            }}
                            
                            if (targetId === expandedId && !visibleNodeIds.has(sourceId)) {{
                                visibleNodeIds.add(sourceId);
                                nodesAdded++;
                            }}
                        }});
                    }});
                    
                    console.log(`Added ${{nodesAdded}} connected nodes to visible set`);
                    console.log(`Total visible nodes: ${{visibleNodeIds.size}}`);
                    
                    // Get visible nodes
                    const visibleNodes = networkData.nodes.filter(node => 
                        visibleNodeIds.has(node.id)
                    );
                    
                    // Get visible links
                    const visibleLinks = networkData.links.filter(link => {{
                        let sourceId, targetId;
                        
                        // Handle both string and object formats
                        if (typeof link.source === 'object') {{
                            sourceId = link.source.id;
                        }} else {{
                            sourceId = String(link.source);
                        }}
                        
                        if (typeof link.target === 'object') {{
                            targetId = link.target.id;
                        }} else {{
                            targetId = String(link.target);
                        }}
                        
                        return visibleNodeIds.has(sourceId) && visibleNodeIds.has(targetId);
                    }});
                    
                    console.log(`Visible nodes: ${{visibleNodes.length}}, Visible links: ${{visibleLinks.length}}`);
                    
                    return {{ nodes: visibleNodes, links: visibleLinks }};
                }}

                // Function to find nodes with hidden connections
                function getAllNodesWithHiddenConnections() {{
                    // Get all nodes
                    const allNodeIds = new Set(networkData.nodes.map(n => n.id));
                    
                    // Get currently visible nodes
                    const visibleData = getVisibleData();
                    const visibleNodeIds = new Set(visibleData.nodes.map(n => n.id));
                    
                    // Build a map of all connections
                    const allConnections = new Map();
                    
                    // Initialize map with all nodes
                    allNodeIds.forEach(nodeId => {{
                        allConnections.set(nodeId, []);
                    }});
                    
                    // Add all connections
                    networkData.links.forEach(link => {{
                        const sourceId = typeof link.source === 'object' ? link.source.id : String(link.source);
                        const targetId = typeof link.target === 'object' ? link.target.id : String(link.target);
                        
                        if (allConnections.has(sourceId)) {{
                            allConnections.get(sourceId).push(targetId);
                        }}
                        
                        if (allConnections.has(targetId)) {{
                            allConnections.get(targetId).push(sourceId);
                        }}
                    }});
                    
                    // Find all nodes that have hidden connections
                    const nodesWithHidden = new Set();
                    
                    // Check each visible node
                    visibleNodeIds.forEach(nodeId => {{
                        const connections = allConnections.get(nodeId) || [];

                        // If any connection is to a non-visible node, this node has hidden connections
                        if (connections.some(connId => !visibleNodeIds.has(connId))) {{
                            nodesWithHidden.add(nodeId);
                        }}
                    }});

                    // Print debug info
                    console.log(`Found ${{nodesWithHidden.size}} nodes with hidden connections`);
                    console.log("Nodes with hidden connections:", Array.from(nodesWithHidden));

                    return nodesWithHidden;
                }}

                // Function to assign initial positions in concentric circles
                function assignInitialPositions(nodes, centralNodeId) {{
                    // Group nodes by layer
                    const layerGroups = {{"priority": [], "secondary": [], "tertiary": []}};

                    nodes.forEach(node => {{
                        if (pinnedNodes.has(node.id)) {{
                            console.log("Preserving position for pinned node:", node.id);
                            // Make sure fx and fy are set from existing position
                            node.fx = node.x;
                            node.fy = node.y;
                            return; // Skip the rest of the positioning for this node
                        }}
                        
                        if (node.id === centralNodeId) {{
                            // Central node stays at center
                            node.x = centerX;
                            node.y = centerY;
                            node.fx = centerX; // Fix position
                            node.fy = centerY; // Fix position
                            node.isCenter = true;
                        }} else {{
                            // Group other nodes by layer
                            const layer = node.layer || "tertiary";
                            layerGroups[layer].push(node);
                            // Clear any fixed positions
                            node.fx = null;
                            node.fy = null;
                            node.isCenter = false;
                        }}
                    }});

                    // Assign positions in concentric circles by layer
                    // Priority nodes closest to center
                    positionNodesInCircle(layerGroups["priority"], 120);
                    positionNodesInCircle(layerGroups["secondary"], 240);
                    positionNodesInCircle(layerGroups["tertiary"], 360);
                }}

                // Helper function to position nodes in a circle
                function positionNodesInCircle(nodes, radius) {{
                    const angleStep = (2 * Math.PI) / Math.max(nodes.length, 1);

                    nodes.forEach((node, i) => {{
                        const angle = i * angleStep;
                        node.x = centerX + radius * Math.cos(angle);
                        node.y = centerY + radius * Math.sin(angle);
                    }});
                }}


                // Function to update the visualization
                function updateVisualization() {{
                    // Get current data
                    const {{ nodes, links }} = getVisibleData();
                    const nodesWithHidden = getAllNodesWithHiddenConnections();

                    // Find central node
                    const centralNode = findCentralNode(nodes);

                    // Clear previous elements
                    g.selectAll("*").remove();

                    // Create a node ID lookup for the simulation
                    const nodeById = new Map(nodes.map(node => [node.id, node]));
                    
                    nodes.forEach(node => {{
                        if (pinnedNodes.has(node.id)) {{
                            // If this node is pinned, ensure it has fixed coordinates
                            const pinnedNode = nodeById.get(node.id);
                            if (pinnedNode) {{
                                node.fx = pinnedNode.x || node.x;
                                node.fy = pinnedNode.y || node.y;
                            }}
                        }}
                    }});

                    // Assign initial positions
                    assignInitialPositions(nodes, centralNode.id);

                    // Set up the simulation with proper node references and forces
                     const simulation = d3.forceSimulation(nodes)
                        .force("link", d3.forceLink()
                            .id(d => d.id)
                            .links(links.map(link => ({{
                                source: nodeById.get(String(link.source)) || String(link.source),
                                target: nodeById.get(String(link.target)) || String(link.target),
                                type: link.type,
                                evidence: link.evidence
                            }})))
                            .distance(d => {{
                                // Adjust distance based on layer and node size
                                const source = typeof d.source === 'object' ? d.source : nodeById.get(String(d.source));
                                const target = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));
                        
                                if (!source || !target) return 120;
                        
                                // Get sizes of source and target nodes
                                const sourceSize = getNodeSize(source);
                                const targetSize = getNodeSize(target);
                                
                                // Base distance on node sizes + a minimum distance
                                const baseDistance = sourceSize + targetSize + 30;
                                
                                // Layer-based adjustments
                                if (source.layer === "priority" && target.layer === "priority") {{
                                    // Priority-to-priority connections are slightly closer
                                    return baseDistance * 1.2;
                                }} else if (source.layer === "priority" || target.layer === "priority") {{
                                    // Priority-to-other connections at medium distance
                                    return baseDistance * 1.5;
                                }}
                                
                                // Other connections have more space
                                return baseDistance * 2.0;
                            }})
                            .strength(0.3))
                        .force("charge", d3.forceManyBody().strength(d => {{
                            // Stronger repulsion for larger nodes
                            return d.isCenter ? -500 : -300;
                        }}))
                        .force("center", d3.forceCenter(centerX, centerY))
                        .force("collide", d3.forceCollide().radius(d => getNodeSize(d) + 10))
                        .force("x", d3.forceX(centerX).strength(d => {{
                            // Layer-based strength to keep priority nodes closer to center
                            if (d.isCenter) return 1.0;
                            if (d.layer === "priority") return 0.1;
                            if (d.layer === "secondary") return 0.05;
                            return 0.01;
                        }}))
                        .force("y", d3.forceY(centerY).strength(d => {{
                            // Layer-based strength to keep priority nodes closer to center
                            if (d.isCenter) return 1.0;
                            if (d.layer === "priority") return 0.1;
                            if (d.layer === "secondary") return 0.05;
                            return 0.01;
                        }}))
                        .force("link-repulsion", d3.forceManyBody()
                            .strength(-10)
                            .distanceMax(150)
                            .distanceMin(25))
                        .alphaDecay(0.02);

                    // Create links with hover effects
                    const link = g.selectAll(".link")
                        .data(links)
                        .join("path")
                        .attr("class", "link")
                        .attr("stroke", function(d) {{
                            // Get the target node
                            const target = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));
                            
                            if (!target) return "#BDBDBD"; // Default gray
                            
                            // Color based on target's layer
                            switch(target.layer) {{
                                case "priority":
                                    return "#B39DDB"; // Purple for priority
                                case "secondary":
                                    return "#90CAF9"; // Blue for secondary
                                case "tertiary":
                                    return "#B2DFDB"; // Light blue/green for tertiary
                                default:
                                    return "#BDBDBD"; // Default gray
                            }}
                        }})
                        .attr("stroke-opacity", 0.6)
                        .attr("stroke-width", function(d) {{
                            const sourceNode = nodes.find(n => n.id === String(d.source));
                            const targetNode = nodes.find(n => n.id === String(d.target));
                            return (sourceNode?.layer === "priority" && targetNode?.layer === "priority") ? 3 : 1.5;
                        }})
                        .attr("fill", "none")
                        .on("mouseover", function(event, d) {{
                            // Highlight the line on hover
                            const currentColor = d3.select(this).attr("stroke");
                            d3.select(this)
                                .attr("stroke-opacity", 1)
                                .attr("stroke-width", function() {{
                                    return parseFloat(d3.select(this).attr("stroke-width")) + 1;
                                }})
                                .attr("stroke", function() {{
                                    // Darken the current color for hover effect
                                    const target = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));
                                    
                                    if (!target) return "#999";
                                    
                                    switch(target.layer) {{
                                        case "priority":
                                            return "#9575CD"; // Slightly darker purple
                                        case "secondary":
                                            return "#64B5F6"; // Slightly darker blue
                                        case "tertiary":
                                            return "#80CBC4"; // Slightly darker teal
                                        default:
                                            return "#999"; // Darker gray
                                    }}
                                }});

                            // Get source and target node objects
                            const sourceNode = typeof d.source === 'object' ? d.source : nodeById.get(String(d.source));
                            const targetNode = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));

                            if (sourceNode && targetNode) {{
                                // Prepare evidence with highlighted terms
                                const evidence = d.evidence || "";
                                const highlightedEvidence = highlightTermsInEvidence(
                                    evidence, 
                                    sourceNode.name || sourceNode.id,
                                    targetNode.name || targetNode.id,
                                    d.type
                                );

                        // Show the evidence tooltip
                        // When showing the evidence tooltip, just display the evidence as plain text
                        evidenceTooltip
                            .style("display", "block")
                            .style("left", (event.pageX + 10) + "px")
                            .style("top", (event.pageY - 10) + "px")
                            .html(`
                                <strong>${{sourceNode.name || sourceNode.id}}</strong>
                                <span style="margin: 0 5px;">→</span>
                                <strong>${{d.type || "relates to"}}</strong>
                                <span style="margin: 0 5px;">→</span>
                                <strong>${{targetNode.name || targetNode.id}}</strong>
                                <hr style="margin: 8px 0;">
                                <div>${{d.evidence || "No evidence available"}}</div>
                            `);
                            }}
                        }})
                        .on("mouseout", function() {{
                            // Restore original line style                            
                            d3.select(this)
                                    .attr("stroke-opacity", 0.6)
                                    .attr("stroke-width", function(d) {{
                                        const target = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));
                                        
                                        if (target && target.layer === "priority") return 2;
                                        if (target && target.layer === "secondary") return 1.8;
                                        return 1.5;
                                    }})
                                    .attr("stroke", function(d) {{
                                        // Restore original color
                                        const target = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));
                                        
                                        if (!target) return "#BDBDBD";
                                        
                                        switch(target.layer) {{
                                            case "priority":
                                                return "#B39DDB"; // Light purple
                                            case "secondary":
                                                return "#90CAF9"; // Light blue
                                            case "tertiary":
                                                return "#B2DFDB"; // Light teal
                                            default:
                                                return "#BDBDBD";
                                        }}
                                    }});

                            // Hide the evidence tooltip
                            evidenceTooltip.style("display", "none");
                        }});

                    // Create node groups
                    const node = g.selectAll(".node")
                        .data(nodes)
                        .join("g")
                        .attr("class", function(d) {{
                            return "node node--" + (d.layer || "tertiary") + 
                                   (expandedNodes.has(d.id) ? " node--expanded" : "") +
                                   (d.isCenter ? " center-node" : "");
                        }});
                    
                    node
                        // Left-click for expanding/collapsing hidden connections
                        .on("click", function(event, d) {{
                            event.stopPropagation();
                        
                            // Only toggle expansion if the node has hidden connections
                            if (nodesWithHidden.has(d.id)) {{
                                // Store current positions of all nodes before expanding
                                const nodePositions = new Map();
                                nodes.forEach(node => {{
                                    nodePositions.set(node.id, {{x: node.x, y: node.y}});
                                }});
                        
                                // Toggle expansion state
                                if (expandedNodes.has(d.id)) {{
                                    expandedNodes.delete(d.id);
                                    pinnedNodes.delete(d.id);
                                    d.fx = null;
                                    d.fy = null;
                                    d3.select(this).classed("node--pinned", false);
                                }} else {{
                                    expandedNodes.add(d.id);
                                    pinnedNodes.add(d.id);
                                    d.fx = d.x;
                                    d.fy = d.y;
                                    console.log("Pinned node at position:", d.x, d.y);
                                    // Add visual indicator
                                    d3.select(this).classed("node--pinned", true);
                                }}
                    
                                // Update visualization
                                updateVisualization();
                        
                                // We need to wait for the nodes to be created in the DOM
                                setTimeout(() => {{
                                    console.log("Checking pinned nodes after update");
                                    g.selectAll(".node").each(function(node) {{
                                        if (pinnedNodes.has(node.id)) {{
                                            console.log("Should be pinned:", node.id, "fx:", node.fx, "fy:", node.fy);
                                        }}
                                    }});
                                }}, 500);
                        
                                sendMessageToStreamlit({{
                                    expandedNodes: Array.from(expandedNodes)
                                }});
                            }}
                        }})
                        // Right-click (contextmenu) for concept explanation
                        .on("contextmenu", function(event, d) {{
                            // Prevent the default context menu
                            event.preventDefault();
                            
                            // Get the evidence for this concept
                            const nodeData = networkData.nodes.find(n => n.id === d.id);
                            const evidence = nodeData.evidence || "No explanation available for this concept.";
                                                        
                            // Create or update the explanation panel
                            if (!d3.select("#explanation-panel").size()) {{
                                d3.select("body").append("div")
                                    .attr("id", "explanation-panel")
                                    .style("position", "absolute")
                                    .style("padding", "15px")
                                    .style("background", "white")
                                    .style("border", "1px solid #ccc")
                                    .style("border-radius", "8px")
                                    .style("box-shadow", "0 2px 10px rgba(0,0,0,0.2)")
                                    .style("max-width", "300px")
                                    .style("z-index", "1000")
                                    .style("font-size", "14px")
                                    .style("line-height", "1.4");
                                    
                                // Add close button
                                d3.select("#explanation-panel")
                                    .append("button")
                                    .attr("class", "close-explanation")
                                    .style("position", "absolute")
                                    .style("top", "5px")
                                    .style("right", "5px")
                                    .style("background", "none")
                                    .style("border", "none")
                                    .style("font-size", "16px")
                                    .style("cursor", "pointer")
                                    .style("color", "#666")
                                    .html("&times;")
                                    .on("click", function() {{
                                        d3.select("#explanation-panel").style("display", "none");
                                    }});
                            }}
                            
                            // Update and position the explanation panel
                            d3.select("#explanation-panel")
                                .style("display", "block")
                                .style("left", (event.pageX + 10) + "px")
                                .style("top", (event.pageY - 10) + "px")
                                .html(`
                                    <button class="close-explanation" style="position:absolute;top:5px;right:5px;background:none;border:none;font-size:16px;cursor:pointer;color:#666;">&times;</button>
                                    <div style="margin-top: 5px;">
                                        <h3 style="margin-top:0;margin-bottom:10px;color:#2196F3;">${{d.name || d.id}}</h3>
                                        <p>${{evidence}}</p>
                                        <span style="display:block;margin-top:8px;font-style:italic;color:#666;font-size:12px;">Layer: ${{d.layer || "unknown"}}</span>
                                    </div>
                                `);
                                
                            // Handle close button click
                            d3.select(".close-explanation").on("click", function() {{
                                d3.select("#explanation-panel").style("display", "none");
                            }});
                                
                            // Visual feedback for right-click
                            d3.select(this).select("circle")
                                .transition()
                                .duration(200)
                                .attr("r", function(d) {{ return getNodeSize(d) * 1.2; }})
                                .transition()
                                .duration(200)
                                .attr("r", function(d) {{ return getNodeSize(d); }});
                        }})
                        .on("mouseover", function(event, d) {{
                            // Show basic node info on hover with updated instructions
                            tooltip
                                .style("display", "block")
                                .style("left", (event.pageX + 10) + "px")
                                .style("top", (event.pageY - 10) + "px")
                                .html("<strong>" + (d.name || d.id) + "</strong><br>" +
                                      "<em>Level: " + (d.layer || "unknown") + "</em><br>" +
                                      "<em>Frequency: " + (d.frequency || 0) + "</em><br>" +
                                      "<em>Connections: " + (d.degree || 0) + "</em>" +
                                      (nodesWithHidden.has(d.id)
                                          ? "<br><span style='color:#FF8A65'><em>Click to expand connections" + 
                                            (pinnedNodes.has(d.id) ? " (pinned)" : "") + "</em></span>"
                                          : "") +
                                      "<br><span style='color:#2196F3'><em>Right-click for explanation</em></span>");
                        }})
                        .on("mouseout", function() {{
                            tooltip.style("display", "none");
                        }})
                        .call(d3.drag()
                            .on("start", dragstarted)
                            .on("drag", dragged)
                            .on("end", dragended));

                    // Add circles to nodes with filled colors
                    const nodeCircles = node.append("circle")
                        .attr("r", function(d) {{ return getNodeSize(d); }})
                        .attr("fill", function(d) {{ return getNodeColor(d); }})  // Use color for fill
                        .attr("stroke", "#7E57C2");  // White stroke by default

                    // Apply RED highlight to nodes with hidden connections
                    nodeCircles.filter(function(d) {{ return nodesWithHidden.has(d.id); }})
                        .classed("hidden-connections-highlight", true);

                    // Add pulse animation to nodes with hidden connections
                    node.filter(function(d) {{ return nodesWithHidden.has(d.id); }})
                        .append("circle")
                        .attr("r", function(d) {{ return getNodeSize(d); }})
                        .attr("fill", "none")
                        .attr("stroke", "#FF8A65")  // soft coral pulse animation
                        .attr("stroke-width", 2)
                        .attr("opacity", 0.5)
                        .attr("class", "pulse-{{unique_id}}");

                    // Add text labels to nodes
                    node.append("text")
                        .attr("class", "node-label")
                        .attr("text-anchor", "middle")
                        .attr("font-size", function(d) {{ 
                            if (d.isCenter) return "14px";
                            return d.layer === "priority" ? "12px" : "10px"; 
                        }})
                        .attr("font-weight", function(d) {{ 
                            if (d.isCenter) return "bold";
                            return d.layer === "priority" ? "bold" : "normal";
                        }})
                        .attr("fill", "#000000")
                        .attr("opacity", function(d) {{
                            // Show all labels for priority nodes, but fewer labels for other layers
                            return d.layer === "priority" ? 1 : 0.7;
                        }})
                        .text(function(d) {{
                            return d.name || d.id;
                        }})
                        .each(function(d) {{
                            // Get label width to improve positioning
                            const bbox = this.getBBox();
                            d.labelWidth = bbox.width;
                            d.labelHeight = bbox.height;
                        }});
                    
                    simulation.force("label-collision", d3.forceCollide().radius(function(d) {{
                        return getNodeSize(d) + (d.labelWidth ? (d.labelWidth / 2) + 5 : 15);
                    }}).strength(0.5));

                    // Add visual indicator for central node
                    node.filter(d => d.isCenter)
                        .append("circle")
                        .attr("r", function(d) {{ return getNodeSize(d) + 5; }})
                        .attr("fill", "none")
                        .attr("stroke", "#5D32A8")
                        .attr("stroke-width", 1.5)
                        .attr("opacity", 0.5);

                    // Update simulation
                    simulation.alpha(1).restart(); // Full restart for better layout
                    
                    node.isPinned = true;

                    simulation.on("tick", function() {{
                        nodes.forEach(d => {{
                            if (pinnedNodes.has(d.id) || d.isPinned) {{
                                if (d.fx !== null && d.fy !== null) {{
                                    d.x = d.fx;
                                    d.y = d.fy;
                                }}
                            }}
                            
                            if (pinnedNodes.has(d.id) && (d.fx === null || d.fy === null)) {{
                                console.warn("Pinned node lost its fixed position:", d.id);
                            }}
                            
                            if (d.isCenter) {{
                                d.x = centerX;
                                d.y = centerY;
                            }}

                            // Apply gentle force to keep nodes in their layer rings
                            if (!d.isCenter) {{
                                // Calculate distance from center
                                const dx = d.x - centerX;
                                const dy = d.y - centerY;
                                const distance = Math.sqrt(dx * dx + dy * dy);

                                // Target radius based on layer
                                let targetRadius;
                                if (d.layer === "priority") targetRadius = 120;
                                else if (d.layer === "secondary") targetRadius = 240;
                                else targetRadius = 360; // tertiary

                                // Strength of the force (adjust as needed)
                                const strength = 0.05;

                                if (distance > 0) {{
                                    // Push/pull toward the target radius
                                    const factor = 1 - (targetRadius / distance);
                                    d.x -= dx * factor * strength;
                                    d.y -= dy * factor * strength;
                                }}
                            }}
                        }});

                        link.attr("d", function(d) {{
                            const source = typeof d.source === 'object' ? d.source : nodeById.get(String(d.source));
                            const target = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));
                            
                            if (!source || !target) return "";
                            
                            // Calculate midpoint
                            const midX = (source.x + target.x) / 2;
                            const midY = (source.y + target.y) / 2;
                            
                            // Calculate normal vector for curve control point
                            const dx = target.x - source.x;
                            const dy = target.y - source.y;
                            const normalX = -dy;
                            const normalY = dx;
                            
                            // Normalize and scale for curvature
                            const len = Math.sqrt(normalX * normalX + normalY * normalY);
                            let curvature = 0;
                            
                            // Determine curvature based on link context
                            if (len > 0) {{
                                // Add more curvature for links between nodes that have many connections
                                curvature = 20 + Math.min(source.degree + target.degree, 20);
                                
                                // If this is a bidirectional link, curve it more
                                const isBidirectional = links.some(l => 
                                    (l.source.id === target.id && l.target.id === source.id) ||
                                    (l.source === target.id && l.target === source.id)
                                );
                                if (isBidirectional) curvature = curvature * 1.5;
                            }}
                            
                            const controlX = midX + (normalX / len) * curvature;
                            const controlY = midY + (normalY / len) * curvature;
                            
                            // Quadratic curve path
                            return `M${{source.x}},${{source.y}} Q${{controlX}},${{controlY}} ${{target.x}},${{target.y}}`;
                        }});
                        
                        node.attr("transform", function(d) {{
                            return "translate(" + d.x + "," + d.y + ")";
                        }});
                        
                        node.select("text")
                            .attr("dy", function(d) {{
                                // Position based on node location
                                const distanceFromCenter = Math.sqrt(
                                    Math.pow(d.x - centerX, 2) + Math.pow(d.y - centerY, 2)
                                );
                                const angle = Math.atan2(d.y - centerY, d.x - centerX);
                                
                                // Position label based on angle from center
                                if (angle > -Math.PI/4 && angle < Math.PI/4) {{
                                    // Right side
                                    return "0.35em"; // Center vertically
                                }} else if (angle >= Math.PI/4 && angle < 3*Math.PI/4) {{
                                    // Bottom
                                    return getNodeSize(d) + 15; // Below node
                                }} else if (angle >= 3*Math.PI/4 || angle <= -3*Math.PI/4) {{
                                    // Left side
                                    return "0.35em"; // Center vertically
                                }} else {{
                                    // Top
                                    return -getNodeSize(d) - 5; // Above node
                                }}
                            }})
                            .attr("dx", function(d) {{
                                // Position based on node location
                                const distanceFromCenter = Math.sqrt(
                                    Math.pow(d.x - centerX, 2) + Math.pow(d.y - centerY, 2)
                                );
                                const angle = Math.atan2(d.y - centerY, d.x - centerX);
                                
                                // Position label based on angle from center
                                if (angle > -Math.PI/4 && angle < Math.PI/4) {{
                                    // Right side
                                    return getNodeSize(d) + 5; // To the right
                                }} else if (angle >= Math.PI/4 && angle < 3*Math.PI/4) {{
                                    // Bottom
                                    return 0; // Centered horizontally
                                }} else if (angle >= 3*Math.PI/4 || angle <= -3*Math.PI/4) {{
                                    // Left side
                                    return -getNodeSize(d) - 5; // To the left
                                }} else {{
                                    // Top
                                    return 0; // Centered horizontally
                                }}
                            }})
                            .attr("text-anchor", function(d) {{
                                const angle = Math.atan2(d.y - centerY, d.x - centerX);

                                // Set text anchor based on angle
                                if (angle > -Math.PI/4 && angle < Math.PI/4) {{
                                    return "start"; // Right side
                                }} else if (angle >= Math.PI/4 && angle < 3*Math.PI/4) {{
                                    return "middle"; // Bottom
                                }} else if (angle >= 3*Math.PI/4 || angle <= -3*Math.PI/4) {{
                                    return "end"; // Left side
                                }} else {{
                                    return "middle"; // Top
                                }}
                            }});
                    }}); 
                    
                    // Drag functions
                    function dragstarted(event, d) {{
                        if (d.isCenter) return; // Don't allow dragging center node
                        if (!event.active) simulation.alphaTarget(0.3).restart();
                        // Store original position
                        d._originalX = d.x;
                        d._originalY = d.y;
                        
                        // Always fix position during drag
                        d.fx = d.x;
                        d.fy = d.y;
                    }}
                            
                    function dragged(event, d) {{
                        if (d.isCenter) return; // Don't allow dragging center node
                        d.fx = event.x;
                        d.fy = event.y;
                    }}
                
                    function dragended(event, d) {{
                        if (d.isCenter) return; // Don't allow dragging center node
                        if (!event.active) simulation.alphaTarget(0);
                        // If this node is pinned, keep it fixed at the new position
                        if (pinnedNodes.has(d.id)) {{
                            d.fx = d.x;
                            d.fy = d.y;
                            console.log("Node remains pinned after drag:", d.id, "at", d.x, d.y);
                        }} else {{
                            // Otherwise, release it
                            d.fx = null;
                            d.fy = null;
                        }}
                    }}
                }}
                
                // Button click handlers
                d3.select("#reset-btn").on("click", function() {{
                    expandedNodes.clear();
                    updateVisualization();
                    sendMessageToStreamlit([]);
                }});
                
                d3.select("#expand-all-btn").on("click", function() {{
                    console.log("Expand All button clicked");
                    
                    // First get all nodes with hidden connections
                    const nodesWithHidden = getAllNodesWithHiddenConnections();
                    
                    // Expand them all at once
                    let expansionsAdded = 0;
                    nodesWithHidden.forEach(nodeId => {{
                        if (!expandedNodes.has(nodeId)) {{
                            expandedNodes.add(nodeId);
                            expansionsAdded++;
                        }}
                    }});
                    
                    console.log(`Added ${{expansionsAdded}} nodes to expanded set`);
                    console.log("Expanded nodes:", Array.from(expandedNodes));
                    
                    // Update visualization with the new expanded set
                    updateVisualization();
                    
                    // Try to communicate with Streamlit if available
                    if (window.Streamlit) {{
                        try {{
                            window.Streamlit.setComponentValue({{expandedNodes: Array.from(expandedNodes)}});
                            console.log("Sent expanded nodes to Streamlit");
                        }} catch (e) {{
                            console.error("Error sending to Streamlit:", e);
                        }}
                    }} else {{
                        console.warn("Streamlit object not available");
                    }}
                }});
                
                d3.select("#reset-btn").on("click", function() {{
                    console.log("Reset button clicked");
                    
                    // Clear expanded nodes
                    const previousCount = expandedNodes.size;
                    expandedNodes.clear();
                    
                    console.log(`Cleared ${{previousCount}} expanded nodes`);
                    
                    // Update visualization
                    updateVisualization();
                    
                    // Try to communicate with Streamlit if available
                    if (window.Streamlit) {{
                        try {{
                            window.Streamlit.setComponentValue({{expandedNodes: []}});
                            console.log("Sent empty expanded nodes to Streamlit");
                        }} catch (e) {{
                            console.error("Error sending to Streamlit:", e);
                        }}
                    }} else {{
                        console.warn("Streamlit object not available");
                    }}
                }});
                
                d3.select("#unpin-btn").on("click", function() {{
                    console.log("Unpin All button clicked");
                    
                    // Unpin all nodes
                    pinnedNodes.forEach(nodeId => {{
                        const node = nodes.find(n => n.id === nodeId);
                        if (node && !node.isCenter) {{
                            node.fx = null;
                            node.fy = null;
                        }}
                    }});
                    
                    // Clear pinned nodes set
                    pinnedNodes.clear();
                    
                    // Remove visual indicators
                    g.selectAll(".node--pinned").classed("node--pinned", false);
                    
                    // Run simulation with low alpha to adjust
                    simulation.alpha(0.1).restart();
                }});
                
                // Function to communicate with Streamlit
                function safelySendMessageToStreamlit(message) {{
                    console.log("Attempting to send message to Streamlit:", message);
                    
                    try {{
                        // Check if Streamlit is available
                        if (window.Streamlit) {{
                            window.Streamlit.setComponentValue(message);
                            console.log("Message sent successfully to Streamlit");
                            return true;
                        }} else {{
                            console.warn("Streamlit object not available yet. Will retry in 500ms");
                            
                            // Retry after a short delay
                            setTimeout(() => {{
                                if (window.Streamlit) {{
                                    window.Streamlit.setComponentValue(message);
                                    console.log("Message sent successfully to Streamlit on retry");
                                }} else {{
                                    console.error("Streamlit object still not available after retry");
                                    
                                    // Fall back to direct update if Streamlit communication fails
                                    try {{
                                        expandedNodes = new Set(message.expandedNodes || []);
                                        updateVisualization();
                                        console.log("Applied changes locally since Streamlit communication failed");
                                    }} catch (localError) {{
                                        console.error("Error applying local changes:", localError);
                                    }}
                                }}
                            }}, 500);
                            return false;
                        }}
                    }} catch (error) {{
                        console.error("Error sending message to Streamlit:", error);
                        return false;
                    }}
                }}
                
                function sendMessageToStreamlit(message) {{
                    // Only proceed if we're in a Streamlit context
                    if (window.Streamlit && window.Streamlit.setComponentValue) {{
                        try {{
                            window.Streamlit.setComponentValue(message);
                            console.log("Message sent to Streamlit:", message);
                            return true;
                        }} catch (e) {{
                            console.error("Error sending to Streamlit:", e);
                            // No need to retry - just apply changes locally
                            console.log("Applying changes locally due to error");
                            return false;
                        }}
                    }} else {{
                        console.log("Streamlit API not available, applying changes locally");
                        // No need to worry about it - all changes are already applied locally
                        return false;
                    }}
                }}
                
                svg.on("click", function(event) {{
                    // Ignore if the click was on a node or a control
                    if (event.target.closest(".node") || event.target.closest(".controls")) 
                        return;
                    
                    // Unpin all nodes
                    if (pinnedNodes.size > 0) {{
                        pinnedNodes.forEach(nodeId => {{
                            const node = nodes.find(n => n.id === nodeId);
                            if (node && !node.isCenter) {{
                                node.fx = null;
                                node.fy = null;
                            }}
                        }});
                        
                        // Clear pinned nodes set
                        pinnedNodes.clear();
                        
                        // Remove visual indicators
                        g.selectAll(".node--pinned").classed("node--pinned", false);
                        
                        // Run simulation with low alpha to adjust
                        simulation.alpha(0.1).restart();
                    }}
                }});
                
                // Initial visualization
                updateVisualization();
                
                document.addEventListener('click', function(event) {{
                    // Check if the click is outside the explanation panel and nodes
                    const explanationPanel = document.getElementById('explanation-panel');
                    const isClickOutsidePanel = explanationPanel && 
                                                !explanationPanel.contains(event.target) && 
                                                !event.target.closest('.node');
                    
                    if (isClickOutsidePanel) {{
                        // Hide the explanation panel
                        d3.select("#explanation-panel").style("display", "none");
                    }}
                }});
            }});
            </script>
        </body>
        </html>
        """
        return html
