import os
import json
import itertools
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# We use this to detect titles ... (they will occupy a large portion of the page)
SPANNING_BOX_WIDTH_RATIO_THRESHOLD = 0.7

ABSOLUTE_SPANNING_WIDTH_THRESHOLD = 700 # pixels, adjust based on typical document resolution

# to consider that a set of text is a column we need at least this many boxed
MIN_BOXES_FOR_COLUMN_CONSIDERATION = 4 

MIN_BOXES_PER_DETECTED_COLUMN = 2    # Each potential column needs at least this many boxes

# Gutter search: look for gutter in the central X% of the layout width
GUTTER_SEARCH_RANGE_LAYOUT_RATIO = (0.25, 0.75) # (min_x_ratio, max_x_ratio)

# Max allowed horizontal overlap between medians of columns (can be negative for a clear gap)
ALLOWED_INTER_COLUMN_MEDIAN_OVERLAP = 20 # pixels

# Min height of each column relative to layout height
MIN_COLUMN_HEIGHT_LAYOUT_RATIO = 0.3
# Min vertical overlap between the two columns, relative to the shorter column's height
MIN_VERTICAL_OVERLAP_RATIO_OF_SHORTER_COLUMN = 0.4
# Minimum absolute height for a layout to be considered for two-column structure
MIN_LAYOUT_HEIGHT_FOR_TWO_COLUMN = 300 # pixels


def _is_likely_spanning_box(text_bbox: list[int], layout_bbox: list[int]) -> bool:
    """
    Determines if a text box is likely spanning the width of a layout (e.g., a title).
    """
    box_x_start, _, box_x_end, _ = text_bbox
    layout_x_start, _, layout_x_end, _ = layout_bbox

    box_width = box_x_end - box_x_start
    layout_width = layout_x_end - layout_x_start

    if layout_width == 0: # Avoid division by zero
        return False

    # Condition 1: Box width is a large fraction of layout width
    if box_width / layout_width > SPANNING_BOX_WIDTH_RATIO_THRESHOLD:
        return True
    
    # Condition 2: Box width is very large in absolute terms
    if box_width > ABSOLUTE_SPANNING_WIDTH_THRESHOLD:
        return True
        
    return False


def detect_two_columns(layout: dict) -> bool:
    """
    Analyzes the spatial distribution of text boxes within a layout
    to determine if they follow a two-column pattern.

    Args:
        layout: A dictionary containing layout information, including
                'bbox_layout' and 'bbox_text'.

    Returns:
        True if the layout is likely two-column, False otherwise.
    """
    layout_bbox = layout.get('bbox_layout')
    text_bboxes = layout.get('bbox_text')

    if not layout_bbox or not text_bboxes:
        return False

    layout_x_start, layout_y_start, layout_x_end, layout_y_end = layout_bbox
    layout_width = layout_x_end - layout_x_start
    layout_height = layout_y_end - layout_y_start

    if layout_height < MIN_LAYOUT_HEIGHT_FOR_TWO_COLUMN or layout_width < 200: # Basic check
        return False

    # 1. Filter out spanning boxes
    non_spanning_boxes = []
    for bbox in text_bboxes:
        if not _is_likely_spanning_box(bbox, layout_bbox):
            non_spanning_boxes.append(bbox)

    if len(non_spanning_boxes) < MIN_BOXES_FOR_COLUMN_CONSIDERATION:
        return False

    # 2. Find potential gutter by looking for the largest gap in x-centers
    #    of non-spanning boxes.
    #    Boxes are tuples: (x_center, original_bbox)
    centered_boxes = []
    for bbox in non_spanning_boxes:
        center_x = (bbox[0] + bbox[2]) / 2
        centered_boxes.append({'cx': center_x, 'bbox': bbox})
    
    # Sort boxes by their horizontal center
    sorted_boxes_by_cx = sorted(centered_boxes, key=lambda b: b['cx'])

    potential_gutters = []
    # A gutter is defined by the space between the x-center of box i and box i+1
    # We also store the actual x-coordinates of the boxes creating this gap
    for i in range(len(sorted_boxes_by_cx) - 1):
        box_left_of_gap = sorted_boxes_by_cx[i]
        box_right_of_gap = sorted_boxes_by_cx[i+1]

        gap_center_midpoint = (box_left_of_gap['cx'] + box_right_of_gap['cx']) / 2
        gap_width_centers = box_right_of_gap['cx'] - box_left_of_gap['cx']
        
        # Check if this gap_center_midpoint is within the layout's central region
        min_gutter_x = layout_x_start + layout_width * GUTTER_SEARCH_RANGE_LAYOUT_RATIO[0]
        max_gutter_x = layout_x_start + layout_width * GUTTER_SEARCH_RANGE_LAYOUT_RATIO[1]

        if min_gutter_x <= gap_center_midpoint <= max_gutter_x and gap_width_centers > 0: # Ensure some positive gap
            potential_gutters.append({
                'gutter_x_candidate': gap_center_midpoint,
                'gap_width_centers': gap_width_centers,
                'split_index': i  # index in sorted_boxes_by_cx; left items up to i, right items from i+1
            })
    
    if not potential_gutters:
        return False

    # Select the gutter candidate that represents the largest jump in centers
    # This implies the most significant separation.
    best_gutter_candidate = max(potential_gutters, key=lambda g: g['gap_width_centers'])
    x_gutter = best_gutter_candidate['gutter_x_candidate']
    split_idx = best_gutter_candidate['split_index']

    # 3. Assign boxes to columns based on the found x_gutter
    #    Original bboxes are needed for further validation
    left_column_boxes = [b['bbox'] for b in sorted_boxes_by_cx[:split_idx + 1]]
    right_column_boxes = [b['bbox'] for b in sorted_boxes_by_cx[split_idx + 1:]]
    
    # 4. Validate columns
    if len(left_column_boxes) < MIN_BOXES_PER_DETECTED_COLUMN or \
       len(right_column_boxes) < MIN_BOXES_PER_DETECTED_COLUMN:
        return False

    # 4a. Validate Horizontal Separation (using medians for robustness)
    median_x_end_left = np.median([b[2] for b in left_column_boxes])
    median_x_start_right = np.median([b[0] for b in right_column_boxes])

    if median_x_start_right - median_x_end_left < -ALLOWED_INTER_COLUMN_MEDIAN_OVERLAP:
        # Too much overlap or left column is to the right of right column
        return False

    # 4b. Validate Vertical Cohesion and Span
    # Left column vertical span
    if not left_column_boxes or not right_column_boxes: return False # Should not happen due to earlier checks

    min_y_L = min(b[1] for b in left_column_boxes)
    max_y_L = max(b[3] for b in left_column_boxes)
    height_L = max_y_L - min_y_L

    # Right column vertical span
    min_y_R = min(b[1] for b in right_column_boxes)
    max_y_R = max(b[3] for b in right_column_boxes)
    height_R = max_y_R - min_y_R

    if height_L < layout_height * MIN_COLUMN_HEIGHT_LAYOUT_RATIO or \
       height_R < layout_height * MIN_COLUMN_HEIGHT_LAYOUT_RATIO:
        return False # One or both columns are too short relative to layout

    # Vertical overlap between the two columns
    vertical_overlap_amount = max(0, min(max_y_L, max_y_R) - max(min_y_L, min_y_R))
    shorter_column_height = min(height_L, height_R)

    if shorter_column_height == 0: # Avoid division by zero if a column has no height
         if vertical_overlap_amount == 0 : # If one column has no height, overlap must be 0 too.
             return False # No real columns if one has no height
    elif vertical_overlap_amount / shorter_column_height < MIN_VERTICAL_OVERLAP_RATIO_OF_SHORTER_COLUMN:
        return False # Not enough vertical overlap

    return True # All checks passed


# --- Original functions (slightly modified or kept for context if needed) ---
def in_same_level(text_box_1:list[int], text_box_2: list[int], margin:int)->bool:
    # This function is not directly used by the new two-column detection logic,
    # but kept here as it was part of the original problem statement.
    _, y1_start, _, y1_end = text_box_1
    _, y2_start, _, y2_end = text_box_2

    y1_center = (y1_start + y1_end) / 2
    y2_center = (y2_start + y2_end) / 2
    same_level = abs(y1_center - y2_center) <= margin

    x1_start, _, x1_end, _ = text_box_1
    x2_start, _, x2_end, _ = text_box_2
    x_overlap = max(0, min(x1_end, x2_end) - max(x1_start, x2_start))
    
    # Check if boxes have significant width before deciding on overlap based column difference
    min_width_of_the_two_boxes = min(x1_end - x1_start, x2_end - x2_start)
    if min_width_of_the_two_boxes == 0: # Avoid issues with zero-width boxes
        different_columns = True # Assume different if one has no width for safety
    else:
        different_columns = x_overlap < 0.5 * min_width_of_the_two_boxes

    return same_level and different_columns
     

def find_min_width(layout, height_margin:int, start_min_width=900)->int:
    # This function's original purpose was to find a minimum width *between columns*.
    # The new `detect_two_columns` function supersedes this for identifying column structure.
    # It might still be useful for other analyses, so it's kept.
    min_width_found = start_min_width
    if 'bbox_text' not in layout or len(layout['bbox_text']) < 2:
        return start_min_width # Return default if not enough boxes

    for text_box_1, text_box_2 in itertools.combinations(layout['bbox_text'], 2):
        if in_same_level(text_box_1, text_box_2, height_margin):
            # This calculates the horizontal distance between the boxes if they don't overlap,
            # or negative if they do. We are interested in the space *between* them.
            # Ensuring box1 is to the left of box2 for consistent gap calculation
            b1_x_start, _, b1_x_end, _ = text_box_1
            b2_x_start, _, b2_x_end, _ = text_box_2

            # Determine which box is left and which is right
            if (b1_x_start + b1_x_end)/2 < (b2_x_start + b2_x_end)/2 : # b1 is left of b2
                gap = b2_x_start - b1_x_end
            else: # b2 is left of b1
                gap = b1_x_start - b2_x_end
            
            if gap > 0 : # Only consider positive gaps as potential column separators
                 min_width_found = min(min_width_found, gap)

    return min_width_found


def visualize_page_layouts(page_data, figsize=(20, 25)):
    """
    Visualize all layouts and their text boxes in a single figure.
    (Copied from the original problem, with minor adjustments if any for clarity)
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    x_coords = []
    y_coords = []
    for layout_item in page_data['page']: # Renamed 'layout' to 'layout_item' to avoid conflict
        x_coords.extend([layout_item['bbox_layout'][0], layout_item['bbox_layout'][2]])
        y_coords.extend([layout_item['bbox_layout'][1], layout_item['bbox_layout'][3]])
    
    if not x_coords or not y_coords: # Handle empty pages
        ax.set_title(f"Page {page_data['index']} - No Layouts to Visualize", fontsize=16)
        plt.tight_layout()
        return fig

    x_min, x_max = min(x_coords) - 50, max(x_coords) + 50
    y_min, y_max = min(y_coords) - 50, max(y_coords) + 50
    
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_max, y_min) 
    
    ax.set_title(f"Page {page_data['index']} - Full Layout Visualization", fontsize=16)
    text_box_colors = plt.cm.Blues(np.linspace(0.3, 0.8, 20)) # Using Blues for text boxes
    column_layout_color = 'green' # Color for detected two-column layouts
    default_layout_color = 'red' # Color for other layouts
    
    for layout_idx, layout_item in enumerate(page_data['page']):
        layout_bbox = layout_item['bbox_layout']
        x_start, y_start, x_end, y_end = layout_bbox
        layout_width_vis = x_end - x_start # Renamed to avoid conflict with internal layout_width
        layout_height_vis = y_end - y_start

        is_two_col = layout_item.get('_is_two_column_debug', False) # Check for debug flag
        
        edge_color = column_layout_color if is_two_col else default_layout_color
        line_width = 2.5 if is_two_col else 1.5
        
        layout_rect = patches.Rectangle(
            (x_start, y_start), layout_width_vis, layout_height_vis,
            linewidth=line_width, 
            edgecolor=edge_color,  
            facecolor='none', 
            alpha=0.7,
            label='Two-Column Layout' if is_two_col and layout_idx == 0 else None # Label only once
        )
        ax.add_patch(layout_rect)
        
        layout_label_text = layout_item.get('label', 'Unknown')
        if is_two_col:
            layout_label_text += " (2-Col Detected)"

        ax.text(
            x_start + 5, y_start + 20, 
            f"Layout {layout_idx}: {layout_label_text}", 
            color='black', 
            fontsize=9, 
            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=1)
        )
        
        if 'bbox_text' in layout_item and 'text' in layout_item:
            for text_idx, (bbox, text_content) in enumerate(zip(layout_item['bbox_text'], layout_item['text'])):
                x_start_text, y_start_text, x_end_text, y_end_text = bbox
                text_width = x_end_text - x_start_text
                text_height = y_end_text - y_start_text
                
                t_color = text_box_colors[text_idx % len(text_box_colors)]
                
                text_rect = patches.Rectangle(
                    (x_start_text, y_start_text), text_width, text_height,
                    linewidth=1, 
                    edgecolor=t_color, 
                    facecolor=t_color, # Fill slightly for visibility
                    alpha=0.3
                )
                ax.add_patch(text_rect)
                
                ax.text(
                    x_start_text + 2, y_start_text + 10, 
                    f"L{layout_idx}-T{text_idx}", 
                    color='black', 
                    fontsize=7, 
                    bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1)
                )
                
                text_preview = text_content[:15] + "..." if len(text_content) > 15 else text_content
                ax.text(
                    x_start_text + 2, y_start_text + text_height / 2 + 5, # Center text a bit
                    text_preview, 
                    color='darkslategray', 
                    fontsize=6, 
                    bbox=dict(facecolor='white', alpha=0.4, edgecolor='none', pad=0.5)
                )
    
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.set_xlabel('X coordinate', fontsize=12)
    ax.set_ylabel('Y coordinate', fontsize=12)
    
    # Create a legend if two-column layouts were found and labeled
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        # Add a default layout legend item
        default_patch = patches.Patch(edgecolor=default_layout_color, facecolor='none', linewidth=1.5, label='Other Layout')
        handles.append(default_patch)
        ax.legend(handles=handles, loc='upper right')

    plt.tight_layout()
    return fig

# --- Main processing loop ---
base_dir = "result_json" # Assumes this directory exists and is populated

# Create a directory for output images if it doesn't exist
output_viz_dir = "visualizations"
os.makedirs(output_viz_dir, exist_ok=True)


for year in sorted(os.listdir(base_dir), reverse=True):
    year_path = os.path.join(base_dir, year)
    
    if os.path.isdir(year_path) and (year > "1964"): # Ensure it's a directory
        print(f"Processing year: {year}")
        year_viz_dir = os.path.join(output_viz_dir, year)
        os.makedirs(year_viz_dir, exist_ok=True)

        for filename in sorted(os.listdir(year_path)):
            if filename.endswith(".json"):
                file_path = os.path.join(year_path, filename)
                # print(f"Processing file: {filename}") # Less verbose

                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                found_two_column_in_file = False
                for page_data in data: # page_data is 'page' from the original loop
                    # print(f"  Page index: {page_data['index']}") # Debugging page index
                    
                    # Add a temporary flag for visualization
                    for layout_item in page_data['page']:
                        layout_item['_is_two_column_debug'] = False


                    # New condition for layout_peek
                    # We are interested in any text layout that is detected as two-column
                    two_column_layout_indices = []
                    for i, layout_item in enumerate(page_data['page']):
                        if layout_item.get('label') == 'Text' and detect_two_columns(layout_item):
                            two_column_layout_indices.append(i)
                            layout_item['_is_two_column_debug'] = True # Mark for viz
                    
                    if two_column_layout_indices:
                        print(f"  File: {filename}, Page: {page_data['index']}, Found two-column structure in layouts: {two_column_layout_indices}")
                        found_two_column_in_file = True
                        
                        fig = visualize_page_layouts(page_data)
                        
                        # Save the figure
                        viz_filename = f"{os.path.splitext(filename)[0]}_page_{page_data['index']}.png"
                        fig_path = os.path.join(year_viz_dir, viz_filename)
                        plt.savefig(fig_path)
                        print(f"    Saved visualization to {fig_path}")
                        plt.close(fig) # Close the figure to free memory
                
                # if found_two_column_in_file:
                #     print(f"Finished processing {filename}. Visualizations saved if two-column layouts were detected.")

print("Processing complete.")