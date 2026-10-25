# Tacit knowledge extraction review

## Findings

The admin upload flow uses `StudioAgents` in `takumi-backend/app/ai/studio_analysis.py`, orchestrated by `studio_analysis_service.analyze`. This is separate from the older background video worker and its `video_extraction_v1.py` prompt. Changing only that worker prompt would not improve the admin diagnosis.

The uploaded recording is attached to the observation call. Subsequent extraction and critique calls consume those observations, the saved course script, and optionally saved expert notes. They do not independently inspect the video.

The previous course extraction had a two-unit limit, which compressed procedural detail. It proposed exact source extracts but did not return structured learning gaps, suggested explanations, or actionable expert questions about missing reasoning. Its approval, source-version checks, revision checks, and immutable release publication were already present.

## Changes

- Course extraction supports up to twelve meaningful units in demonstrated order. Approval supports up to sixty field patches, matching twelve units with five fields each. The model output budget has increased accordingly.
- Observation instructions explicitly request alignment adjustments, changes of grip or tool orientation, pauses, corrections, checks, comparisons, decision conditions, and exceptions. Hidden reasons and sensations must remain unknown.
- Extraction returns structured gaps for cues, interpretation, decisions, and exceptions. Each gap has a source anchor, missing explanation, optional exact source fix, and a neutral expert question. Server validation rejects unsupported source anchors and fixes and preserves uncertainty qualifiers.
- A supported fix becomes a normal selectable field patch. Gap cards link that fix to its patch and display video intervals where the anchor maps to a video observation.
- Saving selected units creates pending clarifications for their unanswered gaps. The existing review workflow can attach an expert answer to a knowledge field. Publishing requires resolving pending questions or explicitly deferring them as unknown. Selecting source patches never supplies a fabricated answer to a question.
- Gap insights remain in the diagnosis history. Selected approved field content reaches the active release and the apprentice course through the existing publication path. Unreviewed diagnosis commentary is not added to approved course content.

## Review workflow

1. Upload the course recording and optionally save its transcript in the admin panel.
2. Run AI diagnosis using uploaded course content.
3. Review the nuances and learning gaps, source intervals, and proposed field patches.
4. Save selected extracts to draft to answer expert questions in Review, or add expert notes and rerun diagnosis.
5. Evaluate and publish the reviewed revision. If publishing the diagnosis directly, unanswered questions require explicit deferral.

## Validation and limits

The frontend production build completed. Static backend lint and formatting checks cover the changed Python modules. No test suite or live Gemini extraction was run for this change. Restart the backend and run a new diagnosis to generate gap insights; historical runs retain their original results.

The observer's descriptions are AI observations, not independently verified transcripts. Exact-quote checks establish consistency with supplied text, not the physical truth of a video interpretation. Observations can still miss events, and no completeness or mechanical correctness guarantee is made. Human review remains necessary. Twelve units and twenty observation intervals remain bounded limits.

The existing course-source mode proposes replacement draft content. Review the complete proposed sequence before approving replacement. The published release stays unchanged until explicit approval.
