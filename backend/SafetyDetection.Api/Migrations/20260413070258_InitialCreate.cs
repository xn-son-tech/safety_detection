using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace SafetyDetection.Api.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "CameraHealthLogs",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    CameraId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    LoggedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    EventType = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Level = table.Column<string>(type: "nvarchar(16)", maxLength: 16, nullable: false),
                    Message = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    Metrics = table.Column<string>(type: "nvarchar(max)", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_CameraHealthLogs", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Detections",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    CameraId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    RunId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                    ModelVersionId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                    FrameTs = table.Column<DateTime>(type: "datetime2", nullable: false),
                    FrameSeq = table.Column<long>(type: "bigint", nullable: true),
                    TrackId = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: true),
                    ClassName = table.Column<string>(type: "nvarchar(128)", maxLength: 128, nullable: false),
                    Confidence = table.Column<decimal>(type: "decimal(5,4)", nullable: true),
                    BboxX1 = table.Column<int>(type: "int", nullable: false),
                    BboxY1 = table.Column<int>(type: "int", nullable: false),
                    BboxX2 = table.Column<int>(type: "int", nullable: false),
                    BboxY2 = table.Column<int>(type: "int", nullable: false),
                    IsEdgeTruncated = table.Column<bool>(type: "bit", nullable: false),
                    Extra = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Detections", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "FramePreprocessingLogs",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    RunId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    CameraId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    FrameTs = table.Column<DateTime>(type: "datetime2", nullable: false),
                    FrameSeq = table.Column<long>(type: "bigint", nullable: true),
                    SsimScore = table.Column<decimal>(type: "decimal(6,5)", nullable: true),
                    LaplacianVar = table.Column<decimal>(type: "decimal(10,4)", nullable: true),
                    ClaheApplied = table.Column<bool>(type: "bit", nullable: false),
                    QualityState = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    DropReason = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: true),
                    Extra = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_FramePreprocessingLogs", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "ModelVersions",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    Name = table.Column<string>(type: "nvarchar(128)", maxLength: 128, nullable: false),
                    Version = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Classes = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    ConfidenceThreshold = table.Column<decimal>(type: "decimal(5,4)", nullable: true),
                    IouThreshold = table.Column<decimal>(type: "decimal(5,4)", nullable: true),
                    IsActive = table.Column<bool>(type: "bit", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ModelVersions", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "RuleEvaluations",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    RunId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                    CameraId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    CriterionId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    RuleDefinitionId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                    FrameTs = table.Column<DateTime>(type: "datetime2", nullable: false),
                    FrameSeq = table.Column<long>(type: "bigint", nullable: true),
                    TrackId = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    RuleCode = table.Column<string>(type: "nvarchar(128)", maxLength: 128, nullable: false),
                    VoteWindow = table.Column<int>(type: "int", nullable: false),
                    VotePositive = table.Column<int>(type: "int", nullable: false),
                    VoteNegative = table.Column<int>(type: "int", nullable: false),
                    Decision = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    PrimaryIou = table.Column<decimal>(type: "decimal(5,4)", nullable: true),
                    AspectRatio = table.Column<decimal>(type: "decimal(8,5)", nullable: true),
                    Details = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_RuleEvaluations", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "SafetyCriteria",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    Code = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Name = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: false),
                    Description = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    IsActive = table.Column<bool>(type: "bit", nullable: false),
                    SortOrder = table.Column<int>(type: "int", nullable: false),
                    DefaultSeverity = table.Column<int>(type: "int", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_SafetyCriteria", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Sites",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    Code = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Name = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: false),
                    Timezone = table.Column<string>(type: "nvarchar(128)", maxLength: 128, nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Sites", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "RuleDefinitions",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    CriterionId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    Code = table.Column<string>(type: "nvarchar(128)", maxLength: 128, nullable: false),
                    Version = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    Name = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: false),
                    IsActive = table.Column<bool>(type: "bit", nullable: false),
                    IsDefault = table.Column<bool>(type: "bit", nullable: false),
                    Definition = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_RuleDefinitions", x => x.Id);
                    table.ForeignKey(
                        name: "FK_RuleDefinitions_SafetyCriteria_CriterionId",
                        column: x => x.CriterionId,
                        principalTable: "SafetyCriteria",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "Zones",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    SiteId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    Code = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Name = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: false),
                    Description = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Zones", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Zones_Sites_SiteId",
                        column: x => x.SiteId,
                        principalTable: "Sites",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "Cameras",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    SiteId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    ZoneId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                    Code = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Name = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: false),
                    RtspUrl = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    Status = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    FpsConfig = table.Column<int>(type: "int", nullable: true),
                    ResolutionW = table.Column<int>(type: "int", nullable: true),
                    ResolutionH = table.Column<int>(type: "int", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Cameras", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Cameras_Sites_SiteId",
                        column: x => x.SiteId,
                        principalTable: "Sites",
                        principalColumn: "Id");
                    table.ForeignKey(
                        name: "FK_Cameras_Zones_ZoneId",
                        column: x => x.ZoneId,
                        principalTable: "Zones",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                });

            migrationBuilder.CreateTable(
                name: "CameraCriterionAssignments",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    CameraId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    CriterionId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    IsEnabled = table.Column<bool>(type: "bit", nullable: false),
                    RuleDefinitionId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_CameraCriterionAssignments", x => x.Id);
                    table.ForeignKey(
                        name: "FK_CameraCriterionAssignments_Cameras_CameraId",
                        column: x => x.CameraId,
                        principalTable: "Cameras",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_CameraCriterionAssignments_RuleDefinitions_RuleDefinitionId",
                        column: x => x.RuleDefinitionId,
                        principalTable: "RuleDefinitions",
                        principalColumn: "Id");
                    table.ForeignKey(
                        name: "FK_CameraCriterionAssignments_SafetyCriteria_CriterionId",
                        column: x => x.CriterionId,
                        principalTable: "SafetyCriteria",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "ProcessingRuns",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    CameraId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    ModelVersionId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                    StreamStartedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    StreamEndedAt = table.Column<DateTime>(type: "datetime2", nullable: true),
                    Status = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    ConfigSnapshot = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    ErrorMessage = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ProcessingRuns", x => x.Id);
                    table.ForeignKey(
                        name: "FK_ProcessingRuns_Cameras_CameraId",
                        column: x => x.CameraId,
                        principalTable: "Cameras",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_ProcessingRuns_ModelVersions_ModelVersionId",
                        column: x => x.ModelVersionId,
                        principalTable: "ModelVersions",
                        principalColumn: "Id");
                });

            migrationBuilder.CreateTable(
                name: "Violations",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    CameraId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    SiteId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    ZoneId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                    RunId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                    CriterionId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    RuleDefinitionId = table.Column<Guid>(type: "uniqueidentifier", nullable: true),
                    TrackId = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Severity = table.Column<int>(type: "int", nullable: false),
                    StartedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    ConfirmedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    EndedAt = table.Column<DateTime>(type: "datetime2", nullable: true),
                    Status = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    CooldownUntil = table.Column<DateTime>(type: "datetime2", nullable: true),
                    VoteTotalFrames = table.Column<int>(type: "int", nullable: false),
                    VoteViolationFrames = table.Column<int>(type: "int", nullable: false),
                    AspectRatio = table.Column<decimal>(type: "decimal(8,5)", nullable: true),
                    HeadRegionBbox = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    PrimaryIou = table.Column<decimal>(type: "decimal(5,4)", nullable: true),
                    EvaluationMetrics = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    RuleSnapshot = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Violations", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Violations_Cameras_CameraId",
                        column: x => x.CameraId,
                        principalTable: "Cameras",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_Violations_SafetyCriteria_CriterionId",
                        column: x => x.CriterionId,
                        principalTable: "SafetyCriteria",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "Alerts",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    ViolationId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    Channel = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    SentAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    DeliveryStatus = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    Response = table.Column<string>(type: "nvarchar(max)", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Alerts", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Alerts_Violations_ViolationId",
                        column: x => x.ViolationId,
                        principalTable: "Violations",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "ViolationEvidences",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    ViolationId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    CaptureTs = table.Column<DateTime>(type: "datetime2", nullable: false),
                    ImagePath = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    ImageSha256 = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: true),
                    Width = table.Column<int>(type: "int", nullable: true),
                    Height = table.Column<int>(type: "int", nullable: true),
                    PersonBbox = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    EquipmentBbox = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    HelmetBbox = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    Meta = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ViolationEvidences", x => x.Id);
                    table.ForeignKey(
                        name: "FK_ViolationEvidences_Violations_ViolationId",
                        column: x => x.ViolationId,
                        principalTable: "Violations",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Alerts_ViolationId",
                table: "Alerts",
                column: "ViolationId");

            migrationBuilder.CreateIndex(
                name: "IX_CameraCriterionAssignments_CameraId",
                table: "CameraCriterionAssignments",
                column: "CameraId");

            migrationBuilder.CreateIndex(
                name: "IX_CameraCriterionAssignments_CriterionId",
                table: "CameraCriterionAssignments",
                column: "CriterionId");

            migrationBuilder.CreateIndex(
                name: "IX_CameraCriterionAssignments_RuleDefinitionId",
                table: "CameraCriterionAssignments",
                column: "RuleDefinitionId");

            migrationBuilder.CreateIndex(
                name: "IX_Cameras_SiteId_Code",
                table: "Cameras",
                columns: new[] { "SiteId", "Code" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_Cameras_ZoneId",
                table: "Cameras",
                column: "ZoneId");

            migrationBuilder.CreateIndex(
                name: "IX_ProcessingRuns_CameraId",
                table: "ProcessingRuns",
                column: "CameraId");

            migrationBuilder.CreateIndex(
                name: "IX_ProcessingRuns_ModelVersionId",
                table: "ProcessingRuns",
                column: "ModelVersionId");

            migrationBuilder.CreateIndex(
                name: "IX_RuleDefinitions_CriterionId",
                table: "RuleDefinitions",
                column: "CriterionId");

            migrationBuilder.CreateIndex(
                name: "IX_ViolationEvidences_ViolationId",
                table: "ViolationEvidences",
                column: "ViolationId");

            migrationBuilder.CreateIndex(
                name: "IX_Violations_CameraId",
                table: "Violations",
                column: "CameraId");

            migrationBuilder.CreateIndex(
                name: "IX_Violations_CriterionId",
                table: "Violations",
                column: "CriterionId");

            migrationBuilder.CreateIndex(
                name: "IX_Zones_SiteId_Code",
                table: "Zones",
                columns: new[] { "SiteId", "Code" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "Alerts");

            migrationBuilder.DropTable(
                name: "CameraCriterionAssignments");

            migrationBuilder.DropTable(
                name: "CameraHealthLogs");

            migrationBuilder.DropTable(
                name: "Detections");

            migrationBuilder.DropTable(
                name: "FramePreprocessingLogs");

            migrationBuilder.DropTable(
                name: "ProcessingRuns");

            migrationBuilder.DropTable(
                name: "RuleEvaluations");

            migrationBuilder.DropTable(
                name: "ViolationEvidences");

            migrationBuilder.DropTable(
                name: "RuleDefinitions");

            migrationBuilder.DropTable(
                name: "ModelVersions");

            migrationBuilder.DropTable(
                name: "Violations");

            migrationBuilder.DropTable(
                name: "Cameras");

            migrationBuilder.DropTable(
                name: "SafetyCriteria");

            migrationBuilder.DropTable(
                name: "Zones");

            migrationBuilder.DropTable(
                name: "Sites");
        }
    }
}
