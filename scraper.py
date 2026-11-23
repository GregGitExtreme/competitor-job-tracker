import json
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
jobs = []

def add_job(comp, jid, title, dept, loc, url):
    jobs.append({
        "competitor": comp,
        "jobId": str(jid).strip(),
        "title": str(title).strip(),
        "department": str(dept or "General").strip(),
        "location": str(loc or "Remote / Unspecified").strip(),
        "url": str(url).strip()
    })

# 1. Innovid (Greenhouse - check both innovid and innovidinc slugs)
for slug in ["innovid", "innovidinc"]:
    try:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=(5, 10))
        if r.status_code == 200:
            for j in r.json().get("jobs", []):
                dept = j["departments"][0]["name"] if j.get("departments") else ""
                add_job("Innovid", j["id"], j["title"], dept, j.get("location", {}).get("name", ""), j["absolute_url"])
    except Exception as e:
        print(f"Innovid ({slug}) error:", e)

# 2. Mediaocean (Check Greenhouse, Lever, and Ashby)
for platform, url in [
    ("gh", "https://boards-api.greenhouse.io/v1/boards/mediaocean/jobs"),
    ("lever", "https://api.lever.co/v0/postings/mediaocean?mode=json"),
    ("ashby", "https://api.ashbyhq.com/posting-api/job-board/mediaocean")
]:
    try:
        r = requests.get(url, timeout=(5, 10))
        if r.status_code == 200:
            data = r.json()
            if platform == "gh":
                for j in data.get("jobs", []):
                    dept = j["departments"][0]["name"] if j.get("departments") else ""
                    add_job("Mediaocean", j["id"], j["title"], dept, j.get("location", {}).get("name", ""), j["absolute_url"])
            elif platform == "lever":
                for j in data:
                    add_job("Mediaocean", j["id"], j["text"], j.get("categories", {}).get("team", ""), j.get("categories", {}).get("location", ""), j["hostedUrl"])
            elif platform == "ashby":
                for j in data.get("jobs", []):
                    add_job("Mediaocean", j["id"], j["title"], j.get("department", ""), j.get("location", ""), j.get("jobUrl", ""))
    except Exception as e:
        print(f"Mediaocean ({platform}) error:", e)

# 3. Wrapbook (Ashby)
try:
    r = requests.get("https://api.ashbyhq.com/posting-api/job-board/wrapbook", timeout=15).json()
    for j in r.get("jobs", []):
        add_job("Wrapbook", j["id"], j["title"], j.get("department", ""), j.get("location", ""), j.get("jobUrl", ""))
except Exception as e:
    print("Wrapbook error:", e)

# 4. Cape.io / Peach / IMD (Ashby)
try:
    r = requests.get("https://api.ashbyhq.com/posting-api/job-board/cape", timeout=15).json()
    for j in r.get("jobs", []):
        add_job("Cape.io", j["id"], j["title"], j.get("department", ""), j.get("location", ""), j.get("jobUrl", ""))
except Exception as e:
    print("Cape.io error:", e)

# 5. GreenSlate (JazzHR) - ignore empty jobId nav links
try:
    soup = BeautifulSoup(requests.get("https://gslate.applytojob.com/apply", headers=HEADERS, timeout=(5, 10)).text, "html.parser")
    for a in soup.select("a[href*='/apply/']"):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        parts = href.split("/apply/")
        jid = parts[1].split("/")[0] if len(parts) > 1 else ""
        if title and jid and title.lower() != "view all jobs":
            add_job("GreenSlate", jid, title, "", "", href if href.startswith("http") else f"https://gslate.applytojob.com{href}")
except Exception as e:
    print("GreenSlate error:", e)

# 6. Cast & Crew (Workday - requires Accept + User-Agent headers)
try:
    wd_url = "https://castandcrew.wd503.myworkdayjobs.com/wday/cxs/castandcrew/CastandCrew/jobs"
    wd_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    r = requests.post(wd_url, json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}, headers=wd_headers, timeout=(5, 10)).json()
    for j in r.get("jobPostings", []):
        path = j.get("externalPath", "")
        jid = path.split("_")[-1] if "_" in path else hashlib.md5(path.encode()).hexdigest()[:10]
        add_job("Cast & Crew", jid, j.get("title", ""), "", j.get("locationsText", ""), f"https://castandcrew.wd503.myworkdayjobs.com/en-US/CastandCrew{path}")
except Exception as e:
    print("Cast & Crew error:", e)

# 7. Entertainment Partners (Oracle Cloud HCM)
try:
    ep_url = "https://eoko.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=all&finder=findReqs;siteNumber=CX_1001,limit=50"
    r = requests.get(ep_url, timeout=15).json()
    for item in r.get("items", []):
        for j in item.get("requisitionList", []):
            jid = j.get("Id", "")
            add_job("Entertainment Partners", jid, j.get("Title", ""), "", j.get("PrimaryLocation", ""), f"https://eoko.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/{jid}")
except Exception as e:
    print("EP error:", e)

# 8. Comcast Technology Solutions (Filter specifically for CTS & FreeWheel roles)
try:
    for kw in ["Comcast Technology Solutions", "FreeWheel"]:
        cts_url = f"https://jobs.comcast.com/search-jobs/results?ActiveFacetID=0&CurrentPage=1&RecordsPerPage=50&Keywords={requests.utils.quote(kw)}"
        r = requests.get(cts_url, headers=HEADERS, timeout=(5, 10)).json()
        soup = BeautifulSoup(r.get("results", ""), "html.parser")
        for a in soup.select("a[data-job-id]"):
            jid = a.get("data-job-id")
            title = a.select_one("h2").get_text(strip=True) if a.select_one("h2") else a.get_text(strip=True)
            loc = a.select_one(".job-location").get_text(strip=True) if a.select_one(".job-location") else ""
            add_job("Comcast Tech Solutions", jid, title, kw, loc, f"https://jobs.comcast.com{a.get('href', '')}")
except Exception as e:
    print("CTS error:", e)

# 9 & 10. Yangaroo & Volacity (Static page link watchers)
for name, page_url in [("Yangaroo", "https://yangaroo.com/careers/"), ("Volacity", "https://volacity.com/careers")]:
    try:
        soup = BeautifulSoup(requests.get(page_url, headers=HEADERS, timeout=15).text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            txt = a.get_text(strip=True)
            if any(k in href for k in ["greenhouse", "lever", "ashby", "workable", "bamboohr", "apply", "job"]):
                jid = hashlib.md5(href.encode()).hexdigest()[:10]
                add_job(name, jid, txt or "Careers Link Update", "", "", a["href"])
    except Exception as e:
        print(f"{name} error:", e)

# Deduplicate by competitor + jobId
unique_jobs = list({f"{j['competitor']}_{j['jobId']}": j for j in jobs}.values())
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
print(f"Saved {len(unique_jobs)} total jobs.")
