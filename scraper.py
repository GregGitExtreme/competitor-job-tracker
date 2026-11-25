import json
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from collections import Counter
import requests
from bs4 import BeautifulSoup
import sys

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
jobs = []
errors = []

def add_job(comp, jid, title, dept, loc, url):
    jobs.append({
        "competitor": comp,
        "jobId": str(jid).strip(),
        "title": str(title).strip(),
        "department": str(dept or "General").strip(),
        "location": str(loc or "Remote / Unspecified").strip(),
        "url": str(url).strip()
    })

def log_error(msg):
    print(msg, flush=True)
    errors.append(msg)

# 1. Innovid (SAP SuccessFactors Recruiting POST endpoint under Mediaocean)
try:
    junk=1/0
    inn_url = "https://careers.mediaocean.com/services/recruiting/v1/jobs"
    inn_headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://careers.mediaocean.com/Innovid/search/?q=&locationsearch=&searchResultView=LIST",
        "X-Requested-With": "XMLHttpRequest"
    }
    inn_payload = {
        "locale": "en_US",
        "pageNumber": 0,
        "sortBy": "",
        "keywords": "",
        "location": "",
        "facetFilters": {},
        "brand": "Innovid",
        "skills": [],
        "categoryId": 0,
        "alertId": "",
        "rcmSiteLocale": "en_US"
    }
    r = requests.post(inn_url, json=inn_payload, headers=inn_headers, timeout=(5, 10))
    print(f"Innovid status: {r.status_code}", flush=True)
    if r.status_code == 200:
        data = r.json()
        results = data.get("jobSearchResult", [])
        for item in results:
            job = item.get("response", item)
            jid = job.get("id", "")
            title = job.get("unifiedStandardTitle") or job.get("title", "")
            loc = job.get("jobLocationShort") or (job.get("location", [""])[0] if isinstance(job.get("location"), list) else "")
            url_title = job.get("urlTitle", "job")
            job_url = f"https://careers.mediaocean.com/Innovid/job/{url_title}/{jid}-en_US/" if jid else "https://careers.mediaocean.com/Innovid/search/"
            if jid and title:
                add_job("Innovid", jid, title, job.get("department", ""), loc, job_url)
    else:
        log_error(f"Innovid HTTP {r.status_code}")
except Exception as e:
    log_error(f"Innovid error: {e}")

# 2. Mediaocean (SAP SuccessFactors Recruiting POST endpoint)
try:
    mo_url = "https://careers.mediaocean.com/services/recruiting/v1/jobs"
    mo_headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://careers.mediaocean.com/search/",
        "X-Requested-With": "XMLHttpRequest"
    }
    mo_payload = {
        "locale": "en_US",
        "pageNumber": 0,
        "sortBy": "",
        "keywords": "",
        "location": "",
        "facetFilters": {},
        "brand": "",
        "skills": [],
        "categoryId": 0,
        "alertId": "",
        "rcmSiteLocale": "en_US"
    }
    r = requests.post(mo_url, json=mo_payload, headers=mo_headers, timeout=(5, 10))
    print(f"Mediaocean status: {r.status_code}", flush=True)
    if r.status_code == 200:
        data = r.json()
        results = data.get("jobSearchResult", [])
        for item in results:
            job = item.get("response", item)
            jid = job.get("id", "")
            title = job.get("unifiedStandardTitle") or job.get("title", "")
            loc = job.get("jobLocationShort") or (job.get("location", [""])[0] if isinstance(job.get("location"), list) else "")
            url_title = job.get("urlTitle", "job")
            job_url = f"https://careers.mediaocean.com/job/{url_title}/{jid}-en_US/" if jid else "https://careers.mediaocean.com/search/"
            if jid and title:
                add_job("Mediaocean", jid, title, job.get("department", ""), loc, job_url)
    else:
        log_error(f"Mediaocean HTTP {r.status_code}")
except Exception as e:
    log_error(f"Mediaocean error: {e}")

# 3. Wrapbook (Ashby)
try:
    resp = requests.get("https://api.ashbyhq.com/posting-api/job-board/wrapbook", timeout=15)
    resp.raise_for_status()
    r = resp.json()
    for j in r.get("jobs", []):
        add_job("Wrapbook", j["id"], j["title"], j.get("department", ""), j.get("location", ""), j.get("jobUrl", ""))
except Exception as e:
    log_error(f"Wrapbook error: {e}")

# 4. Cape.io / Peach / IMD (Ashby)
try:
    resp = requests.get("https://api.ashbyhq.com/posting-api/job-board/cape", timeout=15)
    resp.raise_for_status()
    r = resp.json()
    for j in r.get("jobs", []):
        add_job("Cape.io", j["id"], j["title"], j.get("department", ""), j.get("location", ""), j.get("jobUrl", ""))
except Exception as e:
    log_error(f"Cape.io error: {e}")

# 5. GreenSlate (JazzHR) - ignore empty jobId nav links
try:
    resp = requests.get("https://gslate.applytojob.com/apply", headers=HEADERS, timeout=(5, 10))
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select("a[href*='/apply/']"):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        parts = href.split("/apply/")
        jid = parts[1].split("/")[0] if len(parts) > 1 else ""
        if title and jid and title.lower() != "view all jobs":
            add_job("GreenSlate", jid, title, "", "", href if href.startswith("http") else f"https://gslate.applytojob.com{href}")
except Exception as e:
    log_error(f"GreenSlate error: {e}")

# 6. Cast & Crew (Workday - requires Accept + User-Agent headers)
try:
    wd_url = "https://castandcrew.wd503.myworkdayjobs.com/wday/cxs/castandcrew/CastandCrew/jobs"
    wd_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    resp = requests.post(wd_url, json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}, headers=wd_headers, timeout=(5, 10))
    resp.raise_for_status()
    r = resp.json()
    for j in r.get("jobPostings", []):
        path = j.get("externalPath", "")
        jid = path.split("_")[-1] if "_" in path else hashlib.md5(path.encode()).hexdigest()[:10]
        add_job("Cast & Crew", jid, j.get("title", ""), "", j.get("locationsText", ""), f"https://castandcrew.wd503.myworkdayjobs.com/en-US/CastandCrew{path}")
except Exception as e:
    log_error(f"Cast & Crew error: {e}")

# 7. Entertainment Partners (Oracle Cloud HCM)
try:
    ep_url = "https://eoko.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=all&finder=findReqs;siteNumber=CX_1001,limit=50"
    resp = requests.get(ep_url, timeout=15)
    resp.raise_for_status()
    r = resp.json()
    for item in r.get("items", []):
        for j in item.get("requisitionList", []):
            jid = j.get("Id", "")
            add_job("Entertainment Partners", jid, j.get("Title", ""), "", j.get("PrimaryLocation", ""), f"https://eoko.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/{jid}")
except Exception as e:
    log_error(f"EP error: {e}")

# 8. Comcast Technology Solutions (Filter specifically for CTS & FreeWheel roles)
try:
    for kw in ["Comcast Technology Solutions", "FreeWheel"]:
        cts_url = f"https://jobs.comcast.com/search-jobs/results?ActiveFacetID=0&CurrentPage=1&RecordsPerPage=50&Keywords={requests.utils.quote(kw)}"
        resp = requests.get(cts_url, headers=HEADERS, timeout=(5, 10))
        resp.raise_for_status()
        r = resp.json()
        soup = BeautifulSoup(r.get("results", ""), "html.parser")
        for a in soup.select("a[data-job-id]"):
            jid = a.get("data-job-id")
            title = a.select_one("h2").get_text(strip=True) if a.select_one("h2") else a.get_text(strip=True)
            loc = a.select_one(".job-location").get_text(strip=True) if a.select_one(".job-location") else ""
            add_job("Comcast Tech Solutions", jid, title, kw, loc, f"https://jobs.comcast.com{a.get('href', '')}")
except Exception as e:
    log_error(f"CTS error: {e}")

# 9 & 10. Yangaroo & Volacity (Static page link watchers)
for name, page_url in [("Yangaroo", "https://yangaroo.com/careers/"), ("Volacity", "https://volacity.com/careers")]:
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            txt = a.get_text(strip=True)
            if any(k in href for k in ["greenhouse", "lever", "ashby", "workable", "bamboohr", "apply", "job"]):
                jid = hashlib.md5(href.encode()).hexdigest()[:10]
                add_job(name, jid, txt or "Careers Link Update", "", "", a["href"])
    except Exception as e:
        log_error(f"{name} error: {e}")

# Deduplicate by competitor + jobId
unique_jobs = list({f"{j['competitor']}_{j['jobId']}": j for j in jobs}.values())
print("Breakdown by competitor:", dict(Counter(j["competitor"] for j in unique_jobs)), flush=True)
payload_str = json.dumps(unique_jobs, ensure_ascii=False)

with open("latest_scrape.json", "w", encoding="utf-8") as f:
    f.write(payload_str)

# Generate RSS feed carrying the JSON payload for Power Automate's free RSS trigger
now_rfc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
today_id = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")

rss = ET.Element("rss", version="2.0")
channel = ET.SubElement(rss, "channel")
ET.SubElement(channel, "title").text = "Competitor Job Scrape Feed"
ET.SubElement(channel, "link").text = "https://github.com"
ET.SubElement(channel, "description").text = "Daily ATS scrape payload"

item = ET.SubElement(channel, "item")
ET.SubElement(item, "title").text = f"Job Scrape {today_id} ({len(unique_jobs)} active roles)"
ET.SubElement(item, "guid").text = today_id
ET.SubElement(item, "pubDate").text = now_rfc
ET.SubElement(item, "description").text = payload_str

ET.ElementTree(rss).write("feed.xml", encoding="utf-8", xml_declaration=True)
print(f"Saved {len(unique_jobs)} total jobs.", flush=True)

if errors:
    print("\n--- SCRAPER ERRORS DETECTED ---", flush=True)
    for err in errors:
        print(f"ERROR: {err}", flush=True)
    sys.exit(1)
