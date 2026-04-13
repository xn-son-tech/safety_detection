using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace SafetyDetection.Shared.Models
{
    public class Site
    {
        public Guid Id { get; set; }
        [Required, MaxLength(64)]
        public string Code { get; set; }
        [Required, MaxLength(256)]
        public string Name { get; set; }
        [Required, MaxLength(128)]
        public string Timezone { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }

        public ICollection<Zone> Zones { get; set; }
        public ICollection<Camera> Cameras { get; set; }
    }

    public class Zone
    {
        public Guid Id { get; set; }
        public Guid SiteId { get; set; }
        [Required, MaxLength(64)]
        public string Code { get; set; }
        [Required, MaxLength(256)]
        public string Name { get; set; }
        public string? Description { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }

        public Site Site { get; set; }
        public ICollection<Camera> Cameras { get; set; }
    }

    public class Camera
    {
        public Guid Id { get; set; }
        public Guid SiteId { get; set; }
        public Guid? ZoneId { get; set; }
        [Required, MaxLength(64)]
        public string Code { get; set; }
        [Required, MaxLength(256)]
        public string Name { get; set; }
        public string? RtspUrl { get; set; }
        [Required, MaxLength(32)]
        public string Status { get; set; }
        public int? FpsConfig { get; set; }
        public int? ResolutionW { get; set; }
        public int? ResolutionH { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }

        public Site Site { get; set; }
        public Zone? Zone { get; set; }
        public ICollection<CameraCriterionAssignment> CriterionAssignments { get; set; }
    }

    public class SafetyCriterion
    {
        public Guid Id { get; set; }
        [Required, MaxLength(64)]
        public string Code { get; set; }
        [Required, MaxLength(256)]
        public string Name { get; set; }
        public string? Description { get; set; }
        public bool IsActive { get; set; }
        public int SortOrder { get; set; }
        public int DefaultSeverity { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }

        public ICollection<RuleDefinition> RuleDefinitions { get; set; }
    }

    public class RuleDefinition
    {
        public Guid Id { get; set; }
        public Guid CriterionId { get; set; }
        [Required, MaxLength(128)]
        public string Code { get; set; }
        [Required, MaxLength(32)]
        public string Version { get; set; }
        [Required, MaxLength(256)]
        public string Name { get; set; }
        public bool IsActive { get; set; }
        public bool IsDefault { get; set; }
        [Required]
        public string Definition { get; set; }
        public DateTime CreatedAt { get; set; }

        public SafetyCriterion Criterion { get; set; }
    }

    public class CameraCriterionAssignment
    {
        public Guid Id { get; set; }
        public Guid CameraId { get; set; }
        public Guid CriterionId { get; set; }
        public bool IsEnabled { get; set; }
        public Guid? RuleDefinitionId { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }

        public Camera Camera { get; set; }
        public SafetyCriterion Criterion { get; set; }
        public RuleDefinition? RuleDefinition { get; set; }
    }

    public class ModelVersion
    {
        public Guid Id { get; set; }
        [Required, MaxLength(128)]
        public string Name { get; set; }
        [Required, MaxLength(64)]
        public string Version { get; set; }
        public string? Classes { get; set; }
        [Column(TypeName = "decimal(5,4)")]
        public decimal? ConfidenceThreshold { get; set; }
        [Column(TypeName = "decimal(5,4)")]
        public decimal? IouThreshold { get; set; }
        public bool IsActive { get; set; }
        public DateTime CreatedAt { get; set; }
    }

    public class ProcessingRun
    {
        public Guid Id { get; set; }
        public Guid CameraId { get; set; }
        public Guid? ModelVersionId { get; set; }
        public DateTime StreamStartedAt { get; set; }
        public DateTime? StreamEndedAt { get; set; }
        [Required, MaxLength(32)]
        public string Status { get; set; }
        public string? ConfigSnapshot { get; set; }
        public string? ErrorMessage { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }

        public Camera Camera { get; set; }
        public ModelVersion? ModelVersion { get; set; }
    }

    public class Detection
    {
        public long Id { get; set; }
        public Guid CameraId { get; set; }
        public Guid? RunId { get; set; }
        public Guid? ModelVersionId { get; set; }
        public DateTime FrameTs { get; set; }
        public long? FrameSeq { get; set; }
        [MaxLength(64)]
        public string? TrackId { get; set; }
        [Required, MaxLength(128)]
        public string ClassName { get; set; }
        [Column(TypeName = "decimal(5,4)")]
        public decimal? Confidence { get; set; }
        public int BboxX1 { get; set; }
        public int BboxY1 { get; set; }
        public int BboxX2 { get; set; }
        public int BboxY2 { get; set; }
        public bool IsEdgeTruncated { get; set; }
        public string? Extra { get; set; }
        public DateTime CreatedAt { get; set; }
    }

    public class Violation
    {
        public Guid Id { get; set; }
        public Guid CameraId { get; set; }
        public Guid SiteId { get; set; }
        public Guid? ZoneId { get; set; }
        public Guid? RunId { get; set; }
        public Guid CriterionId { get; set; }
        public Guid? RuleDefinitionId { get; set; }
        [Required, MaxLength(64)]
        public string TrackId { get; set; }
        public int Severity { get; set; }
        public DateTime StartedAt { get; set; }
        public DateTime ConfirmedAt { get; set; }
        public DateTime? EndedAt { get; set; }
        [Required, MaxLength(32)]
        public string Status { get; set; }
        public DateTime? CooldownUntil { get; set; }
        public int VoteTotalFrames { get; set; }
        public int VoteViolationFrames { get; set; }
        [Column(TypeName = "decimal(8,5)")]
        public decimal? AspectRatio { get; set; }
        public string? HeadRegionBbox { get; set; }
        [Column(TypeName = "decimal(5,4)")]
        public decimal? PrimaryIou { get; set; }
        public string? EvaluationMetrics { get; set; }
        public string? RuleSnapshot { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }

        public Camera Camera { get; set; }
        public SafetyCriterion Criterion { get; set; }
        public ICollection<ViolationEvidence> Evidences { get; set; }
    }

    public class RuleEvaluation
    {
        public long Id { get; set; }
        public Guid? RunId { get; set; }
        public Guid CameraId { get; set; }
        public Guid CriterionId { get; set; }
        public Guid? RuleDefinitionId { get; set; }
        public DateTime FrameTs { get; set; }
        public long? FrameSeq { get; set; }
        [Required, MaxLength(64)]
        public string TrackId { get; set; }
        [Required, MaxLength(128)]
        public string RuleCode { get; set; }
        public int VoteWindow { get; set; }
        public int VotePositive { get; set; }
        public int VoteNegative { get; set; }
        [Required, MaxLength(32)]
        public string Decision { get; set; }
        [Column(TypeName = "decimal(5,4)")]
        public decimal? PrimaryIou { get; set; }
        [Column(TypeName = "decimal(8,5)")]
        public decimal? AspectRatio { get; set; }
        public string? Details { get; set; }
        public DateTime CreatedAt { get; set; }
    }

    public class ViolationEvidence
    {
        public Guid Id { get; set; }
        public Guid ViolationId { get; set; }
        public DateTime CaptureTs { get; set; }
        [Required]
        public string ImagePath { get; set; }
        [MaxLength(64)]
        public string? ImageSha256 { get; set; }
        public int? Width { get; set; }
        public int? Height { get; set; }
        public string? PersonBbox { get; set; }
        public string? EquipmentBbox { get; set; }
        public string? HelmetBbox { get; set; }
        public string? Meta { get; set; }
        public DateTime CreatedAt { get; set; }

        public Violation Violation { get; set; }
    }

    public class Alert
    {
        public long Id { get; set; }
        public Guid ViolationId { get; set; }
        [Required, MaxLength(32)]
        public string Channel { get; set; }
        public DateTime SentAt { get; set; }
        [Required, MaxLength(32)]
        public string DeliveryStatus { get; set; }
        public string? Response { get; set; }

        public Violation Violation { get; set; }
    }

    public class CameraHealthLog
    {
        public long Id { get; set; }
        public Guid CameraId { get; set; }
        public DateTime LoggedAt { get; set; }
        [Required, MaxLength(64)]
        public string EventType { get; set; }
        [Required, MaxLength(16)]
        public string Level { get; set; }
        public string? Message { get; set; }
        public string? Metrics { get; set; }
    }

    public class FramePreprocessingLog
    {
        public long Id { get; set; }
        public Guid RunId { get; set; }
        public Guid CameraId { get; set; }
        public DateTime FrameTs { get; set; }
        public long? FrameSeq { get; set; }
        [Column(TypeName = "decimal(6,5)")]
        public decimal? SsimScore { get; set; }
        [Column(TypeName = "decimal(10,4)")]
        public decimal? LaplacianVar { get; set; }
        public bool ClaheApplied { get; set; }
        [Required, MaxLength(32)]
        public string QualityState { get; set; }
        [MaxLength(64)]
        public string? DropReason { get; set; }
        public string? Extra { get; set; }
        public DateTime CreatedAt { get; set; }
    }
}
