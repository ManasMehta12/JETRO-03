# Takumi Bearing Assembly Demo Workflow

The learner builds an authored bearing assembly from a component tray, uses simulated tools, and completes a fixed set of twelve checkpoints. All parts, actions, observations, questions, XP awards and outcomes are deterministic. This is a training puzzle; it does not calculate physical fit or prescribe a real machine assembly procedure.

Run `npm run dev` at the repository root and open the printed local URL. Select **A clean assembly** and **Guided practice** for the first demonstration. If changing scenario or mode, confirm **Start fresh**. Progress is saved automatically in this browser.

## Checkpoints that complete the simulation

| Number | Checkpoint | Required learner interaction | Award |
| --- | --- | --- | --- |
| 1 | Inspect the component kit | Select the base, housing, shaft and bearing in turn; record each inspection | 50 XP |
| 2 | Read the observation card | Request the scripted observation after all four inspections | 50 XP |
| 3 | Anchor the base | Pick up or drag the base from the tray and place it on the workbench target | 50 XP |
| 4 | Locate the housing | Pick up the housing and mount it on the installed base | 50 XP |
| 5 | Align and insert shaft | Equip the alignment jig, nudge the indicator from +2 to 0, pick up the shaft and insert it | 50 XP |
| 6 | Position the bearing | Equip the bearing sleeve, pick up the bearing and place it on the shaft | 50 XP |
| 7 | Seat the bearing | Use the sleeve for three discrete press increments | 50 XP |
| 8 | Secure the housing | Equip the hex key and tighten the four labeled bolts in the authored A, C, B, D sequence | 50 XP |
| 9 | Check rotation | Equip the handwheel and perform three quarter-turn checks | 50 XP |
| 10 | Verify the assembly | Confirm verification after all placement and tool checkpoints are complete | 50 XP |
| 11 | Complete the knowledge check | Submit one answer to each of the three fixed questions | 50 XP |
| 12 | Make a supported decision | Release the clean assembly, or escalate the uncertain-fit variation after reviewing its scripted result | 50 XP |

**Completion rule:** all twelve checkpoints must be checked. A successful mission earns **600 XP**. The eight physical build checkpoints contribute 400 XP. Repeating a completed step cannot earn extra XP. Question correctness is reported separately from answering all three questions; XP records workflow completion, not mechanical competence.

The release and escalation buttons remain locked until inspection, evidence, physical build, verification and all questions are finished. A wrong final decision ends the attempt with the final checkpoint incomplete. Restart to practise again; the interface must not call that a successful mission.

## Guided demonstration sequence

1. Select each component using the labeled component cards. Press **Inspect component** four times, once for each part. Camera motion and highlighting do not record inspections.
2. Press **Request observation**. The component tray and tool rack unlock.
3. Press **Pick up Base plate**, then **Mount base**, or click the matching gold target in the scene. Repeat for the housing using **Mount housing**. Alternatively drag the tray button onto the workbench to attempt placement.
4. Equip **Alignment jig**. Press **Nudge left** twice to center the five-detent indicator. Pick up the drive shaft and press **Insert shaft**. The visible preview follows the indicator and snaps to the authored aligned position.
5. Equip **Bearing sleeve**. Pick up the ball bearing and press **Place bearing**. Press **Press bearing** three times. The bearing moves to a new fixed seating position on each increment.
6. Equip **Hex key**. Use the scene bolts or task controls to tighten **A**, **C**, **B**, then **D**. The next bolt is highlighted and secured bolts change appearance.
7. Equip **Handwheel**. Press **Turn shaft** three times, or click the handwheel target. Each accepted check rotates the modeled shaft by a fixed quarter turn.
8. Press **Verify assembly**. The build is now complete, and the observation card shows the scenario's final scripted check result.
9. Open **Knowledge check**, answer the three fixed questions, and return to **Practice**. The standard demo answers are the explicit inspection action, authored seating requiring verification, and escalation when evidence is missing.
10. For **A clean assembly**, press **Release assembly**. Show **12 / 12 checkpoints**, **600 / 600 XP**, and the mission-complete banner. Procedure, judgment and knowledge scores remain separate.

## Changed condition and recoverable mistakes

Run **The uncertain fit** through the same assembly workflow. Its final check remains inconclusive. Choosing **Escalate for review** completes the final checkpoint; releasing it records a critical error and leaves the mission incomplete.

Demonstrate one recoverable mistake before finishing: pick the housing while the base target is active, try alignment with the wrong tool, or try bolt B before bolt A. The interface explains the prerequisite, leaves checkpoints and XP unchanged, and lets the learner correct the action. Camera rotation, tool switching and part selection do not earn XP.

## Interaction alternatives and persistence

The 3D scene supports component selection, labeled placement targets, sleeve pressing, bolt clicks and handwheel use. The component tray also supports drag and drop onto the workbench. Equivalent labeled buttons provide keyboard and touch access. If WebGL is unavailable, the schematic and the same task controls preserve the workflow.

Reload partway through alignment or seating to demonstrate restoration from validated action history. **Restart exercise** asks for confirmation before replacing the saved attempt. The gameplay uses storage version 2; older inspection-only demo progress is not migrated into this changed workflow.

Assessment mode uses the same physical rules and checkpoint gates while withholding explanatory feedback and field notes until the final decision. This remains a local frontend demo whose fixtures are inspectable in the browser bundle.
