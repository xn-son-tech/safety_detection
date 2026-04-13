using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SafetyDetection.Shared.Data;
using SafetyDetection.Shared.Models;

namespace SafetyDetection.Api.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class SitesController : ControllerBase
    {
        private readonly SafetyDbContext _context;

        public SitesController(SafetyDbContext context)
        {
            _context = context;
        }

        [HttpGet]
        public async Task<ActionResult<IEnumerable<Site>>> GetSites()
        {
            return await _context.Sites.ToListAsync();
        }

        [HttpGet("{id}")]
        public async Task<ActionResult<Site>> GetSite(Guid id)
        {
            var site = await _context.Sites.FindAsync(id);

            if (site == null)
            {
                return NotFound();
            }

            return site;
        }

        [HttpPost]
        public async Task<ActionResult<Site>> PostSite(Site site)
        {
            site.Id = Guid.NewGuid();
            site.CreatedAt = DateTime.UtcNow;
            site.UpdatedAt = DateTime.UtcNow;
            
            _context.Sites.Add(site);
            await _context.SaveChangesAsync();

            return CreatedAtAction(nameof(GetSite), new { id = site.Id }, site);
        }

        [HttpPut("{id}")]
        public async Task<IActionResult> PutSite(Guid id, Site site)
        {
            if (id != site.Id)
            {
                return BadRequest();
            }

            site.UpdatedAt = DateTime.UtcNow;
            _context.Entry(site).State = EntityState.Modified;

            try
            {
                await _context.SaveChangesAsync();
            }
            catch (DbUpdateConcurrencyException)
            {
                if (!SiteExists(id))
                {
                    return NotFound();
                }
                else
                {
                    throw;
                }
            }

            return NoContent();
        }

        [HttpDelete("{id}")]
        public async Task<IActionResult> DeleteSite(Guid id)
        {
            var site = await _context.Sites.FindAsync(id);
            if (site == null)
            {
                return NotFound();
            }

            _context.Sites.Remove(site);
            await _context.SaveChangesAsync();

            return NoContent();
        }

        private bool SiteExists(Guid id)
        {
            return _context.Sites.Any(e => e.Id == id);
        }
    }
}
