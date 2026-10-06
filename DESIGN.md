# Vyapar Saarthi AI — Design System & Frontend Architecture (DESIGN.md)

> **Current Working Condition**: Single-Page Server-Rendered Application ([app/templates/index.html](file:///d:/projectss/Vypaar%20sarthi/app/templates/index.html))  
> **Target Audience**: Indian Kirana & Small Retail Merchants (Multilingual, Non-technical, High-sunlight counters)  
> **Brand Identity**: Warm, trustworthy, voice-first Indian business companion. Devanagari wordmark: **व्यापार सारथी**.

---

## 1. Design Principles & UX Goals

1. **Kirana-First Accessibility**: Clean, high-contrast light theme (`#F7F8FA` page background with pure `#FFFFFF` elevated cards) designed for bright ambient light at retail shop counters.
2. **Zero-Typing Voice Priority**: Large, prominent voice billing action button and microphone interactions with instant Hinglish visual and audio confirmation.
3. **Intuitive Dual Layout**:
   - **Desktop (POS View)**: Fixed 240px navigation sidebar, sticky top header with multi-store switcher, 4 KPI cards, full product tables, and instant billing cart.
   - **Mobile (Counter View)**: Sticky store selector header, quick-action tiles, large voice billing banner, and a persistent 5-tab bottom navigation bar (`Home`, `Inventory`, `Billing FAB`, `Khata`, `Sales History`, `AI Assistant`).
4. **Instant Semantic Recognition**: Predictable color coding across inventory stock levels, payment badges, and transaction alerts.
5. **Multilingual Typography**: Native support for Devanagari script (Hindi/Marathi) alongside English numerals and Indian Rupee (`₹`) formatting.

---

## 2. Color Palette & CSS Variables

The core color system is defined in `:root` of [app/templates/index.html](file:///d:/projectss/Vypaar%20sarthi/app/templates/index.html):

| Token | Value | Semantic Role |
| :--- | :--- | :--- |
| `--primary` | `#1A6FFF` | Primary brand blue, sidebar icons, primary submit buttons, active states |
| `--primary-dark` | `#1558CC` | Hover and active states for primary blue controls |
| `--primary-light`| `#EFF6FF` | Soft blue tint for active navigation items and highlights |
| `--orange` | `#FF6B00` | Signature energy orange, Voice Billing hero banner, microphone action button |
| `--orange-dark` | `#E05A00` | Active/hover state for voice billing buttons |
| `--green` | `#00B96B` | Paid transactions, positive revenue, in-stock inventory indicators |
| `--green-light` | `#DCFCE7` | Background tint for Paid status pills and in-stock badges |
| `--amber` | `#F59E0B` | Pending Udhaar credit, low-stock warnings, clarification alerts |
| `--amber-light` | `#FEF3C7` | Background tint for Pending Khata and low-stock pills |
| `--red` | `#EF4444` | Out-of-stock items, voided transactions, destructive actions |
| `--red-light` | `#FEE2E2` | Background tint for Out-of-Stock and critical alert pills |
| `--bg` | `#F7F8FA` | Neutral soft gray canvas background |
| `--surface` | `#FFFFFF` | Cards, modals, drawers, sidebar, and navbar containers |
| `--surface2` | `#F0F2F6` | Secondary input fill and subtler card containers |
| `--border` | `#E2E8F0` | Dividers, card outlines, table borders, and input borders |
| `--text` | `#111827` | Primary dark headings, body text, and numeric values |
| `--text-secondary`| `#6B7280` | Subtitles, helper text, units, and timestamps |
| `--text-muted` | `#9CA3AF` | Placeholders, inactive state icons |

---

## 3. Typography Hierarchy

- **Headlines & Display**: `'Plus Jakarta Sans'`, sans-serif (Weights: 600, 700, 800)
- **Body & Multilingual Text**: `'Noto Sans'`, sans-serif (Weights: 400, 500, 600)
- **Tabular Data & Numbers**: `'Inter'`, sans-serif (Weights: 400, 500, 600)

### UI Font Weights & Sizing:
- **Dashboard Metric Numbers**: `24px – 28px` / Bold 700 / Tabular Numerals
- **Section Headers**: `20px – 22px` / SemiBold 700
- **Card Titles & Item Names**: `15px – 16px` / SemiBold 600
- **Body & Table Cells**: `13px – 14px` / Regular 400 or Medium 500
- **Badges, Pills & Captions**: `11px – 12px` / Medium 500 or SemiBold 600

---

## 4. Layout Architecture

### A. Desktop Viewport (≥ 992px)
- **Sidebar (`.sidebar`)**: Fixed left position, width `240px`, contains brand logo, store name indicator, and navigation links:
  - 🏠 Dashboard
  - 🎙️ Voice Billing
  - 📦 Inventory
  - 👥 Customers / Khata
  - 🏪 My Stores / Outlets
  - 📜 Sales History
  - 🤖 AI Assistant
- **Header (`.main-header`)**: Displays greeting (`Good morning, Ramesh! 👏`), store selector dropdown with `+ Add Store`, and quick `Refresh` action.
- **Content Area**: Dynamic views switched via `showSection(...)` without full-page reloads.

### B. Mobile Viewport (< 992px)
- **Top Bar**: Sticky store name, outlet switcher dropdown, and sync button.
- **Voice Billing Hero**: Prominent saffron orange card with microphone CTA (*"Start Voice Billing — Speak in Hindi, English, or Marathi"*).
- **Quick Action Grid**: 4 touch-friendly cards (`Add Product`, `Inventory`, `Khata`, `Ask AI`).
- **Bottom Navigation Bar (`.bottom-nav`)**: Fixed at bottom, height `68px`, with 5 touch tabs:
  - `Home` (`#section-dashboard`)
  - `Inventory` (`#section-inventory`)
  - `Billing FAB` (Center elevated orange microphone button for voice billing)
  - `Khata` (`#section-khata`)
  - `History` (`#section-sales`)
  - `AI` (`#section-assistant`)

---

## 5. Key UI Components & Interactions

1. **Dashboard KPI Grid**:
   - **Today's Revenue**: Live aggregate in `₹` with trend indicator.
   - **Bills Today**: Count of confirmed transactions.
   - **Pending Khata**: Outstanding Udhaar sum across all customers.
   - **Low Stock Alerts**: Count of items at or below reorder threshold.
2. **Interactive Voice Billing Screen**:
   - Dual-engine speech input: Browser Web Speech API (zero-config local transcription) with server-side Gemini audio transcription fallback.
   - Real-time animated audio visualizer / pulsing mic states: *Idle*, *Listening*, *Processing*, *Item Matched*.
   - Live Bill Cart: Quantity steppers (`+` / `-`), unit price displays, subtotal, and tax/discount calculations.
   - Payment toggle: Single-tap switch between `Cash / Paid` and `Udhaar (Credit)`.
3. **Modals & Drawers**:
   - **Add / Edit Product Modal**: Full form with barcode/SKU, categories, selling price, cost price, and stock levels.
   - **Khata Customer Drawer**: Customer ledger history, statement breakdown, and WhatsApp payment reminder generator.
   - **Receipt Preview Modal**: Clean printable thermal-style invoice preview with WhatsApp and SMS share actions.
   - **CSV Bulk Import**: 2-step modal with format validation preview before database commit.
