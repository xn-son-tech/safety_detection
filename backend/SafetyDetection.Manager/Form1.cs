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

        private string PythonApiUrl = "http://localhost:5000";

        private void btnSimulate_Click(object sender, EventArgs e)
        {
            _isSimulating = !_isSimulating;
            if (_isSimulating)
            {
                simTimer.Interval = 50; // Pull 5 FPS
                simTimer.Start();
                btnSimulate.Text = "Disconnect Live Feed";
                btnSimulate.BackColor = Color.Gray;
                AppendLog("Connecting to Python Live Stream at " + PythonApiUrl + "...\n");
            }
            else
            {
                simTimer.Stop();
                btnSimulate.Text = "Connect to Live Feed";
                btnSimulate.BackColor = Color.FromArgb(192, 57, 43);
                AppendLog("Connection Closed.\n");
                _drawBbox = false;
                if (picCameraPreview.Image != null) picCameraPreview.Image.Dispose();
                picCameraPreview.Image = null;
                picCameraPreview.Invalidate();
            }
        }

        private async void SimTimer_Tick(object sender, EventArgs e)
        {
             // 1. Fetch Latest Frame from Python API
            try
            {
                var request = System.Net.WebRequest.Create($"{PythonApiUrl}/latest_frame");
                request.Timeout = 1000;
                using var response = await request.GetResponseAsync();
                using var stream = response.GetResponseStream();
                if (stream != null)
                {
                    var img = Image.FromStream(stream);
                    var oldImage = picCameraPreview.Image;
                    picCameraPreview.Image = img;
                    oldImage?.Dispose();
                }
            }
            catch { /* Frame API not running */ }

            // 2. Fetch Latest Violations from Shared DB (created by SafetyDetection.Api / Python)
            if (_context.Sites.Local.Count == 0) return;

            try
            {
                var latestViolations = _context.Violations.AsNoTracking()
                    .OrderByDescending(v => v.CreatedAt)
                    .Take(5)
                    .ToList();
                    
                foreach (var vio in latestViolations)
                {
                    // Check if we already logged this to avoid duplicate prints
                    if (!_context.Violations.Local.Any(x => x.Id == vio.Id))
                    {
                        var critName = _context.SafetyCriteria.FirstOrDefault(c => c.Id == vio.CriterionId)?.Name ?? "NO_HELMET";
                        var severityText = vio.Severity == 3 ? "CRITICAL" : "HIGH";
                        
                        var logStr = $"[{vio.CreatedAt.ToLocalTime():HH:mm:ss}] ⚠️ NEW ALERT!\n" +
                                     $"   Violation : {critName}\n" +
                                     $"   Severity  : {severityText}\n" +
                                     $"   Track ID  : {vio.TrackId}\n" +
                                     $"----------------------------------------";
                        AppendLog(logStr);
                        
                        _totalAlerts++;
                        if (vio.Severity == 3) _totalCritical++;
                        lblTotalAlerts.Text = $"Total Alerts Today: {_totalAlerts}";
                        lblTotalCritical.Text = $"Critical Severity: {_totalCritical}";
                        
                        // Attach to local tracker
                        _context.Violations.Attach(vio);
                    }
                }
            } 
            catch { /* Ignore minor DB timeout/glitches during polling */ }
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

            if (picCameraPreview.Image == null)
            {
                Font font = new Font("Segoe UI", 12, FontStyle.Italic);
                g.DrawString("NO SIGNAL / WAITING FOR PYTHON STREAM...", font, Brushes.Gray, 10, 10);
            }
        }

        private void AppendLog(string message)
        {
            rtbLiveFeed.AppendText(message + "\n");
            rtbLiveFeed.ScrollToCaret();
        }
    }
}
