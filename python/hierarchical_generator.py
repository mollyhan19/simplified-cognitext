#!/usr/bin/env python3
import sys
import json
import argparse
import os
from collections import defaultdict

def create_hierarchical_structure(relations, root_concept=None):
    """Create a hierarchical structure based on relations."""

    # Create a mapping of concepts to their relations
    incoming_relations = defaultdict(list)
    outgoing_relations = defaultdict(list)
    all_concepts = set()
    concept_layers = {}  # Map concepts to their layer (priority, secondary, tertiary)

    for relation in relations:
        source = relation['source'].lower()
        target = relation['target'].lower()
        relation_type = relation['relation_type']

        outgoing_relations[source].append((target, relation_type))
        incoming_relations[target].append((source, relation_type))
        all_concepts.add(source)
        all_concepts.add(target)

        # Record layer if provided
        if 'source_layer' in relation:
            concept_layers[source] = relation['source_layer']
        if 'target_layer' in relation:
            concept_layers[target] = relation['target_layer']

    # If no root concept is provided, find the most connected concept
    if not root_concept:
        concept_connections = {}
        for concept in all_concepts:
            concept_connections[concept] = len(outgoing_relations[concept]) + len(incoming_relations[concept])

        # Find the concept with most connections
        root_concept = max(concept_connections.items(), key=lambda x: x[1])[0]
        print(f"No root concept provided. Using most connected concept: {root_concept}")
    else:
        root_concept = root_concept.lower()
        if root_concept not in all_concepts:
            # Fall back to most connected concept if specified root doesn't exist
            concept_connections = {}
            for concept in all_concepts:
                concept_connections[concept] = len(outgoing_relations[concept]) + len(incoming_relations[concept])

            # Find the concept with most connections
            root_concept = max(concept_connections.items(), key=lambda x: x[1])[0]
            print(f"Specified root concept not found. Using most connected concept: {root_concept}")

    # Create the hierarchical structure
    hierarchy = {
        "name": root_concept,
        "layer": concept_layers.get(root_concept, "priority"),  # Default to priority for root
        "has_secondary_relations": False,
        "has_tertiary_relations": False,
        "children": []
    }

    # Track which concepts have been added to the hierarchy
    added_concepts = {root_concept}

    # Function to check if a concept has hidden children
    def has_hidden_children(concept):
        has_secondary = False
        has_tertiary = False

        # Check outgoing relations
        for rel_list in [outgoing_relations[concept], incoming_relations[concept]]:
            for related, _ in rel_list:
                if related not in added_concepts:
                    layer = concept_layers.get(related, "tertiary")
                    if layer == "secondary":
                        has_secondary = True
                    elif layer == "tertiary":
                        has_tertiary = True

        return has_secondary, has_tertiary

    # Function to check what kinds of relations a concept has
    def get_relation_types(concept):
        has_secondary = False
        has_tertiary = False

        # Check outgoing relations
        for rel_list in [outgoing_relations[concept], incoming_relations[concept]]:
            for related, _ in rel_list:
                if related not in added_concepts:
                    layer = concept_layers.get(related, "tertiary")
                    if layer == "secondary":
                        has_secondary = True
                    elif layer == "tertiary":
                        has_tertiary = True

        return has_secondary, has_tertiary

    # First, identify concepts directly related to the root
    root_related = []
    for target, rel_type in outgoing_relations[root_concept]:
        root_related.append((target, rel_type, "outgoing"))

    for source, rel_type in incoming_relations[root_concept]:
        root_related.append((source, rel_type, "incoming"))

    # Sort by connection strength (could be refined)
    root_related.sort(key=lambda x: len(outgoing_relations[x[0]]) + len(incoming_relations[x[0]]), reverse=True)

    # Add top-level branches (up to 8)
    for concept, rel_type, direction in root_related[:8]:
        # Include relation type in the node data
        relationship = f"{rel_type}" if direction == "outgoing" else f"REVERSED: {rel_type}"

        # Check what kinds of hidden relations this concept has
        has_secondary, has_tertiary = get_relation_types(concept)

        # Add to hierarchy
        hierarchy["children"].append({
            "name": concept,
            "relation": relationship,
            "layer": concept_layers.get(concept, "secondary"),  # Default to secondary for direct connections
            "has_secondary_relations": has_secondary,
            "has_tertiary_relations": has_tertiary,
            "children": []
        })
        added_concepts.add(concept)

    # Function to recursively add related concepts
    def add_related_concepts(parent_node, parent_concept, depth=0, max_depth=3):
        if depth >= max_depth:
            return

        # Find related concepts not yet in hierarchy
        related = []

        # Add outgoing relations
        for target, rel_type in outgoing_relations[parent_concept]:
            if target not in added_concepts:
                related.append((target, rel_type, "outgoing"))

        # Add incoming relations
        for source, rel_type in incoming_relations[parent_concept]:
            if source not in added_concepts:
                related.append((source, rel_type, "incoming"))

        # Sort by connection strength
        related.sort(key=lambda x: len(outgoing_relations[x[0]]) + len(incoming_relations[x[0]]), reverse=True)

        # Add up to 5 related concepts to this node
        for concept, rel_type, direction in related[:5]:
            # Include relation type in the node data
            relationship = f"{rel_type}" if direction == "outgoing" else f"REVERSED: {rel_type}"

            # Check what kinds of hidden relations this concept has
            has_secondary, has_tertiary = get_relation_types(concept)

            # Create the child node
            child_node = {
                "name": concept,
                "relation": relationship,
                "layer": concept_layers.get(concept, "tertiary"),  # Default to tertiary for deeper levels
                "has_secondary_relations": has_secondary,
                "has_tertiary_relations": has_tertiary,
                "children": []
            }
            parent_node["children"].append(child_node)
            added_concepts.add(concept)

            # Recursively add children to this node
            add_related_concepts(child_node, concept, depth + 1, max_depth)

    # Process each top-level branch
    for branch in hierarchy["children"]:
        add_related_concepts(branch, branch["name"])

    # Count the concepts included
    concept_count = sum(1 for c in added_concepts) - 1
    print(f"Included {concept_count} concepts out of {len(all_concepts) - 1}")

    return hierarchy


def generate_html_visualization(hierarchy, output_file_path):
    """Generate an HTML file with JavaScript for visualizing the hierarchy."""

    # Convert the Python dict to a JSON string for embedding in the HTML
    hierarchy_json = json.dumps(hierarchy, indent=2)

    # Create the HTML content - first part before JSON data
    html_head = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hierarchical Concept Map</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: transparent;
        }

        .node {
            cursor: pointer;
        }

        .node circle {
            fill: #fff;
            stroke: steelblue;
            stroke-width: 1.5px;
            transition: all 0.3s ease;
        }

        .node text {
            font: 12px sans-serif;
        }

        .node--priority circle {
            fill: #e3f2fd;
            stroke: #2196f3;
        }

        .node--secondary circle {
            fill: #f1f8e9;
            stroke: #8bc34a;
        }

        .node--tertiary circle {
            fill: #fff3e0;
            stroke: #ff9800;
        }

        .node--hidden circle {
            animation: pulse 2s infinite;
            stroke: #9c27b0 !important;  /* Purple color for nodes with hidden children */
        }

        @keyframes pulse {
            0% { stroke-width: 1.5px; stroke-opacity: 1; }
            50% { stroke-width: 3px; stroke-opacity: 0.8; }
            100% { stroke-width: 1.5px; stroke-opacity: 1; }
        }

        .link {
            fill: none;
            stroke: #ccc;
            stroke-width: 1.5px;
        }

        #concept-map {
            width: 100%;
            height: 600px;
            overflow: auto;
            background-color: white;
        }

        .tooltip {
            position: absolute;
            padding: 8px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            border-radius: 4px;
            pointer-events: none;
            font-size: 12px;
        }

        .relation-label {
            font-size: 10px;
            fill: #666;
        }

        .controls {
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .filter-option {
            margin-bottom: 8px;
        }

        .legend {
            position: absolute;
            bottom: 10px;
            right: 10px;
            background: white;
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .legend-item {
            display: flex;
            align-items: center;
            margin-bottom: 5px;
        }

        .legend-color {
            width: 15px;
            height: 15px;
            border-radius: 50%;
            margin-right: 8px;
        }

        .priority-color {
            background-color: #e3f2fd;
            border: 1.5px solid #2196f3;
        }

        .secondary-color {
            background-color: #f1f8e9;
            border: 1.5px solid #8bc34a;
        }

        .tertiary-color {
            background-color: #fff3e0;
            border: 1.5px solid #ff9800;
        }

        .pulse-indicator {
            width: 15px;
            height: 15px;
            border-radius: 50%;
            background-color: white;
            border: 1.5px solid #9c27b0;
            animation: pulse 2s infinite;
            margin-right: 8px;
        }
        .edge-tooltip {
            position: absolute;
            padding: 10px;
            background: rgba(255, 255, 255, 0.95);
            color: black;
            border-radius: 4px;
            pointer-events: none;
            font-size: 12px;
            max-width: 300px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            z-index: 1000;
            border: 1px solid #ccc;
        }
        .evidence-panel {
            position: absolute;
            padding: 15px;
            background: white;
            border: 1px solid #ccc;
            border-radius: 4px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            z-index: 1001;
            max-width: 350px;
            max-height: 200px;
            overflow-y: auto;
            font-size: 13px;
            display: none;
        }

        .close-button {
            position: absolute;
            top: 5px;
            right: 5px;
            background: none;
            border: none;
            font-size: 16px;
            cursor: pointer;
            color: #666;
        }

        .link {
            fill: none;
            stroke: #ccc;
            stroke-width: 1.5px;
            cursor: pointer;
        }

        .link:hover {
            stroke: #999;
            stroke-width: 2px;
        }
    </style>
</head>
<body>
    <div id="concept-map"></div>

    <div class="controls">
        <button id="expand-all">Expand All</button>
        <button id="collapse-all">Collapse All</button>
    </div>

    <div class="legend">
        <h4 style="margin-top: 0; margin-bottom: 10px;">Legend</h4>
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
            <div class="pulse-indicator"></div>
            <span>Has Hidden Children</span>
        </div>
    </div>

    <script>
    // Variable to track ID of nodes
    let i = 0;

    // Hierarchy data
    const treeData = """

    # Middle part with JSON data
    html_middle = hierarchy_json

    # Last part with all the JavaScript
    html_tail = """;

    function click(event, d) {
        // Stop event propagation
        event.stopPropagation();
        
        if (d.children) {
            // If the node is expanded, collapse it
            d._children = d.children;
            d.children = null;
        } else if (d._children) {
            // If the node has hidden children, expand it
            d.children = d._children;
            d._children = null;
        }
        
        // Update the visualization
        update(d);
    }


    // Set up the tree diagram
    const margin = {top: 20, right: 120, bottom: 20, left: 120},
          width = 1200 - margin.left - margin.right,
          height = 600 - margin.top - margin.bottom;

    // Create the SVG container
    const svg = d3.select("#concept-map").append("svg")
        .attr("width", width + margin.right + margin.left)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

    // Create a tooltip
    const tooltip = d3.select("body").append("div")
        .attr("class", "tooltip")
        .style("opacity", 0);

    // Create the tree layout
    const treemap = d3.tree().size([height, width]);

    // Assigns parent, children, height, depth
    const root = d3.hierarchy(treeData, d => d.children);
    root.x0 = height / 2;
    root.y0 = 0;

    // Filter settings
    let showPriorityOnly = true;
    let showSecondary = false;
    let showTertiary = false;

    // Handle filter changes
    d3.select("#show-priority-only").on("change", function() {
        showPriorityOnly = this.checked;
        if (showPriorityOnly) {
            d3.select("#show-secondary").property("checked", false);
            d3.select("#show-tertiary").property("checked", false);
            showSecondary = false;
            showTertiary = false;
        }
        update(root);
    });

    d3.select("#show-secondary").on("change", function() {
        showSecondary = this.checked;
        if (showSecondary) {
            d3.select("#show-priority-only").property("checked", false);
            showPriorityOnly = false;
        }
        update(root);
    });

    d3.select("#show-tertiary").on("change", function() {
        showTertiary = this.checked;
        if (showTertiary) {
            d3.select("#show-priority-only").property("checked", false);
            showPriorityOnly = false;
        }
        update(root);
    });

    // Expand all nodes
    d3.select("#expand-all").on("click", function() {
        expandAll(root);
        update(root);
    });

    // Collapse all nodes
    d3.select("#collapse-all").on("click", function() {
        collapseAll(root);
        // Keep the root expanded
        root.children = root._children;
        root._children = null;
        update(root);
    });

    function expandAll(d) {
        if (d._children) {
            d.children = d._children;
            d._children = null;
        }
        if (d.children) d.children.forEach(expandAll);
    }

    function collapseAll(d) {
        if (d.children) {
            d._children = d.children;
            d.children = null;
        }
        if (d._children) d._children.forEach(collapseAll);
    }

    // Recursively process all nodes, filtering based on layer
    function processNodes(node) {
        if (!node) return;
    
        // Flag to track if this node has hidden children
        node.data.hasHiddenChildren = false;
        
        // If this is a priority node, check if it has non-priority connections
        if (node.data.layer === "priority") {
            // Check if this node has children that would be hidden in priority-only mode
            if (node.children) {
                node.children.forEach(child => {
                    if (child.data.layer !== "priority") {
                        node.data.hasHiddenChildren = true;
                    }
                });
            }
            
            // Also check _children (collapsed nodes)
            if (node._children) {
                node._children.forEach(child => {
                    if (child.data.layer !== "priority") {
                        node.data.hasHiddenChildren = true;
                    }
                });
            }
        }
    
        // Process children recursively
        if (node.children) {
            node.children.forEach(processNodes);
        }
    }

    // Expand first level and collapse other levels
    function filterToPriorityOnly(node) {
        if (!node) return;
        
        // First, mark if node has hidden children
        node.data.hasHiddenChildren = false;
        
        // If it's the root, always keep it expanded
        if (!node.parent) {
            if (node._children) {
                node.children = node._children;
                node._children = null;
            }
            
            // For the root's children, keep only priority nodes expanded
            if (node.children) {
                node.children.forEach(child => {
                    // If this is not a priority node, collapse it
                    if (child.data.layer !== "priority") {
                        if (child.children) {
                            child._children = child.children;
                            child.children = null;
                        }
                    }
                    
                    // Mark if the child has non-priority children
                    if (child.children) {
                        child.children.forEach(grandchild => {
                            if (grandchild.data.layer !== "priority") {
                                child.data.hasHiddenChildren = true;
                            }
                        });
                    }
                    
                    if (child._children) {
                        child._children.forEach(grandchild => {
                            if (grandchild.data.layer !== "priority") {
                                child.data.hasHiddenChildren = true;
                            }
                        });
                    }
                    
                    // Recursively process this child
                    filterToPriorityOnly(child);
                });
            }
        } else {
            // For non-root nodes, only keep priority nodes visible
            const isPriority = node.data.layer === "priority";
            
            // If it's not a priority node and it has children, collapse them
            if (!isPriority && node.children) {
                node._children = node.children;
                node.children = null;
            }
            
            // Check if this node has non-priority children that would be hidden
            if (node.children) {
                node.children.forEach(child => {
                    if (child.data.layer !== "priority") {
                        node.data.hasHiddenChildren = true;
                    }
                });
            }
            
            if (node._children) {
                node._children.forEach(child => {
                    if (child.data.layer !== "priority") {
                        node.data.hasHiddenChildren = true;
                    }
                });
            }
            
            // Recursively process children if they exist
            if (node.children) {
                node.children.forEach(filterToPriorityOnly);
            }
        }
    }


    filterToPriorityOnly(root);
    update(root);

    function update(source) {
        // Process nodes according to filter settings
        processNodes(root);

        // Assigns the x and y position for the nodes
        const treeData = treemap(root);

        // Compute the new tree layout
        const nodes = treeData.descendants();
        const links = treeData.descendants().slice(1);

        // Normalize for fixed-depth
        nodes.forEach(d => { d.y = d.depth * 180 });

        // Create the edge tooltip
        const edgeTooltip = d3.select("body").append("div")
            .attr("class", "edge-tooltip")
            .style("opacity", 0);

        // Create the evidence panel
        const evidencePanel = d3.select("body").append("div")
            .attr("class", "evidence-panel")
            .style("display", "none");

        // Add close button to evidence panel
        evidencePanel.append("button")
            .attr("class", "close-button")
            .html("&times;")
            .on("click", function() {
                evidencePanel.style("display", "none");
            });

        // Create the content div in evidence panel
        const evidenceContent = evidencePanel.append("div")
            .attr("class", "evidence-content");

        // ****************** Nodes section ***************************

        // Update the nodes
        const node = svg.selectAll('g.node')
            .data(nodes, d => d.id || (d.id = ++i));

        // Enter any new nodes at the parent's previous position
        const nodeEnter = node.enter().append('g')
            .attr('class', d => {
                const layer = d.data.layer || "tertiary";
                return `node node--${layer}`;
            })
            .attr("transform", d => `translate(${source.y0},${source.x0})`)
            .on('click', click)
            .on('dblclick', function(event, d) {
                // Prevent the click event from firing
                event.stopPropagation();

                // Store the selected concept in localStorage
                localStorage.setItem('selected_concept', d.data.name);
                localStorage.setItem('selected_concept_layer', d.data.layer || "tertiary");

                // Reload the page to trigger Streamlit rerun with new data
                window.parent.location.href = window.parent.location.pathname + '?concept=' + 
                    encodeURIComponent(d.data.name) + '&timestamp=' + new Date().getTime();

                // Visual feedback
                d3.select(this).select('circle')
                    .transition()
                    .duration(200)
                    .attr('r', 10)
                    .transition()
                    .duration(200)
                    .attr('r', 6);
            })
            .on("mouseover", function(event, d) {
                let tooltipContent = `<strong>${d.data.name}</strong><br/>Layer: ${d.data.layer || "unknown"}`;
                
                // Add special message for nodes with hidden children
                if (d.data.hasHiddenChildren) {
                    tooltipContent += `<br/><span style="color:#9c27b0; font-style: italic;">✨ Click to expand hidden connections</span>`;
                }
                
                // Add instructions for nodes that can be expanded
                if (d._children && d._children.length > 0) {
                    tooltipContent += `<br/><span style="color:#2196f3;">+ Click to expand (${d._children.length} connections)</span>`;
                }
                
                // Add instructions for nodes that can be collapsed
                if (d.children && d.children.length > 0) {
                    tooltipContent += `<br/><span style="color:#ff9800;">- Click to collapse (${d.children.length} connections)</span>`;
                }
                
                tooltip.transition()
                    .duration(200)
                    .style("opacity", .9);
                tooltip.html(tooltipContent)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseout", function() {
                tooltip.transition()
                    .duration(500)
                    .style("opacity", 0);
            });

        // Add Circle for the nodes
        nodeEnter.append('circle')
            .attr('r', 1e-6)
            .classed('node--hidden', d => d.data.has_hidden_children)
            .style("fill", d => {
                // Color based on layer
                const layer = d.data.layer || "tertiary";
                if (layer === "priority") return "#e3f2fd";
                if (layer === "secondary") return "#f1f8e9";
                return "#fff3e0"; // tertiary
            })
            .style("stroke", d => {
                // Base stroke color on layer but override if node has hidden children
                if (d.data.has_hidden_children) return "#9c27b0"; // Purple for nodes with hidden children

                const layer = d.data.layer || "tertiary";
                if (layer === "priority") return "#2196f3";
                if (layer === "secondary") return "#8bc34a";
                return "#ff9800"; // tertiary
            });

        // Add labels for the nodes
        nodeEnter.append('text')
            .attr("dy", ".35em")
            .attr("x", d => d.children || d._children ? -13 : 13)
            .attr("text-anchor", d => d.children || d._children ? "end" : "start")
            .text(d => d.data.name.length > 25 ? d.data.name.substring(0, 25) + "..." : d.data.name);

        // UPDATE
        const nodeUpdate = nodeEnter.merge(node);

        nodeUpdate.transition()
            .duration(750)
            .attr("transform", d => `translate(${d.y},${d.x})`);

        function hasHiddenChildren(d) {
            // Check if the node has relations that would be filtered out by current settings
            return (d.data.has_secondary_relations && !showSecondary) || 
                   (d.data.has_tertiary_relations && !showTertiary);
        }

        nodeUpdate.select('circle')
            .attr('r', 6)
            .classed('node--hidden', d => d.data.hasHiddenChildren)
            .style("fill", d => {
                // Color based on layer
                const layer = d.data.layer || "tertiary";
                if (layer === "priority") return "#e3f2fd";
                if (layer === "secondary") return "#f1f8e9";
                return "#fff3e0"; // tertiary
            })
            .style("stroke", d => {
                // Use purple stroke only for priority nodes with hidden children
                if (d.data.hasHiddenChildren) {
                    return "#9c27b0"; // Purple for nodes with hidden children
                }
                
                // Otherwise use layer-based color
                const layer = d.data.layer || "tertiary";
                if (layer === "priority") return "#2196f3";
                if (layer === "secondary") return "#8bc34a";
                return "#ff9800"; // tertiary
            })
            .attr('cursor', 'pointer');

        nodeUpdate.on("mouseover", function(event, d) {
            let tooltipText = `<strong>${d.data.name}</strong><br/>Layer: ${d.data.layer || "unknown"}`;

            // Add info about hidden relations if any
            if (d.data.has_secondary_relations && !showSecondary) {
                tooltipText += "<br/><span style='color:#8bc34a'>Has hidden secondary concepts</span>";
            }
            if (d.data.has_tertiary_relations && !showTertiary) {
                tooltipText += "<br/><span style='color:#ff9800'>Has hidden tertiary concepts</span>";
            }

            tooltip.transition()
                .duration(200)
                .style("opacity", .9);
            tooltip.html(tooltipText)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 28) + "px");
        });

        const nodeExit = node.exit().transition()
            .duration(750)
            .attr("transform", d => `translate(${source.y},${source.x})`)
            .remove();

        // On exit reduce the node circles size to 0
        nodeExit.select('circle')
            .attr('r', 1e-6);

        // On exit reduce the opacity of text labels
        nodeExit.select('text')
            .style('fill-opacity', 1e-6);

        // ****************** links section ***************************

        const link = svg.selectAll('path.link')
            .data(links, d => d.id);

        // Enter any new links at the parent's previous position
        const linkEnter = link.enter().insert('path', "g")
            .attr("class", "link")
            .attr('d', d => {
                const o = {x: source.x0, y: source.y0};
                return diagonal(o, o);
            })
            .on("mouseover", function(event, d) {
                // Show relation type on hover with a more visible tooltip
                const relationText = d.data.relation || "relates to";

                edgeTooltip.transition()
                    .duration(200)
                    .style("opacity", 1);

                // Enhanced tooltip with better styling
                edgeTooltip.html(`
                    <div style="font-weight: bold; margin-bottom: 5px; color: #2196f3;">
                        Relationship:
                    </div>
                    <div style="display: flex; align-items: center; margin-bottom: 5px;">
                        <span style="font-weight: bold;">${d.parent.data.name}</span>
                        <span style="margin: 0 5px;">→</span>
                        <span style="font-style: italic; color: #2196f3;">${relationText}</span>
                        <span style="margin: 0 5px;">→</span>
                        <span style="font-weight: bold;">${d.data.name}</span>
                    </div>
                    <div style="font-size: 10px; color: #666;">Click for evidence</div>
                `)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");

                // Highlight the hovered link
                d3.select(this)
                    .transition()
                    .duration(200)
                    .style("stroke", "#2196f3")
                    .style("stroke-width", "2.5px");
            })
            .on("mouseout", function() {
                edgeTooltip.transition()
                    .duration(500)
                    .style("opacity", 0);

                // Return the link to normal style
                d3.select(this)
                    .transition()
                    .duration(500)
                    .style("stroke", "#ccc")
                    .style("stroke-width", "1.5px");
            });

        // UPDATE
        const linkUpdate = linkEnter.merge(link);

        // Transition back to the parent element position
        linkUpdate.transition()
            .duration(750)
            .attr('d', d => diagonal(d, d.parent));

        // Remove any exiting links
        link.exit().transition()
            .duration(750)
            .attr('d', d => {
                const o = {x: source.x, y: source.y};
                return diagonal(o, o);
            })
            .remove();

        // Store the old positions for transition
        nodes.forEach(d => {
            d.x0 = d.x;
            d.y0 = d.y;
        });

        function diagonal(s, d) {
            return `M ${s.y} ${s.x}
                    C ${(s.y + d.y) / 2} ${s.x},
                      ${(s.y + d.y) / 2} ${d.x},
                      ${d.y} ${d.x}`;
        }

        svg.on("click", function() {
            evidencePanel.style("display", "none");
        });

        // Add a global click handler to close the panel when clicking outside
        d3.select("body").on("click", function(event) {
            if (!event.target.closest(".evidence-panel") && !event.target.closest("path.link")) {
                evidencePanel.style("display", "none");
            }
        });
    }
    </script>
</body>
</html>"""

    # Combine all parts
    html_content = html_head + html_middle + html_tail

    # Save the HTML file
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Hierarchical concept map HTML saved to {output_file_path}")


def preprocess_relations(relations, entities=None):
    """
    Preprocess relations to include concept layer information and evidence.

    Args:
        relations: List of relation dictionaries
        entities: Optional dictionary mapping concept IDs to their layer information

    Returns:
        Enhanced relations list with layer information
    """
    if not entities:
        entities = {}

    enhanced_relations = []

    for relation in relations:
        source = relation['source'].lower()
        target = relation['target'].lower()

        # Create enhanced relation with layer and evidence info
        enhanced_relation = relation.copy()

        # Add source layer if available
        if source in entities:
            enhanced_relation['source_layer'] = entities[source]

        # Add target layer if available
        if target in entities:
            enhanced_relation['target_layer'] = entities[target]

        # Make sure evidence field exists
        if 'evidence' not in enhanced_relation:
            enhanced_relation['evidence'] = ""

        enhanced_relations.append(enhanced_relation)

    return enhanced_relations


def extract_concept_layers(entities_data):
    """
    Extract concept layers from entities data.

    Args:
        entities_data: Dictionary with entity information

    Returns:
        Dictionary mapping concept IDs to their layers
    """
    concept_layers = {}

    # Handle different potential formats of entity data
    # Format 1: Direct list of entities
    if isinstance(entities_data, list):
        for entity in entities_data:
            if 'id' in entity and 'layer' in entity:
                concept_layers[entity['id'].lower()] = entity['layer']

    # Format 2: Nested structure with entities under article key
    elif isinstance(entities_data, dict):
        # Try to find entities list under an article key
        for key, value in entities_data.items():
            if isinstance(value, dict) and 'entities' in value:
                for entity in value['entities']:
                    if 'id' in entity and 'layer' in entity:
                        concept_layers[entity['id'].lower()] = entity['layer']

    return concept_layers


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate hierarchical concept map')
    parser.add_argument('input_file', help='Input JSON file with concept relations')
    parser.add_argument('output_file', help='Output HTML file path')
    parser.add_argument('--root', help='Root concept for the hierarchical map')
    parser.add_argument('--entities', help='Optional JSON file with entity layer information')

    args = parser.parse_args()

    # Load input data
    try:
        with open(args.input_file, 'r') as f:
            data = json.load(f)

        print(f"Loaded input data from {args.input_file}")
    except Exception as e:
        print(f"Error loading input file: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # Load entities data if provided
    concept_layers = {}
    if args.entities:
        try:
            with open(args.entities, 'r') as f:
                entities_data = json.load(f)
            concept_layers = extract_concept_layers(entities_data)
            print(f"Loaded {len(concept_layers)} concept layers from entities file")
        except Exception as e:
            print(f"Warning: Error loading entities file: {str(e)}")

    # Extract domain name and relations
    try:
        # Handle different formats based on data structure
        if 'articles' in data and isinstance(data['articles'], dict):
            # Format with nested 'articles' key
            domain_name = list(data['articles'].keys())[0]
            relations = data['articles'][domain_name]['relations']
        else:
            # Direct format (domain -> relations)
            domain_name = list(data.keys())[0]
            relations = data[domain_name]['relations']

        print(f"Found domain: {domain_name} with {len(relations)} relations")
    except Exception as e:
        print(f"Error extracting relations from input file: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # Preprocess relations to include layer information
    enhanced_relations = preprocess_relations(relations, concept_layers)

    # Create the hierarchical structure
    hierarchy = create_hierarchical_structure(enhanced_relations, args.root)

    # Generate the HTML visualization
    generate_html_visualization(hierarchy, args.output_file)

    print("Hierarchical map generation completed successfully")


if __name__ == "__main__":
    main()