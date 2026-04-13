using Microsoft.EntityFrameworkCore;
using SafetyDetection.Shared.Models;

namespace SafetyDetection.Shared.Data
{
    public class SafetyDbContext : DbContext
    {
        public SafetyDbContext(DbContextOptions<SafetyDbContext> options) : base(options) { }

        // Design-time constructor requires empty constructor if no other method provided. 
        // We will use factory or provide options via DI.

        public DbSet<Site> Sites { get; set; }
        public DbSet<Zone> Zones { get; set; }
        public DbSet<Camera> Cameras { get; set; }
        public DbSet<SafetyCriterion> SafetyCriteria { get; set; }
        public DbSet<RuleDefinition> RuleDefinitions { get; set; }
        public DbSet<CameraCriterionAssignment> CameraCriterionAssignments { get; set; }
        public DbSet<ModelVersion> ModelVersions { get; set; }
        public DbSet<ProcessingRun> ProcessingRuns { get; set; }
        public DbSet<Detection> Detections { get; set; }
        public DbSet<Violation> Violations { get; set; }
        public DbSet<RuleEvaluation> RuleEvaluations { get; set; }
        public DbSet<ViolationEvidence> ViolationEvidences { get; set; }
        public DbSet<Alert> Alerts { get; set; }
        public DbSet<CameraHealthLog> CameraHealthLogs { get; set; }
        public DbSet<FramePreprocessingLog> FramePreprocessingLogs { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);

            // Composite indexes
            modelBuilder.Entity<Zone>()
                .HasIndex(z => new { z.SiteId, z.Code })
                .IsUnique();

            modelBuilder.Entity<Camera>()
                .HasIndex(c => new { c.SiteId, c.Code })
                .IsUnique();
            
            // Relationships
            modelBuilder.Entity<Zone>()
                .HasOne(z => z.Site)
                .WithMany(s => s.Zones)
                .HasForeignKey(z => z.SiteId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<Camera>()
                .HasOne(c => c.Site)
                .WithMany(s => s.Cameras)
                .HasForeignKey(c => c.SiteId)
                .OnDelete(DeleteBehavior.NoAction);

            modelBuilder.Entity<Camera>()
                .HasOne(c => c.Zone)
                .WithMany(z => z.Cameras)
                .HasForeignKey(c => c.ZoneId)
                .OnDelete(DeleteBehavior.SetNull);
        }
    }
}
