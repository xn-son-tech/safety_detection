using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SafetyDetection.Shared.Data;
using SafetyDetection.Shared.Models;

namespace SafetyDetection.Api.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class ViolationsController : ControllerBase
    {
        private readonly SafetyDbContext _context;

        public ViolationsController(SafetyDbContext context)
        {
            _context = context;
        }

        [HttpGet]
        public async Task<ActionResult<IEnumerable<Violation>>> GetViolations()
        {
            return await _context.Violations
                .Include(v => v.Evidences)
                .OrderByDescending(v => v.CreatedAt)
                .Take(100)
                .ToListAsync();
        }

        [HttpPost]
        public async Task<ActionResult<Violation>> PostViolation(Violation violation)
        {
            var cutoffTime = DateTime.UtcNow.AddMinutes(-5);
            var existingViolation = await _context.Violations
                .Include(v => v.Evidences)
                .Where(v => v.TrackId == violation.TrackId && v.Status == "open" && v.CreatedAt >= cutoffTime)
                .OrderByDescending(v => v.CreatedAt)
                .FirstOrDefaultAsync();

            if (existingViolation != null)
            {
                // UPSERT: Tránh tạo Record mới, chỉ cập nhật dồn dữ liệu
                existingViolation.UpdatedAt = DateTime.UtcNow;
                existingViolation.VoteTotalFrames += violation.VoteTotalFrames;
                existingViolation.VoteViolationFrames += violation.VoteViolationFrames;

                // Chỉ lưu tối đa 5 ảnh để tiết kiệm dung lượng DB Base64
                if (violation.Evidences != null && violation.Evidences.Any() && existingViolation.Evidences.Count < 5)
                {
                    foreach (var ev in violation.Evidences)
                    {
                        ev.Id = Guid.NewGuid();
                        ev.ViolationId = existingViolation.Id;
                        existingViolation.Evidences.Add(ev);
                    }
                }
                
                await _context.SaveChangesAsync();
                return Ok(existingViolation);
            }

            // MỚI: Nếu chưa có, tiến hành Insert tạo Guid
            violation.Id = Guid.NewGuid();
            violation.CreatedAt = DateTime.UtcNow;
            violation.UpdatedAt = DateTime.UtcNow;
            
            if (violation.Evidences != null)
            {
                foreach (var ev in violation.Evidences)
                {
                    ev.Id = Guid.NewGuid();
                    ev.ViolationId = violation.Id;
                }
            }

            _context.Violations.Add(violation);
            await _context.SaveChangesAsync();

            return CreatedAtAction(nameof(GetViolations), new { id = violation.Id }, violation);
        }
    }
}
