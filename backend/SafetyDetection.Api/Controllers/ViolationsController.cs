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
            violation.Id = Guid.NewGuid();
            violation.CreatedAt = DateTime.UtcNow;
            violation.UpdatedAt = DateTime.UtcNow;
            
            _context.Violations.Add(violation);
            await _context.SaveChangesAsync();

            return CreatedAtAction(nameof(GetViolations), new { id = violation.Id }, violation);
        }
    }
}
