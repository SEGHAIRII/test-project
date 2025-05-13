# Document Layout Analysis Challenge: Multi-Column Detection

## Background

In document analysis and OCR systems, layout detection plays a crucial role in correctly extracting and sequencing text from complex documents. A common challenge in layout analysis arises when dealing with multi-column documents: if the layout detection algorithm fails to recognize the columnar structure, the reading order becomes jumbled, and the document loses its coherence.

Our current system detects large text layouts using a simple condition:
```python
layout_peek = [i for i, layout in enumerate(page['page']) 
               if ((layout['label'] == 'Text') and
                    ((layout['bbox_layout'][2] - layout['bbox_layout'][0]) > 900) and 
                    ((layout['bbox_layout'][3] - layout['bbox_layout'][1]) > 800))]
```

This condition only considers the overall dimensions of the layout box, without analyzing the internal arrangement of text elements. As a result, we often miss multi-column layouts, leading to incorrect text sequencing.

## Your Task

Your challenge is to improve the `layout_peek` condition to detect layouts containing a two-column structure. Instead of relying solely on the layout box dimensions, you'll need to analyze the spatial distribution of text boxes within each layout to determine if they follow a two-column pattern.

### Technical Requirements

1. Modify the existing codebase to implement a more sophisticated detection mechanism for two-column layouts.

2. Your solution should handle several edge cases:
   - Pages with a title spanning across both columns
   - Non-perfectly aligned columns (slightly tilted or with varying widths)
   - Varying box sizes within columns
   - Text boxes that may slightly overlap between columns

3. Create appropriate helper functions to analyze the spatial distribution of text boxes.

4. Document your approach and assumptions clearly.

### Considerations

When analyzing text boxes to detect a two-column layout, consider:

- **Column Gaps**: Look for a consistent vertical gap in the middle of the layout
- **Text Box Distribution**: Analyze the distribution of text boxes along the x-axis
- **Reading Order**: Check if text boxes follow a zigzag pattern (moving from left column to right column and back)
- **Tolerance for Irregularity**: Your solution should allow for some deviation in column alignment

The OCR process isn't 100% reliable, so your solution should be robust to imperfections:
- Column separations might not be perfectly vertical
- The end-x-coordinate of a box in the top left might be greater than the start-x-coordinate of a box at the bottom right
- The start-x-coordinate of a box at the top right might be greater than the end-x-coordinate of a box at the bottom left
- Some text boxes might span across columns (like titles)

### Data Structure

Each layout contains:
- `bbox_layout`: Overall bounding box [x_start, y_start, x_end, y_end]
- `bbox_text`: List of text box coordinates [x_start, y_start, x_end, y_end]
- `text`: List of text content for each box
- `label`: Type of layout (e.g., "Text", "SectionHeader")

## Deliverables

1. Modified code for detecting two-column layouts
2. Documentation explaining your approach

## Evaluation Criteria

Your solution will be evaluated on:
- Accuracy, Robustness
- The check must not take more than 1 second per page.

## Recommended Approach

1. run visualzer-test.py to view some patterns
2. check some captures in /assets folder for references
2. Make your solution

Good luck! This challenge tests your ability to solve real-world document analysis problems with creative algorithmic thinking.