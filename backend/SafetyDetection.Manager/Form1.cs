using System;
using System.Drawing;
using System.Linq;
using System.Threading.Tasks;
using System.Collections.Generic;
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

        private System.Threading.CancellationTokenSource _streamCts;

        private void btnSimulate_Click(object sender, EventArgs e)
        {
            _isSimulating = !_isSimulating;
            if (_isSimulating)
            {
                btnSimulate.Text = "Disconnect Live Feed";
                btnSimulate.BackColor = Color.Gray;
                AppendLog("Connecting to Python Live Stream (MJPEG via TCP) at " + PythonApiUrl + "...\n");
                
                _streamCts = new System.Threading.CancellationTokenSource();
                _ = StartMjpegStreamAsync(_streamCts.Token);
                _ = PollDatabaseAsync(_streamCts.Token);
            }
            else
            {
                if (_streamCts != null)
                {
                    _streamCts.Cancel();
                    _streamCts.Dispose();
                    _streamCts = null;
                }
                btnSimulate.Text = "Connect to Live Feed";
                btnSimulate.BackColor = Color.FromArgb(192, 57, 43);
                AppendLog("Connection Closed.\n");
                _drawBbox = false;
                if (picCameraPreview.Image != null) picCameraPreview.Image.Dispose();
                picCameraPreview.Image = null;
                picCameraPreview.Invalidate();
            }
        }

        private async Task StartMjpegStreamAsync(System.Threading.CancellationToken token)
        {
            using var client = new System.Net.Http.HttpClient();
            client.Timeout = TimeSpan.FromMilliseconds(System.Threading.Timeout.Infinite);
            
            try 
            {
                using var response = await client.GetAsync($"{PythonApiUrl}/stream", System.Net.Http.HttpCompletionOption.ResponseHeadersRead, token);
                response.EnsureSuccessStatusCode();
                using var stream = await response.Content.ReadAsStreamAsync(token);
                
                var buffer = new byte[81920]; 
                var imgBuffer = new List<byte>(1024 * 1024); 
                
                while (!token.IsCancellationRequested)
                {
                    int bytesRead = await stream.ReadAsync(buffer, 0, buffer.Length, token);
                    if (bytesRead == 0) break;
                    
                    imgBuffer.AddRange(buffer.Take(bytesRead));
                    
                    int startIdx = FindBoundary(imgBuffer, new byte[] { 0xFF, 0xD8 });
                    if (startIdx >= 0)
                    {
                        int endIdx = FindBoundary(imgBuffer, new byte[] { 0xFF, 0xD9 }, startIdx);
                        if (endIdx > startIdx)
                        {
                            endIdx += 2; 
                            var imgData = imgBuffer.Skip(startIdx).Take(endIdx - startIdx).ToArray();
                            imgBuffer.RemoveRange(0, endIdx);
                            
                            try
                            {
                                using var ms = new System.IO.MemoryStream(imgData);
                                var img = Image.FromStream(ms);
                                
                                this.Invoke((MethodInvoker)delegate {
                                    var oldImage = picCameraPreview.Image;
                                    picCameraPreview.Image = img;
                                    oldImage?.Dispose();
                                });
                            }
                            catch { }
                        }
                    }
                    if (imgBuffer.Count > 5 * 1024 * 1024) imgBuffer.Clear();
                }
            }
            catch { }
        }

        private int FindBoundary(List<byte> buffer, byte[] marker, int startIndex = 0)
        {
            for (int i = startIndex; i <= buffer.Count - marker.Length; i++)
            {
                bool match = true;
                for (int j = 0; j < marker.Length; j++)
                {
                    if (buffer[i + j] != marker[j])
                    {
                        match = false;
                        break;
                    }
                }
                if (match) return i;
            }
            return -1;
        }

        private async Task PollDatabaseAsync(System.Threading.CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                if (_context.Sites.Local.Count > 0)
                {
                    try
                    {
                        var latestViolations = _context.Violations.AsNoTracking()
                            .OrderByDescending(v => v.CreatedAt)
                            .Take(5)
                            .ToList();

                        foreach (var vio in latestViolations)
                        {
                            if (!_context.Violations.Local.Any(x => x.Id == vio.Id))
                            {
                                var critName = _context.SafetyCriteria.FirstOrDefault(c => c.Id == vio.CriterionId)?.Name ?? "NO_HELMET";
                                var severityText = vio.Severity == 3 ? "CRITICAL" : "HIGH";

                                var logStr = $"[{vio.CreatedAt.ToLocalTime():HH:mm:ss}] ⚠️ NEW ALERT!\n" +
                                             $"   Violation : {critName}\n" +
                                             $"   Severity  : {severityText}\n" +
                                             $"   Track ID  : {vio.TrackId}\n" +
                                             $"----------------------------------------";
                                this.Invoke((MethodInvoker)delegate {
                                    AppendLog(logStr);
                                    _totalAlerts++;
                                    if (vio.Severity == 3) _totalCritical++;
                                    lblTotalAlerts.Text = $"Total Alerts Today: {_totalAlerts}";
                                    lblTotalCritical.Text = $"Critical Severity: {_totalCritical}";
                                });

                                _context.Violations.Attach(vio);
                            }
                        }
                    }
                    catch { }
                }
                
                await Task.Delay(500, token); // Optimised: DB checked only 2 times a second
            }
        }

        private void SimTimer_Tick(object sender, EventArgs e)
        {
            // Deprecated: Loop functionality moved to StartMjpegStreamAsync & PollDatabaseAsync
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

        private void rtbLiveFeed_TextChanged(object sender, EventArgs e)
        {

        }
    }
}
