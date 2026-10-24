# Takumi bearing assembly playground

Interactive React Three Fiber frontend with a hands-on bearing assembly mission, exploded view, two fixed scenarios, three multiple-choice questions and authored learning notes. Pick and place components, equip tools, align the shaft, press the bearing, secure bolts and use the handwheel. Twelve checkpoints award up to 600 XP and gate successful completion.

```powershell
npm install
npm run dev
```

Open the local URL printed by Vite. Follow the [demo workflow and checkpoint list](markdowns/globals/Takumi_Bearing_Assembly_Demo_Workflow.md). Inspect each of the four parts and request the observation to unlock the tray. Use pick-and-place targets or drag tray parts onto the workbench. Equip the alignment jig, bearing sleeve, hex key and handwheel for their matching tasks. Answer all three questions before making the final release or escalation decision. Change scenarios or learning mode using the selectors; confirmation starts a new attempt. Progress is restored from browser local storage by replaying validated actions. Gameplay uses storage version 2, so older inspection-only attempts start fresh.

```powershell
npm test
npm run build
npm run test:e2e
```

Browser tests require Playwright Chromium (`npx playwright install chromium`). To use an existing Chromium installation, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to its executable path. Tests start the Vite server automatically and exercise full flows, persistence, assessment display, mobile layout and the WebGL fallback. Screenshots are written under `test-results/`.

## Implementation boundaries

This request implements the frontend of the [Playground plan](markdowns/globals/Takumi_Apprentice_Playground_Implementation_Plan.md). Vite provides a small standalone demo instead of the planned shared Next.js application. No backend, real expert evidence, API authentication, private server rubrics, media playback or Viva service is connected. All fixture content is visible in the client bundle; assessment mode conceals feedback in the interface but is not a secure examination system. Notes are illustrative and await instructor review. The model demonstrates authored movement and decisions, not mechanical physics or practical certification.

`src/simulation.ts` contains the attempt state machine and frozen authored content. `src/workshop.ts` controls placement, tools, detents, pressing, bolt order and rotation. `src/mission.ts` derives the twelve checkpoints and XP. `src/persistence.ts` restores validated action history rather than trusting stored scores. `src/components/AssemblyScene.tsx` owns the 3D view and equivalent schematic fallback. All assets are procedural and require no remote downloads at runtime. IDs, question order, outcomes and scores are fixed for the same input sequence; camera movement and animation timing do not affect training results.

Work was divided among agents for simulation and unit tests, the 3D environment, browser integration tests, and frontend integration.

## UI redesign progress

The workspace uses a full-width module header, an off-white/grey palette with restrained green accents, and a compact engineering workbench. Desktop panels share the available viewport height, with internal scrolling for longer instructions, component tools, and checkpoint lists. Scenario and progress widgets share a compact row. Save state, practice notes, feedback, rewards, and warnings are contained in one aligned bottom status panel. Small screens use a responsive vertical layout. Learning tabs support arrow keys, Home, and End. The procedural 3D scene renders on interaction and while parts animate, then rests when idle.

Design references: [IBM Carbon UI shell](https://v10.carbondesignsystem.com/components/UI-shell-header/usage/) for persistent product navigation, [SAP Fiori page structure](https://www.sap.com/design-system/fiori-design-web/v1-142/discover/sap-products/sap-s4hana-only/best-practices-for-designing-sap-fiori-apps) for compact page context and work areas, and [Autodesk Fusion](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-THE-FUSION-INTERFACE.htm) for grouped tools around an assembly canvas.

The browser suite covers full mission flows, header module selection, inspection shortcuts, keyboard expansion of checkpoints, desktop viewport containment, internal panel scrolling, mobile overflow, and the WebGL fallback. Use `PLAYWRIGHT_CHROMIUM_EXECUTABLE` when running against an installed Chrome browser.
