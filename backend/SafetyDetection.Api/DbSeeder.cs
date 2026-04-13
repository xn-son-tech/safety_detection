using System;
using System.Linq;
using SafetyDetection.Shared.Data;
using SafetyDetection.Shared.Models;

namespace SafetyDetection.Api
{
    public static class DbSeeder
    {
        public static void Seed(SafetyDbContext context)
        {
            context.Database.EnsureCreated();

            if (!context.Sites.Any())
            {
                var site1 = new Site { Id = Guid.NewGuid(), Code = "SITE_HN_01", Name = "Công trường Cầu Giấy", Timezone = "Asia/Ho_Chi_Minh", CreatedAt = DateTime.UtcNow, UpdatedAt = DateTime.UtcNow };
                var site2 = new Site { Id = Guid.NewGuid(), Code = "SITE_HCM_02", Name = "Công trình Quận 1", Timezone = "Asia/Ho_Chi_Minh", CreatedAt = DateTime.UtcNow, UpdatedAt = DateTime.UtcNow };
                
                context.Sites.AddRange(site1, site2);

                var zone1 = new Zone { Id = Guid.NewGuid(), SiteId = site1.Id, Code = "ZONE_GATE", Name = "Khu vực Cổng Chính", CreatedAt = DateTime.UtcNow, UpdatedAt = DateTime.UtcNow };
                var zone2 = new Zone { Id = Guid.NewGuid(), SiteId = site1.Id, Code = "ZONE_CRANE", Name = "Khu vực Cẩu tháp", CreatedAt = DateTime.UtcNow, UpdatedAt = DateTime.UtcNow };
                
                context.Zones.AddRange(zone1, zone2);

                var cam1 = new Camera { Id = Guid.NewGuid(), SiteId = site1.Id, ZoneId = zone1.Id, Code = "CAM_01", Name = "Camera Cổng", Status = "active", FpsConfig = 30, CreatedAt = DateTime.UtcNow, UpdatedAt = DateTime.UtcNow };
                var cam2 = new Camera { Id = Guid.NewGuid(), SiteId = site1.Id, ZoneId = zone2.Id, Code = "CAM_02", Name = "Camera Cẩu Tháp Góc A", Status = "active", FpsConfig = 15, CreatedAt = DateTime.UtcNow, UpdatedAt = DateTime.UtcNow };
                
                context.Cameras.AddRange(cam1, cam2);

                var crit1 = new SafetyCriterion { Id = Guid.NewGuid(), Code = "NO_HELMET", Name = "Không đội mũ bảo hiểm", IsActive = true, DefaultSeverity = 2, CreatedAt = DateTime.UtcNow, UpdatedAt = DateTime.UtcNow };
                var crit2 = new SafetyCriterion { Id = Guid.NewGuid(), Code = "NO_REFLECTIVE_VEST", Name = "Không mặc áo phản quang", IsActive = true, DefaultSeverity = 2, CreatedAt = DateTime.UtcNow, UpdatedAt = DateTime.UtcNow };
                var crit3 = new SafetyCriterion { Id = Guid.NewGuid(), Code = "UNAUTHORIZED_ACCESS", Name = "Xâm nhập trái phép", IsActive = true, DefaultSeverity = 3, CreatedAt = DateTime.UtcNow, UpdatedAt = DateTime.UtcNow };

                context.SafetyCriteria.AddRange(crit1, crit2, crit3);

                context.SaveChanges();
            }
        }
    }
}
