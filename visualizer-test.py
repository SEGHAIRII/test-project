import os
import json

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

def visualize_page_layouts(page_data, figsize=(20, 25)):
    """
    Visualize all layouts and their text boxes in a single figure.
    
    Parameters:
    - page_data: A page dictionary containing layout information
    - figsize: Size of the figure (width, height)
    
    Returns:
    - matplotlib figure object
    """
    # Create figure and axis
    fig, ax = plt.subplots(figsize=figsize)
    
    # Calculate overall document dimensions
    x_coords = []
    y_coords = []
    for layout in page_data['page']:
        x_coords.extend([layout['bbox_layout'][0], layout['bbox_layout'][2]])
        y_coords.extend([layout['bbox_layout'][1], layout['bbox_layout'][3]])
    
    # Add some padding
    x_min, x_max = min(x_coords) - 50, max(x_coords) + 50
    y_min, y_max = min(y_coords) - 50, max(y_coords) + 50
    
    # Set axis limits
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_max, y_min)  # Invert y-axis to match document coordinates
    
    # Set title
    ax.set_title(f"Page {page_data['index']} - Full Layout Visualization", fontsize=16)
    
    # Prepare color palette for text boxes
    text_box_colors = plt.cm.Blues(np.linspace(0.3, 0.8, 20))
    
    # Draw each layout and its text boxes
    for layout_idx, layout in enumerate(page_data['page']):
        # Draw layout bounding box
        layout_bbox = layout['bbox_layout']
        x_start, y_start, x_end, y_end = layout_bbox
        layout_width = x_end - x_start
        layout_height = y_end - y_start
        
        # Determine if this is a large text layout
        is_large_text_layout = (
            layout['label'] == 'Text' and 
            layout_width > 900 and 
            layout_height > 800
        )
        
        # Layout box style - ALL layouts will now have red border
        layout_line_width = 2.5 if is_large_text_layout else 1.5
        
        # Draw layout rectangle with red border
        layout_rect = patches.Rectangle(
            (x_start, y_start), layout_width, layout_height,
            linewidth=layout_line_width, 
            edgecolor='red',  
            facecolor='none', 
            alpha=0.7
        )
        ax.add_patch(layout_rect)
        
        # Add layout index and label
        layout_label = layout.get('label', 'Unknown')
        ax.text(
            x_start + 5, y_start + 20, 
            f"Layout {layout_idx}: {layout_label}", 
            color='black', 
            fontsize=9, 
            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=1)
        )
        
        # If layout has bbox_text, draw its text boxes
        if 'bbox_text' in layout and 'text' in layout:
            # Draw each text box
            for text_idx, (bbox, text) in enumerate(zip(layout['bbox_text'], layout['text'])):
                x_start_text, y_start_text, x_end_text, y_end_text = bbox
                text_width = x_end_text - x_start_text
                text_height = y_end_text - y_start_text
                
                # Cycle through text box colors
                text_color = text_box_colors[text_idx % len(text_box_colors)]
                
                # Text box rectangle
                text_rect = patches.Rectangle(
                    (x_start_text, y_start_text), text_width, text_height,
                    linewidth=1, 
                    edgecolor=text_color, 
                    facecolor='none', 
                    alpha=0.7
                )
                ax.add_patch(text_rect)
                
                # Add text index label
                ax.text(
                    x_start_text + 2, y_start_text + 10, 
                    f"L{layout_idx}-T{text_idx}", 
                    color='black', 
                    fontsize=7, 
                    bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1)
                )
                
                # Optionally add text preview
                text_preview = text[:15] + "..." if len(text) > 15 else text
                ax.text(
                    x_start_text + 2, y_start_text + 20, 
                    text_preview, 
                    color='black', 
                    fontsize=6, 
                    bbox=dict(facecolor='white', alpha=0.5, edgecolor='none', pad=1)
                )
    
    # Add grid for reference
    ax.grid(True, linestyle='--', alpha=0.3)
    
    # Add axis labels
    ax.set_xlabel('X coordinate', fontsize=12)
    ax.set_ylabel('Y coordinate', fontsize=12)
    
    plt.tight_layout()
    return fig

# Path to the directory containing yearly result_json folders
base_dir = "result_json"

# Iterate through each year folder
for year in sorted(os.listdir(base_dir), reverse=True):
    year_path = os.path.join(base_dir, year)
    
    if os.path.isdir(year_path) and (year > "1964"):  # Ensure it's a directory
        print(f"Processing year: {year}")

        # Iterate through each JSON file in the year folder
        for filename in sorted(os.listdir(year_path)):
            if filename.endswith(".json"):
                file_path = os.path.join(year_path, filename)
                print(f"Processing file: {filename}")

                # Read the JSON file
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for page_num, page in enumerate(data):
                    # Condition to find layout with large width and height
                    layout_peek = [i for i, layout in enumerate(page['page']) 
                                   if ((layout['label'] == 'Text') and
                                        ((layout['bbox_layout'][2] - layout['bbox_layout'][0]) > 900) and 
                                        ((layout['bbox_layout'][3] - layout['bbox_layout'][1]) > 800))]
                    
                    if layout_peek:
                        print(f"File: {filename}, Page: {page['index']}")
                        
                        # Visualize all layouts and their text boxes in one figure
                        fig = visualize_page_layouts(page)
                        plt.show()