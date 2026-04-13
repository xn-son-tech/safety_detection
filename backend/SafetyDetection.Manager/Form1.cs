using System;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using Microsoft.EntityFrameworkCore;
using SafetyDetection.Shared.Data;
using SafetyDetection.Shared.Models;

namespace SafetyDetection.Manager
{
    public partial class Form1 : Form
    {
        private SafetyDbContext _context;
        private bool _isSimulating = false;
        private Random _random = new Random();
        
        private int _totalAlerts = 0;
        private int _totalCritical = 0;

        // Bounding box animation states
        private bool _drawBbox = false;
        private Rectangle _currentBbox;
        private string _currentBboxLabel;

        public Form1()
        {
            InitializeComponent();
        }

        private void Form1_Load(object sender, EventArgs e)
        {
            var optionsBuilder = new DbContextOptionsBuilder<SafetyDbContext>();
            optionsBuilder.UseSqlServer("Server=localhost;Database=SafetyDetectionDb;Trusted_Connection=True;MultipleActiveResultSets=true;TrustServerCertificate=True");
            _context = new SafetyDbContext(optionsBuilder.Options);

            _context.Database.EnsureCreated();
            LoadData();
        }

        private void LoadData()
        {
            _context.Sites.Load();
            _context.Zones.Load();
            _context.Cameras.Load();
            _context.SafetyCriteria.Load();

            dataGridViewSites.DataSource = _context.Sites.Local.ToBindingList();
            dataGridViewZones.DataSource = _context.Zones.Local.ToBindingList();
            dataGridViewCameras.DataSource = _context.Cameras.Local.ToBindingList();
            dataGridViewCriteria.DataSource = _context.SafetyCriteria.Local.ToBindingList();
        }

        private void btnRefresh_Click(object sender, EventArgs e)
        {
            LoadData();
        }

        private void btnSave_Click(object sender, EventArgs e)
        {
            try
            {
                // Auto generate Guids for any new entities across collections
                foreach (var site in _context.Sites.Local.Where(s => s.Id == Guid.Empty))
                {
                    site.Id = Guid.NewGuid();
                    site.CreatedAt = DateTime.UtcNow;
                }
                foreach (var zone in _context.Zones.Local.Where(z => z.Id == Guid.Empty))
                {
                    zone.Id = Guid.NewGuid();
                    zone.CreatedAt = DateTime.UtcNow;
                }
                foreach (var cam in _context.Cameras.Local.Where(c => c.Id == Guid.Empty))
                {
                    cam.Id = Guid.NewGuid();
                    cam.CreatedAt = DateTime.UtcNow;
                }
                foreach (var crit in _context.SafetyCriteria.Local.Where(c => c.Id == Guid.Empty))
                {
                    crit.Id = Guid.NewGuid();
                    crit.CreatedAt = DateTime.UtcNow;
                }

                foreach (var entry in _context.ChangeTracker.Entries().Where(e => e.State == EntityState.Modified))
                {
                    if (entry.Entity is Site s) s.UpdatedAt = DateTime.UtcNow;
                    else if (entry.Entity is Zone z) z.UpdatedAt = DateTime.UtcNow;
                    else if (entry.Entity is Camera c) c.UpdatedAt = DateTime.UtcNow;
                    else if (entry.Entity is SafetyCriterion sc) sc.UpdatedAt = DateTime.UtcNow;
                }

                _context.SaveChanges();
                MessageBox.Show("All database changes saved successfully!", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error saving data: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void btnSimulate_Click(object sender, EventArgs e)
        {
            _isSimulating = !_isSimulating;
            if (_isSimulating)
            {
                simTimer.Start();
                btnSimulate.Text = "Stop Simulation";
                btnSimulate.BackColor = Color.Gray;
                AppendLog("Simulation Started. Waiting for live streams...\n");
            }
            else
            {
                simTimer.Stop();
                btnSimulate.Text = "Start Simulation";
                btnSimulate.BackColor = Color.FromArgb(192, 57, 43);
                AppendLog("Simulation Stopped.\n");
                _drawBbox = false;
                picCameraPreview.Invalidate();
            }
        }

        private void SimTimer_Tick(object sender, EventArgs e)
        {
            if (_context.Sites.Local.Count == 0) return; // Wait for data sync if none exists

            var severity = _random.Next(1, 4);
            var severityText = severity == 3 ? "CRITICAL" : (severity == 2 ? "HIGH" : "MEDIUM");
            var ruleCode = _random.Next(0, 2) == 0 ? "NO_HELMET" : "UNAUTHORIZED_ACCESS";

            // Find Real objects for UI rendering
            var mockSite = _context.Sites.FirstOrDefault();
            var mockSiteId = mockSite?.Id ?? Guid.NewGuid();
            var siteName = mockSite?.Name ?? "Unknown Site";

            var mockCamera = _context.Cameras.FirstOrDefault(c => c.SiteId == mockSiteId) ?? _context.Cameras.FirstOrDefault();
            var mockCameraId = mockCamera?.Id ?? Guid.NewGuid();
            var camName = mockCamera?.Name ?? "Unknown Camera";

            var mockCriterion = _context.SafetyCriteria.FirstOrDefault(c => c.Code == ruleCode) ?? _context.SafetyCriteria.FirstOrDefault();
            var mockCriterionId = mockCriterion?.Id ?? Guid.NewGuid();
            var critName = mockCriterion?.Name ?? ruleCode;

            var violationId = Guid.NewGuid();

            // Update Logs
            var logStr = $"[{DateTime.Now:HH:mm:ss}] ⚠️ NEW ALERT!\n" +
                         $"   Violation : {critName} ({ruleCode})\n" +
                         $"   Severity  : {severityText}\n" +
                         $"   Location  : {siteName} - {camName}\n" +
                         $"   Track ID  : person_{_random.Next(1000, 9999)}\n" +
                         $"----------------------------------------";
            AppendLog(logStr);

            // Update Analytics Labels
            _totalAlerts++;
            if (severity == 3) _totalCritical++;
            lblTotalAlerts.Text = $"Total Alerts Today: {_totalAlerts}";
            lblTotalCritical.Text = $"Critical Severity: {_totalCritical}";

            // Trigger Camera Preview Bounding Box Animation
            _drawBbox = true;
            _currentBboxLabel = $"{ruleCode} ({Math.Round(_random.NextDouble() * 0.4 + 0.5, 2)*100}%)";
            _currentBbox = new Rectangle(
                _random.Next(20, picCameraPreview.Width - 100), 
                _random.Next(20, picCameraPreview.Height - 100), 
                _random.Next(50, 100), 
                _random.Next(50, 150)
            );
            picCameraPreview.Invalidate();

            // Persist to database
            var v = new Violation
            {
                Id = violationId,
                SiteId = mockSiteId,
                CameraId = mockCameraId,
                CriterionId = mockCriterionId,
                TrackId = $"person_{_random.Next(1000, 9999)}",
                Severity = severity,
                StartedAt = DateTime.UtcNow,
                ConfirmedAt = DateTime.UtcNow,
                Status = "open",
                VoteTotalFrames = 30,
                VoteViolationFrames = 25,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow
            };
            
            try
            {
                _context.Violations.Add(v);
                _context.SaveChanges();
            } 
            catch { /* Ignore minor FK glitches during fast polling */ }
        }

        private void picCameraPreview_Paint(object sender, PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;

            // Draw a subtle grid to simulate a raw camera feed viewport
            Pen gridPen = new Pen(Color.FromArgb(30, 255, 255, 255), 1);
            for (int i = 0; i < picCameraPreview.Width; i += 40)
                g.DrawLine(gridPen, i, 0, i, picCameraPreview.Height);
            for (int i = 0; i < picCameraPreview.Height; i += 40)
                g.DrawLine(gridPen, 0, i, picCameraPreview.Width, i);

            if (_drawBbox)
            {
                // Draw AI Bounding Box
                Pen boxPen = new Pen(Color.Red, 3);
                g.DrawRectangle(boxPen, _currentBbox);
                
                // Draw Label Box
                Font font = new Font("Segoe UI", 9, FontStyle.Bold);
                SizeF textSize = g.MeasureString(_currentBboxLabel, font);
                RectangleF textRect = new RectangleF(_currentBbox.X, _currentBbox.Y - 20, textSize.Width, 20);
                
                g.FillRectangle(Brushes.Red, textRect);
                g.DrawString(_currentBboxLabel, font, Brushes.White, _currentBbox.X, _currentBbox.Y - 20);
                
                // Overlay REC icon
                g.FillEllipse(Brushes.Red, picCameraPreview.Width - 30, 10, 15, 15);
                g.DrawString("REC", font, Brushes.White, picCameraPreview.Width - 65, 10);
            }
            else
            {
                Font font = new Font("Segoe UI", 12, FontStyle.Italic);
                g.DrawString("NO SIGNAL / WAITING...", font, Brushes.Gray, 10, 10);
            }
        }

        private void AppendLog(string message)
        {
            rtbLiveFeed.AppendText(message + "\n");
            rtbLiveFeed.ScrollToCaret();
        }
    }
}
