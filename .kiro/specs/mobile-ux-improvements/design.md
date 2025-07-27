# Design Document

## Overview

This design addresses two critical mobile UX issues in the church map application:
1. Search results visibility on mobile devices in portrait orientation
2. Removal of technical status information that clutters the interface

The current implementation hides the results container entirely on mobile (`display: none`), making search functionality unusable on mobile devices. Additionally, technical statistics like "With Coordinates" and "Geocoding Rate" provide no value to end users.

## Architecture

### Current Mobile Layout Issues
- **Search Panel Height**: Fixed at 200px on mobile, with results container hidden
- **Stats Container**: Takes up valuable space with technical information
- **Results Container**: Completely hidden on mobile with `display: none`

### Proposed Mobile Layout
- **Adaptive Search Panel**: Dynamic height based on content and search state
- **Streamlined Stats**: Show only "Total Churches" count
- **Visible Results**: Search results displayed in a mobile-optimized container

## Components and Interfaces

### 1. Mobile CSS Improvements

#### Search Panel Responsive Design
```css
@media (max-width: 768px) {
    .search-panel {
        width: 100%;
        height: auto; /* Changed from fixed 200px */
        max-height: 50vh; /* Prevent taking over entire screen */
        border-right: none;
        border-bottom: 1px solid #e0e0e0;
        display: flex;
        flex-direction: column;
    }
}
```

#### Results Container Mobile Optimization
```css
@media (max-width: 768px) {
    .results-container {
        display: block; /* Changed from display: none */
        flex: 1;
        overflow-y: auto;
        max-height: 30vh; /* Limit height to keep map visible */
        min-height: 100px; /* Ensure minimum visibility */
    }
}
```

#### Stats Container Simplification
```css
.stats-container {
    background: #f8f9fa;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #e0e0e0;
}

/* Hide technical stats on all devices */
.stats-item.technical {
    display: none;
}
```

### 2. HTML Structure Updates

#### Simplified Stats Container
```html
<div class="stats-container">
    <div class="stats-item">
        <span class="stats-label">Total Churches:</span>
        <span class="stats-value" id="totalChurches">Loading...</span>
    </div>
    <!-- Remove "With Coordinates" and "Geocoding Rate" items -->
</div>
```

#### Enhanced Results Container
```html
<div class="results-container" id="resultsContainer">
    <div class="results-header" style="display: none;">
        <h4>Search Results</h4>
    </div>
    <div class="results-list" id="resultsList">
        <p style="color: #666; text-align: center; margin-top: 2rem;">
            Search for a location to see nearby churches
        </p>
    </div>
</div>
```

### 3. Mobile Search Results Display

#### Result Item Mobile Styling
```css
@media (max-width: 768px) {
    .result-item {
        padding: 0.75rem;
        border-bottom: 1px solid #eee;
        cursor: pointer;
        transition: background-color 0.2s ease;
    }
    
    .result-item:hover {
        background-color: #f8f9fa;
    }
    
    .result-item:last-child {
        border-bottom: none;
    }
    
    .result-distance {
        font-size: 0.8rem;
        color: #666;
        font-weight: 500;
    }
    
    .result-name {
        font-weight: 600;
        color: #333;
        margin-bottom: 0.25rem;
    }
    
    .result-address {
        font-size: 0.85rem;
        color: #666;
        line-height: 1.3;
    }
}
```

## Data Models

No data model changes are required. This is purely a frontend UI/UX improvement.

## Error Handling

### Mobile Viewport Constraints
- **Minimum Heights**: Ensure search results have minimum visibility
- **Maximum Heights**: Prevent search panel from overwhelming the map
- **Overflow Handling**: Proper scrolling for long result lists

### Responsive Breakpoints
- **768px and below**: Primary mobile layout
- **480px and below**: Compact mobile layout with reduced padding
- **Landscape orientation**: Maintain usability in both orientations

## Testing Strategy

### Mobile Testing Requirements
1. **Device Testing**: Test on actual mobile devices (iOS Safari, Android Chrome)
2. **Orientation Testing**: Verify functionality in both portrait and landscape
3. **Search Flow Testing**: Complete search-to-selection flow on mobile
4. **Viewport Testing**: Test various screen sizes (320px to 768px width)

### Specific Test Cases
1. **Search Results Visibility**: Verify results are visible and scrollable on mobile
2. **Stats Simplification**: Confirm only "Total Churches" is displayed
3. **Touch Interaction**: Ensure search results are easily tappable
4. **Map Visibility**: Confirm map remains visible and usable after search

### Browser Compatibility
- iOS Safari (primary mobile browser)
- Android Chrome (primary Android browser)
- Mobile Firefox (secondary)
- Samsung Internet (secondary)

## Implementation Notes

### CSS-Only Solution
This improvement can be implemented entirely through CSS changes, making it low-risk and easily reversible.

### Progressive Enhancement
The changes maintain full desktop functionality while enhancing mobile experience.

### Performance Considerations
- No JavaScript changes required
- Minimal CSS additions
- No impact on loading performance