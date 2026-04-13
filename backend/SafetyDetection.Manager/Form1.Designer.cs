namespace SafetyDetection.Manager
{
    partial class Form1
    {
        private System.ComponentModel.IContainer components = null;

        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        private void InitializeComponent()
        {
            components = new System.ComponentModel.Container();
            splitContainer1 = new SplitContainer();
            splitContainerLeft = new SplitContainer();
            tabControlData = new TabControl();
            tabPageSites = new TabPage();
            dataGridViewSites = new DataGridView();
            tabPageZones = new TabPage();
            dataGridViewZones = new DataGridView();
            tabPageCameras = new TabPage();
            dataGridViewCameras = new DataGridView();
            tabPageCriteria = new TabPage();
            dataGridViewCriteria = new DataGridView();
            panelAnalytics = new Panel();
            picCameraPreview = new PictureBox();
            lblTotalCritical = new Label();
            lblTotalAlerts = new Label();
            lblAnalyticsTitle = new Label();
            panelLeftTop = new Panel();
            btnSave = new Button();
            btnRefresh = new Button();
            label1 = new Label();
            rtbLiveFeed = new RichTextBox();
            panelRightTop = new Panel();
            btnSimulate = new Button();
            label2 = new Label();
            simTimer = new System.Windows.Forms.Timer(components);
            ((System.ComponentModel.ISupportInitialize)splitContainer1).BeginInit();
            splitContainer1.Panel1.SuspendLayout();
            splitContainer1.Panel2.SuspendLayout();
            splitContainer1.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)splitContainerLeft).BeginInit();
            splitContainerLeft.Panel1.SuspendLayout();
            splitContainerLeft.Panel2.SuspendLayout();
            splitContainerLeft.SuspendLayout();
            tabControlData.SuspendLayout();
            tabPageSites.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)dataGridViewSites).BeginInit();
            tabPageZones.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)dataGridViewZones).BeginInit();
            tabPageCameras.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)dataGridViewCameras).BeginInit();
            tabPageCriteria.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)dataGridViewCriteria).BeginInit();
            panelAnalytics.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)picCameraPreview).BeginInit();
            panelLeftTop.SuspendLayout();
            panelRightTop.SuspendLayout();
            SuspendLayout();
            // 
            // splitContainer1
            // 
            splitContainer1.Dock = DockStyle.Fill;
            splitContainer1.Location = new Point(0, 0);
            splitContainer1.Name = "splitContainer1";
            // 
            // splitContainer1.Panel1
            // 
            splitContainer1.Panel1.Controls.Add(splitContainerLeft);
            splitContainer1.Panel1.Controls.Add(panelLeftTop);
            // 
            // splitContainer1.Panel2
            // 
            splitContainer1.Panel2.Controls.Add(rtbLiveFeed);
            splitContainer1.Panel2.Controls.Add(panelRightTop);
            splitContainer1.Size = new Size(1300, 800);
            splitContainer1.SplitterDistance = 750;
            splitContainer1.TabIndex = 0;
            // 
            // splitContainerLeft
            // 
            splitContainerLeft.Dock = DockStyle.Fill;
            splitContainerLeft.Location = new Point(0, 60);
            splitContainerLeft.Name = "splitContainerLeft";
            splitContainerLeft.Orientation = Orientation.Horizontal;
            // 
            // splitContainerLeft.Panel1
            // 
            splitContainerLeft.Panel1.Controls.Add(tabControlData);
            // 
            // splitContainerLeft.Panel2
            // 
            splitContainerLeft.Panel2.Controls.Add(panelAnalytics);
            splitContainerLeft.Size = new Size(750, 740);
            splitContainerLeft.SplitterDistance = 525;
            splitContainerLeft.TabIndex = 0;
            // 
            // tabControlData
            // 
            tabControlData.Controls.Add(tabPageSites);
            tabControlData.Controls.Add(tabPageZones);
            tabControlData.Controls.Add(tabPageCameras);
            tabControlData.Controls.Add(tabPageCriteria);
            tabControlData.Dock = DockStyle.Fill;
            tabControlData.Location = new Point(0, 0);
            tabControlData.Name = "tabControlData";
            tabControlData.SelectedIndex = 0;
            tabControlData.Size = new Size(750, 525);
            tabControlData.TabIndex = 0;
            // 
            // tabPageSites
            // 
            tabPageSites.Controls.Add(picCameraPreview);
            tabPageSites.Controls.Add(dataGridViewSites);
            tabPageSites.Location = new Point(4, 29);
            tabPageSites.Name = "tabPageSites";
            tabPageSites.Padding = new Padding(3);
            tabPageSites.Size = new Size(742, 492);
            tabPageSites.TabIndex = 0;
            tabPageSites.Text = "🌍 Sites";
            tabPageSites.UseVisualStyleBackColor = true;
            // 
            // dataGridViewSites
            // 
            dataGridViewSites.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
            dataGridViewSites.BackgroundColor = Color.White;
            dataGridViewSites.BorderStyle = BorderStyle.None;
            dataGridViewSites.ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            dataGridViewSites.Dock = DockStyle.Fill;
            dataGridViewSites.Location = new Point(3, 3);
            dataGridViewSites.Name = "dataGridViewSites";
            dataGridViewSites.RowHeadersWidth = 51;
            dataGridViewSites.Size = new Size(736, 486);
            dataGridViewSites.TabIndex = 0;
            // 
            // tabPageZones
            // 
            tabPageZones.Controls.Add(dataGridViewZones);
            tabPageZones.Location = new Point(4, 29);
            tabPageZones.Name = "tabPageZones";
            tabPageZones.Padding = new Padding(3);
            tabPageZones.Size = new Size(192, 67);
            tabPageZones.TabIndex = 1;
            tabPageZones.Text = "📏 Zones";
            tabPageZones.UseVisualStyleBackColor = true;
            // 
            // dataGridViewZones
            // 
            dataGridViewZones.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
            dataGridViewZones.BackgroundColor = Color.White;
            dataGridViewZones.BorderStyle = BorderStyle.None;
            dataGridViewZones.ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            dataGridViewZones.Dock = DockStyle.Fill;
            dataGridViewZones.Location = new Point(3, 3);
            dataGridViewZones.Name = "dataGridViewZones";
            dataGridViewZones.RowHeadersWidth = 51;
            dataGridViewZones.Size = new Size(186, 61);
            dataGridViewZones.TabIndex = 0;
            // 
            // tabPageCameras
            // 
            tabPageCameras.Controls.Add(dataGridViewCameras);
            tabPageCameras.Location = new Point(4, 29);
            tabPageCameras.Name = "tabPageCameras";
            tabPageCameras.Padding = new Padding(3);
            tabPageCameras.Size = new Size(192, 67);
            tabPageCameras.TabIndex = 2;
            tabPageCameras.Text = "🎥 Cameras";
            tabPageCameras.UseVisualStyleBackColor = true;
            // 
            // dataGridViewCameras
            // 
            dataGridViewCameras.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
            dataGridViewCameras.BackgroundColor = Color.White;
            dataGridViewCameras.BorderStyle = BorderStyle.None;
            dataGridViewCameras.ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            dataGridViewCameras.Dock = DockStyle.Fill;
            dataGridViewCameras.Location = new Point(3, 3);
            dataGridViewCameras.Name = "dataGridViewCameras";
            dataGridViewCameras.RowHeadersWidth = 51;
            dataGridViewCameras.Size = new Size(186, 61);
            dataGridViewCameras.TabIndex = 0;
            // 
            // tabPageCriteria
            // 
            tabPageCriteria.Controls.Add(dataGridViewCriteria);
            tabPageCriteria.Location = new Point(4, 29);
            tabPageCriteria.Name = "tabPageCriteria";
            tabPageCriteria.Padding = new Padding(3);
            tabPageCriteria.Size = new Size(192, 67);
            tabPageCriteria.TabIndex = 3;
            tabPageCriteria.Text = "⚠️ Criteria";
            tabPageCriteria.UseVisualStyleBackColor = true;
            // 
            // dataGridViewCriteria
            // 
            dataGridViewCriteria.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
            dataGridViewCriteria.BackgroundColor = Color.White;
            dataGridViewCriteria.BorderStyle = BorderStyle.None;
            dataGridViewCriteria.ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            dataGridViewCriteria.Dock = DockStyle.Fill;
            dataGridViewCriteria.Location = new Point(3, 3);
            dataGridViewCriteria.Name = "dataGridViewCriteria";
            dataGridViewCriteria.RowHeadersWidth = 51;
            dataGridViewCriteria.Size = new Size(186, 61);
            dataGridViewCriteria.TabIndex = 0;
            // 
            // panelAnalytics
            // 
            panelAnalytics.BackColor = Color.FromArgb(236, 240, 241);
            panelAnalytics.Controls.Add(lblTotalCritical);
            panelAnalytics.Controls.Add(lblTotalAlerts);
            panelAnalytics.Controls.Add(lblAnalyticsTitle);
            panelAnalytics.Dock = DockStyle.Fill;
            panelAnalytics.Location = new Point(0, 0);
            panelAnalytics.Name = "panelAnalytics";
            panelAnalytics.Size = new Size(750, 211);
            panelAnalytics.TabIndex = 0;
            // 
            // picCameraPreview
            // 
            picCameraPreview.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            picCameraPreview.BackColor = Color.Black;
            picCameraPreview.Location = new Point(27, 237);
            picCameraPreview.Name = "picCameraPreview";
            picCameraPreview.Size = new Size(668, 237);
            picCameraPreview.SizeMode = PictureBoxSizeMode.StretchImage;
            picCameraPreview.TabIndex = 0;
            picCameraPreview.TabStop = false;
            picCameraPreview.Paint += picCameraPreview_Paint;
            // 
            // lblTotalCritical
            // 
            lblTotalCritical.AutoSize = true;
            lblTotalCritical.Font = new Font("Segoe UI", 12F, FontStyle.Bold);
            lblTotalCritical.ForeColor = Color.FromArgb(192, 57, 43);
            lblTotalCritical.Location = new Point(12, 120);
            lblTotalCritical.Name = "lblTotalCritical";
            lblTotalCritical.Size = new Size(185, 28);
            lblTotalCritical.TabIndex = 1;
            lblTotalCritical.Text = "Critical Severity: 0";
            // 
            // lblTotalAlerts
            // 
            lblTotalAlerts.AutoSize = true;
            lblTotalAlerts.Font = new Font("Segoe UI", 12F, FontStyle.Bold);
            lblTotalAlerts.ForeColor = Color.FromArgb(41, 128, 185);
            lblTotalAlerts.Location = new Point(12, 80);
            lblTotalAlerts.Name = "lblTotalAlerts";
            lblTotalAlerts.Size = new Size(207, 28);
            lblTotalAlerts.TabIndex = 2;
            lblTotalAlerts.Text = "Total Alerts Today: 0";
            // 
            // lblAnalyticsTitle
            // 
            lblAnalyticsTitle.AutoSize = true;
            lblAnalyticsTitle.Font = new Font("Segoe UI", 14F, FontStyle.Bold);
            lblAnalyticsTitle.ForeColor = Color.FromArgb(44, 62, 80);
            lblAnalyticsTitle.Location = new Point(12, 15);
            lblAnalyticsTitle.Name = "lblAnalyticsTitle";
            lblAnalyticsTitle.Size = new Size(322, 32);
            lblAnalyticsTitle.TabIndex = 3;
            lblAnalyticsTitle.Text = "📊 AI Analytics Dashboard";
            // 
            // panelLeftTop
            // 
            panelLeftTop.BackColor = Color.FromArgb(41, 128, 185);
            panelLeftTop.Controls.Add(btnSave);
            panelLeftTop.Controls.Add(btnRefresh);
            panelLeftTop.Controls.Add(label1);
            panelLeftTop.Dock = DockStyle.Top;
            panelLeftTop.Location = new Point(0, 0);
            panelLeftTop.Name = "panelLeftTop";
            panelLeftTop.Size = new Size(750, 60);
            panelLeftTop.TabIndex = 1;
            // 
            // btnSave
            // 
            btnSave.BackColor = Color.FromArgb(46, 204, 113);
            btnSave.FlatStyle = FlatStyle.Flat;
            btnSave.ForeColor = Color.White;
            btnSave.Location = new Point(510, 15);
            btnSave.Name = "btnSave";
            btnSave.Size = new Size(100, 30);
            btnSave.TabIndex = 0;
            btnSave.Text = "Save DB";
            btnSave.UseVisualStyleBackColor = false;
            btnSave.Click += btnSave_Click;
            // 
            // btnRefresh
            // 
            btnRefresh.BackColor = Color.FromArgb(52, 152, 219);
            btnRefresh.FlatStyle = FlatStyle.Flat;
            btnRefresh.ForeColor = Color.White;
            btnRefresh.Location = new Point(400, 15);
            btnRefresh.Name = "btnRefresh";
            btnRefresh.Size = new Size(100, 30);
            btnRefresh.TabIndex = 1;
            btnRefresh.Text = "Refresh";
            btnRefresh.UseVisualStyleBackColor = false;
            btnRefresh.Click += btnRefresh_Click;
            // 
            // label1
            // 
            label1.AutoSize = true;
            label1.Font = new Font("Segoe UI", 16F, FontStyle.Bold);
            label1.ForeColor = Color.White;
            label1.Location = new Point(12, 15);
            label1.Name = "label1";
            label1.Size = new Size(287, 37);
            label1.TabIndex = 2;
            label1.Text = "System Management";
            // 
            // rtbLiveFeed
            // 
            rtbLiveFeed.BackColor = Color.FromArgb(44, 62, 80);
            rtbLiveFeed.Dock = DockStyle.Fill;
            rtbLiveFeed.Font = new Font("Consolas", 11F);
            rtbLiveFeed.ForeColor = Color.FromArgb(236, 240, 241);
            rtbLiveFeed.Location = new Point(0, 60);
            rtbLiveFeed.Name = "rtbLiveFeed";
            rtbLiveFeed.ReadOnly = true;
            rtbLiveFeed.Size = new Size(546, 740);
            rtbLiveFeed.TabIndex = 0;
            rtbLiveFeed.Text = "Waiting for AI streams...\n";
            // 
            // panelRightTop
            // 
            panelRightTop.BackColor = Color.FromArgb(231, 76, 60);
            panelRightTop.Controls.Add(btnSimulate);
            panelRightTop.Controls.Add(label2);
            panelRightTop.Dock = DockStyle.Top;
            panelRightTop.Location = new Point(0, 0);
            panelRightTop.Name = "panelRightTop";
            panelRightTop.Size = new Size(546, 60);
            panelRightTop.TabIndex = 1;
            // 
            // btnSimulate
            // 
            btnSimulate.BackColor = Color.FromArgb(192, 57, 43);
            btnSimulate.FlatStyle = FlatStyle.Flat;
            btnSimulate.ForeColor = Color.White;
            btnSimulate.Location = new Point(320, 15);
            btnSimulate.Name = "btnSimulate";
            btnSimulate.Size = new Size(140, 30);
            btnSimulate.TabIndex = 0;
            btnSimulate.Text = "Start Simulation";
            btnSimulate.UseVisualStyleBackColor = false;
            btnSimulate.Click += btnSimulate_Click;
            // 
            // label2
            // 
            label2.AutoSize = true;
            label2.Font = new Font("Segoe UI", 16F, FontStyle.Bold);
            label2.ForeColor = Color.White;
            label2.Location = new Point(12, 15);
            label2.Name = "label2";
            label2.Size = new Size(297, 37);
            label2.TabIndex = 1;
            label2.Text = "Live AI Violation Feed";
            // 
            // simTimer
            // 
            simTimer.Interval = 2500;
            simTimer.Tick += SimTimer_Tick;
            // 
            // Form1
            // 
            AutoScaleDimensions = new SizeF(8F, 20F);
            AutoScaleMode = AutoScaleMode.Font;
            ClientSize = new Size(1300, 800);
            Controls.Add(splitContainer1);
            Name = "Form1";
            Text = "Safety Detection Manager Dashboard";
            Load += Form1_Load;
            splitContainer1.Panel1.ResumeLayout(false);
            splitContainer1.Panel2.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)splitContainer1).EndInit();
            splitContainer1.ResumeLayout(false);
            splitContainerLeft.Panel1.ResumeLayout(false);
            splitContainerLeft.Panel2.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)splitContainerLeft).EndInit();
            splitContainerLeft.ResumeLayout(false);
            tabControlData.ResumeLayout(false);
            tabPageSites.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)dataGridViewSites).EndInit();
            tabPageZones.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)dataGridViewZones).EndInit();
            tabPageCameras.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)dataGridViewCameras).EndInit();
            tabPageCriteria.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)dataGridViewCriteria).EndInit();
            panelAnalytics.ResumeLayout(false);
            panelAnalytics.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)picCameraPreview).EndInit();
            panelLeftTop.ResumeLayout(false);
            panelLeftTop.PerformLayout();
            panelRightTop.ResumeLayout(false);
            panelRightTop.PerformLayout();
            ResumeLayout(false);
        }

        #endregion

        private System.Windows.Forms.SplitContainer splitContainer1;
        private System.Windows.Forms.SplitContainer splitContainerLeft;
        private System.Windows.Forms.Panel panelLeftTop;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.Button btnSave;
        private System.Windows.Forms.Button btnRefresh;
        
        private System.Windows.Forms.TabControl tabControlData;
        private System.Windows.Forms.TabPage tabPageSites;
        private System.Windows.Forms.DataGridView dataGridViewSites;
        private System.Windows.Forms.TabPage tabPageZones;
        private System.Windows.Forms.DataGridView dataGridViewZones;
        private System.Windows.Forms.TabPage tabPageCameras;
        private System.Windows.Forms.DataGridView dataGridViewCameras;
        private System.Windows.Forms.TabPage tabPageCriteria;
        private System.Windows.Forms.DataGridView dataGridViewCriteria;

        private System.Windows.Forms.Panel panelAnalytics;
        private System.Windows.Forms.Label lblAnalyticsTitle;
        private System.Windows.Forms.Label lblTotalAlerts;
        private System.Windows.Forms.Label lblTotalCritical;
        private System.Windows.Forms.PictureBox picCameraPreview;

        private System.Windows.Forms.Panel panelRightTop;
        private System.Windows.Forms.RichTextBox rtbLiveFeed;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.Button btnSimulate;
        private System.Windows.Forms.Timer simTimer;
    }
}
