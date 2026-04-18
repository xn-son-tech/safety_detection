# Database Design Specification (Section 3a Aligned)

## 1) Document Purpose

This document defines the production-oriented database design for the PPE safety detection system, aligned with the 4-module pipeline in `docs_section_3a_analysis.md`:

1. Pre-processing (SSIM, blur filtering, CLAHE)
2. Feature extraction and inference (YOLOv8 + tracking)
3. Rule engine and post-processing (dynamic head region + IoU)
4. Alert validation and evidence persistence

Primary schema source:
- `agent_output/safety_detection_schema.dbml`

---

## 2) Scope and Design Principles

### 2.1 Scope
- Real-time camera stream ingestion (RTSP-oriented architecture).
- Multi-criteria PPE and safety enforcement: **criteria are data-driven** (helmet today; reflective vest, gloves, and others tomorrow) while **YOLO continues to emit detection classes**; new behavior is added primarily via **`rule_definitions`** and **camera assignments**, not new base tables.
- Detection and tracking: any class names the active `model_versions.classes` JSON exposes (e.g. `person`, `helmet`, `reflective_vest`, `glove`, …).
- Violation confirmation through sliding-window voting (parameters may vary per rule/criterion).
- Evidence storage for audit/review workflows.
- Alert delivery traceability.

### 2.2 Principles
- Preserve runtime-critical decisions in memory/cache, persist only what is needed for audit and analytics.
- Keep tables normalized for core entities (`sites`, `cameras`, `model_versions`, `safety_criteria`, `rule_definitions`, `violations`).
- Record enough per-frame/per-track metadata to explain why a violation was triggered or ignored.
- **Extensibility:** add a row to `safety_criteria`, versioned logic in `rule_definitions.definition` (JSON), and enable per camera in `camera_criterion_assignments`. Disabling a criterion is `is_enabled = false` or `safety_criteria.is_active = false` (global catalog off).

---

## 3) End-to-End Data Flow Mapping (3a)

1. Camera frames are ingested and associated with a `processing_runs` session.
2. Pre-processing metrics are recorded in `frame_preprocessing_logs`.
3. Valid frames are inferred by model, producing `detections`.
4. Rule engine evaluates **each enabled criterion** for the camera (from `camera_criterion_assignments`) using the assigned or default `rule_definitions` row; per-frame/per-track state is recorded in `rule_evaluations`.
5. Confirmed violations are persisted in `violations` with `criterion_id` and optional `rule_definition_id`.
6. Cropped evidence images and metadata are stored in `violation_evidences`.
7. Notifications are tracked in `alerts`.
8. Camera operational anomalies are logged in `camera_health_logs`.

---

## 4) Entity Overview

- `sites`, `zones`, `cameras`: physical deployment hierarchy.
- `safety_criteria`: catalog of enforceable criteria (stable `code`, display name, default severity, global on/off).
- `rule_definitions`: versioned rule packs per criterion; **`definition` JSON** binds YOLO class names to geometry/logic (IoU targets, anchor class such as `person`, voting window overrides, etc.).
- `camera_criterion_assignments`: which criteria apply to which camera; optional per-camera rule override.
- `model_versions`: model registry and active threshold reference.
- `processing_runs`: stream processing session metadata and config snapshots.
- `frame_preprocessing_logs`: frame quality decisions before inference.
- `detections`: per-frame model outputs and tracker IDs.
- `rule_evaluations`: per-criterion, per-track rule-engine decisions and voting state.
- `violations`: confirmed business events (**one row per criterion × track × episode** as designed by your runtime).
- `violation_evidences`: immutable evidence pointers and bbox metadata.
- `alerts`: delivery attempts and response payloads.
- `camera_health_logs`: operational health events.

---

## 5) Table-Level Specification

### 5.1 `safety_criteria`
Purpose:
- Canonical list of safety/PPE criteria the platform understands.

Key fields:
- `code` (unique): stable identifier used in APIs and reports (`NO_HELMET`, `NO_REFLECTIVE_VEST`, …).
- `is_active`: global enable for new assignments; existing historical data remains valid via FK.

Why:
- Adding a new criterion is primarily an **insert**, not a migration.

### 5.2 `rule_definitions`
Purpose:
- Versioned rule configuration per criterion. The rule engine reads `definition` JSON; schema of that JSON is owned by the application (document in your rule-engine spec).

Key fields:
- `criterion_id`, `code`, `version`, `is_default`, `is_active`, `definition`.

Why:
- **Change rules without DB migrations:** ship new `version` rows and flip `is_default` / assignments.

Recommended JSON keys (illustrative, not enforced by SQL):
- `anchor_class`, `equipment_classes`, `iou_mode`, `min_iou`, `vote_window`, `vote_threshold`, `head_region_policy` (helmet-only), `torso_region_policy` (vest), etc.

### 5.3 `camera_criterion_assignments`
Purpose:
- Turn criteria on/off per camera and optionally pin a specific `rule_definitions` row.

Key fields:
- `camera_id`, `criterion_id`, `is_enabled`, `rule_definition_id` (nullable).

Why:
- Matches real sites where gate A enforces helmet+vest and gate B only helmet.

### 5.4 `processing_runs`
Purpose:
- Trace each processing session and its runtime config.

Key fields:
- `camera_id`, `model_version_id`
- `stream_started_at`, `stream_ended_at`
- `status` (`running|success|failed|stopped`)
- `config_snapshot` (thresholds, voting, cooldown, tracker settings)

Why:
- Enables reproducibility and debugging when outcomes differ across runs.

### 5.5 `frame_preprocessing_logs`
Purpose:
- Persist pre-inference quality checks and frame drop reasons.

Key fields:
- `ssim_score`, `laplacian_var`, `clahe_applied`
- `quality_state` (`passed|dropped_glitch|dropped_blur|dropped_other`)
- `drop_reason`

Why:
- Provides auditable evidence for dropped frames and stream quality behavior.

### 5.6 `detections`
Purpose:
- Persist model and tracker output per frame.

Key fields:
- `run_id`, `camera_id`, `frame_ts`, `frame_seq`
- `track_id`, `class_name`, `confidence`
- Bounding box coordinates and optional metadata (`extra`)

Why:
- Supports explainability, replay analysis, and rule-debug traceability.

### 5.7 `rule_evaluations`
Purpose:
- Store rule-engine decisions before final violation confirmation, **scoped by criterion**.

Key fields:
- `criterion_id`, `rule_definition_id`, `rule_code`
- `vote_window`, `vote_positive`, `vote_negative`
- `decision` (`safe|danger|cooldown_skip|insufficient_evidence`)
- `primary_iou` (criterion-dependent), `aspect_ratio`, `details`

Why:
- Separates "model says" from "business rule decides", and supports **multiple parallel criteria** on the same track.

### 5.8 `violations`
Purpose:
- Store confirmed incidents as the canonical business event **per criterion**.

Key fields:
- `criterion_id`, `rule_definition_id`
- `started_at`, `confirmed_at`, `ended_at`
- `status`, `cooldown_until`
- `vote_total_frames`, `vote_violation_frames`
- Helmet-oriented optional fields: `aspect_ratio`, `head_region_bbox`
- Generic: `primary_iou`, `evaluation_metrics` (JSON), `rule_snapshot` (frozen config)

Why:
- Feeds dashboard, reporting, SLA workflows, and operational escalation across all PPE types.

### 5.9 `violation_evidences`
Purpose:
- Store evidence references and visual metadata.

Key fields:
- `violation_id`, `capture_ts`, `image_path`, `image_sha256`
- `person_bbox`, `equipment_bbox` (preferred for any PPE crop), `helmet_bbox` (legacy for helmet flows), `meta`

Why:
- Supports human review and legal/compliance traceability.

### 5.10 `alerts`
Purpose:
- Log alert delivery attempts and outcomes across channels.

Key fields:
- `channel`, `sent_at`, `delivery_status`, `response`

Why:
- Enables alert reliability monitoring and retry policy tuning.

### 5.11 `camera_health_logs`
Purpose:
- Persist stream and decoder health events.

Key fields:
- `event_type`, `level`, `message`, `metrics`

Why:
- Supports proactive maintenance and incident triage.

---

## 6) Relationship Model

Main relationships:
- `sites` 1-n `zones`
- `sites` 1-n `cameras`
- `zones` 1-n `cameras` (optional zone assignment)
- `safety_criteria` 1-n `rule_definitions`
- `safety_criteria` n-n `cameras` via `camera_criterion_assignments`
- `cameras` 1-n `processing_runs`
- `processing_runs` 1-n `frame_preprocessing_logs`
- `processing_runs` 1-n `detections`
- `processing_runs` 1-n `rule_evaluations`
- `processing_runs` 1-n `violations`
- `violations` 1-n `violation_evidences`
- `violations` 1-n `alerts`

---

## 7) Indexing Strategy

Core indexing goals:
- Fast timeline queries (`camera_id`, `frame_ts`, `confirmed_at`)
- Efficient per-track investigations (`track_id`, time)
- Fast operational filtering (`status`, `decision`, `quality_state`)

Notable index groups:
- Pre-processing: `(camera_id, frame_ts)`, `(run_id, frame_seq)`
- Detections: `(camera_id, frame_ts)`, `(track_id, frame_ts)`, `(class_name, frame_ts)`
- Rule evaluations: `(camera_id, frame_ts)`, `(track_id, frame_ts)`, `(decision, frame_ts)`
- Violations: `(camera_id, confirmed_at)`, `(criterion_id, confirmed_at)`, `(status, confirmed_at)`

---

## 8) Data Quality and Constraints

Recommended service-layer checks:
- `0.0 <= confidence <= 1.0`
- `vote_violation_frames <= vote_total_frames`
- `ended_at >= started_at` when `ended_at` is present
- Bounding boxes must remain in image boundaries
- `quality_state` and `decision` should map to controlled vocabularies

Operational conventions:
- Store timestamps in UTC.
- Keep `track_id` scoped as runtime identifier, not person identity.
- Treat `rule_snapshot` and `config_snapshot` as immutable historical context.

---

## 9) Example Query Use Cases

- Latest confirmed violations for one camera and time range.
- Full track investigation: pre-processing -> detections -> rule decisions -> violation.
- Evidence retrieval for reviewer UI sorted by capture timestamp.
- Health anomaly trend by `event_type` over 24h/7d windows.
- Alert delivery failure analysis by channel.

---

## 10) Extension Roadmap

Future-ready extensions without core redesign:
- New PPE types: insert `safety_criteria`, add `rule_definitions` versions, extend YOLO `classes` on `model_versions`, assign on cameras.
- Optional `site_criterion_assignments` if policy is site-wide defaults before camera overrides.
- Introduce partitioning on large time-series tables (`detections`, `frame_preprocessing_logs`, `rule_evaluations`).
- Add retention policy tables for evidence lifecycle management.
- Add user action audit trail for manual review/acknowledgement workflows.
- Optional JSON Schema registry table for `definition` if you want DB-documented rule shape validation.

---

## 11) Approval Status

- Status: Draft (Full RTSP-Oriented Design)
- Baseline: Section 3a flow + current DBML
- Next step: Validate with runtime service contracts and migration scripts
