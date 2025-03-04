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

        # Generate HTML for the D3 visualization
        html_content = self._generate_html(title, formatted_entities, formatted_relations)

        # Calculate entity degree (for information purposes)
        entity_degrees = self._calculate_entity_degrees(formatted_entities, formatted_relations)

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
                st.info("Click on nodes with red outlines to expand hidden connections")

        with col2:
            # Reset button
            if st.button("Reset View", key="network_reset"):
                st.session_state.network_expanded_nodes = []
                st.rerun()

        # Make sure expanded nodes are included in the HTML
        updated_html = self._inject_expanded_nodes(
            map_data["html_content"],
            st.session_state.network_expanded_nodes
        )

        # Display using Streamlit component
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

        Args:
            entities: Entities from extracted_data

        Returns:
            Formatted entities for D3 visualization
        """
        formatted_entities = []

        for entity in entities:
            # Extract key attributes
            entity_id = entity.get("id", "")
            frequency = entity.get("frequency", 0)
            section_count = entity.get("section_count", 0)
            layer = entity.get("layer", "tertiary")

            # Calculate initial degree (estimate)
            degree = len(entity.get("variants", [])) + section_count

            # Build snippet from appearance contexts
            snippet = ""
            appearances = entity.get("appearances", [])
            if appearances and len(appearances) > 0:
                # Use the first appearance context as snippet
                snippet = appearances[0].get("context", "")

            # Format for network map
            formatted_entity = {
                "id": entity_id,
                "name": entity_id,
                "frequency": frequency,
                "degree": degree,
                "layer": layer,
                "snippet": snippet
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
            <meta http-equiv="cache-control" content="no-cache, no-store, must-revalidate">
            <meta http-equiv="pragma" content="no-cache">
            <meta http-equiv="expires" content="0">
            <script src="https://d3js.org/d3.v7.min.js"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    overflow: hidden;
                }}
                .node {{
                    cursor: pointer;
                }}
                .node circle {{
                    stroke-width: 2px;
                    transition: all 0.3s ease;
                }}
                .node--priority circle {{
                    stroke: #004d00;
                }}
                .node--secondary circle {{
                    stroke: #267326;
                }}
                .node--tertiary circle {{
                    stroke: #4db84d;
                }}
                .hidden-connections-highlight {{
                    stroke: #FF0000 !important;
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
                    stroke: #ccc;
                    stroke-width: 1.5px;
                    cursor: pointer;
                    transition: stroke 0.3s ease;
                }}
                .link:hover {{
                    stroke: #666;
                    stroke-width: 2.5px;
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
                    background-color: #006400;
                    border: 1.5px solid #004d00;
                }}
                .secondary-color {{
                    background-color: #339933;
                    border: 1.5px solid #267326;
                }}
                .tertiary-color {{
                    background-color: #66c266;
                    border: 1.5px solid #4db84d;
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
                    <div style="width:15px; height:15px; margin-right:8px; border:1.5px solid #FF0000; border-radius:50%; background-color: rgba(255, 0, 0, 0.3);" class="pulse-{unique_id}"></div>
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
                const width = 800;
                const height = 600;
                const centerX = width / 2;
                const centerY = height / 2;

                // Color scheme - shades of green from lightest to darkest
                const colorScheme = [
                    "#e6f5e6", "#ccebcc", "#99d699", "#66c266", "#4db84d", "#339933", "#267326", "#194d19", "#006400"
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
                            baseIntensity = 8; // Darkest shade
                            break;
                        case 'secondary':
                            baseIntensity = 5; // Medium shade
                            break;
                        case 'tertiary':
                        default:
                            baseIntensity = 2; // Lightest shade
                    }}

                    const score = calculateImportanceScore(node);
                    const intensityVariation = Math.min(Math.floor(score * 2), 1);
                    const colorIndex = Math.min(Math.max(baseIntensity - intensityVariation, 0), colorScheme.length - 1);

                    return colorScheme[colorIndex];
                }}

                // Function to get visible data based on expanded nodes
                function getVisibleData() {{
                    // Priority nodes are always visible
                    const visibleNodeIds = new Set(
                        networkData.nodes
                            .filter(node => node.layer === "priority" || expandedNodes.has(node.id))
                            .map(node => node.id)
                    );

                    // Find all nodes connected to expanded nodes
                    expandedNodes.forEach(expandedId => {{
                        networkData.links.forEach(link => {{
                            const sourceId = String(link.source);
                            const targetId = String(link.target);

                            if (sourceId === expandedId && !visibleNodeIds.has(targetId)) {{
                                visibleNodeIds.add(targetId);
                            }}
                            if (targetId === expandedId && !visibleNodeIds.has(sourceId)) {{
                                visibleNodeIds.add(sourceId);
                            }}
                        }});
                    }});

                    // Get visible nodes
                    const visibleNodes = networkData.nodes.filter(node => 
                        visibleNodeIds.has(node.id)
                    );

                    // Get visible links
                    const visibleLinks = networkData.links.filter(link => {{
                        const sourceId = String(link.source);
                        const targetId = String(link.target);
                        return visibleNodeIds.has(sourceId) && visibleNodeIds.has(targetId);
                    }});

                    return {{ nodes: visibleNodes, links: visibleLinks }};
                }}

                // Function to find nodes with hidden connections
                function getNodesWithHiddenConnections() {{
                    const visibleData = getVisibleData();
                    const visibleNodeIds = new Set(visibleData.nodes.map(n => n.id));
                    const allConnections = new Map();
                    
                    // Initialize map with all nodes
                    networkData.nodes.forEach(node => {{
                        allConnections.set(node.id, []);
                    }});
                    
                    // Add all connections
                    networkData.links.forEach(link => {{
                        const sourceId = String(link.source);
                        const targetId = String(link.target);
                        
                        if (allConnections.has(sourceId)) {{
                            allConnections.get(sourceId).push(targetId);
                        }}
                        
                        if (allConnections.has(targetId)) {{
                            allConnections.get(targetId).push(sourceId);
                        }}
                    }});
                    
                    // Find nodes with hidden connections
                    const nodesWithHidden = new Set();
                    
                    visibleNodeIds.forEach(nodeId => {{
                        const connections = allConnections.get(nodeId) || [];
                        if (connections.some(connId => !visibleNodeIds.has(connId))) {{
                            nodesWithHidden.add(nodeId);
                        }}
                    }});
                    
                    return nodesWithHidden;
                }}

                // Function to assign initial positions in concentric circles
                function assignInitialPositions(nodes, centralNodeId) {{
                    // Group nodes by layer
                    const layerGroups = {{"priority": [], "secondary": [], "tertiary": []}};

                    nodes.forEach(node => {{
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
                    const nodesWithHidden = getNodesWithHiddenConnections();

                    // Find central node
                    const centralNode = findCentralNode(nodes);

                    // Clear previous elements
                    g.selectAll("*").remove();

                    // Create a node ID lookup for the simulation
                    const nodeById = new Map(nodes.map(node => [node.id, node]));

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
                                // Adjust distance based on layer
                                const source = typeof d.source === 'object' ? d.source : nodeById.get(String(d.source));
                                const target = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));

                                if (!source || !target) return 100;

                                // Shorter links for priority connections
                                if (source.layer === "priority" && target.layer === "priority") return 80;
                                if (source.layer === "priority" || target.layer === "priority") return 100;

                                return 150;
                            }}))
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
                        }}));

                    // Create links with hover effects
                    const link = g.selectAll(".link")
                        .data(links)
                        .join("line")
                        .attr("class", "link")
                        .attr("stroke", "#999")
                        .attr("stroke-opacity", 0.6)
                        .attr("stroke-width", function(d) {{
                            const sourceNode = nodes.find(n => n.id === String(d.source));
                            const targetNode = nodes.find(n => n.id === String(d.target));
                            return (sourceNode?.layer === "priority" && targetNode?.layer === "priority") ? 3 : 1.5;
                        }})
                        .on("mouseover", function(event, d) {{
                            // Highlight the line on hover
                            d3.select(this)
                                .attr("stroke", "#333")
                                .attr("stroke-width", 3);

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
                                .attr("stroke", "#999")
                                .attr("stroke-width", function(d) {{
                                    const sourceNode = nodes.find(n => n.id === String(d.source));
                                    const targetNode = nodes.find(n => n.id === String(d.target));
                                    return (sourceNode?.layer === "priority" && targetNode?.layer === "priority") ? 3 : 1.5;
                                }});

                            // Hide the evidence tooltip
                            evidenceTooltip.style("display", "none");
                        }});

                    // Create link labels (only for important links)
                    const linkText = g.selectAll(".link-label")
                        .data(links.filter(d => {{
                            const sourceNode = nodes.find(n => n.id === String(d.source));
                            const targetNode = nodes.find(n => n.id === String(d.target));
                            return (sourceNode?.layer === "priority" && targetNode?.layer === "priority") || 
                                   (sourceNode?.isCenter || targetNode?.isCenter);
                        }}))
                        .join("text")
                        .attr("class", "link-label")
                        .attr("dy", -5)
                        .attr("text-anchor", "middle")
                        .text(d => d.type || "");

                    // Create node groups
                    const node = g.selectAll(".node")
                        .data(nodes)
                        .join("g")
                        .attr("class", function(d) {{
                            return "node node--" + (d.layer || "tertiary") + 
                                   (expandedNodes.has(d.id) ? " node--expanded" : "") +
                                   (d.isCenter ? " center-node" : "");
                        }})
                        .on("click", function(event, d) {{
                            event.stopPropagation();

                            if (expandedNodes.has(d.id)) {{
                                expandedNodes.delete(d.id);
                            }} else {{
                                expandedNodes.add(d.id);
                            }}

                            updateVisualization();
                            sendMessageToStreamlit(Array.from(expandedNodes));
                        }})
                        .on("mouseover", function(event, d) {{
                            // Show basic node info on hover (without the snippet)
                            tooltip
                                .style("display", "block")
                                .style("left", (event.pageX + 10) + "px")
                                .style("top", (event.pageY - 10) + "px")
                                .html("<strong>" + (d.name || d.id) + "</strong><br>" +
                                      "<em>Level: " + (d.layer || "unknown") + "</em><br>" +
                                      "<em>Frequency: " + (d.frequency || 0) + "</em><br>" +
                                      "<em>Connections: " + (d.degree || 0) + "</em>");
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
                        .attr("stroke", "#FFFFFF");  // White stroke by default

                    // Apply RED highlight to nodes with hidden connections
                    nodeCircles.filter(function(d) {{ return nodesWithHidden.has(d.id); }})
                        .classed("hidden-connections-highlight", true);

                    // Add pulse animation to nodes with hidden connections
                    node.filter(function(d) {{ return nodesWithHidden.has(d.id); }})
                        .append("circle")
                        .attr("r", function(d) {{ return getNodeSize(d); }})
                        .attr("fill", "none")
                        .attr("stroke", "#FF0000")  // RED pulse animation
                        .attr("stroke-width", 2)
                        .attr("opacity", 0.5)
                        .attr("class", "pulse-{unique_id}");

                    // Add text labels to nodes
                    node.append("text")
                        .attr("dy", function(d) {{ return getNodeSize(d) + 10; }})
                        .attr("text-anchor", "middle")
                        .attr("font-size", function(d) {{ 
                            if (d.isCenter) return "14px";
                            return d.layer === "priority" ? "12px" : "10px"; 
                        }})
                        .attr("font-weight", function(d) {{ 
                            if (d.isCenter) return "bold";
                            return d.layer === "priority" ? "bold" : "normal"; 
                        }})
                        .attr("fill", "#000000")  // Black text for better contrast
                        .text(function(d) {{ 
                            const name = d.name || d.id;
                            return name.length > 20 ? name.substring(0, 18) + "..." : name;
                        }});

                    // Add visual indicator for central node
                    node.filter(d => d.isCenter)
                        .append("circle")
                        .attr("r", function(d) {{ return getNodeSize(d) + 5; }})
                        .attr("fill", "none")
                        .attr("stroke", "#000000")
                        .attr("stroke-width", 1.5)
                        .attr("opacity", 0.5);

                    // Update simulation
                    simulation.alpha(1).restart(); // Full restart for better layout

                    simulation.on("tick", function() {{
                        // Keep central node fixed
                        nodes.forEach(d => {{
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

                        link
                            .attr("x1", function(d) {{ 
                                const source = typeof d.source === 'object' ? d.source : nodeById.get(String(d.source));
                                return source ? source.x : 0; 
                            }})
                            .attr("y1", function(d) {{ 
                                const source = typeof d.source === 'object' ? d.source : nodeById.get(String(d.source));
                                return source ? source.y : 0; 
                            }})
                            .attr("x2", function(d) {{ 
                                const target = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));
                                return target ? target.x : 0; 
                            }})
                            .attr("y2", function(d) {{ 
                                const target = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));
                                return target ? target.y : 0; 
                            }});

                        linkText
                            .attr("x", function(d) {{ 
                                const source = typeof d.source === 'object' ? d.source : nodeById.get(String(d.source));
                                const target = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));
                                return (source && target) ? (source.x + target.x) / 2 : 0; 
                            }})
                            .attr("y", function(d) {{ 
                                const source = typeof d.source === 'object' ? d.source : nodeById.get(String(d.source));
                                const target = typeof d.target === 'object' ? d.target : nodeById.get(String(d.target));
                                return (source && target) ? (source.y + target.y) / 2 : 0;  
                            }});
                        
                        node.attr("transform", function(d) {{
                            return "translate(" + d.x + "," + d.y + ")";
                        }});
                    }}); 
                    
                    // Drag functions
                    function dragstarted(event, d) {{
                        if (d.isCenter) return; // Don't allow dragging center node
                        if (!event.active) simulation.alphaTarget(0.3).restart();
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
                        d.fx = null;
                        d.fy = null;
                    }}
                }}
                
                // Button click handlers
                d3.select("#reset-btn").on("click", function() {{
                    expandedNodes.clear();
                    updateVisualization();
                    sendMessageToStreamlit([]);
                }});
                
                d3.select("#expand-all-btn").on("click", function() {{
                    // Expand all nodes with hidden connections
                    const nodesWithHidden = getNodesWithHiddenConnections();
                    nodesWithHidden.forEach(function(nodeId) {{
                        expandedNodes.add(nodeId);
                    }});
                    updateVisualization();
                    sendMessageToStreamlit(Array.from(expandedNodes));
                }});
                
                d3.select("#recenter-btn").on("click", function() {{
                    // Reset zoom and center the view
                    svg.transition().duration(750).call(
                        zoom.transform,
                        d3.zoomIdentity.translate(0, 0).scale(1)
                    );
                }});
                
                // Function to communicate with Streamlit
                function sendMessageToStreamlit(expandedNodes) {{
                    // Send message to Streamlit component
                    if (window.Streamlit) {{
                        const message = {{
                            expandedNodes: expandedNodes
                        }};
                        window.Streamlit.setComponentValue(message);
                    }}
                }}
                
                // Initial visualization
                updateVisualization();
            }});
            </script>
        </body>
        </html>
        """
        return html
