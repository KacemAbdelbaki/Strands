import logging
from strands import tool

logger = logging.getLogger(__name__)


@tool
def search_pfe_jobs(
    keywords: str = "PFE stage informatique",
    location: str = "Tunisia",
    max_results: int = 15,
    hours_old: int = 168,
    sites: str = "linkedin",
) -> str:
    """Search LinkedIn (and optionally Indeed/Glassdoor) for PFE / internship / stage offers.

    Use this tool when the user asks to find PFE offers, internships, or stage
    opportunities on LinkedIn or other job boards.

    Args:
        keywords:    Search terms, e.g. "PFE développement web", "stage data science".
        location:    City, region, or country, e.g. "Tunisia", "France", "Tunis".
        max_results: Maximum number of results to return (default 15).
        hours_old:   Only return jobs posted within this many hours (default 168 = 1 week).
        sites:       Comma-separated list of sites to search. Options: linkedin, indeed, glassdoor.
                     Default is "linkedin". Example: "linkedin,indeed".

    Returns:
        A formatted Markdown summary of matching job offers, or an error message.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError:
        return (
            "Error: python-jobspy is not installed. "
            "Run `pip install python-jobspy` to enable LinkedIn job search."
        )

    site_list = [s.strip().lower() for s in sites.split(",") if s.strip()]
    if not site_list:
        site_list = ["linkedin"]

    logger.info(
        "Searching %s for '%s' in '%s' (max %d, last %dh)",
        site_list, keywords, location, max_results, hours_old,
    )

    try:
        jobs_df = scrape_jobs(
            site_name=site_list,
            search_term=keywords,
            location=location,
            results_wanted=max_results,
            hours_old=hours_old,
            country_indeed="France",  # fallback for Indeed
        )
    except Exception as exc:
        error_msg = f"Job search failed: {exc}"
        logger.error(error_msg, exc_info=True)
        return error_msg

    if jobs_df is None or jobs_df.empty:
        return (
            f"No PFE/internship offers found for **{keywords}** "
            f"in **{location}** (last {hours_old} hours). "
            "Try broadening the keywords or location."
        )

    # Build a clean Markdown report
    lines = [
        f"## 🎓 PFE / Internship Offers — {keywords}",
        f"**Location:** {location} · **Source:** {', '.join(site_list)} · "
        f"**Posted within:** {hours_old}h · **Results:** {len(jobs_df)}",
        "",
    ]

    for idx, row in jobs_df.iterrows():
        title = row.get("title", "N/A")
        company = row.get("company", "N/A")
        job_location = row.get("location", "N/A")
        date_posted = row.get("date_posted", "N/A")
        job_url = row.get("job_url", "")
        site = row.get("site", "")
        description = row.get("description", "")

        # Truncate description to first 200 chars for the summary
        short_desc = ""
        if description and str(description) != "nan":
            short_desc = str(description)[:200].strip()
            if len(str(description)) > 200:
                short_desc += "…"

        lines.append(f"### {idx + 1}. {title}")
        lines.append(f"**🏢 Company:** {company}")
        lines.append(f"**📍 Location:** {job_location}")
        lines.append(f"**📅 Posted:** {date_posted}")
        if site:
            lines.append(f"**🌐 Source:** {site}")
        if job_url and str(job_url) != "nan":
            lines.append(f"**🔗 Link:** [{title}]({job_url})")
        if short_desc:
            lines.append(f"\n> {short_desc}")
        lines.append("")

    lines.append(
        "---\n*Use `scrape_webpage` on any link above to get the full job description.*"
    )

    result = "\n".join(lines)
    logger.info("Returned %d job results for '%s'", len(jobs_df), keywords)
    return result
