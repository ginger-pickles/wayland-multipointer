# Wayland Multi-Pointer Support (MPX for Wayland)

## Overview

A system to provide multiple independent pointer/keyboard pairs on Wayland, analogous to X11's MPX (Multi-Pointer X). Each pair has its own cursor and text insertion caret. Primary use case: one pointer captured by a fullscreen game while another remains free for other displays/applications.

## Problem Statement

```
Current Wayland:
┌─────────────────────────────────────────────────────────┐
│ Single pointer ──▶ Game grabs it ──▶ Entire system    │
│                                       loses pointer     │
└─────────────────────────────────────────────────────────┘

Desired:
┌─────────────────────────────────────────────────────────┐
│ Pointer A ──▶ Game (fullscreen, grabbed)               │
│ Pointer B ──▶ Other apps (free, usable)                │
│                                                         │
│ Both visible, same desktop, same session                │
└─────────────────────────────────────────────────────────┘
```

## Requirements

### Functional Requirements

1. **Multiple Pointers**
   - At least 2 independent cursor positions
   - Each cursor rendered on screen simultaneously
   - Each has independent focus (which window is "active")
   - Pointer grab by one app doesn't affect other pointers

2. **Multiple Keyboards**
   - At least 2 independent keyboard inputs
   - Each has independent text insertion caret/focus
   - Typically paired with a pointer (pointer A + keyboard A = seat A)

3. **Device Assignment**
   - Physical input devices (mice, keyboards) assigned to virtual seats
   - Persistent configuration (survives reboot)
   - Runtime switchable (move device between seats without restart)
   - Support for multiple physical devices
   - Nice-to-have: virtual/synthetic input splitting

4. **XWayland Compatibility**
   - Must work with X11 apps running under XWayland
   - Wine/Proton games are primary use case
   - Pointer grab via XWayland must be seat-scoped

5. **Conflict Resolution**
   - Single operator assumption: only one pointer active at a time
   - App responds to whichever pointer is currently providing input
   - No complex arbitration needed; idle pointers are simply idle

### Non-Functional Requirements

- Configuration via CLI or config file (minimum)
- GUI configuration (nice-to-have)
- Should not require application modification
- Performance: negligible overhead for cursor rendering

## Technical Context

### Wayland Architecture

```
┌─────────────┐      ┌──────────────────────────────────┐
│ Application │◀──▶│ Compositor (KWin, Mutter, etc.)  │
└─────────────┘      │                                  │
                     │ - Handles all input              │
┌─────────────┐      │ - Renders all output             │
│ Application │◀──▶│ - Manages wl_seat objects        │
└─────────────┘      │ - Implements Wayland protocol    │
                     └──────────────────────────────────┘
                                    ▲                    
                                    │                    
                     ┌──────────────┴──────────────┐     
                     │ Physical input devices      │     
                     │ (via libinput)              │     
                     └─────────────────────────────┘     
```

### Relevant Wayland Concepts

- **wl_seat**: Represents a group of input devices (pointer + keyboard)
- **wl_pointer**: Pointer device within a seat
- **wl_keyboard**: Keyboard device within a seat
- **Pointer grab**: App requests exclusive pointer input (e.g., for mouselook)

### X11 MPX (Reference Implementation)

X11's Multi-Pointer X (MPX) provides the model we're emulating:

```bash
# Create new master pointer/keyboard pair
xinput create-master "Aux"

# List devices
xinput list
# Shows: "Aux pointer" and "Aux keyboard" masters

# Attach physical device to a master
xinput reattach <device-id> "Aux pointer"
```

- Each master has independent cursor and focus
- Apps unaware of MPX still work (X server handles routing)
- Grab by one master doesn't affect others

## Proposed Architecture

### Option A: KWin Plugin/Script

```
┌──────────────────────────────────────────────────────┐
│ KWin                                                 │
│  ┌────────────────────────────────────────────────┐  │
│  │ Multi-Pointer Plugin                           │  │
│  │                                                │  │
│  │ - Creates additional wl_seat objects           │  │
│  │ - Routes physical devices to seats             │  │
│  │ - Manages per-seat cursor rendering            │  │
│  │ - Intercepts/scopes pointer grabs              │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  [Seat 0: Primary]  [Seat 1: Aux]                    │
│   - Mouse A          - Mouse B                       │
│   - Keyboard A       - Keyboard B                    │
│   - Cursor ●         - Cursor ○                      │
└──────────────────────────────────────────────────────┘
```

**Pros**: Integrated, uses existing KWin infrastructure
**Cons**: May require KWin core changes, KDE-specific

### Option B: Wrapper Compositor

```
┌─────────────────────────────────────────────────────────┐
│ MultiPointer Compositor (Weston-based or custom)        │
│                                                         │
│  Presents as Wayland compositor to KWin (nested)        │
│  Manages multiple seats internally                      │
│  Forwards to real compositor with seat routing          │
└─────────────────────────────────────────────────────────┘
                          │                                
                          ▼                                
┌─────────────────────────────────────────────────────────┐
│ KWin (host compositor)                                  │
│  Sees wrapper as single client                          │
└─────────────────────────────────────────────────────────┘
```

**Pros**: Compositor-agnostic, isolated development
**Cons**: Performance overhead, complexity, may not handle grabs correctly

### Option C: libinput Multiplexer + Compositor Patches

```
Physical devices
       │                          
       ▼                          
┌──────────────────┐              
│ multipointer-mux │  (New daemon)
│                  │              
│ Routes devices   │              
│ to virtual seats │              
└──────────────────┘              
       │                          
       ▼                          
┌──────────────────┐              
│ KWin (patched)   │              
│                  │              
│ Recognizes       │              
│ multiple seats   │              
└──────────────────┘              
```

**Pros**: Clean separation, potentially upstreamable
**Cons**: Requires compositor patches anyway

## Recommended Approach

**Start with Option A (KWin Plugin)** with fallback research into Option C.

### Phase 1: Proof of Concept
1. Study KWin source: seat handling, cursor rendering, grab logic
2. Determine if KWin scripting API sufficient, or need C++ plugin
3. Create hardcoded two-seat setup, verify cursors render
4. Test grab scoping with simple Wayland app

### Phase 2: Device Assignment
1. Implement libinput device → seat routing
2. Config file for persistent assignment
3. CLI tool for runtime reassignment
4. Test with actual multi-mouse setup

### Phase 3: XWayland Integration
1. Study how XWayland interacts with wl_seat
2. Ensure X11 apps (Wine games) see correct seat
3. Verify grab behavior through XWayland
4. Test with actual game (UT99 via Bottles)

### Phase 4: Polish
1. GUI configuration (KDE System Settings module)
2. Visual indicator of which seat is active
3. Documentation
4. Upstream discussion with KDE developers

## Research Starting Points

### KWin Source Code
- Repository: `https://invent.kde.org/plasma/kwin`
- Key directories:
  - `src/wayland/` - Wayland protocol implementation
  - `src/wayland/seat_interface.cpp` - Seat handling
  - `src/cursor.cpp` - Cursor rendering
  - `src/pointer_input.cpp` - Pointer input processing

### Wayland Protocol
- `wayland.xml` - Core protocol (wl_seat, wl_pointer, wl_keyboard)
- `xdg-shell.xml` - Window management
- `pointer-constraints-unstable-v1.xml` - Pointer grab/lock

### Related Projects
- **wlroots**: Modular Wayland compositor library (Sway uses it)
  - May have cleaner seat handling to study
  - `https://gitlab.freedesktop.org/wlroots/wlroots`

- **Weston**: Reference Wayland compositor
  - `https://gitlab.freedesktop.org/wayland/weston`

- **libinput**: Input device handling
  - `https://gitlab.freedesktop.org/libinput/libinput`

### Existing Discussions
- KDE Discuss: "Multi-Pointer or Multi-Cursor to use with Wayland?"
  - `https://discuss.kde.org/t/multi-pointer-or-multi-cursor-to-use-with-wayland/9742`

## Open Questions

1. **Hardware cursor limits**: GPUs typically support 1-2 hardware cursors. Software cursor fallback needed for additional pointers?

2. **Keyboard focus model**: Should keyboard focus follow pointer (click-to-focus per seat), or be independently assignable?

3. **Cross-seat interaction**: If pointer A drags a window and pointer B clicks it mid-drag, what happens? (Recommendation: undefined, user shouldn't do this)

4. **Hot-plugging**: When a new mouse is connected, which seat does it join?

5. **Upstream appetite**: Would KDE accept this feature? Worth discussing before major investment.

## Success Criteria

1. Two cursors visible simultaneously on desktop
2. Each cursor has independent window focus
3. Game (via XWayland/Wine) can grab one cursor
4. Other cursor remains fully functional
5. Physical mice assignable to specific cursors
6. Configuration persists across reboots

## Glossary

- **MPX**: Multi-Pointer X - X11's multi-pointer implementation
- **Seat**: Wayland concept for a group of input devices operated by one user
- **wl_seat**: Wayland protocol object representing a seat
- **Pointer grab**: Application's request for exclusive pointer input
- **XWayland**: X11 compatibility layer for Wayland
- **libinput**: Library for handling input devices on Linux
- **Compositor**: Program that combines window contents and handles input (KWin, Mutter, Sway)
