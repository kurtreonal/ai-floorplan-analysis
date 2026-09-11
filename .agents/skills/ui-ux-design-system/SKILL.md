---
name: ui-ux-design-system
description: >-
  Design system guidelines, UI/UX aesthetics, and interactive component patterns for
  VED Electrical Services. Use when styling 2D/3D canvas interfaces, building toolbars,
  floating inspectors, dark-mode glassmorphic cards, responsive panels, and micro-animations
  using Vanilla CSS and React.
---

# VED Electrical Services — UI/UX Design System

This skill defines the visual language, design tokens, component anatomy, and micro-interaction patterns for the VED Electrical Services web platform.

---

## 1. Core Visual Principles

1. **Rich & Professional Engineering Aesthetic**: The interface must look modern, high-precision, and technical without feeling cluttered or overwhelming. Avoid raw default browser controls or plain primary colors.
2. **Curated HSL Color Tokens**: Deep slate backgrounds, frosted-glass floating layers, high-contrast typography, and purposeful electrical status accents.
3. **Responsive & Dynamic Feedback**: Hover micro-interactions, subtle borders, tactile button states, and smooth transitions that keep the user confident during editing.
4. **Vanilla CSS Architecture**: Build reusable CSS utility tokens and component classes in `index.css` and scoped component CSS. Avoid TailwindCSS unless explicitly directed.

---

## 2. Design Tokens & Color Palette

Add and reference these CSS custom properties in `index.css`:

```css
:root {
  /* Surface & Background Colors */
  --ved-bg-primary: #0b0f19;       /* Deep obsidian canvas background */
  --ved-bg-surface: #111827;       /* Card and sidebar background */
  --ved-bg-panel: rgba(17, 24, 39, 0.85); /* Frosted glass panel */
  --ved-bg-elevated: #1f2937;      /* Hover and dropdown surfaces */
  --ved-bg-border: #374151;        /* Structural borders */
  --ved-bg-border-subtle: #1f2937; /* Subtle divider lines */

  /* Electrical & Functional Accents */
  --ved-accent-blue: #3b82f6;      /* Primary active action / selections */
  --ved-accent-blue-glow: rgba(59, 130, 246, 0.25);
  --ved-accent-cyan: #06b6d4;      /* Measurement & scale guides */
  --ved-accent-emerald: #10b981;   /* Verified & approved states */
  --ved-accent-amber: #f59e0b;     /* Needs review / warnings */
  --ved-accent-rose: #ef4444;      /* Rejections, errors, high voltage */

  /* Text & Typography Colors */
  --ved-text-primary: #f9fafb;     /* High-contrast headings and labels */
  --ved-text-secondary: #9ca3af;   /* Metadata and descriptions */
  --ved-text-muted: #6b7280;       /* Disabled and placeholder text */

  /* Shadows & Glassmorphic Blur */
  --ved-shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.4);
  --ved-shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.5), 0 2px 4px -2px rgba(0, 0, 0, 0.5);
  --ved-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.6), 0 4px 6px -4px rgba(0, 0, 0, 0.6);
  --ved-glass-blur: blur(12px);

  /* Transitions & Radii */
  --ved-radius-sm: 6px;
  --ved-radius-md: 10px;
  --ved-radius-lg: 16px;
  --ved-transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

## 3. Floor Plan Editor Layout Anatomy

The editing workspace consists of four synchronized layout regions:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Header: Project Title, Floor Selector, Mode Switch (2D / 3D / Split), Save   │
├─────────┬─────────────────────────────────────────────────────────┬─────────┤
│ Tool    │ Center Workspace:                                       │ Right   │
│ Palette │ 2D Konva Stage or 3D R3F Canvas                         │ Inspector│
│         │                                                         │         │
│ • Select│ [Floating Viewport HUD: Zoom In/Out, Reset, Fit Page]   │ • Props │
│ • Wall  │                                                         │ • Layers│
│ • Room  │                                                         │ • Legend│
│ • Device│                                                         │ • Cost  │
│ • Route │                                                         │         │
├─────────┴─────────────────────────────────────────────────────────┴─────────┤
│ Footer / Status Bar: Coordinates (m), Selected Object ID, Scale (px/m)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Floating Glassmorphic Component Patterns

### Floating Toolbar

```css
.ved-floating-toolbar {
  position: absolute;
  top: 1.5rem;
  left: 1.5rem;
  z-index: 20;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.5rem;
  background: var(--ved-bg-panel);
  backdrop-filter: var(--ved-glass-blur);
  border: 1px solid var(--ved-bg-border);
  border-radius: var(--ved-radius-md);
  box-shadow: var(--ved-shadow-lg);
}

.ved-tool-btn {
  width: 2.5rem;
  height: 2.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--ved-radius-sm);
  color: var(--ved-text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: var(--ved-transition);
}

.ved-tool-btn:hover {
  color: var(--ved-text-primary);
  background: var(--ved-bg-elevated);
}

.ved-tool-btn.active {
  color: var(--ved-text-primary);
  background: var(--ved-accent-blue);
  box-shadow: 0 0 12px var(--ved-accent-blue-glow);
}
```

### Property Inspector Drawer

```css
.ved-property-inspector {
  position: absolute;
  top: 1.5rem;
  right: 1.5rem;
  bottom: 1.5rem;
  width: 22rem;
  z-index: 20;
  background: var(--ved-bg-panel);
  backdrop-filter: var(--ved-glass-blur);
  border: 1px solid var(--ved-bg-border);
  border-radius: var(--ved-radius-lg);
  box-shadow: var(--ved-shadow-lg);
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow-y: auto;
}
```

---

## 5. Micro-Animations & Interaction Feedback

1. **Selection Glow**: When an item is clicked, apply a subtle pulsing border or box-shadow:
   ```css
   @keyframes pulseGlow {
     0%, 100% { box-shadow: 0 0 0 1px var(--ved-accent-blue); }
     50% { box-shadow: 0 0 12px var(--ved-accent-blue-glow); }
   }
   ```
2. **Snapping Feedback**: When dragging near a wall, show an emerald `#10b981` snapping indicator ring and subtle magnetic feel.
3. **Status Badges**:
   - `detected`: Amber warning badge (`#f59e0b` bg-subtle, text).
   - `verified` / `accepted`: Emerald success badge (`#10b981`).
   - `rejected` / `deleted`: Rose danger badge (`#ef4444`).
   - `manual`: Blue accent badge (`#3b82f6`).

---

## 6. Keyboard & Mouse UX Standards

- **Spacebar + Drag** or **Middle Mouse Click + Drag**: Pan canvas.
- **Mouse Wheel / Trackpad Pinch**: Smooth zoom centered at cursor.
- **Escape**: Deselect active item or cancel current drawing tool.
- **Delete / Backspace**: Delete selected symbol or wall (with confirmation toast).
- **Ctrl+Z / Ctrl+Shift+Z**: Undo / Redo geometry edits.
