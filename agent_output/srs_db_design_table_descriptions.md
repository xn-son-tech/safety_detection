# Software Requirements Specification — Database Design (Excerpt)

**System:** Safety / PPE Detection (YOLO-based video analytics)  
**Schema reference:** `agent_output/safety_detection_schema.dbml`

---

## 2.1. Table Descriptions

| No | Entity | Description |
| 01 | **sites** | Top-level deployment sites (e.g., construction yards or facilities). Stores human-readable name, stable business code, and default timezone. Each site owns many zones and cameras. |
| 02 | **zones** | Logical areas within a site (e.g., excavation zone, gate). Linked to **sites**; used to group cameras for reporting and to annotate where events occurred. |
| 03 | **cameras** | Individual RTSP cameras tied to a **site** and optionally a **zone**. Holds stream endpoint reference, operational status, and configured frame rate / resolution metadata. |
| 04 | **safety_criteria** | Catalog of enforceable safety/PPE criteria (e.g., missing helmet, missing reflective vest). Each row defines a stable **code**, display name, default severity, and whether the criterion is globally active. Multiple **rule_definitions** and **violations** reference one criterion. |
| 05 | **rule_definitions** | Versioned rule packs for a **safety_criterion**. The **definition** JSON binds YOLO class names to evaluation logic (IoU, geometry, voting parameters). Allows rule changes without altering core tables; **violations** and **rule_evaluations** may reference the rule version used. |
| 06 | **camera_criterion_assignments** | Per-**camera** configuration of which **safety_criteria** are enabled, with optional override of **rule_definitions**. Models “turn criteria on/off per camera” without schema migration. |
| 07 | **model_versions** | Registry of YOLO checkpoints: name, semantic version, declared **classes** JSON, and suggested thresholds. **processing_runs** and **detections** reference the model that produced outputs. |
| 08 | **processing_runs** | One processing session for a **camera** stream (start/end time, status). Stores a **config_snapshot** of runtime thresholds and tracker settings so results can be reproduced or audited later. Parent for preprocess logs, detections, rule evaluations, and violations tied to that run. |
| 09 | **frame_preprocessing_logs** | Per-frame (or sampled) pre-inference quality records for a **processing_run**: SSIM, blur metric, CLAHE flag, pass/drop state and reason. Explains which frames reached the detector and why others were discarded. |
| 10 | **detections** | Raw model output per frame: **class_name**, bounding box, confidence, optional **track_id**, linked to **camera** and optionally **processing_run** / **model_version**. Feeds the rule engine and forensic replay. |
| 11 | **rule_evaluations** | Intermediate rule-engine decisions per **criterion**, **camera**, time, and **track_id**: sliding-window vote counts, **decision** (safe, danger, cooldown skip, etc.), and criterion-specific scores (**primary_iou**, **details**). Bridges **detections** and confirmed **violations**. |
| 12 | **violations** | Confirmed business events after validation (e.g., sustained missing PPE). References **camera**, **site**, optional **zone**, **safety_criterion**, and **rule_definition**; stores confirmation time, voting summary, frozen **rule_snapshot**, and optional geometry/metrics for audit. |
| 13 | **violation_evidences** | Evidence artifacts for a **violation**: image storage path/checksum, capture time, person and equipment bounding boxes (and legacy helmet box), plus **meta** for review workflows. |
| 14 | **alerts** | Notification delivery log for a **violation** (channel, send time, delivery status, provider response). Supports tracing WebSocket, mobile push, email, or SMS attempts. |
| 15 | **camera_health_logs** | Operational health events for a **camera** (stream glitches, low FPS, decoder errors, occlusion). Separate from safety violations; used for monitoring and maintenance. |

---

## 2.2. Field specifications (per table)

Conventions used below (SQL Server–oriented mapping of `safety_detection_schema.dbml`):

- **Type:** logical SQL Server types; JSON columns as `nvarchar(max)` with `CHECK (ISJSON(...)=1)` optional at implementation time.
- **Unique / Not Null:** `x` when the constraint applies.
- **PK/FK:** `PK` primary key, or `FK -> {Table}.{Field}` for foreign keys.
- **PascalCase** field names match common .NET / EF naming; physical columns may remain snake_case if the team prefers—keep names consistent in one convention per deployment.

Legend: leave cells empty when the constraint does not apply.

---

### 2.2.1. `sites`

**Table 2.2.1** — Table `sites` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | uniqueidentifier | x | x | PK | Primary key for the site. |
| 02 | Code | nvarchar(64) | x | x | | Stable business code used in APIs and reports. |
| 03 | Name | nvarchar(256) | | x | | Human-readable site name. |
| 04 | Timezone | nvarchar(128) | | x | | Default IANA timezone (e.g., `Asia/Ho_Chi_Minh`) for display and local boundaries. |
| 05 | CreatedAt | datetime2(7) | | x | | Row creation timestamp (UTC recommended). |
| 06 | UpdatedAt | datetime2(7) | | x | | Row last update timestamp (UTC recommended). |

---

### 2.2.2. `zones`

**Table 2.2.2** — Table `zones` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | uniqueidentifier | x | x | PK | Primary key for the zone. |
| 02 | SiteId | uniqueidentifier | | x | FK -> sites.Id | Owning site. |
| 03 | Code | nvarchar(64) | | x | | Zone code; must be unique together with `SiteId` (composite unique index). |
| 04 | Name | nvarchar(256) | | x | | Display name of the zone. |
| 05 | Description | nvarchar(max) | | | | Optional free-text description. |
| 06 | CreatedAt | datetime2(7) | | x | | Row creation timestamp. |
| 07 | UpdatedAt | datetime2(7) | | x | | Row last update timestamp. |

---

### 2.2.3. `cameras`

**Table 2.2.3** — Table `cameras` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | uniqueidentifier | x | x | PK | Primary key for the camera. |
| 02 | SiteId | uniqueidentifier | | x | FK -> sites.Id | Site where the camera is installed. |
| 03 | ZoneId | uniqueidentifier | | | FK -> zones.Id | Optional zone assignment for reporting. |
| 04 | Code | nvarchar(64) | | x | | Camera code; unique together with `SiteId` (composite unique index). |
| 05 | Name | nvarchar(256) | | x | | Display name (e.g., “Gate 1 west”). |
| 06 | RtspUrl | nvarchar(max) | | | | RTSP URL or connection string; store encrypted or in a secret manager in production. |
| 07 | Status | nvarchar(32) | | x | | Operational state: `active`, `inactive`, `maintenance`, etc. |
| 08 | FpsConfig | int | | | | Target or configured frames per second for the pipeline. |
| 09 | ResolutionW | int | | | | Optional frame width in pixels. |
| 10 | ResolutionH | int | | | | Optional frame height in pixels. |
| 11 | CreatedAt | datetime2(7) | | x | | Row creation timestamp. |
| 12 | UpdatedAt | datetime2(7) | | x | | Row last update timestamp. |

---

### 2.2.4. `safety_criteria`

**Table 2.2.4** — Table `safety_criteria` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | uniqueidentifier | x | x | PK | Primary key for the criterion. |
| 02 | Code | nvarchar(64) | x | x | | Stable machine code (e.g., `NO_HELMET`, `NO_REFLECTIVE_VEST`). |
| 03 | Name | nvarchar(256) | | x | | Display name for UI and reports. |
| 04 | Description | nvarchar(max) | | | | Optional explanation of the criterion. |
| 05 | IsActive | bit | | x | | When `0`, criterion is disabled for new assignments; historical FK rows remain valid. |
| 06 | SortOrder | int | | x | | Display ordering in admin UI. |
| 07 | DefaultSeverity | int | | x | | Default severity level when a violation is raised under this criterion. |
| 08 | CreatedAt | datetime2(7) | | x | | Row creation timestamp. |
| 09 | UpdatedAt | datetime2(7) | | x | | Row last update timestamp. |

---

### 2.2.5. `rule_definitions`

**Table 2.2.5** — Table `rule_definitions` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | uniqueidentifier | x | x | PK | Primary key for the rule definition row. |
| 02 | CriterionId | uniqueidentifier | | x | FK -> safety_criteria.Id | Criterion this rule evaluates. |
| 03 | Code | nvarchar(128) | | x | | Stable rule identifier (e.g., `helmet_head_iou`); unique per criterion with `Version`. |
| 04 | Version | nvarchar(32) | | x | | Semantic version string (e.g., `1.0.0`). |
| 05 | Name | nvarchar(256) | | x | | Human-readable rule name. |
| 06 | IsActive | bit | | x | | Whether this rule version may be selected by runtime. |
| 07 | IsDefault | bit | | x | | Marks the default rule pack for the criterion when no per-camera override exists. |
| 08 | Definition | nvarchar(max) | | x | | JSON: YOLO class names, anchor class, IoU thresholds, voting window, geometry hints, etc. |
| 09 | CreatedAt | datetime2(7) | | x | | Row creation timestamp. |

---

### 2.2.6. `camera_criterion_assignments`

**Table 2.2.6** — Table `camera_criterion_assignments` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | uniqueidentifier | x | x | PK | Primary key for the assignment row. |
| 02 | CameraId | uniqueidentifier | | x | FK -> cameras.Id | Camera receiving the policy. |
| 03 | CriterionId | uniqueidentifier | | x | FK -> safety_criteria.Id | Criterion to enforce or disable. |
| 04 | IsEnabled | bit | | x | | When `0`, this criterion is off for this camera. |
| 05 | RuleDefinitionId | uniqueidentifier | | | FK -> rule_definitions.Id | Optional override; if null, runtime uses the criterion’s default active rule. |
| 06 | CreatedAt | datetime2(7) | | x | | Row creation timestamp. |
| 07 | UpdatedAt | datetime2(7) | | x | | Row last update timestamp. |

*Constraint note:* one row per (`CameraId`, `CriterionId`) (unique index).

---

### 2.2.7. `model_versions`

**Table 2.2.7** — Table `model_versions` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | uniqueidentifier | x | x | PK | Primary key for the model checkpoint. |
| 02 | Name | nvarchar(128) | | x | | Model family or artifact name; unique together with `Version`. |
| 03 | Version | nvarchar(64) | | x | | Checkpoint version label. |
| 04 | Classes | nvarchar(max) | | | | JSON array of YOLO class labels emitted by this checkpoint. |
| 05 | ConfidenceThreshold | decimal(5,4) | | | | Suggested default confidence threshold for inference. |
| 06 | IouThreshold | decimal(5,4) | | | | Suggested default IoU for NMS / pairing (implementation-specific). |
| 07 | IsActive | bit | | x | | Whether this row is a candidate “current” model in admin workflows. |
| 08 | CreatedAt | datetime2(7) | | x | | Row creation timestamp. |

---

### 2.2.8. `processing_runs`

**Table 2.2.8** — Table `processing_runs` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | uniqueidentifier | x | x | PK | Primary key for the stream processing session. |
| 02 | CameraId | uniqueidentifier | | x | FK -> cameras.Id | Camera being processed. |
| 03 | ModelVersionId | uniqueidentifier | | | FK -> model_versions.Id | Model used for this run, if recorded. |
| 04 | StreamStartedAt | datetime2(7) | | x | | Session start time. |
| 05 | StreamEndedAt | datetime2(7) | | | | Session end time when stopped gracefully or on failure. |
| 06 | Status | nvarchar(32) | | x | | `running`, `success`, `failed`, `stopped`, etc. |
| 07 | ConfigSnapshot | nvarchar(max) | | | | JSON snapshot of thresholds, voting, cooldown, tracker settings for audit/replay. |
| 08 | ErrorMessage | nvarchar(max) | | | | Populated when `Status` indicates failure. |
| 09 | CreatedAt | datetime2(7) | | x | | Row creation timestamp. |
| 10 | UpdatedAt | datetime2(7) | | x | | Row last update timestamp. |

---

### 2.2.9. `frame_preprocessing_logs`

**Table 2.2.9** — Table `frame_preprocessing_logs` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | bigint | x | x | PK | Surrogate primary key (identity). |
| 02 | RunId | uniqueidentifier | | x | FK -> processing_runs.Id | Processing session. |
| 03 | CameraId | uniqueidentifier | | x | FK -> cameras.Id | Redundant camera key for partition/query convenience. |
| 04 | FrameTs | datetime2(7) | | x | | Timestamp of the frame in stream time. |
| 05 | FrameSeq | bigint | | | | Optional monotonic frame sequence within the run. |
| 06 | SsimScore | decimal(6,5) | | | | Structural similarity metric for anti-glitch / tear detection. |
| 07 | LaplacianVar | decimal(10,4) | | | | Blur metric (variance of Laplacian). |
| 08 | ClaheApplied | bit | | x | | Whether CLAHE lighting adjustment was applied before inference. |
| 09 | QualityState | nvarchar(32) | | x | | `passed`, `dropped_glitch`, `dropped_blur`, `dropped_other`, etc. |
| 10 | DropReason | nvarchar(64) | | | | Reason when the frame was dropped (e.g., `rtsp_glitch`, `motion_blur`). |
| 11 | Extra | nvarchar(max) | | | | Optional JSON for additional preprocess metrics. |
| 12 | CreatedAt | datetime2(7) | | x | | Row insertion time (ingest time). |

---

### 2.2.10. `detections`

**Table 2.2.10** — Table `detections` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | bigint | x | x | PK | Surrogate primary key (identity). |
| 02 | CameraId | uniqueidentifier | | x | FK -> cameras.Id | Source camera. |
| 03 | RunId | uniqueidentifier | | | FK -> processing_runs.Id | Optional link to the processing session. |
| 04 | ModelVersionId | uniqueidentifier | | | FK -> model_versions.Id | Model that produced the detection. |
| 05 | FrameTs | datetime2(7) | | x | | Frame timestamp. |
| 06 | FrameSeq | bigint | | | | Optional frame index within the run. |
| 07 | TrackId | nvarchar(64) | | | | Tracker-assigned ID; not a real person identity. |
| 08 | ClassName | nvarchar(128) | | x | | YOLO class label (e.g., `person`, `helmet`, `reflective_vest`). |
| 09 | Confidence | decimal(5,4) | | | | Class confidence score. |
| 10 | BboxX1 | int | | x | | Bounding box left (pixels). |
| 11 | BboxY1 | int | | x | | Bounding box top (pixels). |
| 12 | BboxX2 | int | | x | | Bounding box right (pixels). |
| 13 | BboxY2 | int | | x | | Bounding box bottom (pixels). |
| 14 | IsEdgeTruncated | bit | | x | | Whether the box touches image border (quality hint). |
| 15 | Extra | nvarchar(max) | | | | Optional JSON (e.g., raw model aux outputs). |
| 16 | CreatedAt | datetime2(7) | | x | | Row creation timestamp. |

---

### 2.2.11. `violations`

**Table 2.2.11** — Table `violations` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | uniqueidentifier | x | x | PK | Primary key for the confirmed violation event. |
| 02 | CameraId | uniqueidentifier | | x | FK -> cameras.Id | Camera where the violation was observed. |
| 03 | SiteId | uniqueidentifier | | x | FK -> sites.Id | Denormalized site for fast filtering/reporting. |
| 04 | ZoneId | uniqueidentifier | | | FK -> zones.Id | Optional zone at confirmation time. |
| 05 | RunId | uniqueidentifier | | | FK -> processing_runs.Id | Optional processing session link. |
| 06 | CriterionId | uniqueidentifier | | x | FK -> safety_criteria.Id | Which safety criterion was violated. |
| 07 | RuleDefinitionId | uniqueidentifier | | | FK -> rule_definitions.Id | Rule version that produced the confirmation. |
| 08 | TrackId | nvarchar(64) | | x | | Tracker ID associated with the person/object track. |
| 09 | Severity | int | | x | | Effective severity for this event (may differ from criterion default). |
| 10 | StartedAt | datetime2(7) | | x | | When the violating state began (per business rules). |
| 11 | ConfirmedAt | datetime2(7) | | x | | When sliding-window / cooldown logic confirmed the violation. |
| 12 | EndedAt | datetime2(7) | | | | When the violating episode ended, if tracked. |
| 13 | Status | nvarchar(32) | | x | | Workflow state: `open`, `acknowledged`, `resolved`, `ignored`, etc. |
| 14 | CooldownUntil | datetime2(7) | | | | Suppress duplicate alerts until this time when using cooldown. |
| 15 | VoteTotalFrames | int | | x | | Frames considered in the confirmation window. |
| 16 | VoteViolationFrames | int | | x | | Frames counted as violating within the window. |
| 17 | AspectRatio | decimal(8,5) | | | | Optional person aspect ratio for helmet/head-style rules. |
| 18 | HeadRegionBbox | nvarchar(max) | | | | Optional JSON bbox for inferred head region (helmet-type rules). |
| 19 | PrimaryIou | decimal(5,4) | | | | Main overlap score (criterion-dependent: helmet-head, vest-torso, etc.). |
| 20 | EvaluationMetrics | nvarchar(max) | | | | JSON for additional numeric scores per criterion. |
| 21 | RuleSnapshot | nvarchar(max) | | | | Frozen JSON of effective rule parameters at confirmation time. |
| 22 | CreatedAt | datetime2(7) | | x | | Row creation timestamp. |
| 23 | UpdatedAt | datetime2(7) | | x | | Row last update timestamp. |

---

### 2.2.12. `rule_evaluations`

**Table 2.2.12** — Table `rule_evaluations` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | bigint | x | x | PK | Surrogate primary key (identity). |
| 02 | RunId | uniqueidentifier | | | FK -> processing_runs.Id | Optional session link. |
| 03 | CameraId | uniqueidentifier | | x | FK -> cameras.Id | Camera under evaluation. |
| 04 | CriterionId | uniqueidentifier | | x | FK -> safety_criteria.Id | Criterion being evaluated. |
| 05 | RuleDefinitionId | uniqueidentifier | | | FK -> rule_definitions.Id | Rule version in use, if resolved. |
| 06 | FrameTs | datetime2(7) | | x | | Frame timestamp for this evaluation row. |
| 07 | FrameSeq | bigint | | | | Optional frame sequence. |
| 08 | TrackId | nvarchar(64) | | x | | Track under evaluation. |
| 09 | RuleCode | nvarchar(128) | | x | | Denormalized `rule_definitions.Code` for fast filtering. |
| 10 | VoteWindow | int | | x | | Sliding window size (frames). |
| 11 | VotePositive | int | | x | | Count of frames voting toward violation (or rule-specific meaning). |
| 12 | VoteNegative | int | | x | | Count of frames voting against violation (or rule-specific meaning). |
| 13 | Decision | nvarchar(32) | | x | | `safe`, `danger`, `cooldown_skip`, `insufficient_evidence`, etc. |
| 14 | PrimaryIou | decimal(5,4) | | | | Criterion-dependent primary overlap score. |
| 15 | AspectRatio | decimal(8,5) | | | | Optional geometry metric for head/person rules. |
| 16 | Details | nvarchar(max) | | | | JSON for debug: matched boxes, thresholds, intermediate flags. |
| 17 | CreatedAt | datetime2(7) | | x | | Row creation timestamp. |

---

### 2.2.13. `violation_evidences`

**Table 2.2.13** — Table `violation_evidences` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | uniqueidentifier | x | x | PK | Primary key for the evidence row. |
| 02 | ViolationId | uniqueidentifier | | x | FK -> violations.Id | Parent violation. |
| 03 | CaptureTs | datetime2(7) | | x | | Timestamp of the captured frame used as evidence. |
| 04 | ImagePath | nvarchar(max) | | x | | File path or object-storage key for the cropped or full-frame image. |
| 05 | ImageSha256 | nvarchar(64) | | | | Optional SHA-256 of the image bytes for integrity. |
| 06 | Width | int | | | | Image width in pixels. |
| 07 | Height | int | | | | Image height in pixels. |
| 08 | PersonBbox | nvarchar(max) | | | | JSON bounding box for the person region. |
| 09 | EquipmentBbox | nvarchar(max) | | | | JSON bounding box for PPE/equipment (helmet, vest, gloves, etc.). |
| 10 | HelmetBbox | nvarchar(max) | | | | Legacy JSON bbox for helmet-only flows; prefer `EquipmentBbox`. |
| 11 | Meta | nvarchar(max) | | | | JSON metadata (scores, labels, crop policy). |
| 12 | CreatedAt | datetime2(7) | | x | | Row creation timestamp. |

---

### 2.2.14. `alerts`

**Table 2.2.14** — Table `alerts` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | bigint | x | x | PK | Surrogate primary key (identity). |
| 02 | ViolationId | uniqueidentifier | | x | FK -> violations.Id | Violation that triggered the notification. |
| 03 | Channel | nvarchar(32) | | x | | Delivery channel: `websocket`, `mobile`, `email`, `sms`, etc. |
| 04 | SentAt | datetime2(7) | | x | | When the send was attempted or queued. |
| 05 | DeliveryStatus | nvarchar(32) | | x | | `queued`, `sent`, `failed`, etc. |
| 06 | Response | nvarchar(max) | | | | JSON or text payload from the provider (message id, error body). |

---

### 2.2.15. `camera_health_logs`

**Table 2.2.15** — Table `camera_health_logs` field descriptions

| No | Field Name | Type | Unique | Not Null | PK/FK | Description |
| 01 | Id | bigint | x | x | PK | Surrogate primary key (identity). |
| 02 | CameraId | uniqueidentifier | | x | FK -> cameras.Id | Camera reporting the health event. |
| 03 | LoggedAt | datetime2(7) | | x | | Event time. |
| 04 | EventType | nvarchar(64) | | x | | e.g., `rtsp_glitch`, `lens_occlusion`, `low_fps`, `decoder_error`. |
| 05 | Level | nvarchar(16) | | x | | `info`, `warn`, `error`. |
| 06 | Message | nvarchar(max) | | | | Human-readable detail. |
| 07 | Metrics | nvarchar(max) | | | | JSON numeric context (FPS, dropped frames, error codes). |

---

*End of sections 2.1–2.2.*
