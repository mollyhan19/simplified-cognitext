import os
import json
import time
import math
import numpy as np
import plotly.graph_objects as go
from typing import List, Dict, Tuple, Optional
import openai
from math import cos, sin, pi

class CyclicConceptMapGenerator:
    """Python implementation of cyclic concept map generation using Plotly."""

    def __init__(self, api_key: str, output_dir: str = "output"):
        self.api_key = api_key
        self.output_dir = output_dir
        self.openai_client = openai.OpenAI(api_key=api_key)

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

    def generate_constellations(self,
                                title: str,
                                category: str,
                                entities: List[Dict],
                                relations: List[Dict],
                                num_constellations: int = 3) -> List[Dict]:
        """
        Generate concept constellations using LLM similar to llmProcessor.js.

        Args:
            title: Title of the article
            category: Category of the article
            entities: List of entity objects
            relations: List of relation objects
            num_constellations: Number of constellations to generate

        Returns:
            List of constellation definitions
        """
        # Extract priority concepts by layer
        priority_concepts = [entity["id"] for entity in entities
                             if entity.get("layer") == "priority"]

        # Extract top concepts by frequency
        concept_frequencies = {}
        for entity in entities:
            concept_frequencies[entity["id"]] = entity.get("frequency", 0)

        top_concepts = sorted(concept_frequencies.items(),
                              key=lambda x: x[1],
                              reverse=True)[:15]

        # Combine priority and frequent concepts
        core_concepts = list(set([c[0] for c in top_concepts] + priority_concepts))[:15]

        # Sample some relations
        sample_relations = relations[:20] if len(relations) > 20 else relations

        # Create prompt for LLM
        prompt = self._create_constellation_prompt(
            title, category, core_concepts, sample_relations, num_constellations
        )

        # Generate constellations using LLM
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert in knowledge visualization and concept mapping."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        # Parse LLM response
        constellations = self._parse_constellation_response(
            response.choices[0].message.content,
            all_relations=relations
        )

        return constellations

    def _create_constellation_prompt(self,
                                     title: str,
                                     category: str,
                                     core_concepts: List[str],
                                     sample_relations: List[Dict],
                                     num_constellations: int) -> str:
        """Create a prompt for constellation generation."""
        return f"""
You are an expert in knowledge visualization and concept mapping. I have a dataset of concept relations about "{title}" in the category of "{category}".

I need you to identify {num_constellations}-{num_constellations + 2} meaningful "concept constellations" from this data. A constellation is a group of closely related concepts that form a coherent theme or cycle.

Here are some of the most frequently occurring concepts:
{', '.join(core_concepts)}

Here's a sample of the concept relations:
{json.dumps(sample_relations, indent=2)}

For each constellation:
1. Provide a clear name (e.g., "{title} Process Cycle")
2. Write a brief description explaining the theme
3. List 4-8 key concepts that should be included in this constellation

Return your response in this JSON format:
{{
  "constellations": [
    {{
      "name": "Name of constellation 1",
      "description": "Brief description of what this constellation represents",
      "concepts": ["concept1", "concept2", "concept3", "concept4"]
    }},
    // Additional constellations...
  ]
}}

Focus on creating meaningful groupings that illustrate important relationships, cycles, or themes in the domain.
"""

    def _parse_constellation_response(self,
                                      response: str,
                                      all_relations: List[Dict]) -> List[Dict]:
        """Parse the LLM response to extract constellation definitions."""
        try:
            # Extract JSON from the response
            json_match = response.strip()
            if not json_match.startswith('{'):
                # Try to find JSON block in the response
                json_block = response.find('{')
                if json_block >= 0:
                    json_match = response[json_block:]

            # Parse the JSON
            parsed_response = json.loads(json_match)
            constellations = parsed_response.get("constellations", [])

            if not constellations or not isinstance(constellations, list):
                raise ValueError("Invalid constellation format in LLM response")

            # Normalize and validate the constellations
            normalized_constellations = []
            for constellation in constellations:
                # Ensure all required fields are present
                if not all(k in constellation for k in ["name", "description", "concepts"]):
                    continue

                # Normalize concept names to lowercase for matching
                concepts = [c.lower() for c in constellation.get("concepts", [])]

                # Ensure we have enough concepts
                if len(concepts) < 3:
                    continue

                normalized_constellations.append({
                    "name": constellation["name"],
                    "description": constellation["description"],
                    "concepts": concepts
                })

            return normalized_constellations

        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            print(f"Response was: {response}")

            # Fallback to basic constellations if parsing fails
            return self._generate_fallback_constellations(all_relations)

    def _generate_fallback_constellations(self, relations: List[Dict]) -> List[Dict]:
        """Generate basic fallback constellations if LLM parsing fails."""
        # Count concept occurrences in relations
        concept_count = {}
        for rel in relations:
            source = rel.get("source", "")
            target = rel.get("target", "")

            concept_count[source] = concept_count.get(source, 0) + 1
            concept_count[target] = concept_count.get(target, 0) + 1

        # Get top concepts
        top_concepts = sorted(concept_count.items(), key=lambda x: x[1], reverse=True)

        # Create fallback constellations
        constellations = []

        # First constellation: Top concepts
        if len(top_concepts) >= 5:
            constellations.append({
                "name": "Primary Concept Cluster",
                "description": "A constellation of the most connected concepts in the domain.",
                "concepts": [c[0].lower() for c in top_concepts[:6]]
            })

        # Second constellation: Next set of top concepts
        if len(top_concepts) >= 10:
            constellations.append({
                "name": "Secondary Concept Cluster",
                "description": "Secondary important concepts in the domain.",
                "concepts": [c[0].lower() for c in top_concepts[6:12]]
            })

        return constellations

    def _curved_edge(self, x0, y0, x1, y1, curvature=0.2):
        """Create a curved edge between two points."""
        # Midpoint
        mid_x = (x0 + x1) / 2
        mid_y = (y0 + y1) / 2

        # Direction vector
        dx = x1 - x0
        dy = y1 - y0

        # Perpendicular direction (for curve control point)
        perp_x = -dy
        perp_y = dx

        # Normalize perpendicular vector
        length = math.sqrt(perp_x ** 2 + perp_y ** 2)
        if length > 0:
            perp_x /= length
            perp_y /= length

        # Control point location (perpendicular to midpoint)
        ctrl_x = mid_x + curvature * perp_x
        ctrl_y = mid_y + curvature * perp_y

        # Generate points along the quadratic Bezier curve
        t_values = np.linspace(0, 1, 20)
        curve_x = []
        curve_y = []

        for t in t_values:
            # Quadratic Bezier formula
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * ctrl_x + t ** 2 * x1
            y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * ctrl_y + t ** 2 * y1
            curve_x.append(x)
            curve_y.append(y)

        return curve_x, curve_y

    def generate_cyclic_map(self,
                            title: str,
                            constellation: Dict,
                            entities: List[Dict],
                            relations: List[Dict]) -> go.Figure:
        """
        Generate an interactive cyclic concept map visualization using Plotly.

        Args:
            title: Title of the article
            constellation: Constellation definition
            entities: List of entity objects
            relations: List of relation objects

        Returns:
            Plotly figure
        """
        # Build node and edge data
        nodes = {}  # Nodes keyed by concept id
        edges = []  # List of edges

        # Calculate total connections (degree) for each concept
        concept_degrees = {}
        for rel in relations:
            source = rel.get("source", "").lower()
            target = rel.get("target", "").lower()

            concept_degrees[source] = concept_degrees.get(source, 0) + 1
            concept_degrees[target] = concept_degrees.get(target, 0) + 1

        # Get concepts to include from the constellation
        constellation_concepts = [c.lower() for c in constellation.get("concepts", [])]

        # First pass: Add nodes for constellation concepts
        for concept in constellation_concepts:
            # Find the entity in the entities list
            matching_entity = next((e for e in entities
                                    if e.get("id", "").lower() == concept.lower()), None)

            if matching_entity:
                # Get degree (total connections)
                degree = concept_degrees.get(concept.lower(), 0)

                # Add node with entity attributes
                nodes[concept.lower()] = {
                    "id": concept.lower(),
                    "label": matching_entity.get("id", concept),
                    "layer": matching_entity.get("layer", "secondary"),
                    "frequency": matching_entity.get("frequency", 1),
                    "section_count": matching_entity.get("section_count", 1),
                    "degree": degree,
                    # Combined score for sizing (weighted sum of frequency and degree)
                    "importance_score": (matching_entity.get("frequency", 1) * 0.6) + (degree * 0.4)
                }

        # Ensure we have enough nodes - add connected concepts if needed
        if len(nodes) < 4:
            # Get additional related concepts
            additional_concepts = self._find_related_concepts(
                constellation_concepts, relations, entities, limit=4
            )

            # Add them to the nodes dictionary
            for concept in additional_concepts:
                if concept.lower() not in nodes:
                    matching_entity = next((e for e in entities
                                            if e.get("id", "").lower() == concept.lower()), None)

                    if matching_entity:
                        # Get degree
                        degree = concept_degrees.get(concept.lower(), 0)

                        nodes[concept.lower()] = {
                            "id": concept.lower(),
                            "label": matching_entity.get("id", concept),
                            "layer": matching_entity.get("layer", "tertiary"),
                            "frequency": matching_entity.get("frequency", 1),
                            "section_count": matching_entity.get("section_count", 1),
                            "degree": degree,
                            "importance_score": (matching_entity.get("frequency", 1) * 0.6) + (degree * 0.4)
                        }

        # Get the relations between nodes
        for rel in relations:
            source = rel.get("source", "").lower()
            target = rel.get("target", "").lower()
            relation_type = rel.get("relation_type", "")
            evidence = rel.get("evidence", "")

            if source in nodes and target in nodes:
                edges.append({
                    "source": source,
                    "target": target,
                    "relation": relation_type,
                    "evidence": evidence if isinstance(evidence, str) else
                    (evidence[0] if isinstance(evidence, list) and evidence else "")
                })

        # Arrange nodes in a circle
        node_positions = self._arrange_nodes_circular(list(nodes.values()))

        # Create Plotly figure
        fig = go.Figure()

        # Add edges as lines with hover info showing the relationship
        for edge in edges:
            source = nodes[edge["source"]]
            target = nodes[edge["target"]]

            # Get positions
            x0, y0 = node_positions[source["id"]]
            x1, y1 = node_positions[target["id"]]

            # Calculate a curve for the edge to avoid straight overlapping lines
            # Use different curve directions for bidirectional relationships
            has_reverse = any(e["source"] == edge["target"] and e["target"] == edge["source"] for e in edges)

            # Determine curvature
            curvature = 0.2 if has_reverse else 0.1

            # Create curved path
            path_x, path_y = self._curved_edge(x0, y0, x1, y1, curvature)

            # Create hover text with the full evidence
            hover_text = f"<b>{source['label']}</b> {edge['relation']} <b>{target['label']}</b><br><br>"
            if edge["evidence"]:
                hover_text += f"<i>Evidence:</i> {edge['evidence']}"

            # Draw the edge
            fig.add_trace(go.Scatter(
                x=path_x,
                y=path_y,
                mode='lines',
                line=dict(width=1.5, color='rgba(150,150,150,0.7)'),
                hoverinfo='text',
                hovertext=hover_text,
                hoverlabel=dict(
                    bgcolor="white",
                    font_size=12,
                    font_family="Arial"
                ),
                name=f'{source["label"]} {edge["relation"]} {target["label"]}',
                showlegend=False
            ))

            # Add an arrow at the end of the line (last segment)
            arrow_start = len(path_x) - 2
            arrow_end = len(path_x) - 1

            fig.add_trace(go.Scatter(
                x=[path_x[arrow_start], path_x[arrow_end]],
                y=[path_y[arrow_start], path_y[arrow_end]],
                mode='lines',
                line=dict(width=2, color='rgba(100,100,100,0.9)'),
                marker=dict(symbol='arrow', size=8),
                hoverinfo='none',
                showlegend=False
            ))

            # Add the relation text at the middle of the curved path
            middle_idx = len(path_x) // 2
            text_x = path_x[middle_idx]
            text_y = path_y[middle_idx]

            # Only show edge label if we don't have too many edges
            if len(edges) <= 12:
                fig.add_annotation(
                    x=text_x,
                    y=text_y,
                    text=edge["relation"],
                    showarrow=False,
                    font=dict(size=8, color="gray"),
                    bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="rgba(150,150,150,0.3)",
                    borderwidth=1,
                    borderpad=2,
                    opacity=0.8
                )

        # Define node colors based on layer
        color_map = {
            "priority": "#2196f3",  # Blue
            "secondary": "#4caf50",  # Green
            "tertiary": "#ff9800",  # Orange
            "unknown": "#9e9e9e"  # Gray
        }

        # Add nodes as scatter points
        node_x = []
        node_y = []
        node_text = []
        node_size = []
        node_color = []
        node_line_width = []
        node_hover_text = []

        for node_id, pos in node_positions.items():
            node = nodes[node_id]
            layer = node.get("layer", "unknown")

            node_x.append(pos[0])
            node_y.append(pos[1])
            node_text.append(node["label"])

            # Size based on importance score (normalized between 20 and 50)
            score = node.get("importance_score", 1)
            min_size = 20
            max_size = 50

            # Normalize size with a base size plus a scaling factor
            size = min_size + (
                        (score / max(n.get("importance_score", 1) for n in nodes.values())) * (max_size - min_size))
            node_size.append(size)

            # Color based on layer
            node_color.append(color_map.get(layer, color_map["unknown"]))

            # Extra emphasis for original constellation concepts
            if node["id"] in constellation_concepts:
                node_line_width.append(2)
            else:
                node_line_width.append(1)

            # Create detailed hover information
            hover_info = (
                f"<b>{node['label']}</b><br>"
                f"Frequency: {node.get('frequency', '-')}<br>"
                f"Sections: {node.get('section_count', '-')}<br>"
                f"Connections: {node.get('degree', '-')}<br>"
                f"Layer: {node.get('layer', '-').capitalize()}"
            )
            node_hover_text.append(hover_info)

        # Add nodes to the figure
        fig.add_trace(go.Scatter(
            x=node_x,
            y=node_y,
            mode='markers+text',
            marker=dict(
                size=node_size,
                color=node_color,
                opacity=0.8,
                line=dict(
                    width=node_line_width,
                    color='white'
                )
            ),
            text=node_text,
            textposition="top center",
            hoverinfo='text',
            hovertext=node_hover_text,
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Arial"
            ),
            name='Concepts',
            showlegend=False
        ))

        # Add legend for node layers
        for layer, color in color_map.items():
            if any(nodes[n]["layer"] == layer for n in nodes):
                fig.add_trace(go.Scatter(
                    x=[None],
                    y=[None],
                    mode='markers',
                    marker=dict(size=10, color=color),
                    name=f"{layer.capitalize()} Layer",
                    showlegend=True
                ))

        # Layout configuration
        fig.update_layout(
            title=dict(
                text=f"{constellation['name']}",
                x=0.5,
                font=dict(size=20)
            ),
            annotations=[
                dict(
                    text=constellation.get('description', ''),
                    align='center',
                    showarrow=False,
                    xref='paper',
                    yref='paper',
                    x=0.5,
                    y=-0.1,
                    font=dict(size=12, color="gray"),
                )
            ],
            hovermode='closest',
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            # No axes or grid
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False
            ),
            # Keep aspect ratio equal
            autosize=True,
            width=800,
            height=600
        )

        # Make the plot responsive
        fig.update_layout(
            autosize=True,
            margin=dict(l=20, r=20, t=60, b=100),
        )

        return fig

    def _find_related_concepts(self,
                               existing_concepts: List[str],
                               relations: List[Dict],
                               entities: List[Dict],
                               limit: int = 4) -> List[str]:
        """Find additional concepts related to existing concepts."""
        related_concepts = set()

        # Normalize existing concepts
        existing_concepts_lower = [c.lower() for c in existing_concepts]

        # Find concepts directly connected to existing concepts
        for rel in relations:
            source = rel.get("source", "").lower()
            target = rel.get("target", "").lower()

            if source in existing_concepts_lower and target not in existing_concepts_lower:
                related_concepts.add(target)
            elif target in existing_concepts_lower and source not in existing_concepts_lower:
                related_concepts.add(source)

            if len(related_concepts) >= limit:
                break

        # If we still need more, add high-frequency concepts
        if len(related_concepts) < limit:
            sorted_entities = sorted(
                entities,
                key=lambda x: x.get("frequency", 0),
                reverse=True
            )

            for entity in sorted_entities:
                entity_id = entity.get("id", "").lower()
                if entity_id not in existing_concepts_lower and entity_id not in related_concepts:
                    related_concepts.add(entity_id)
                    if len(related_concepts) >= limit:
                        break

        return list(related_concepts)

    def _arrange_nodes_circular(self, nodes: List[Dict]) -> Dict:
        """
        Arrange nodes in a circle layout.
        Returns a dictionary mapping node IDs to (x,y) positions.
        """
        positions = {}

        # Count the nodes
        node_count = len(nodes)
        if node_count == 0:
            return positions

        # For just one node, place it at the center
        if node_count == 1:
            positions[nodes[0]["id"]] = (0, 0)
            return positions

        # Choose a central node if we have more than 2 nodes
        if node_count > 2:
            # Prefer a priority node
            priority_nodes = [n for n in nodes if n.get("layer") == "priority"]

            if priority_nodes:
                # Sort by frequency for most important
                central_node = sorted(
                    priority_nodes,
                    key=lambda x: x.get("frequency", 0),
                    reverse=True
                )[0]
            else:
                # Use the highest frequency node
                central_node = sorted(
                    nodes,
                    key=lambda x: x.get("frequency", 0),
                    reverse=True
                )[0]

            # Place central node at the center
            positions[central_node["id"]] = (0, 0)

            # Remove central node from the list for circular arrangement
            peripheral_nodes = [n for n in nodes if n["id"] != central_node["id"]]

            # Arrange other nodes in a circle
            radius = 1
            for i, node in enumerate(peripheral_nodes):
                angle = 2 * pi * i / len(peripheral_nodes)
                x = radius * cos(angle)
                y = radius * sin(angle)
                positions[node["id"]] = (x, y)
        else:
            # For 2 nodes, place them horizontally
            positions[nodes[0]["id"]] = (-0.5, 0)
            positions[nodes[1]["id"]] = (0.5, 0)

        return positions