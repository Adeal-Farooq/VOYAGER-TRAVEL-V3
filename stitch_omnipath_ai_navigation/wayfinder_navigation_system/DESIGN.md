---
name: WayFinder Navigation System
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadada'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f3'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#454652'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f1f1f1'
  outline: '#767683'
  outline-variant: '#c6c5d4'
  surface-tint: '#4c56af'
  primary: '#000666'
  on-primary: '#ffffff'
  primary-container: '#1a237e'
  on-primary-container: '#8690ee'
  inverse-primary: '#bdc2ff'
  secondary: '#006e1c'
  on-secondary: '#ffffff'
  secondary-container: '#91f78e'
  on-secondary-container: '#00731e'
  tertiary: '#400001'
  on-tertiary: '#ffffff'
  tertiary-container: '#680002'
  on-tertiary-container: '#ff6555'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e0e0ff'
  primary-fixed-dim: '#bdc2ff'
  on-primary-fixed: '#000767'
  on-primary-fixed-variant: '#343d96'
  secondary-fixed: '#94f990'
  secondary-fixed-dim: '#78dc77'
  on-secondary-fixed: '#002204'
  on-secondary-fixed-variant: '#005313'
  tertiary-fixed: '#ffdad5'
  tertiary-fixed-dim: '#ffb4a9'
  on-tertiary-fixed: '#410001'
  on-tertiary-fixed-variant: '#930005'
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 30px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 32px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 24px
---

## Brand & Style
The design system is engineered for high-stakes urban navigation, prioritizing reliability, clarity, and a premium "Realistic and Attractive" aesthetic. The brand personality is authoritative yet helpful—acting as a sophisticated digital concierge for transit. 

The visual style blends **Modern Corporate** precision with **Glassmorphism**. High-fidelity map textures are paired with translucent overlays to maintain spatial context while providing data-rich insights. The emotional response should be one of "controlled confidence," where the user feels empowered by real-time data presented through a polished, professional lens.

## Colors
The palette is rooted in **Deep Transit Blue**, signaling institutional trust and stability. 

- **Primary & Secondary:** Use Deep Transit Blue for core branding, primary buttons, and active navigation states. Map Green and Alert Red are reserved strictly for semantic reliability markers (pins, scores, and status indicators).
- **Accents:** Electric Blue is used for "Active Path" polyline rendering and the "Current Location" pulsing glyph. Amber is utilized for transient warnings (traffic, delays).
- **Surfaces:** Backgrounds utilize a "Clean Surface White" for cards and "Soft Gray" for the interface foundation to ensure high contrast against map tiles.

## Typography
This design system utilizes **Inter** exclusively for its superior legibility in UI environments and its neutral, modern tone. 

- **Headlines:** Set with tight tracking and bold weights to establish immediate hierarchy for destination names and ETA headers.
- **Body:** Standardized on 16px for primary information to ensure readability while in motion.
- **Labels:** Used for metadata (distance, transit line numbers, and reliability percentages). All labels should use uppercase sparingly for category headers to maintain a professional, data-dense look.

## Layout & Spacing
The layout follows a **Fluid Grid** model centered around the map view. Information density is managed through a 4px baseline grid.

- **Safe Zones:** Top and bottom safe areas are reserved for the Floating Search Bar and the Navigation Pill.
- **Side Panels:** On desktop/tablet, the "Discovery" panel occupies a fixed 360px right-aligned slot. On mobile, this transforms into a bottom-sheet drawer.
- **Margins:** 16px standard margin for all floating UI elements from the edge of the screen to ensure they do not interfere with map controls or edge-gestures.

## Elevation & Depth
Elevation is the primary tool for distinguishing interface layers from the underlying map.

- **Glassmorphism:** All floating overlays (Search, Discovery Panel, Pills) use a `backdrop-filter: blur(20px)` with a semi-transparent white fill (`rgba(255, 255, 255, 0.8)`). 
- **Shadows:** Use extra-diffused "Ambient Shadows." A 15% opacity Deep Transit Blue tint is added to the shadow of the primary cards to create a subtle glow that ties the element to the brand color.
- **Z-Index:**
  - Level 1: Map markers and active paths.
  - Level 2: Segmented journey cards and Discovery panel.
  - Level 3: Search bar and Bottom Navigation Pill.

## Shapes
The design system adopts a **Rounded** aesthetic (0.5rem base) to balance professionalism with modern software trends.

- **Standard Components:** Buttons and input fields use the base 8px (0.5rem) radius.
- **Containers:** Large cards and the Discovery Panel use `rounded-xl` (24px) for a soft, premium feel.
- **Pills:** The bottom navigation and reliability badges use full-radius (capsule) styling to distinguish them as high-interaction or status-heavy elements.

## Components
Consistent styling of these key components ensures the "WayFinder" identity remains cohesive:

- **Dynamic Search Bar:** A floating element with a thin 1px border (`#E0E0E0`) and a glassmorphic background. It should include a leading search icon and a trailing "Voice" or "Filter" icon.
- **Bottom Navigation Pill:** A capsule-shaped container floating above the map. Active states are indicated by a Deep Transit Blue fill and white text/icon.
- **Segmented Journey Cards:** Visual timelines using "Walk -> Bus -> Metro" iconography. Use vertical or horizontal "steppers" with transit line colors (e.g., Metro Line Blue) to show transitions clearly.
- **Reliability Badges:** Circular or pill-shaped badges showing a 0-100 score. Scores > 80 use Map Green with a subtle outer glow; scores < 40 use Alert Red.
- **Interactive Map Markers:** Pins that scale up by 15% on hover/tap. The "Active" marker includes a pulsing Electric Blue ring to indicate the user's specific target.
- **Discovery Panel:** Features AI summaries using a slightly tighter line-height for dense information, separated by thin dividers.